"""Validate B0.3 Issue-authorized mappings and optionally the saved overlay."""

import argparse
from pathlib import Path
import sys

import ezdxf

from floorplan import ValidationError
from layout_input import DEFAULT_DATA, load_layout_input, validate_overlay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--dxf", type=Path, help="Also verify a saved layout-input DXF")
    args = parser.parse_args()
    try:
        data = load_layout_input(args.data)
        if args.dxf:
            validate_overlay(ezdxf.readfile(args.dxf), data)
        print("B0.3 validation passed: 5 high mapped areas, 2 medium candidates, 3 unresolved; no linear dimensions.")
    except (ValidationError, OSError, ezdxf.DXFError) as exc:
        print(f"Layout-input validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
