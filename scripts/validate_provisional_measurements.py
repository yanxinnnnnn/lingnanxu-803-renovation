"""Validate provisional references and optionally their separate DXF overlay."""

import argparse
from pathlib import Path
import sys

import ezdxf

from floorplan import ValidationError
from provisional_measurements import BASE_DXF, DEFAULT_DATA, DEFAULT_MANIFEST, load_measurements, validate_overlay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--base-dxf", type=Path, default=BASE_DXF)
    parser.add_argument("--dxf", type=Path, help="Also verify an existing provisional overlay")
    args = parser.parse_args()
    try:
        data = load_measurements(args.data, args.manifest)
        if args.dxf:
            validate_overlay(ezdxf.readfile(args.dxf), data, args.base_dxf, args.manifest)
        print(f"B0.2 validation passed: {len(data['areas'])} unresolved reference areas, "
              f"{len(data['linear_dimensions'])} linear dimensions; pending onsite verification.")
    except (ValidationError, OSError, ezdxf.DXFError) as exc:
        print(f"Provisional validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
