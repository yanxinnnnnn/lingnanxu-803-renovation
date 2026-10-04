"""Validate B0 data and generated DXF layers, warning, provenance and geometry."""

import argparse
from pathlib import Path
import sys

import ezdxf

from floorplan import (
    APP_ID, DEFAULT_DATA, LAYERS, WARNING, ValidationError,
    load_floorplan, require, transform,
)
from generate_b0_dxf import build_dxf


def validate_dxf(doc, data):
    require(not doc.audit().has_errors, "DXF audit failed")
    require(set(LAYERS) <= set(layer.dxf.name for layer in doc.layers), "Missing expected CAD layers")
    require(doc.units == ezdxf.units.MM, "DXF storage units must be mm")
    entities = list(doc.modelspace())
    warnings = [entity for entity in entities if entity.dxftype() == "TEXT"
                and entity.dxf.layer == "A-UNVERIFIED" and entity.dxf.text == WARNING]
    require(bool(warnings), "DXF is missing the visible B0 warning")
    by_id = {}
    for entity in entities:
        require(entity.has_xdata(APP_ID), "DXF entity is missing B0 provenance")
        tags = entity.get_xdata(APP_ID)
        values = [tag.value for tag in tags]
        require(len(values) == 4 and values[:2] == ["B0", "estimated"], "DXF entity provenance must be estimated B0")
        require(values[3] in {source["id"] for source in data["sources"]}, "DXF entity has unknown source")
        by_id.setdefault(values[2], []).append(entity)
    calibration = data["trace_coordinate_system"]
    for record, layer in [(data["perimeter"], "A-WALL-EXT")] + [(r, "A-WALL-INT") for r in data["rooms"]]:
        matches = [e for e in by_id.get(record["id"], []) if e.dxftype() == "LWPOLYLINE"]
        require(len(matches) == 1, f"DXF must contain one polygon for {record['id']}")
        entity = matches[0]
        expected = [transform(p, calibration) for p in record["polygon_px"]]
        if expected[-1] == expected[0]:
            expected = expected[:-1]
        require(entity.closed and entity.dxf.layer == layer, f"Incorrect polygon layer/closure for {record['id']}")
        # Exact numerical equality checks this serialization, not field accuracy.
        require(list(entity.get_points("xy")) == expected, f"DXF polygon differs from source: {record['id']}")
        if "display_name" in record:
            labels = [e for e in by_id.get(record["id"], []) if e.dxftype() == "TEXT" and e.dxf.layer == "A-ROOM"]
            require(len(labels) == 1 and labels[0].dxf.text == record["display_name"],
                    f"DXF Chinese display name differs from source: {record['id']}")
    for record in data["glazing"]:
        matches = [e for e in by_id.get(record["id"], []) if e.dxftype() == "LINE"]
        require(len(matches) == 1, f"DXF must contain one segment for {record['id']}")
        entity = matches[0]
        expected = [transform(p, calibration) for p in record["segment_px"]]
        actual = [tuple(entity.dxf.start)[:2], tuple(entity.dxf.end)[:2]]
        require(entity.dxf.layer == "A-GLAZ" and actual == expected, f"DXF segment differs from source: {record['id']}")
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--dxf", type=Path, help="Also check an existing DXF against the YAML")
    args = parser.parse_args()
    try:
        data = load_floorplan(args.data)
        validate_dxf(build_dxf(data), data)
        if args.dxf:
            validate_dxf(ezdxf.readfile(args.dxf), data)
        print(f"B0 validation passed: {len(data['rooms'])} estimated rooms; all required layers emitted.")
    except (ValidationError, OSError, ezdxf.DXFError) as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
