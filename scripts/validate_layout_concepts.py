"""Validate Issue #9 concepts, optionally including all saved DXF/PNG outputs."""

import argparse
from pathlib import Path
import sys

import ezdxf
from PIL import Image

from floorplan import ROOT, ValidationError, require
from generate_layout_concepts import build_overlay
from layout_concepts import DEFAULT_DATA, WARNING, load_concepts, output_paths, validate_overlay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--artifacts", action="store_true", help="Also check saved A/B/C DXFs and PNGs")
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        data = load_concepts(args.data)
        for concept in data["concepts"]:
            build_overlay(data, concept)
            if args.artifacts:
                dxf, png = output_paths(concept["id"], args.output_dir)
                validate_overlay(ezdxf.readfile(dxf), data, concept)
                with Image.open(png) as preview:
                    require(preview.size == (3360, 2240) and preview.info.get("Description") == WARNING, "PNG size/warning differs")
                    preview.verify()
        print("Layout A/B/C validated: B0 estimated, four bedrooms, three bathrooms, five cats; B1/L1 pending.")
    except (ValidationError, OSError, ezdxf.DXFError) as exc:
        print(f"Concept validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
