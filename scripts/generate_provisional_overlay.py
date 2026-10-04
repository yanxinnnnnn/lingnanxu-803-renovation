"""Generate a separate B0.2 provisional DXF and review PNG without rewriting B0.1."""

import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import ezdxf
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PIL import Image

from floorplan import DEFAULT_DATA as BASE_DATA, DEFAULT_PREVIEW as BASE_PREVIEW, ValidationError, load_floorplan, require
from provisional_measurements import (
    APP_ID, BASE_DXF, DEFAULT_DATA, DEFAULT_DXF, DEFAULT_MANIFEST, DEFAULT_PREVIEW,
    LAYER, WARNING, annotation_lines, load_measurements, reference_tags, validate_overlay,
)
from render_preview import render as render_base
from validate_floorplan import validate_dxf


def build_overlay(data, base_path=BASE_DXF, manifest_path=DEFAULT_MANIFEST):
    doc = ezdxf.readfile(base_path)
    validate_dxf(doc, load_floorplan())
    require(LAYER not in doc.layers, "Base DXF must be the B0.1 plan, without a provisional overlay")
    doc.layers.new(LAYER, dxfattribs={"color": 6})
    doc.appids.new(APP_ID)
    polygons = doc.modelspace().query("LWPOLYLINE")
    points = [p for polygon in polygons for p in polygon.get_points("xy")]
    right = max(x for x, _ in points)
    top = max(y for _, y in points)
    for index, (record_id, text) in enumerate(annotation_lines(data)):
        entity = doc.modelspace().add_text(text, dxfattribs={"layer": LAYER, "height": 220})
        entity.set_placement((right + 1500, top + 2200 - index * 500))
        entity.set_xdata(APP_ID, reference_tags(data, record_id))
    return validate_overlay(doc, data, base_path, manifest_path)


def render_overlay(data, dxf_path, output_path, base_path=BASE_DXF, manifest_path=DEFAULT_MANIFEST):
    doc = validate_overlay(ezdxf.readfile(dxf_path), data, base_path, manifest_path)
    annotations = [entity.dxf.text for entity in doc.modelspace() if entity.dxf.layer == LAYER]
    figure = Figure(figsize=(20, 11), dpi=140, facecolor="#f5f7fa")
    FigureCanvasAgg(figure)
    # Reuse the unchanged B0.1 renderer, always writing its intermediate to temp.
    with TemporaryDirectory(prefix="ln803-overlay-") as directory:
        image_path = render_base(dxf_path=base_path, output_path=Path(directory) / "b0.png")
        with Image.open(image_path) as base_image:
            plan = figure.add_axes((0.01, 0.015, 0.61, 0.875))
            plan.imshow(base_image)
            plan.axis("off")
    figure.text(0.5, 0.96, annotations[0], fontsize=16, weight="bold", color="#7b239b",
                ha="center", fontfamily="DejaVu Sans")
    figure.text(0.5, 0.925, "B0 estimated geometry: original plan  |  Third-party reference: purple schedule, mappings unresolved",
                fontsize=12, ha="center", color="#465c70", fontfamily="DejaVu Sans")
    panel = figure.add_axes((0.64, 0.04, 0.35, 0.84))
    panel.set_facecolor("#f0e8f7")
    panel.set_xticks([])
    panel.set_yticks([])
    for spine in panel.spines.values():
        spine.set_edgecolor("#c1a3d4")
    spacing = min(0.037, 0.88 / max(1, len(annotations) - 2))
    for index, text in enumerate(annotations[1:]):
        panel.text(0.035, 0.955 - index * spacing, text, fontsize=10, color="#672082",
                   weight="bold" if text.isupper() else "normal", fontfamily="DejaVu Sans",
                   transform=panel.transAxes, va="top")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, format="png", dpi=140,
                   metadata={"Software": "LN803 B0.2 provisional preview", "Description": WARNING})
    return output_path


def generate(data_path=DEFAULT_DATA, manifest_path=DEFAULT_MANIFEST, base_path=BASE_DXF,
             output_path=DEFAULT_DXF, preview_path=DEFAULT_PREVIEW):
    data = load_measurements(data_path, manifest_path)
    protected = {Path(p).resolve() for p in (BASE_DATA, BASE_DXF, BASE_PREVIEW, data_path, manifest_path, base_path)}
    output_path, preview_path = Path(output_path), Path(preview_path)
    for path in (output_path, preview_path):
        require(path.resolve() not in protected, "Overlay output cannot overwrite B0.1 artifacts or source data")
    require(output_path.resolve() != preview_path.resolve(), "DXF and preview outputs must have distinct paths")
    previous = ezdxf.options.write_fixed_meta_data_for_testing
    try:
        ezdxf.options.write_fixed_meta_data_for_testing = True
        doc = build_overlay(data, base_path, manifest_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="\n") as stream:
            doc.write(stream)
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = previous
    render_overlay(data, output_path, preview_path, base_path, manifest_path)
    return output_path, preview_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--base-dxf", type=Path, default=BASE_DXF)
    parser.add_argument("--output", type=Path, default=DEFAULT_DXF)
    parser.add_argument("--preview", type=Path, default=DEFAULT_PREVIEW)
    args = parser.parse_args()
    try:
        dxf, preview = generate(args.data, args.manifest, args.base_dxf, args.output, args.preview)
        print(f"Generated {dxf}\nRendered {preview}\n{WARNING}")
    except (ValidationError, OSError, ezdxf.DXFError) as exc:
        print(f"Provisional generation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
