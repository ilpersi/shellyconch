"""
publish.py — orchestrate a release of shellyconch to PyPI.

Steps performed (each gated by a confirmation prompt by default):

    1.  Preflight — verify ``git``, ``build``, and ``twine`` are available.
    2.  Verify the working tree has no uncommitted changes to tracked files.
    3.  Bump ``__version__`` in ``shelly/__init__.py`` (skipped when already
        at the target).
    4.  Remove old build artefacts (``dist/``, ``build/``, ``*.egg-info/``).
    5.  Build sdist + wheel via ``py -m build``.
    6.  Validate the artefacts with ``twine check``.
    7.  Optional — upload to TestPyPI and verify install in a clean venv.
    8.  Commit the version bump and create an annotated tag ``vX.Y.Z``.
    9.  Push the commit and tag to ``origin``.
    10. Upload to real PyPI.
    11. Wait for PyPI's CDN to publish the new version, then verify it
        installs cleanly into a fresh venv and imports at the right version.

Dependencies
------------
* Python standard library only — no ``pip install``-able runtime deps.
* External tools: ``git``, ``build`` (``py -m build``), ``twine``
  (``py -m twine``).  ``build`` and ``twine`` can be installed with:
  ``py -m pip install --upgrade build twine``.

Credentials
-----------
PyPI / TestPyPI tokens are read by ``twine`` from ``~/.pypirc`` automatically;
this script does not handle credentials.

Usage
-----
    py publish.py 1.0.1                          # interactive full flow
    py publish.py 1.0.1 --skip-testpypi          # skip the TestPyPI dry-run
    py publish.py 1.0.1 --skip-push              # commit + tag locally, don't push
    py publish.py 1.0.1 -y                       # assume "yes" for every prompt
    py publish.py 1.0.1 --dry-run                # print actions but execute nothing

    # Run only the post-upload install verification — useful when the
    # automatic verify at the end of a previous run lost the race against
    # PyPI's CDN, or to spot-check an old release at any time.  Polls the
    # PyPI JSON API until the version is resolvable, then installs into a
    # temp venv and confirms the imported __version__ matches.
    py publish.py 1.0.1 --verify-only            # verify against real PyPI
    py publish.py 1.0.1 --verify-only --testpypi # verify against TestPyPI
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import venv
from pathlib import Path


# --- project-specific constants ---------------------------------------------

ROOT = Path(__file__).parent.resolve()
INIT_PY = ROOT / "shelly" / "__init__.py"
DIST = ROOT / "dist"
PKG_NAME = "shellyconch"   # distribution name on PyPI
IMPORT_NAME = "shelly"     # importable package name


# --- exceptions -------------------------------------------------------------

class Aborted(SystemExit):
    """Raised when a precondition or user input forces the script to stop."""


# --- I/O helpers ------------------------------------------------------------

def step(msg: str) -> None:
    print(f"\n=== {msg} ===")


def confirm(prompt: str, *, default_yes: bool = False, assume_yes: bool = False) -> bool:
    if assume_yes:
        return True
    suffix = " [Y/n] " if default_yes else " [y/N] "
    ans = input(prompt + suffix).strip().lower()
    if not ans:
        return default_yes
    return ans in ("y", "yes")


def run(cmd: list[str], *, dry_run: bool = False) -> None:
    """Run a command, echoing it first.  Raises CalledProcessError on failure."""
    printable = " ".join(c if " " not in c else f'"{c}"' for c in cmd)
    print(f"$ {printable}")
    if not dry_run:
        subprocess.run(cmd, check=True)


def capture(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


# --- version management ------------------------------------------------------

_VERSION_RE = re.compile(r'^(__version__\s*=\s*)["\']([^"\']+)["\']\s*$', re.M)


def current_version() -> str:
    m = _VERSION_RE.search(INIT_PY.read_text(encoding="utf-8"))
    if not m:
        raise Aborted(f"Could not find __version__ in {INIT_PY}")
    return m.group(2)


def bump_version(new: str, *, dry_run: bool = False) -> None:
    text = INIT_PY.read_text(encoding="utf-8")
    new_text, n = _VERSION_RE.subn(rf'\1"{new}"', text)
    if n != 1:
        raise Aborted("Failed to bump version — pattern matched zero or multiple times.")
    if dry_run:
        print(f"(dry-run) would bump {INIT_PY.name} __version__ -> {new}")
        return
    INIT_PY.write_text(new_text, encoding="utf-8")
    print(f"Bumped {INIT_PY.name} __version__ -> {new}")


# --- preflight ---------------------------------------------------------------

def check_tools() -> None:
    checks = {
        "git":   ["git", "--version"],
        "build": [sys.executable, "-m", "build", "--version"],
        "twine": [sys.executable, "-m", "twine", "--version"],
    }
    missing: list[str] = []
    for name, cmd in checks.items():
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            missing.append(name)
    if missing:
        raise Aborted(
            f"Missing required tool(s): {', '.join(missing)}.\n"
            "Install Python tools with:\n"
            "    py -m pip install --upgrade build twine\n"
            "and ensure `git` is on PATH."
        )


def working_tree_clean() -> bool:
    return capture(["git", "status", "--porcelain", "--untracked-files=no"]).strip() == ""


def current_branch() -> str:
    return capture(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()


def tag_exists(tag: str) -> bool:
    r = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"],
        capture_output=True,
    )
    return r.returncode == 0


# --- build pipeline ----------------------------------------------------------

def clean(*, dry_run: bool = False) -> None:
    targets = [DIST, ROOT / "build", ROOT / f"{PKG_NAME}.egg-info"]
    for d in targets:
        if d.exists():
            print(f"removing {d.relative_to(ROOT)}")
            if not dry_run:
                shutil.rmtree(d, ignore_errors=True)


def build(*, dry_run: bool = False) -> None:
    run([sys.executable, "-m", "build"], dry_run=dry_run)


def twine_check(*, dry_run: bool = False) -> None:
    artefacts = sorted(str(p) for p in DIST.glob("*"))
    if not artefacts and not dry_run:
        raise Aborted("dist/ is empty — nothing to check.")
    run([sys.executable, "-m", "twine", "check", *artefacts], dry_run=dry_run)


def twine_upload(*, testpypi: bool = False, dry_run: bool = False) -> None:
    artefacts = sorted(str(p) for p in DIST.glob("*"))
    if not artefacts and not dry_run:
        raise Aborted("dist/ is empty — nothing to upload.")
    cmd = [sys.executable, "-m", "twine", "upload"]
    if testpypi:
        cmd += ["--repository", "testpypi"]
    cmd += artefacts
    run(cmd, dry_run=dry_run)


# --- git operations ----------------------------------------------------------

def git_commit_version(version: str, *, dry_run: bool = False) -> None:
    run(["git", "add", str(INIT_PY.relative_to(ROOT))], dry_run=dry_run)
    run(["git", "commit", "-m", f"Bump version to {version}"], dry_run=dry_run)


def git_tag(version: str, *, dry_run: bool = False) -> None:
    tag = f"v{version}"
    if tag_exists(tag):
        print(f"tag {tag} already exists; skipping")
        return
    run(["git", "tag", "-a", tag, "-m", tag], dry_run=dry_run)


def git_push(version: str, *, dry_run: bool = False) -> None:
    branch = current_branch() if not dry_run else "<current-branch>"
    run(["git", "push", "origin", branch], dry_run=dry_run)
    run(["git", "push", "origin", f"v{version}"], dry_run=dry_run)


# --- install verification ----------------------------------------------------

def _json_api_has_version(host: str, version: str) -> tuple[bool, str]:
    """Check PyPI's JSON API.  Returns (ready, short status for diagnostics)."""
    url = f"https://{host}/pypi/{PKG_NAME}/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        if version in data.get("releases", {}):
            return True, "ok"
        return False, "version not in releases"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        return False, type(exc).__name__


def _simple_index_has_version(host: str, version: str) -> tuple[bool, str]:
    """Check PyPI's Simple index (PEP 691 JSON form) — the one pip actually uses."""
    url = f"https://{host}/simple/{PKG_NAME}/"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.pypi.simple.v1+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        # PEP 700 adds a top-level `versions` list; prefer it when present.
        versions = data.get("versions")
        if versions is not None:
            if version in versions:
                return True, "ok"
            return False, "version not in versions"
        # Fallback: scan filenames (sdist: pkg-version.tar.gz; wheel: pkg-version-…whl).
        prefixes = (f"{PKG_NAME}-{version}.", f"{PKG_NAME}-{version}-")
        for f in data.get("files", []):
            filename = f.get("filename", "")
            if filename.startswith(prefixes):
                return True, "ok"
        return False, "version not in files"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        return False, type(exc).__name__


def wait_for_pypi_release(
    version: str,
    *,
    testpypi: bool = False,
    timeout: float = 300.0,
    interval: float = 5.0,
) -> None:
    """
    Poll PyPI until ``version`` is visible on both the JSON API and the
    Simple index.

    ``twine upload`` returns as soon as the upload succeeds, but PyPI's CDN
    needs a few seconds (occasionally minutes) before the new version is
    resolvable to ``pip install``.  The JSON API (``/pypi/{pkg}/json``) and
    the Simple index (``/simple/{pkg}/``) are served by independent Fastly
    caches and can be out of sync — ``pip`` reads the Simple index, so we
    wait for both endpoints to agree before declaring readiness.
    """
    host = "test.pypi.org" if testpypi else "pypi.org"
    deadline = time.monotonic() + timeout
    print(f"waiting for {PKG_NAME}=={version} to appear on {host}", end="", flush=True)
    last_status: str = "no response yet"
    while time.monotonic() < deadline:
        json_ok, json_status = _json_api_has_version(host, version)
        simple_ok, simple_status = _simple_index_has_version(host, version)
        if json_ok and simple_ok:
            print(" — ready")
            return
        last_status = f"json={json_status}, simple={simple_status}"
        print(".", end="", flush=True)
        time.sleep(interval)
    print()
    raise Aborted(
        f"timed out after {timeout:.0f}s waiting for {PKG_NAME}=={version} "
        f"to appear on {host} (last check: {last_status})"
    )


def verify_install(version: str, *, testpypi: bool = False, dry_run: bool = False) -> None:
    if dry_run:
        src = "TestPyPI" if testpypi else "PyPI"
        print(f"(dry-run) would create a temp venv and install {PKG_NAME}=={version} from {src}")
        return

    # Wait for CDN propagation before pip-installing.
    wait_for_pypi_release(version, testpypi=testpypi)

    with tempfile.TemporaryDirectory(prefix=f"{PKG_NAME}-verify-") as td:
        venv_dir = Path(td) / "v"
        print(f"creating venv at {venv_dir}")
        venv.create(venv_dir, with_pip=True)
        bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
        py = bin_dir / ("python.exe" if sys.platform == "win32" else "python")

        if testpypi:
            install_cmd = [
                str(py), "-m", "pip", "install",
                "--index-url", "https://test.pypi.org/simple/",
                "--extra-index-url", "https://pypi.org/simple/",
                f"{PKG_NAME}=={version}",
            ]
        else:
            install_cmd = [str(py), "-m", "pip", "install", "--upgrade",
                           f"{PKG_NAME}=={version}"]
        run(install_cmd)

        got = capture([str(py), "-c",
                       f"import {IMPORT_NAME}; print({IMPORT_NAME}.__version__)"]).strip()
        if got != version:
            raise Aborted(f"version mismatch: expected {version!r}, got {got!r}")
        print(f"OK — installed and imported {PKG_NAME} {got}")


# --- main --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Release helper for shellyconch.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("version", help="target version, e.g. 1.0.1")
    parser.add_argument("--skip-testpypi", action="store_true",
                        help="skip the optional TestPyPI dry-run")
    parser.add_argument("--skip-verify", action="store_true",
                        help="skip the post-upload install verification")
    parser.add_argument("--skip-push", action="store_true",
                        help="commit + tag locally but do not push to origin")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="assume 'yes' for every confirmation prompt")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="print actions without executing them")
    parser.add_argument("--verify-only", action="store_true",
                        help="skip everything and just verify install of the "
                             "given version from PyPI (use --testpypi for TestPyPI)")
    parser.add_argument("--testpypi", action="store_true",
                        help="with --verify-only, target TestPyPI instead of PyPI")
    args = parser.parse_args(argv)

    version = args.version
    dry = args.dry_run

    if args.verify_only:
        step(f"Verify-only: installing {PKG_NAME}=={version} from "
             f"{'TestPyPI' if args.testpypi else 'PyPI'}")
        verify_install(version, testpypi=args.testpypi, dry_run=dry)
        print("\nVerification complete.")
        return 0

    step("Preflight: checking required tools")
    check_tools()

    cur = current_version()
    print(f"Current __version__: {cur}")
    print(f"Target  __version__: {version}")

    if not working_tree_clean():
        raise Aborted(
            "Working tree has uncommitted changes to tracked files.\n"
            "Commit or stash them before releasing."
        )

    if cur != version:
        step(f"Bumping version: {cur} -> {version}")
        bump_version(version, dry_run=dry)
    else:
        print("(version already at target; skipping bump)")

    step("Cleaning previous artefacts")
    clean(dry_run=dry)

    step("Building sdist + wheel")
    build(dry_run=dry)

    step("Validating with twine check")
    twine_check(dry_run=dry)

    if not args.skip_testpypi:
        if confirm("Upload to TestPyPI as a dry run?", default_yes=True, assume_yes=args.yes):
            step("Uploading to TestPyPI")
            twine_upload(testpypi=True, dry_run=dry)
            if not args.skip_verify:
                step("Verifying TestPyPI install in a clean venv")
                verify_install(version, testpypi=True, dry_run=dry)

    if cur != version:
        step("Committing the version bump")
        if confirm(f"Commit & tag v{version}?", default_yes=True, assume_yes=args.yes):
            git_commit_version(version, dry_run=dry)
            git_tag(version, dry_run=dry)
    else:
        step(f"Tagging v{version} (no version bump to commit)")
        if not tag_exists(f"v{version}"):
            if confirm(f"Create tag v{version} at HEAD?", default_yes=True, assume_yes=args.yes):
                git_tag(version, dry_run=dry)

    if not args.skip_push:
        if confirm("Push commit + tag to origin?", default_yes=True, assume_yes=args.yes):
            git_push(version, dry_run=dry)

    step("Uploading to real PyPI")
    print("This is irreversible — PyPI does not allow re-uploading the same version.")
    if confirm("Continue with the upload?", default_yes=False, assume_yes=args.yes):
        twine_upload(testpypi=False, dry_run=dry)

        if not args.skip_verify:
            step("Verifying PyPI install in a clean venv")
            verify_install(version, testpypi=False, dry_run=dry)

    print("\nAll done.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Aborted as exc:
        print(f"\nABORTED: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except subprocess.CalledProcessError as exc:
        print(f"\nCommand failed (exit {exc.returncode}): {' '.join(exc.cmd)}",
              file=sys.stderr)
        sys.exit(exc.returncode)
