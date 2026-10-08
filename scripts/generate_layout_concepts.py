"""Generate deterministic A/B/C TEXT-only concept DXFs and review PNGs."""

import argparse
from pathlib import Path
import sys
import textwrap

import ezdxf
from ezdxf.enums import TextEntityAlignment
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Polygon

from floorplan import APP_ID as B0_APP_ID, ROOT, ValidationError, require
from layout_concepts import (APP_ID, BASE_DXF, DEFAULT_DATA, LAYERS, PRESERVED_FILES, WARNING,
                             annotations, load_concepts, output_paths, tags, validate_overlay)

COLORS = {"A-CONCEPT-ROLE": "#087f5b", "A-CONCEPT-ZONE": "#245fa1", "A-CONCEPT-PET": "#8c3999", "A-CONCEPT-NOTE": "#a12317"}


def build_overlay(data, concept):
    doc = ezdxf.readfile(BASE_DXF)
    doc.appids.new(APP_ID)
    for name, color in LAYERS.items():
        doc.layers.new(name, dxfattribs={"color": color})
    for spec in annotations(data, concept):
        entity = doc.modelspace().add_text(spec["text"], dxfattribs={
            "layer": spec["layer"], "height": 160 if spec["kind"] == "plan" else 220})
        entity.set_placement(spec["position"], align=TextEntityAlignment.MIDDLE_CENTER
                             if spec["kind"] == "plan" else TextEntityAlignment.LEFT)
        entity.set_xdata(APP_ID, tags(spec, concept["id"]))
    return validate_overlay(doc, data, concept)


def card(figure, bounds, title, rows, width=54, fontsize=10):
    axes = figure.add_axes(bounds)
    axes.set_facecolor("#eef2f6")
    axes.set_xticks([])
    axes.set_yticks([])
    for spine in axes.spines.values():
        spine.set_edgecolor("#ccd6e0")
    axes.text(.035, .95, title, va="top", fontsize=12, weight="bold", color="#21364b", fontfamily="DejaVu Sans")
    lines = []
    for row in rows:
        lines.extend(textwrap.wrap(row, width=width, subsequent_indent="  ", break_long_words=False))
        lines.append("")
    axes.text(.035, .84, "\n".join(lines).rstrip(), va="top", fontsize=fontsize,
              linespacing=1.25, color="#465c70", fontfamily="DejaVu Sans")


def render_overlay(data, concept, dxf_path, preview_path):
    doc = validate_overlay(ezdxf.readfile(dxf_path), data, concept)
    figure = Figure(figsize=(24, 16), dpi=140, facecolor="#f8fafc")
    FigureCanvasAgg(figure)
    axes = figure.add_axes((.025, .30, .56, .56))
    axes.set_aspect("equal")
    axes.axis("off")
    points, room_bounds = [], {}
    for entity in doc.modelspace():
        layer = entity.dxf.layer
        if entity.dxftype() == "LWPOLYLINE":
            polygon = list(entity.get_points("xy"))
            points.extend(polygon)
            outer = layer == "A-WALL-EXT"
            axes.add_patch(Polygon(polygon, closed=True, fill=not outer, facecolor="#e2eaf1",
                                   edgecolor="#172b40" if outer else "#93a3b3", linewidth=2 if outer else 1,
                                   alpha=1 if outer else .65, zorder=3 if outer else 1))
            if not outer:
                room = entity.get_xdata(B0_APP_ID)[2].value
                left, right = min(x for x, _ in polygon), max(x for x, _ in polygon)
                bottom, top = min(y for _, y in polygon), max(y for _, y in polygon)
                room_bounds[room] = (left, right, bottom, top)
                axes.text((left + right) / 2, top - 110, room, fontsize=6.5, ha="center", va="top",
                          color="#61758a", fontfamily="DejaVu Sans", zorder=5)
        elif entity.dxftype() == "LINE" and layer == "A-GLAZ":
            start, end = entity.dxf.start, entity.dxf.end
            axes.plot([start.x, end.x], [start.y, end.y], color="#008baf", linewidth=3, zorder=4)
    for entity in doc.modelspace():
        if entity.dxf.layer not in LAYERS or entity.dxf.layer == "A-CONCEPT-NOTE":
            continue
        room = entity.get_xdata(APP_ID)[4].value
        left, right, _, _ = room_bounds[room]
        width = 25 if right - left >= 3000 else 18
        label = "\n".join(textwrap.wrap(entity.dxf.text, width=width, break_long_words=False))
        point = entity.dxf.align_point
        role = entity.dxf.layer == "A-CONCEPT-ROLE"
        axes.text(point.x, point.y, label, ha="center", va="center", fontsize=8 if role else 7,
                  color=COLORS[entity.dxf.layer], weight="bold" if role else "normal", linespacing=1.1,
                  fontfamily="DejaVu Sans", zorder=6,
                  bbox={"facecolor": "#ffffff", "edgecolor": "none", "alpha": .85, "pad": 1.5})
    axes.set_xlim(min(x for x, _ in points) - 550, max(x for x, _ in points) + 550)
    axes.set_ylim(min(y for _, y in points) - 350, max(y for _, y in points) + 350)
    figure.text(.5, .969, WARNING, ha="center", fontsize=14, color="#a12317", weight="bold", fontfamily="DejaVu Sans")
    figure.text(.5, .928, f"LAYOUT {concept['id']}  |  {concept['title']}", ha="center", fontsize=24,
                color="#21364b", weight="bold", fontfamily="DejaVu Sans")
    figure.text(.5, .894, "Uses only; no measured fit.  |  Green: room role  /  Blue: concept zone  /  Purple: pet candidate",
                ha="center", fontsize=12, color="#465c70", fontfamily="DejaVu Sans")
    shared = data["shared_program"]
    rows = [
        "Intervention: " + concept["intervention_level"] + "; no physical alteration selected.",
        "PRIMARY WORK: " + concept["master_wfh"]["strategy"],
        "FALLBACK ONLY IF: " + concept["master_wfh"]["fallback_condition"],
        "FAMILY FLEX: " + concept["family_flex"]["strategy"],
        "PUBLIC: " + concept["living_dining_strategy"],
        "PARENTS: " + concept["parents_strategy"],
        "ENTRANCE: " + concept["entrance_right"]["strategy"],
        "CONDITIONS: " + concept["entrance_right"]["condition"],
        "Entry-garden trace is an unverified entrance-right anchor only.",
        f"PET SUPPORT / {concept['pet_infrastructure']['cat_count']} CATS: " + concept["pet_infrastructure"]["indoor_fallback"],
        "REQUIREMENTS ONLY / EXACT FIT UNVERIFIED: " + " | ".join(label.removeprefix("REQUIREMENT ONLY: ") for label in data["requirement_labels"].values()),
        "Retain four bedrooms, three bathrooms and kitchen sliding-door logic. Bathtub optional; no forced gym/cat wall or enclosure approval.",
    ]
    card(figure, (.61, .30, .365, .56), "STRATEGY / REQUIREMENTS", rows, width=100, fontsize=10)
    card(figure, (.025, .045, .30, .23), "ASSUMPTIONS / STRENGTHS", concept["assumptions"] + concept["strengths"], width=78, fontsize=9.5)
    card(figure, (.34, .045, .30, .23), "TRADEOFFS / NO WINNER SELECTED", concept["tradeoffs"] + [
        "Child/guest assignment is provisional; compare upper-room light, clear spans and furniture fit in B1.",
        "B0 trace gaps/overlaps remain; label positions are typography, not furniture or service points."], width=78, fontsize=9.5)
    card(figure, (.655, .045, .32, .23), "B1 BLOCKERS / FIELD EVIDENCE", concept["b1_blockers"], width=84, fontsize=9.5)
    figure.text(.5, .020, "B0 estimated; B1 pending; L1 pending / not selected. Product Owner selects or combines after review. NOT FOR CONSTRUCTION.",
                ha="center", fontsize=12, color="#a12317", fontfamily="DejaVu Sans")
    preview_path = Path(preview_path)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(preview_path, format="png", dpi=140, metadata={"Software": "LN803 Layout Concepts v0.1", "Description": WARNING})
    return preview_path


def generate(data_path=DEFAULT_DATA, directory=ROOT, concept_id=None):
    data = load_concepts(data_path)
    require(concept_id is None or concept_id in ("A", "B", "C"), "Unknown concept")
    concepts = [c for c in data["concepts"] if concept_id is None or c["id"] == concept_id]
    outputs = [output_paths(c["id"], directory) for c in concepts]
    # Check all destinations before writing. Preserve prior files and arbitrary CAD
    # work such as editor backups; only these exact new concept artifacts regenerate.
    protected = {p.resolve() for p in PRESERVED_FILES + (DEFAULT_DATA, Path(data_path))}
    known_outputs = {p.resolve() for cid in ("A", "B", "C") for p in output_paths(cid)}
    for pair in outputs:
        for path in pair:
            resolved = path.resolve()
            require(resolved not in protected, "Concept output cannot overwrite prior baselines or inputs")
            require(not path.exists() or resolved in known_outputs, "Concept output cannot overwrite unrelated existing files")
    previous = ezdxf.options.write_fixed_meta_data_for_testing
    try:
        ezdxf.options.write_fixed_meta_data_for_testing = True
        for concept, (dxf, preview) in zip(concepts, outputs):
            doc = build_overlay(data, concept)
            dxf.parent.mkdir(parents=True, exist_ok=True)
            with dxf.open("w", encoding="utf-8", newline="\n") as stream:
                doc.write(stream)
            render_overlay(data, concept, dxf, preview)
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = previous
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=ROOT, help="Root containing cad/ and artifacts/")
    parser.add_argument("--concept", choices=("A", "B", "C"), help="Default: all three")
    args = parser.parse_args()
    try:
        for dxf, png in generate(args.data, args.output_dir, args.concept):
            print(f"Generated {dxf}\nRendered {png}")
    except (ValidationError, OSError, ezdxf.DXFError) as exc:
        print(f"Concept generation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
