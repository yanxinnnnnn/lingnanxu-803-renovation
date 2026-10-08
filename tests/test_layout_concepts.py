"""Issue #9 program invariants, precision boundaries and frozen artifact evidence."""

from copy import deepcopy
from hashlib import sha256
import json
import os
import subprocess
import sys

import ezdxf
from ezdxf.lldxf.tagwriter import TagCollector
from PIL import Image
import pytest
import yaml

from floorplan import ROOT, ValidationError
import generate_layout_concepts as generator
from layout_concepts import (APP_ID, BASE_DXF, BEDROOMS, DEFAULT_DATA, LAYERS, PRESERVED_FILES,
                             WARNING, load_concepts, output_paths, requirement_labels, validate_concepts, validate_overlay)
from provisional_measurements import read_yaml


@pytest.fixture
def data():
    return deepcopy(load_concepts())


def digest(path):
    content = path.read_bytes()
    # Markdown is text=auto: ignore checkout newline style, never PNG/DXF changes.
    if path.suffix == ".md":
        content = content.replace(b"\r\n", b"\n")
    return sha256(content).hexdigest()


def test_program_and_opposite_hypotheses(data):
    program = read_yaml(ROOT / "data/space_program_v0.1.yaml")
    assert [c["id"] for c in data["concepts"]] == ["A", "B", "C"]
    assert data["shared_program"]["bedroom_count"] == 4
    assert data["shared_program"]["master_occupants"] == ["homeowner", "spouse"]
    assert data["shared_program"]["bathroom_room_ids"] == ["bathroom_1", "bathroom_2", "master_bathroom"]
    assert data["shared_program"]["bathtub_status"] == "optional"
    assert data["shared_program"]["parents_residency"] == "long_term"
    assert all(data["shared_program"][k] is False for k in ("permanent_cat_wall", "gym_required", "enclosure_approved"))
    assert data["requirement_labels"] == requirement_labels(program)
    hypotheses = set()
    for c in data["concepts"]:
        assert set(c["room_roles"]) == BEDROOMS
        assert c["room_roles"]["bedroom_south"] == "parents"
        assert c["room_roles"]["master_bedroom"] == "master"
        assert c["child_guest_status"] == "provisional_hypothesis"
        hypotheses.add((c["room_roles"]["bedroom_north_1"], c["room_roles"]["bedroom_north_2"]))
        assert c["master_wfh"]["first_attempt"] == "master_suite"
        assert c["master_wfh"]["fallback_condition"] == program["work_from_home"]["location_strategy"]["fallback_condition"]
        assert c["pet_infrastructure"]["cat_count"] == 5
        uses = {p["use"] for p in c["pet_infrastructure"]["candidates"]}
        assert {"litter_primary", "litter_backup", "water", "feeding", "scratch_rest_perch"} <= uses
        assert c["entrance_right"]["status"] == "provisional_condition_dependent"
        assert c["entrance_right"]["enclosure_approved"] is False
        assert all(c[k] for k in ("assumptions", "strengths", "tradeoffs", "b1_blockers"))
    assert hypotheses == {("child", "guest"), ("guest", "child")}


def test_materially_distinct_modes_and_zone_labels(data):
    a, b, c = data["concepts"]
    assert a["intervention_level"] == "low"
    assert a["family_flex"]["opening_change"] == "none_assumed"
    assert b["family_flex"]["opening_change"] == "wide_living_facing_candidate"
    assert b["family_flex"]["functional_wall"] == "solid_functional_wall_candidate"
    assert c["family_flex"]["opening_change"] == "closable_connection_candidate"
    assert c["family_flex"]["primary_use"] == "family_quiet_activity"
    assert len({tuple(item["zones"]["flex_tea_room"]) for item in (a, b, c)}) == 3
    assert len({item["entrance_right"]["mode"] for item in (a, b, c)}) == 3


@pytest.mark.parametrize("path,value", [
    (("concepts",), []),
    (("construction_ready",), True), (("baseline",), "B1"), (("l1_status",), "complete"),
    (("linear_dimensions",), [{"width_mm": 1000}]),
    (("shared_program", "bedroom_count"), 3),
    (("shared_program", "bathroom_room_ids"), ["bathroom_1", "master_bathroom"]),
    (("shared_program", "bathtub_status"), "required"),
    (("shared_program", "permanent_cat_wall"), True),
    (("shared_program", "gym_required"), True),
    (("concepts", 0, "room_roles", "bedroom_south"), "guest"),
    (("concepts", 0, "room_roles", "bedroom_north_1"), "office"),
    (("concepts", 0, "child_guest_status"), "verified"),
    (("concepts", 1, "room_roles", "bedroom_north_1"), "child"),
    (("concepts", 0, "master_wfh", "first_attempt"), "family_flex_room"),
    (("concepts", 2, "master_wfh", "fallback_condition"), ""),
    (("concepts", 2, "family_flex", "primary_use"), "primary_office"),
    (("concepts", 0, "family_flex", "opening_change"), "wide_living_facing_candidate"),
    (("concepts", 1, "family_flex", "functional_wall"), "none_assumed"),
    (("concepts", 2, "pet_infrastructure", "cat_count"), 2),
    (("concepts", 0, "pet_infrastructure", "candidates"), []),
    (("concepts", 1, "pet_infrastructure", "indoor_fallback"), ""),
    (("concepts", 0, "entrance_right", "status"), "approved"),
    (("concepts", 2, "entrance_right", "enclosure_approved"), True),
    (("concepts", 2, "entrance_right", "condition"), ""),
    (("zone_bindings", "entrance_right", "status"), "verified"),
    (("requirement_labels", "parents_bed"), "REQUIREMENT ONLY: parents bed width 2 m"),
    (("concepts", 0, "zones", "master_bedroom"), ["WFH DESK 1601 mm"]),
    (("concepts", 1, "assumptions"), []), (("concepts", 1, "strengths"), []),
    (("concepts", 2, "tradeoffs"), []), (("concepts", 2, "b1_blockers"), []),
])
def test_invalid_program_or_precision_rejected(data, path, value):
    record = data
    for key in path[:-1]:
        record = record[key]
    record[path[-1]] = value
    with pytest.raises(ValidationError):
        validate_concepts(data)


def test_hypotheses_cannot_all_be_fixed_to_one_assignment(data):
    data["concepts"][1]["room_roles"].update(bedroom_north_1="child", bedroom_north_2="guest")
    with pytest.raises(ValidationError, match="Opposite"):
        validate_concepts(data)


def test_backup_litter_and_indoor_alternatives_required(data):
    for cid in range(3):
        mutated = deepcopy(data)
        pets = mutated["concepts"][cid]["pet_infrastructure"]
        pets["candidates"] = [p for p in pets["candidates"] if p["use"] != "litter_backup"]
        with pytest.raises(ValidationError, match="backup litter"):
            validate_concepts(mutated)
    data["concepts"][2]["pet_infrastructure"]["candidates"] = [p for p in data["concepts"][2]["pet_infrastructure"]["candidates"] if p["room_id"] != "bathroom_2"]
    with pytest.raises(ValidationError, match="indoor litter"):
        validate_concepts(data)


@pytest.mark.parametrize("path", [(), ("concepts", 0), ("concepts", 0, "master_wfh"),
                                    ("concepts", 0, "family_flex"), ("concepts", 0, "pet_infrastructure", "candidates", 0)])
@pytest.mark.parametrize("field", ["width_mm", "polygon_px", "scale_x_mm_per_px", "wall_geometry"])
def test_new_geometry_fields_rejected(data, path, field):
    record = data
    for key in path:
        record = record[key]
    record[field] = 1000
    with pytest.raises(ValidationError, match="no dimensions"):
        validate_concepts(data)


@pytest.mark.parametrize("cid", ["A", "B", "C"])
def test_only_text_added_and_all_baseline_entities_unchanged(data, cid):
    concept = next(c for c in data["concepts"] if c["id"] == cid)
    doc = generator.build_overlay(data, concept)
    base = ezdxf.readfile(BASE_DXF)
    assert [TagCollector.dxftags(e) for e in doc.modelspace() if e.dxf.layer not in LAYERS] == [TagCollector.dxftags(e) for e in base.modelspace()]
    overlay = [e for e in doc.modelspace() if e.dxf.layer in LAYERS]
    assert all(e.dxftype() == "TEXT" for e in overlay)
    assert any(e.dxf.text == WARNING for e in overlay)
    assert all(e.get_xdata(APP_ID)[1].value == "provisional_concepts" for e in overlay)
    assert not doc.modelspace().query("DIMENSION INSERT HATCH")
    validate_overlay(doc, data, concept)


@pytest.mark.parametrize("damage", ["wall", "dimension", "furniture", "warning", "provenance", "hidden_layer", "placement"])
def test_saved_dxf_rejects_geometry_or_visibility_damage(data, damage):
    concept = data["concepts"][0]
    doc = generator.build_overlay(data, concept)
    entity = next(e for e in doc.modelspace() if e.dxf.layer == "A-CONCEPT-ZONE")
    if damage == "wall":
        doc.modelspace().query("LWPOLYLINE")[0].set_points([(0, 0), (1, 0), (1, 1)])
    elif damage == "dimension":
        doc.modelspace().add_linear_dim(base=(0, 0), p1=(0, 0), p2=(1, 1))
    elif damage == "furniture":
        doc.modelspace().add_lwpolyline([(0, 0), (1, 0), (1, 1)], dxfattribs={"layer": "A-CONCEPT-ZONE"})
    elif damage == "warning":
        next(e for e in doc.modelspace() if e.dxftype() == "TEXT" and e.dxf.text == WARNING).dxf.text = "removed"
    elif damage == "provenance":
        entity.set_xdata(APP_ID, [(1000, "B1")])
    elif damage == "hidden_layer":
        doc.layers.get("A-CONCEPT-NOTE").off()
    else:
        entity.dxf.align_point = (0, 0)
    with pytest.raises(ValidationError):
        validate_overlay(doc, data, concept)


@pytest.mark.parametrize("protected", PRESERVED_FILES + (DEFAULT_DATA,))
def test_output_guards_preserve_previous_baselines_and_inputs(tmp_path, monkeypatch, protected):
    before = protected.read_bytes()
    monkeypatch.setattr(generator, "output_paths", lambda cid, directory=ROOT: (protected, tmp_path / "new.png"))
    with pytest.raises(ValidationError, match="cannot overwrite"):
        generator.generate(directory=tmp_path)
    assert protected.read_bytes() == before
    assert not (tmp_path / "new.png").exists()


def test_all_destinations_checked_before_writing(tmp_path):
    _, last_png = output_paths("C", tmp_path)
    last_png.parent.mkdir(parents=True)
    last_png.write_bytes(b"unrelated existing work")
    with pytest.raises(ValidationError, match="unrelated"):
        generator.generate(directory=tmp_path)
    assert last_png.read_bytes() == b"unrelated existing work"
    assert not output_paths("A", tmp_path)[0].exists()


def test_previous_baselines_frozen():
    expected = json.loads((ROOT / "tests/fixtures/layout_preserved_baselines_v0.1.json").read_text(encoding="utf-8"))
    actual = {path.relative_to(ROOT).as_posix(): digest(path) for path in PRESERVED_FILES}
    assert actual == expected


def test_independent_process_determinism_and_committed_artifacts(tmp_path, data):
    before = {p: p.read_bytes() for p in PRESERVED_FILES}
    runs = []
    for index, seed in enumerate(("17", "931")):
        directory = tmp_path / f"run_{index}"
        env = dict(os.environ, PYTHONHASHSEED=seed)
        subprocess.run([sys.executable, str(ROOT / "scripts/generate_layout_concepts.py"), "--output-dir", str(directory)],
                       cwd=tmp_path, capture_output=True, check=True, env=env)
        runs.append([tuple(p.read_bytes() for p in output_paths(cid, directory)) for cid in ("A", "B", "C")])
    assert runs[0] == runs[1]
    for index, concept in enumerate(data["concepts"]):
        paths = output_paths(concept["id"])
        assert runs[0][index] == tuple(p.read_bytes() for p in paths)
        validate_overlay(ezdxf.readfile(paths[0]), data, concept)
        with Image.open(paths[1]) as preview:
            assert preview.size == (3360, 2240)
            assert preview.info["Description"] == WARNING
            preview.verify()
    assert len({sha256(pair[0]).hexdigest() for pair in runs[0]}) == 3
    assert len({sha256(pair[1]).hexdigest() for pair in runs[0]}) == 3
    assert all(p.read_bytes() == content for p, content in before.items())


def test_project_ready_and_review_files_exist(data):
    project = read_yaml(ROOT / "project.yaml")
    assert project["baseline"]["current"] == "B0" and project["baseline"]["construction_ready"] is False
    assert project["design"]["layout_status"] == "concept_variants_ready"
    assert project["design"]["b1_status"] == "pending"
    assert project["design"]["l1_status"] == "pending_not_selected"
    for key in ("layout_concepts_data", "layout_concepts_comparison", "layout_a_cad", "layout_a_preview", "layout_b_cad", "layout_b_preview", "layout_c_cad", "layout_c_preview"):
        assert (ROOT / project["files"][key]).exists()
    doc = (ROOT / project["files"]["layout_concepts_comparison"]).read_text(encoding="utf-8")
    assert WARNING in doc and "no winner is selected" in doc
    assert all(term in doc for term in ("Parents' comfort", "Master WFH quality", "Family Flex utility", "Five-cat infrastructure", "B1 light, clear-span and furniture-fit evidence"))


def test_invalid_cli_nonzero_without_writes(tmp_path, data):
    data["concepts"][0]["pet_infrastructure"]["cat_count"] = 2
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    for script in ("validate_layout_concepts.py", "generate_layout_concepts.py"):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / script), "--data", str(invalid)],
                                cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == 1 and "Five-cat" in result.stderr
