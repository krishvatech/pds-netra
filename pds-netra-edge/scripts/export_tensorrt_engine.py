#!/usr/bin/env python3
"""
Backward-compatible wrapper for the new export helper.

Use scripts/export_engine.py for the canonical command.
"""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    target = Path(__file__).resolve().with_name("export_engine.py")
    runpy.run_path(str(target), run_name="__main__")
