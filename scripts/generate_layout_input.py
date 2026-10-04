"""Generate separate B0.3 planning DXF/PNG with semantic area annotations only."""

import argparse
from pathlib import Path
import sys

import ezdxf
from ezdxf.enums import TextEntityAlignment
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Polygon

from floorplan import APP_ID as B0_APP_ID, WARNING as B0_WARNING, ValidationError, require
from layout_input import (
    APP_ID, BASE_DXF, DEFAULT_DATA, DEFAULT_DXF, DEFAULT_MANIFEST, DEFAULT_PREVIEW, LAYER,
    PRESERVED_FILES, ROOT, WARNING, annotations, layout_tags, load_layout_input,
    validate_layout_data, validate_overlay,
)

COLORS = {"mapped:high": "#087f5b", "candidate:medium": "#b76b00", "unresolved:low": "#7b239b", "note": "#465c70"}


def build_overlay(data):
    validate_layout_data(data)
    doc = ezdxf.readfile(BASE_DXF)
    doc.layers.new(LAYER, dxfattribs={"color": 3})
    doc.appids.new(APP_ID)
    for spec in annotations(data):
        entity = doc.modelspace().add_text(spec["text"], dxfattribs={
            "layer": LAYER, "height": 160 if spec["role"] == "plan" else 220, "color": spec["color"],
        })
        entity.set_placement(spec["position"], align=TextEntityAlignment.MIDDLE_CENTER
                             if spec["role"] == "plan" else TextEntityAlignment.LEFT)
        entity.set_xdata(APP_ID, layout_tags(spec))
    return validate_overlay(doc, data)


def render_overlay(data, dxf_path, preview_path):
    doc = validate_overlay(ezdxf.readfile(dxf_path), data)
    figure = Figure(figsize=(22, 12), dpi=140, facecolor="#f5f7fa")
    FigureCanvasAgg(figure)
    axes = figure.add_axes((0.02, 0.075, 0.605, 0.76))
    axes.set_aspect("equal")
    axes.axis("off")
    points = []
    panel_rows = []
    for entity in doc.modelspace():
        layer = entity.dxf.layer
        if entity.dxftype() == "LWPOLYLINE":
            polygon = list(entity.get_points("xy"))
            points.extend(polygon)
            outer = layer == "A-WALL-EXT"
            axes.add_patch(Polygon(polygon, closed=True, fill=not outer, facecolor="#dde6ee",
                                   edgecolor="#172b40" if outer else "#8194a6",
                                   linewidth=2 if outer else 1, alpha=1 if outer else 0.6,
                                   zorder=3 if outer else 1))
        elif entity.dxftype() == "LINE" and layer == "A-GLAZ":
            start, end = entity.dxf.start, entity.dxf.end
            axes.plot([start.x, end.x], [start.y, end.y], color="#008baf", linewidth=3, zorder=4)
        elif entity.dxftype() == "TEXT" and layer == "A-ROOM":
            room_id = entity.get_xdata(B0_APP_ID)[2].value
            point = entity.dxf.align_point
            axes.text(point.x, point.y, room_id.replace("_", "\n"), fontsize=8, ha="center", va="center",
                      color="#21364b", fontfamily="DejaVu Sans", zorder=5)
        elif entity.dxftype() == "TEXT" and layer == LAYER:
            tags = entity.get_xdata(APP_ID)
            category, role = tags[6].value, tags[7].value
            if role == "panel":
                panel_rows.append((entity.dxf.text, category))
            else:
                point = entity.dxf.align_point
                axes.text(point.x, point.y, entity.dxf.text, fontsize=8.5, ha="center", va="center",
                          weight="bold", color=COLORS[category], fontfamily="DejaVu Sans", zorder=6,
                          bbox={"facecolor": "white", "edgecolor": COLORS[category], "alpha": 0.95, "pad": 3})
    axes.set_xlim(min(x for x, _ in points) - 550, max(x for x, _ in points) + 550)
    axes.set_ylim(min(y for _, y in points) - 700, max(y for _, y in points) + 1000)
    figure.text(0.5, 0.955, panel_rows[0][0], ha="center", fontsize=16, weight="bold",
                color="#a12317", fontfamily="DejaVu Sans")
    figure.text(0.5, 0.915, B0_WARNING, ha="center", fontsize=13, color="#a12317", fontfamily="DejaVu Sans")
    figure.text(0.5, 0.88, "Green: high semantic mapping  |  Amber: medium candidate  |  Purple: unresolved source area",
                ha="center", fontsize=12, color="#465c70", fontfamily="DejaVu Sans")
    panel = figure.add_axes((0.65, 0.055, 0.33, 0.785))
    panel.set_facecolor("#eef2f6")
    panel.set_xticks([])
    panel.set_yticks([])
    for spine in panel.spines.values():
        spine.set_edgecolor("#c1cdd9")
    spacing = min(0.038, 0.89 / max(1, len(panel_rows) - 2))
    for index, (text, category) in enumerate(panel_rows[1:]):
        panel.text(0.035, 0.96 - index * spacing, text, transform=panel.transAxes, va="top",
                   fontsize=10, color=COLORS[category], weight="bold" if text.isupper() else "normal",
                   fontfamily="DejaVu Sans")
    figure.text(0.32, 0.045, "B0 geometry stays estimated. Areas are source reports, not verified room envelopes.",
                ha="center", fontsize=10, color="#465c70", fontfamily="DejaVu Sans")
    preview_path = Path(preview_path)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(preview_path, format="png", dpi=140,
                   metadata={"Software": "LN803 B0.3 layout-input preview", "Description": WARNING})
    return preview_path


def generate(data_path=DEFAULT_DATA, output_path=DEFAULT_DXF, preview_path=DEFAULT_PREVIEW):
    data = load_layout_input(data_path)
    protected = {path.resolve() for path in PRESERVED_FILES + (DEFAULT_MANIFEST, DEFAULT_DATA,
                 ROOT / "measurements/onsite-survey-803.md", Path(data_path))}
    output_path, preview_path = Path(output_path), Path(preview_path)
    for path in (output_path, preview_path):
        require(path.resolve() not in protected, "Layout output cannot overwrite B0.1/B0.2 artifacts or input sources")
    require(output_path.resolve() != preview_path.resolve(), "DXF and PNG outputs must be distinct")
    previous = ezdxf.options.write_fixed_meta_data_for_testing
    try:
        ezdxf.options.write_fixed_meta_data_for_testing = True
        doc = build_overlay(data)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="\n") as stream:
            doc.write(stream)
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = previous
    render_overlay(data, output_path, preview_path)
    return output_path, preview_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_DXF)
    parser.add_argument("--preview", type=Path, default=DEFAULT_PREVIEW)
    args = parser.parse_args()
    try:
        dxf, preview = generate(args.data, args.output, args.preview)
        print(f"Generated {dxf}\nRendered {preview}\n{WARNING}")
    except (ValidationError, OSError, ezdxf.DXFError) as exc:
        print(f"Layout-input generation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
