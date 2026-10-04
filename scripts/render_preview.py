"""Render a portable PNG review preview directly from the generated B0 DXF."""

import argparse
from pathlib import Path
import sys

import ezdxf
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Polygon

from floorplan import APP_ID, DEFAULT_DATA, DEFAULT_DXF, DEFAULT_PREVIEW, WARNING, ValidationError, load_floorplan
from validate_floorplan import validate_dxf


def render(data_path=DEFAULT_DATA, dxf_path=DEFAULT_DXF, output_path=DEFAULT_PREVIEW):
    data = load_floorplan(data_path)
    doc = validate_dxf(ezdxf.readfile(dxf_path), data)
    figure = Figure(figsize=(14, 10), dpi=140, facecolor="#f5f7fa")
    FigureCanvasAgg(figure)
    axes = figure.add_axes((0.04, 0.05, 0.92, 0.77))
    axes.set_facecolor("#f5f7fa")
    axes.set_aspect("equal")
    all_points = []
    for entity in doc.modelspace():
        layer = entity.dxf.layer
        if entity.dxftype() == "LWPOLYLINE":
            points = list(entity.get_points("xy"))
            all_points.extend(points)
            is_perimeter = layer == "A-WALL-EXT"
            axes.add_patch(Polygon(
                points, closed=True, fill=not is_perimeter,
                facecolor="#dde6ee", edgecolor="#172b40" if is_perimeter else "#8194a6",
                linewidth=2.0 if is_perimeter else 1.0, zorder=3 if is_perimeter else 1,
                alpha=1.0 if is_perimeter else 0.6,
            ))
        elif entity.dxftype() == "LINE" and layer == "A-GLAZ":
            start, end = entity.dxf.start, entity.dxf.end
            axes.plot([start.x, end.x], [start.y, end.y], color="#008baf", linewidth=3, zorder=4)
        elif entity.dxftype() == "TEXT" and layer == "A-ROOM":
            # IDs give portable labels without requiring an OS-specific Chinese font.
            # The actual Chinese display names are retained in YAML and DXF TEXT.
            room_id = entity.get_xdata(APP_ID)[2].value
            position = entity.dxf.align_point
            axes.text(position.x, position.y, room_id.replace("_", "\n"),
                      fontsize=8, color="#21364b", ha="center", va="center", zorder=5,
                      fontfamily="DejaVu Sans", linespacing=1.1)
    left = min(x for x, _ in all_points)
    right = max(x for x, _ in all_points)
    bottom = min(y for _, y in all_points)
    top = max(y for _, y in all_points)
    axes.set_xlim(left - 500, right + 500)
    axes.set_ylim(bottom - 500, top + 500)
    axes.axis("off")
    figure.text(0.5, 0.95, WARNING, ha="center", color="#b42318", fontsize=18, weight="bold", fontfamily="DejaVu Sans")
    figure.text(0.5, 0.913, "LN803 | B0 v" + data["metadata"]["version"] + " | " + data["metadata"]["artifact_date"],
                ha="center", color="#21364b", fontsize=12, fontfamily="DejaVu Sans")
    figure.text(0.5, 0.880, "Visual trace in estimated CAD mm. B1 verified dimensions will supersede B0.",
                ha="center", color="#465c70", fontsize=10, fontfamily="DejaVu Sans")
    figure.text(0.5, 0.852, "Dark: simplified perimeter   /   Grey: schematic room boundaries   /   Cyan: estimated glazing",
                ha="center", color="#465c70", fontsize=10, fontfamily="DejaVu Sans")
    figure.text(0.5, 0.024, "Issue #1 trace preserved, including overlaps and gaps. No wall thickness or structural interpretation.",
                ha="center", color="#465c70", fontsize=9, fontfamily="DejaVu Sans")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, format="png", dpi=140, metadata={"Software": "LN803 B0 preview", "Description": WARNING})
    return output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--dxf", type=Path, default=DEFAULT_DXF)
    parser.add_argument("--output", type=Path, default=DEFAULT_PREVIEW)
    args = parser.parse_args()
    try:
        print(f"Rendered {render(args.data, args.dxf, args.output)}")
    except (ValidationError, OSError, ezdxf.DXFError) as exc:
        print(f"Preview failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
