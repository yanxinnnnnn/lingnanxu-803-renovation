"""Issue #3 provenance, preservation and reproducibility acceptance checks."""

from copy import deepcopy
from hashlib import sha256
import subprocess
import sys

import ezdxf
from ezdxf.lldxf.tagwriter import TagCollector
from PIL import Image
import pytest
import yaml

from floorplan import (
    DEFAULT_DATA as BASE_DATA, DEFAULT_DXF as BASE_DXF, DEFAULT_PREVIEW as BASE_PREVIEW,
    ROOT, ValidationError, load_floorplan, validate_data,
)
from generate_b0_dxf import generate as generate_base
from generate_provisional_overlay import build_overlay, generate
from provisional_measurements import (
    APP_ID, DEFAULT_MANIFEST, LAYER, PROVENANCE, STATUS, WARNING,
    load_measurements, read_yaml, validate_measurements, validate_overlay,
)
from render_preview import render as render_base


@pytest.fixture
def data():
    return deepcopy(load_measurements())


@pytest.fixture
def manifest():
    return deepcopy(read_yaml(DEFAULT_MANIFEST))


def test_issue3_readable_values_and_unresolved_mappings(data):
    assert data["source_id"] == "measurement-ref-001"
    assert data["reported_totals"]["measured_internal_area_sqm"]["value"] == 124.518
    assert data["reported_totals"]["building_area_sqm"]["value"] == 118.4494
    assert data["reported_totals"]["reported_space_efficiency_percent"]["value"] == 105.12
    assert [item["value"] for item in data["areas"]] == [
        5.143, 2.202, 2.515, 7.743, 7.029, 24.345, 13.398, 10.419, 11.326, 15.139,
    ]
    assert data["linear_dimensions"] == []
    items = list(data["reported_totals"].values()) + data["areas"]
    assert all(item["provenance"] == PROVENANCE and item["verification_status"] == STATUS for item in items)
    assert all(item["mapping_status"] == "unresolved" and item["room_id"] is None for item in data["areas"])


@pytest.mark.parametrize("provenance", ["measured", "onsite_measured", "official", "estimated"])
@pytest.mark.parametrize("location", ["root", "total", "area", "source"])
def test_reject_provenance_conversion(data, manifest, provenance, location):
    record = {
        "root": data, "total": data["reported_totals"]["building_area_sqm"],
        "area": data["areas"][0], "source": manifest["sources"][1],
    }[location]
    record["provenance"] = provenance
    with pytest.raises(ValidationError, match="provenance"):
        validate_measurements(data, manifest)


@pytest.mark.parametrize("location", ["total", "area"])
@pytest.mark.parametrize("status", [None, "verified", "onsite_measured"])
def test_every_measurement_requires_pending_verification(data, manifest, location, status):
    item = data["reported_totals"]["building_area_sqm"] if location == "total" else data["areas"][0]
    if status is None:
        del item["verification_status"]
    else:
        item["verification_status"] = status
    with pytest.raises(ValidationError, match="verification_status"):
        validate_measurements(data, manifest)


def test_source_must_exist_in_manifest(data, manifest):
    manifest["sources"] = [source for source in manifest["sources"] if source["id"] != data["source_id"]]
    with pytest.raises(ValidationError, match="not registered"):
        validate_measurements(data, manifest)


@pytest.mark.parametrize("collection", ["total", "area"])
def test_records_must_reference_registered_source(data, manifest, collection):
    item = data["reported_totals"]["building_area_sqm"] if collection == "total" else data["areas"][0]
    item["source_id"] = "showroom-001"
    with pytest.raises(ValidationError, match="source ID"):
        validate_measurements(data, manifest)


def test_totals_must_match_source_report(data, manifest):
    data["reported_totals"]["building_area_sqm"]["value"] = 118
    with pytest.raises(ValidationError, match="differs"):
        validate_measurements(data, manifest)


@pytest.mark.parametrize("key,value", [
    ("subject_unit_match", True), ("construction_ready", True), ("baseline", "B1"),
    ("confidence", "verified"), ("warning", ""), ("source_id", "unknown"),
])
def test_reject_subject_or_authority_upgrades(data, manifest, key, value):
    data[key] = value
    with pytest.raises(ValidationError):
        validate_measurements(data, manifest)


@pytest.mark.parametrize("key,value", [
    ("mapping_status", "resolved"), ("room_id", "living"), ("unit", "mm"),
    ("value", float("nan")), ("value", True), ("value", -5),
])
def test_reject_guessed_mapping_or_invalid_value(data, manifest, key, value):
    data["areas"][0][key] = value
    with pytest.raises(ValidationError):
        validate_measurements(data, manifest)


def test_linear_dimension_contract_if_legible_record_added(data, manifest):
    # Synthetic schema exercise only, never committed as a real measurement.
    dimension = deepcopy(data["areas"][0])
    dimension.update(id="test_dimension", value=1000, unit="mm", source_location="test source position")
    data["linear_dimensions"].append(dimension)
    validate_measurements(data, manifest)
    del dimension["verification_status"]
    with pytest.raises(ValidationError, match="verification_status"):
        validate_measurements(data, manifest)


def test_third_party_cannot_contaminate_b0_trace(data):
    b0 = load_floorplan()
    b0["rooms"][0]["provenance"] = data["provenance"]
    with pytest.raises(ValidationError, match="estimated"):
        validate_data(b0)


def test_builder_rejects_upgraded_reference(data):
    data["provenance"] = "onsite_measured"
    with pytest.raises(ValidationError, match="third_party_reference"):
        build_overlay(data)


def test_overlay_warning_exact_values_and_preserved_entities(data):
    overlay = build_overlay(data)
    base = ezdxf.readfile(BASE_DXF)
    assert [TagCollector.dxftags(e) for e in overlay.modelspace() if e.dxf.layer != LAYER] == [
        TagCollector.dxftags(e) for e in base.modelspace()
    ]
    annotations = [e for e in overlay.modelspace() if e.dxf.layer == LAYER]
    assert annotations[0].dxf.text == WARNING
    assert any("118.4494 sqm" in e.dxf.text for e in annotations)
    assert all(e.get_xdata(APP_ID)[1].value == PROVENANCE for e in annotations)
    assert all(e.get_xdata(APP_ID)[5].value == STATUS for e in annotations)
    assert overlay.layers.get(LAYER).dxf.color == 6
    validate_overlay(overlay, data)


@pytest.mark.parametrize("damage", ["warning", "provenance", "base_geometry", "value", "hidden_layer"])
def test_reject_damaged_overlay(data, damage):
    doc = build_overlay(data)
    annotations = [e for e in doc.modelspace() if e.dxf.layer == LAYER]
    if damage == "warning":
        annotations[0].dxf.text = "warning removed"
    elif damage == "provenance":
        annotations[1].set_xdata(APP_ID, [(1000, "onsite_measured")])
    elif damage == "base_geometry":
        doc.modelspace().query("LWPOLYLINE")[0].set_points([(0, 0), (1, 0), (1, 1)])
    elif damage == "value":
        annotations[6].dxf.text = "Reported internal / usable area: 999 sqm"
    else:
        doc.layers.get(LAYER).off()
    with pytest.raises(ValidationError):
        validate_overlay(doc, data)


@pytest.mark.parametrize("protected", [BASE_DATA, BASE_DXF, BASE_PREVIEW, DEFAULT_MANIFEST])
def test_generator_refuses_to_overwrite_originals(tmp_path, protected):
    original = protected.read_bytes()
    with pytest.raises(ValidationError, match="cannot overwrite"):
        generate(output_path=protected, preview_path=tmp_path / "overlay.png")
    assert protected.read_bytes() == original


def test_separate_process_reproducibility_and_original_regeneration(tmp_path):
    originals = {path: path.read_bytes() for path in (BASE_DATA, BASE_DXF, BASE_PREVIEW)}
    outputs = []
    for name in ("first", "second"):
        dxf, preview = tmp_path / f"{name}.dxf", tmp_path / f"{name}.png"
        subprocess.run([sys.executable, str(ROOT / "scripts/generate_provisional_overlay.py"),
                        "--output", str(dxf), "--preview", str(preview)],
                       cwd=tmp_path, capture_output=True, check=True)
        outputs.append((dxf.read_bytes(), preview.read_bytes()))
    assert outputs[0] == outputs[1]
    doc = ezdxf.readfile(tmp_path / "first.dxf")
    validate_overlay(doc, load_measurements())
    with Image.open(tmp_path / "first.png") as preview:
        assert preview.info["Description"] == WARNING
        assert preview.size == (2800, 1540)
        preview.verify()
    regenerated = generate_base(output_path=tmp_path / "base.dxf")
    regenerated_preview = render_base(dxf_path=regenerated, output_path=tmp_path / "base.png")
    assert regenerated.read_bytes() == originals[BASE_DXF]
    assert regenerated_preview.read_bytes() == originals[BASE_PREVIEW]
    assert all(path.read_bytes() == content for path, content in originals.items())


def test_frozen_b0_1_artifact_checksums():
    expected = {
        BASE_DATA: "cd2b5128833e871d2136c001b0b69db2605f3b3c4165e4b0be0feb0485869a0b",
        BASE_DXF: "adead70d9e14b98ff3cf44466284c9ca4cf5fee5eb48110530d6a90be0fd5ded",
        BASE_PREVIEW: "bf0b1094b08b596df3d2a4af53a375ad4336b992546993db942e6743eb7eff00",
    }
    for path, digest in expected.items():
        assert sha256(path.read_bytes()).hexdigest() == digest


def test_validator_cli_rejects_upgraded_source(tmp_path, data):
    data["provenance"] = "official"
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(yaml.safe_dump(data), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_provisional_measurements.py"),
                             "--data", str(invalid)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1
    assert "third_party_reference" in result.stderr


def test_worksheet_has_every_bedroom_bathroom_and_evidence_blanks():
    worksheet = (ROOT / "measurements/onsite-survey-803.md").read_text(encoding="utf-8")
    for room_id in ("bedroom_north_1", "bedroom_north_2", "master_bedroom", "bedroom_south",
                    "bathroom_1", "bathroom_2", "master_bathroom"):
        assert room_id in worksheet
    assert all(field in worksheet for field in ("数值", "单位", "方法/来源", "照片/视频编号", "置信度", "备注"))
    measurement_rows = [line for line in worksheet.splitlines() if line.count("______") >= 6]
    assert measurement_rows and "单位（mm）" in worksheet
