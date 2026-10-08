"""Issue #5 authority, provenance, preserved baselines and planning overlay checks."""

from copy import deepcopy
from hashlib import sha256
import subprocess
import sys

import ezdxf
from ezdxf.lldxf.tagwriter import TagCollector
from PIL import Image
import pytest
import yaml

from floorplan import ROOT, ValidationError
from generate_layout_input import build_overlay, generate
from layout_input import (
    APP_ID, BASE_DXF, DEFAULT_DATA, LAYER, PRESERVED_FILES, PROVENANCE, STATUS, WARNING,
    load_layout_input, validate_layout_data, validate_overlay,
)
from provisional_measurements import load_measurements


@pytest.fixture
def data():
    return deepcopy(load_layout_input())


def test_issue_authorized_semantic_mappings(data):
    high = {row["area_sqm"]: row["candidate_room_ids"] for row in data["zone_mappings"] if row["mapping_status"] == "mapped"}
    assert high == {13.398: ["bedroom_south"], 10.419: ["kitchen"], 11.326: ["dining"],
                    15.139: ["living"], 7.029: ["flex_tea_room"]}
    assert all(row["mapping_confidence"] == "high" for row in data["zone_mappings"] if row["mapping_status"] == "mapped")
    medium = [row for row in data["zone_mappings"] if row["mapping_status"] == "candidate"]
    assert {row["area_sqm"] for row in medium} == {7.743, 24.345}
    assert all(row["mapping_confidence"] == "medium" for row in medium)
    suite = next(row for row in medium if row["area_sqm"] == 24.345)
    assert suite["planning_zone_id"] == "master_suite_reference"
    assert suite["candidate_room_ids"] == ["master_bedroom", "walk_in_closet", "master_bathroom"]


def test_unresolved_and_b02_transcription_stay_unresolved(data):
    unresolved = [row for row in data["zone_mappings"] if row["mapping_status"] == "unresolved"]
    assert {row["area_sqm"] for row in unresolved} == {5.143, 2.202, 2.515}
    assert all(row["candidate_room_ids"] == [] and row["planning_zone_id"] is None for row in unresolved)
    reference = load_measurements()
    assert all(row["mapping_status"] == "unresolved" and row["room_id"] is None for row in reference["areas"])
    assert data["linear_dimensions"] == reference["linear_dimensions"] == []


def test_all_layout_records_remain_provisional(data):
    records = [data] + data["zone_mappings"] + data["topology_findings"] + data["layout_constraints"]
    assert all(record["provenance"] == PROVENANCE and record["confidence"] == "provisional"
               and record["verification_status"] == STATUS for record in records)
    assert data["construction_ready"] is False and data["subject_unit_match"] is False
    budgets = [record for record in data["layout_constraints"] if record["type"] == "area"]
    assert len(budgets) == 5
    assert {row["area_sqm"] for row in budgets} == {13.398, 10.419, 11.326, 15.139, 7.029}


@pytest.mark.parametrize("index", [0, 1, 2, 3, 5])
def test_no_candidate_or_unresolved_value_can_be_marked_mapped(data, index):
    data["zone_mappings"][index]["mapping_status"] = "mapped"
    data["zone_mappings"][index]["mapping_confidence"] = "high"
    with pytest.raises(ValidationError, match="Issue #5"):
        validate_layout_data(data)


@pytest.mark.parametrize("field,value", [
    ("candidate_room_ids", ["master_bedroom"]), ("planning_zone_id", "master_bedroom"),
    ("area_sqm", 24), ("mapping_confidence", "high"),
])
def test_master_suite_cannot_be_forced_to_single_room(data, field, value):
    data["zone_mappings"][5][field] = value
    with pytest.raises(ValidationError):
        validate_layout_data(data)


def test_high_area_cannot_be_reassigned(data):
    data["zone_mappings"][7]["candidate_room_ids"] = ["living"]
    with pytest.raises(ValidationError, match="Issue #5"):
        validate_layout_data(data)


@pytest.mark.parametrize("collection", ["root", "zone_mappings", "topology_findings", "layout_constraints"])
@pytest.mark.parametrize("field,value", [("provenance", "official"), ("provenance", "onsite_measured"),
    ("confidence", "verified"), ("verification_status", None), ("source_id", "unknown")])
def test_reject_record_authority_upgrades_or_missing_status(data, collection, field, value):
    record = data if collection == "root" else data[collection][0]
    if value is None:
        del record[field]
    else:
        record[field] = value
    with pytest.raises(ValidationError):
        validate_layout_data(data)


@pytest.mark.parametrize("collection", ["root", "zone_mappings", "layout_constraints", "topology_findings"])
def test_no_new_linear_dimension_or_geometry_field(data, collection):
    record = data if collection == "root" else data[collection][0]
    record["width_mm"] = 1000  # Synthetic invalid input, never a real measurement.
    with pytest.raises(ValidationError, match="no linear dimensions"):
        validate_layout_data(data)


def test_no_linear_dimension_collection(data):
    data["linear_dimensions"] = [{"id": "invented", "value": 1000, "unit": "mm"}]
    with pytest.raises(ValidationError, match="No linear dimension"):
        validate_layout_data(data)


def test_incomplete_or_duplicate_zone_mappings_rejected(data):
    data["zone_mappings"].pop()
    with pytest.raises(ValidationError, match="Every B0.2 area"):
        validate_layout_data(data)
    data = load_layout_input()
    data["zone_mappings"].append(deepcopy(data["zone_mappings"][0]))
    with pytest.raises(ValidationError, match="duplicate"):
        validate_layout_data(data)


def test_medium_suite_cannot_be_room_area_constraint(data):
    constraint = deepcopy(data["layout_constraints"][0])
    constraint.update(id="invalid_suite_budget", reference_zone_id="ref_area_06", room_ids=["master_bedroom"], area_sqm=24.345)
    data["layout_constraints"].append(constraint)
    with pytest.raises(ValidationError, match="Only high mapped"):
        validate_layout_data(data)


def test_required_topology_findings_and_questions(data):
    findings = {record["id"]: record for record in data["topology_findings"]}
    assert {"public_zone_sequence", "separate_flex_zone", "distinct_south_bedroom", "master_suite_boundary",
            "left_central_unresolved", "preserve_trace_geometry", "trace_flex_connection", "trace_corridor_overlaps"} <= set(findings)
    assert all(record["onsite_question"].strip() for record in findings.values())
    assert findings["master_suite_boundary"]["severity"] == "review_required"
    data["topology_findings"] = [row for row in data["topology_findings"] if row["id"] != "master_suite_boundary"]
    with pytest.raises(ValidationError, match="topology"):
        validate_layout_data(data)


def test_overlay_preserves_original_geometry_and_distinct_categories(data):
    doc = build_overlay(data)
    original = ezdxf.readfile(BASE_DXF)
    assert [TagCollector.dxftags(e) for e in doc.modelspace() if e.dxf.layer != LAYER] == [
        TagCollector.dxftags(e) for e in original.modelspace()
    ]
    overlay = [e for e in doc.modelspace() if e.dxf.layer == LAYER]
    assert all(e.dxftype() == "TEXT" for e in overlay)
    assert any(e.dxf.text == WARNING for e in overlay)
    styles = {category: {e.dxf.color for e in overlay if e.get_xdata(APP_ID)[6].value == category}
              for category in ("mapped:high", "candidate:medium", "unresolved:low")}
    assert styles == {"mapped:high": {3}, "candidate:medium": {30}, "unresolved:low": {6}}
    plan_labels = [e for e in overlay if e.get_xdata(APP_ID)[7].value == "plan"]
    assert sum(e.get_xdata(APP_ID)[6].value == "mapped:high" for e in plan_labels) == 5
    assert not any(e.get_xdata(APP_ID)[6].value == "unresolved:low" for e in plan_labels)
    assert any(e.dxf.text == "SUITE CANDIDATE | 24.345 sqm" for e in plan_labels)
    validate_overlay(doc, data)


@pytest.mark.parametrize("damage", ["warning", "base_geometry", "style", "provenance", "placement", "hidden_layer"])
def test_saved_overlay_validation_rejects_damage(data, damage):
    doc = build_overlay(data)
    overlay = [e for e in doc.modelspace() if e.dxf.layer == LAYER]
    if damage == "warning":
        next(e for e in overlay if e.dxf.text == WARNING).dxf.text = "removed"
    elif damage == "base_geometry":
        doc.modelspace().query("LWPOLYLINE")[0].set_points([(0, 0), (1, 0), (1, 1)])
    elif damage == "style":
        overlay[0].dxf.color = 6
    elif damage == "provenance":
        overlay[0].set_xdata(APP_ID, [(1000, "onsite_measured")])
    elif damage == "placement":
        overlay[0].dxf.align_point = (0, 0)
    else:
        doc.layers.get(LAYER).off()
    with pytest.raises(ValidationError):
        validate_overlay(doc, data)


@pytest.mark.parametrize("protected", PRESERVED_FILES)
@pytest.mark.parametrize("output_kind", ["dxf", "preview"])
def test_output_cannot_overwrite_previous_baselines(tmp_path, protected, output_kind):
    before = protected.read_bytes()
    kwargs = {"output_path": tmp_path / "new.dxf", "preview_path": tmp_path / "new.png"}
    kwargs["output_path" if output_kind == "dxf" else "preview_path"] = protected
    with pytest.raises(ValidationError, match="cannot overwrite"):
        generate(**kwargs)
    assert protected.read_bytes() == before


def test_determinism_separate_processes_and_preserved_baselines(tmp_path):
    before = {path: path.read_bytes() for path in PRESERVED_FILES}
    outputs = []
    for name in ("first", "second"):
        dxf, preview = tmp_path / f"{name}.dxf", tmp_path / f"{name}.png"
        subprocess.run([sys.executable, str(ROOT / "scripts/generate_layout_input.py"),
                        "--output", str(dxf), "--preview", str(preview)],
                       cwd=tmp_path, capture_output=True, check=True)
        outputs.append((dxf.read_bytes(), preview.read_bytes()))
    assert outputs[0] == outputs[1]
    validate_overlay(ezdxf.readfile(tmp_path / "first.dxf"), load_layout_input())
    with Image.open(tmp_path / "first.png") as preview:
        assert preview.info["Description"] == WARNING
        assert preview.size == (3080, 1680)
        preview.verify()
    assert all(path.read_bytes() == content for path, content in before.items())


def test_b02_frozen_checksums():
    expected = ["988886a81195d9c357b63c700939ef65f99d33dc458452d76e8b734062261a27",
                "70e3faf6733d5b7fa227060f8852a7efde59aeda3f1be643b252caaef185a056",
                "0b460d185707ee3a0e5128731d18145963d4245b26ff5f485c89a5651f56dcde"]
    assert [sha256(path.read_bytes()).hexdigest() for path in PRESERVED_FILES[3:]] == expected


def test_invalid_mapping_cli_fails_nonzero(tmp_path, data):
    data["zone_mappings"][0]["candidate_room_ids"] = ["utility"]
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(yaml.safe_dump(data), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_layout_input.py"),
                             "--data", str(invalid)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1 and "Issue #5" in result.stderr


def test_project_and_planning_summary_ready_without_b1_or_l1():
    project = yaml.safe_load((ROOT / "project.yaml").read_text(encoding="utf-8"))
    assert project["baseline"]["current"] == "B0"
    assert project["baseline"]["construction_ready"] is False
    # Issue #9 advances readiness while retaining this provisional input and B0.
    assert project["design"]["layout_status"] == "concept_variants_ready"
    assert project["files"]["layout_input_data"] == "data/b0_layout_input.yaml"
    summary = (ROOT / project["files"]["layout_input_summary"]).read_text(encoding="utf-8")
    assert all(term in summary for term in ("24.345", "5.143", "2.202", "2.515", "B1", "L1", "ONSITE"))
