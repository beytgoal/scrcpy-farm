#!/usr/bin/env python3
"""
scrcpy-farm — Cross-Platform Android Device Farm Manager
Version: 3.0
License: MIT
"""

import setuptools

setuptools.setup(
    name="scrcpy-farm",
    version="3.0.0",
    description="Multi-Device Android Farm Manager — GUI for scrcpy",
    author="scrcpy-farm",
    url="https://github.com/beytgoal/scrcpy-farm",
    py_modules=["scrcpy_farm"],
    python_requires=">=3.8",
    install_requires=[],
    entry_points={
        "console_scripts": [
            "scrcpy-farm=scrcpy_farm:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
    ],
)
