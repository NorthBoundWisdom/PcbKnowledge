#!/usr/bin/env python3
"""Read-only v2 catalog CLI for the explicitly selected Git workspace."""
from pathlib import Path
import sys

SOURCE_ROOT=Path(__file__).resolve().parents[1]/'src'
sys.path.insert(0,str(SOURCE_ROOT))
from pcbknowledge.v2.cli import main

if __name__=='__main__':
    raise SystemExit(main())
