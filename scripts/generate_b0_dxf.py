"""Generate the B0 artifact from structured visual-trace data."""

import argparse
from pathlib import Path
import sys

import ezdxf
from ezdxf.enums import TextEntityAlignment

from floorplan import (
    APP_ID, DEFAULT_DATA, DEFAULT_DXF, LAYERS, WARNING,
    ValidationError, load_floorplan, tag_entity, transform, validate_data,
)


def build_dxf(data):
    validate_data(data)
    doc = ezdxf.new("R2010")
    # ezdxf discovers these default object classes via a set on first write.
    # Register them in a fixed order so Python's hash seed cannot reorder CLASSES.
    doc.classes.add_class("ACDBPLACEHOLDER")
    doc.classes.add_class("LAYOUT")
    doc.units = ezdxf.units.MM  # Storage units only: the underlying trace remains estimated.
    doc.appids.new(APP_ID)
    for name, color in LAYERS.items():
        doc.layers.new(name, dxfattribs={"color": color})
    msp = doc.modelspace()
    calibration = data["trace_coordinate_system"]

    def polygon(record, layer):
        points = [transform(p, calibration) for p in record["polygon_px"]]
        # The issue includes a repeated perimeter endpoint; DXF's closed flag supplies it.
        if points[-1] == points[0]:
            points = points[:-1]
        entity = msp.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
        tag_entity(entity, record["id"], record["source"])
        return points

    perimeter_points = polygon(data["perimeter"], "A-WALL-EXT")
    for room in data["rooms"]:
        points = polygon(room, "A-WALL-INT")
        # Bounding-box centres avoid adding a new geometric interpretation of the trace.
        centre = ((min(x for x, _ in points) + max(x for x, _ in points)) / 2,
                  (min(y for _, y in points) + max(y for _, y in points)) / 2)
        label = msp.add_text(room["display_name"], dxfattribs={"layer": "A-ROOM", "height": 170})
        label.set_placement(centre, align=TextEntityAlignment.MIDDLE_CENTER)
        tag_entity(label, room["id"], room["source"])
    for glazing in data["glazing"]:
        start, end = [transform(p, calibration) for p in glazing["segment_px"]]
        entity = msp.add_line(start, end, dxfattribs={"layer": "A-GLAZ"})
        tag_entity(entity, glazing["id"], glazing["source"])

    left = min(x for x, _ in perimeter_points)
    top = max(y for _, y in perimeter_points)
    notes = [
        (WARNING, "A-UNVERIFIED", 400),
        ("LN803 / B0 v" + data["metadata"]["version"] + " / " + data["metadata"]["artifact_date"], "A-NOTE", 220),
        ("Visual trace only; CAD mm are estimated. B1 verified dimensions will supersede B0.", "A-NOTE", 220),
        ("Room outlines are schematic boundaries; no wall thickness or structural claims.", "A-NOTE", 220),
    ]
    for index, (text, layer, height) in enumerate(notes):
        entity = msp.add_text(text, dxfattribs={"layer": layer, "height": height})
        entity.set_placement((left, top + 2200 - index * 500))
        tag_entity(entity, f"note_{index}", data["sources"][0]["id"])
    return doc


def generate(data_path=DEFAULT_DATA, output_path=DEFAULT_DXF):
    # ezdxf's fixed-metadata mode removes volatile timestamps, GUIDs and writer metadata.
    previous = ezdxf.options.write_fixed_meta_data_for_testing
    try:
        ezdxf.options.write_fixed_meta_data_for_testing = True
        doc = build_dxf(load_floorplan(data_path))
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Explicit LF makes the committed text artifact portable between OSes.
        with output_path.open("w", encoding="utf-8", newline="\n") as stream:
            doc.write(stream)
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = previous
    return output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_DXF)
    args = parser.parse_args()
    try:
        print(f"Generated {generate(args.data, args.output)} ({WARNING})")
    except (ValidationError, OSError) as exc:
        print(f"Generation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
