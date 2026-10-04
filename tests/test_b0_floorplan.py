"""Issue #1 acceptance checks; all output goes to pytest's temporary directory."""

from copy import deepcopy
import subprocess
import sys

import ezdxf
from PIL import Image
import pytest
import yaml

from floorplan import (
    APP_ID, ROOT, WARNING, ValidationError,
    load_floorplan, transform, validate_data,
)
from generate_b0_dxf import generate
from render_preview import render
from validate_floorplan import validate_dxf


@pytest.fixture
def data():
    return deepcopy(load_floorplan())


def test_yaml_baseline_and_required_rooms(data):
    assert data["metadata"]["baseline"] == "B0"
    assert data["metadata"]["construction_ready"] is False
    assert {r["id"] for r in data["rooms"]} == {
        "utility", "shoe_storage", "entry_garden", "service_balcony",
        "bedroom_north_1", "bedroom_north_2", "bathroom_1", "corridor_entry",
        "master_bathroom", "walk_in_closet", "master_bedroom", "flex_tea_room",
        "bathroom_2", "bedroom_south", "kitchen", "dining", "living",
    }
    assert len(data["glazing"]) == 8
    assert data["rooms"][0]["display_name"] == "家政间"


@pytest.mark.parametrize("point_px,expected", [
    ([150, 1400], (0, 0)),
    ([450, 500], (4650, 11250)),
    ([1400, 1400], (19375, 0)),
    ([100, 1500], (-775, -1250)),
])
def test_documented_coordinate_transform(data, point_px, expected):
    assert data["trace_coordinate_system"]["origin_px"] == [150, 1400]
    assert data["trace_coordinate_system"]["scale_x_mm_per_px"] == 15.5
    assert data["trace_coordinate_system"]["scale_y_mm_per_px"] == 12.5
    assert transform(point_px, data["trace_coordinate_system"]) == expected


def test_all_geometry_and_sources_estimated(data):
    records = [data["metadata"], data["trace_coordinate_system"], data["perimeter"]]
    records += data["rooms"] + data["glazing"] + data["sources"]
    assert all(record["provenance"] == "estimated" for record in records)


def test_readable_dxf_layers_geometry_warning_and_names(tmp_path, data):
    output = generate(output_path=tmp_path / "base.dxf")
    doc = ezdxf.readfile(output)
    assert not doc.audit().has_errors
    assert {
        "A-WALL-EXT", "A-WALL-INT", "A-GLAZ", "A-DOOR", "A-FURN",
        "A-ROOM", "A-NOTE", "A-UNVERIFIED",
    } <= {layer.dxf.name for layer in doc.layers}
    validate_dxf(doc, data)
    entities = list(doc.modelspace())
    assert len(doc.modelspace().query("LWPOLYLINE")) == 18
    assert len(doc.modelspace().query("LINE")) == 8
    assert any(e.dxftype() == "TEXT" and e.dxf.text == WARNING for e in entities)
    assert all(e.get_xdata(APP_ID)[1].value == "estimated" for e in entities)


def test_generation_deterministic_across_processes_and_cwd(tmp_path):
    outputs = [tmp_path / "first.dxf", tmp_path / "second.dxf"]
    for output in outputs:
        subprocess.run([sys.executable, str(ROOT / "scripts/generate_b0_dxf.py"),
                        "--output", str(output)], cwd=tmp_path, check=True, capture_output=True)
    assert outputs[0].read_bytes() == outputs[1].read_bytes()


def test_preview_is_readable_and_repeatable(tmp_path):
    dxf = generate(output_path=tmp_path / "base.dxf")
    first = render(dxf_path=dxf, output_path=tmp_path / "first.png")
    second = render(dxf_path=dxf, output_path=tmp_path / "second.png")
    with Image.open(first) as preview:
        assert preview.format == "PNG"
        assert preview.size == (1960, 1400)
        assert preview.info["Description"] == WARNING
        preview.verify()
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize("field,value", [
    ("polygon_px", [[1, 2], [3, 4]]),
    ("polygon_px", [[1, 2], [1, 2], [1, 2]]),
    ("polygon_px", [[1, 2], [3, 4], [5, 6]]),
    ("polygon_px", [[True, 2], [3, 4], [5, 7]]),
    ("polygon_px", [["1", 2], [3, 4], [5, 7]]),
    ("polygon_px", [[float("nan"), 2], [3, 4], [5, 7]]),
    ("polygon_px", [[float("inf"), 2], [3, 4], [5, 7]]),
    ("polygon_px", [[1, 2, 3], [3, 4], [5, 7]]),
    ("provenance", "measured"),
    ("provenance", "official"),
    ("provenance", None),
    ("display_name", " "),
    ("source", "unknown"),
])
def test_reject_malformed_room(data, field, value):
    data["rooms"][0][field] = value
    with pytest.raises(ValidationError):
        validate_data(data)


@pytest.mark.parametrize("points", [[], [[1, 2]], [[1, 2], [3, 4], [5, 6]], [[1, 2], [1, 2]]])
def test_reject_malformed_segment(data, points):
    data["glazing"][0]["segment_px"] = points
    with pytest.raises(ValidationError):
        validate_data(data)


@pytest.mark.parametrize("collection", ["sources", "rooms", "glazing"])
def test_reject_duplicate_ids(data, collection):
    data[collection].append(deepcopy(data[collection][0]))
    with pytest.raises(ValidationError, match="duplicate"):
        validate_data(data)


@pytest.mark.parametrize("location", ["metadata", "trace_coordinate_system", "perimeter", "source", "glazing"])
def test_reject_provenance_upgrades(data, location):
    record = data["sources"][0] if location == "source" else data["glazing"][0] if location == "glazing" else data[location]
    record["provenance"] = "official"
    with pytest.raises(ValidationError):
        validate_data(data)


@pytest.mark.parametrize("section", ["metadata", "trace_coordinate_system", "sources", "perimeter", "rooms", "glazing"])
def test_reject_missing_required_section(data, section):
    del data[section]
    with pytest.raises(ValidationError):
        validate_data(data)


def test_reject_missing_room_and_invalid_metadata(data):
    data["rooms"].pop()
    with pytest.raises(ValidationError, match="Missing required rooms"):
        validate_data(data)


@pytest.mark.parametrize("key,value", [("baseline", "B1"), ("cad_unit", "px"),
    ("construction_ready", True), ("warning", ""), ("artifact_date", "invalid")])
def test_reject_invalid_metadata(data, key, value):
    data["metadata"][key] = value
    with pytest.raises(ValidationError):
        validate_data(data)


@pytest.mark.parametrize("key,value", [("unit", "mm"), ("origin_px", [150]),
    ("scale_x_mm_per_px", 0), ("scale_y_mm_per_px", "12.5")])
def test_reject_invalid_calibration(data, key, value):
    data["trace_coordinate_system"][key] = value
    with pytest.raises(ValidationError):
        validate_data(data)


@pytest.mark.parametrize("content", ["rooms: []\nrooms: []\n", "[broken", "null\n"])
def test_reject_invalid_yaml(tmp_path, content):
    path = tmp_path / "invalid.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValidationError):
        load_floorplan(path)


def test_validator_cli_fails_nonzero(tmp_path, data):
    data["rooms"][0]["provenance"] = "measured"
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_floorplan.py"),
                             "--data", str(path)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1
    assert "estimated" in result.stderr


@pytest.mark.parametrize("damage", ["layer", "warning", "provenance", "geometry", "label"])
def test_validator_rejects_damaged_dxf(tmp_path, data, damage):
    doc = ezdxf.readfile(generate(output_path=tmp_path / "base.dxf"))
    if damage == "layer":
        doc.layers.remove("A-DOOR")
    elif damage == "warning":
        doc.modelspace().query('TEXT[layer=="A-UNVERIFIED"]')[0].dxf.text = "removed"
    elif damage == "provenance":
        doc.modelspace()[0].discard_xdata(APP_ID)
    elif damage == "geometry":
        doc.modelspace().query("LWPOLYLINE")[0].set_points([(0, 0), (1, 0), (1, 1)])
    else:
        doc.modelspace().query('TEXT[layer=="A-ROOM"]')[0].dxf.text = "wrong"
    with pytest.raises(ValidationError):
        validate_dxf(doc, data)
