from setuptools import find_packages, setup

setup(
    name="shelly",
    version="0.1.0",
    description="Python library for discovering and controlling Shelly smart home devices",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "requests>=2.26.0",
        "zeroconf>=0.38.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
