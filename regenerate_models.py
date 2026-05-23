"""Regenerate the ``GEN1_MODELS`` / ``GEN2_PLUS_MODELS`` dicts in shelly/models.py.

The upstream source of truth for ``{model_id: human_name}`` is the
``aioshelly`` library maintained by the Home Assistant team:

    https://raw.githubusercontent.com/home-assistant-libs/aioshelly/main/aioshelly/const.py

That file defines ``MODEL_* = "<code>"`` constants plus a ``DEVICES`` dict of
``ShellyDevice(model=..., name=..., gen=GEN{1,2,3,4}, ...)`` entries.  This
script downloads the file, parses it with ``ast`` (no execution), and prints
ready-to-paste Python literals grouped by generation:

  * Gen 1 → ``GEN1_MODELS``
  * Gen 2/3/4 → ``GEN2_PLUS_MODELS``

Usage::

    python regenerate_models.py            # print both dicts to stdout
    python regenerate_models.py --diff     # also show which codes the
                                           # current models.py is missing

The script has no third-party dependencies — it only needs urllib + ast from
the standard library.
"""

from __future__ import annotations

import argparse
import ast
import sys
import urllib.request
from collections import defaultdict

AIOSHELLY_CONST_URL = (
    "https://raw.githubusercontent.com/home-assistant-libs/aioshelly/main/"
    "aioshelly/const.py"
)

GEN_NAMES = {1: "GEN1_MODELS", 2: "GEN2_PLUS_MODELS", 3: "GEN2_PLUS_MODELS",
             4: "GEN2_PLUS_MODELS"}


def fetch_const() -> str:
    with urllib.request.urlopen(AIOSHELLY_CONST_URL, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse_models(source: str) -> dict[int, dict[str, str]]:
    """Return ``{gen: {model_code: human_name}}`` extracted from ``source``."""
    tree = ast.parse(source)

    # Pass 1 — collect MODEL_* = "<code>" string constants and GEN{N} = <int>.
    str_consts: dict[str, str] = {}
    int_consts: dict[str, int] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = node.value
        if isinstance(value, ast.Constant):
            if isinstance(value.value, str):
                str_consts[target.id] = value.value
            elif isinstance(value.value, int) and not isinstance(value.value, bool):
                int_consts[target.id] = value.value

    # Pass 2 — find the DEVICES = {...} dict and extract entries.
    devices_node: ast.Dict | None = None
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "DEVICES"
                and isinstance(node.value, ast.Dict)):
            devices_node = node.value
            break
    if devices_node is None:
        raise RuntimeError("Could not find DEVICES dict in aioshelly const.py")

    by_gen: dict[int, dict[str, str]] = defaultdict(dict)
    for value in devices_node.values:
        if not isinstance(value, ast.Call):
            continue
        kwargs: dict[str, ast.expr] = {kw.arg: kw.value for kw in value.keywords
                                       if kw.arg is not None}
        model_expr = kwargs.get("model")
        name_expr = kwargs.get("name")
        gen_expr = kwargs.get("gen")
        if model_expr is None or name_expr is None or gen_expr is None:
            continue

        # Resolve model code (almost always a MODEL_* constant reference).
        if isinstance(model_expr, ast.Name):
            model = str_consts.get(model_expr.id)
        elif isinstance(model_expr, ast.Constant) and isinstance(model_expr.value, str):
            model = model_expr.value
        else:
            model = None
        if not model:
            continue
        model = model.strip()  # upstream has one entry with a leading space

        # Resolve human-readable name (string literal).
        if isinstance(name_expr, ast.Constant) and isinstance(name_expr.value, str):
            name = name_expr.value
        else:
            continue

        # Resolve generation (GEN1/GEN2/GEN3/GEN4 reference).
        if isinstance(gen_expr, ast.Name):
            gen = int_consts.get(gen_expr.id)
        elif isinstance(gen_expr, ast.Constant) and isinstance(gen_expr.value, int):
            gen = gen_expr.value
        else:
            gen = None
        if gen is None:
            continue

        by_gen[gen][model] = name

    return dict(by_gen)


def emit_dict(name: str, mapping: dict[str, str]) -> str:
    lines = [f"{name} = {{"]
    for code in sorted(mapping):
        human = mapping[code].replace('"', '\\"')
        lines.append(f'    "{code}": "{human}",')
    lines.append("}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--diff", action="store_true",
                        help="show codes missing from shelly/models.py")
    args = parser.parse_args()

    source = fetch_const()
    by_gen = parse_models(source)

    gen1 = by_gen.get(1, {})
    gen2_plus: dict[str, str] = {}
    for gen in (2, 3, 4):
        gen2_plus.update(by_gen.get(gen, {}))

    print(f"# Auto-generated from {AIOSHELLY_CONST_URL}")
    print(f"# Gen1 entries: {len(gen1)}")
    print(f"# Gen2+ entries: {len(gen2_plus)} "
          f"(Gen2={len(by_gen.get(2, {}))}, "
          f"Gen3={len(by_gen.get(3, {}))}, "
          f"Gen4={len(by_gen.get(4, {}))})")
    print()
    print(emit_dict("GEN1_MODELS", gen1))
    print()
    print(emit_dict("GEN2_PLUS_MODELS", gen2_plus))

    if args.diff:
        try:
            from shelly.models import GEN1_MODELS as current_gen1
        except Exception as exc:
            print(f"\n# Could not import current GEN1_MODELS: {exc}",
                  file=sys.stderr)
            return 0
        upstream_codes = set(gen1)
        current_codes = set(current_gen1)
        missing = sorted(upstream_codes - current_codes)
        extra = sorted(current_codes - upstream_codes)
        print(f"\n# Diff vs. shelly/models.py:GEN1_MODELS", file=sys.stderr)
        print(f"# Missing locally ({len(missing)}): {missing}", file=sys.stderr)
        print(f"# Local-only ({len(extra)}): {extra}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
