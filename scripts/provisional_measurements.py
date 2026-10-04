"""B0.2 reference records and annotation validation, separate from B0 trace data."""

from datetime import datetime
from pathlib import Path

import ezdxf
from ezdxf.lldxf.tagwriter import TagCollector
import yaml

from floorplan import (
    APP_ID as B0_APP_ID, DEFAULT_DXF as BASE_DXF, ROOT, UniqueKeyLoader,
    ValidationError, load_floorplan, mapping, nonempty, number, require,
)
from validate_floorplan import validate_dxf

DEFAULT_DATA = ROOT / "data/b0_provisional_measurements.yaml"
DEFAULT_MANIFEST = ROOT / "references/source-manifest.yaml"
DEFAULT_DXF = ROOT / "cad/LN803_REF_B0.2_provisional_20261004.dxf"
DEFAULT_PREVIEW = ROOT / "artifacts/LN803_REF_B0.2_provisional_20261004_preview.png"
SOURCE_ID = "measurement-ref-001"
PROVENANCE = "third_party_reference"
STATUS = "pending_onsite_verification"
LAYER = "A-REF-PROVISIONAL"
APP_ID = "LN803_REF_PROVISIONAL"
WARNING = "THIRD-PARTY PROVISIONAL REFERENCE - VERIFY ON SITE BEFORE B1"
TOTALS = {
    "measured_internal_area_sqm": ("sqm", "reported_measured_internal_area_sqm", "Reported internal / usable area"),
    "building_area_sqm": ("sqm", "reported_building_area_sqm", "Reported building area"),
    "reported_space_efficiency_percent": ("percent", "reported_space_efficiency_percent", "Reported space efficiency"),
}


def read_yaml(path):
    try:
        with Path(path).open(encoding="utf-8") as stream:
            return yaml.load(stream, Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ValidationError(f"Invalid YAML in {path}: {exc}") from exc


def validate_measurements(data, manifest):
    mapping(data, "provisional measurements")
    require(data.get("baseline") == "B0", "Reference baseline must remain B0")
    require(data.get("provenance") == PROVENANCE, "Reference provenance must be third_party_reference")
    require(data.get("confidence") == "provisional", "Reference confidence must be provisional")
    require(data.get("subject_unit_match") is False, "Reference is not the subject unit 803")
    require(data.get("construction_ready") is False, "Provisional reference is not for construction")
    require(data.get("source_id") == SOURCE_ID, "Expected registered source measurement-ref-001")
    require(data.get("warning") == WARNING, "Provisional warning must be preserved")
    for key in ("version", "artifact_date", "value_reference"):
        nonempty(data.get(key), key)
    try:
        datetime.strptime(data["artifact_date"], "%Y%m%d")
    except ValueError as exc:
        raise ValidationError("artifact_date must be YYYYMMDD") from exc
    require(isinstance(data.get("notes"), list) and bool(data["notes"]), "Reference notes are required")
    for note in data["notes"]:
        nonempty(note, "notes")

    mapping(manifest, "source manifest")
    sources = manifest.get("sources")
    require(isinstance(sources, list), "Manifest sources must be a list")
    ids = []
    for source in sources:
        mapping(source, "manifest source")
        nonempty(source.get("id"), "manifest source.id")
        ids.append(source["id"])
    require(len(ids) == len(set(ids)), "Manifest contains duplicate source IDs")
    matches = [s for s in sources if s["id"] == SOURCE_ID]
    require(len(matches) == 1, "Provisional source is not registered in manifest")
    source = matches[0]
    for key, value in (("provenance", PROVENANCE), ("confidence", "provisional"),
                       ("baseline", "B0"), ("type", "third_party_measured_reference")):
        require(source.get(key) == value, f"Manifest source.{key} must be {value}")
    nonempty(source.get("sha256"), "manifest source.sha256")
    storage = mapping(source.get("storage"), "manifest source.storage")
    nonempty(storage.get("provider"), "manifest source.storage.provider")
    nonempty(storage.get("path"), "manifest source.storage.path")

    def record(value, path, unit):
        mapping(value, path)
        require(value.get("source_id") == SOURCE_ID, f"{path}: unknown provisional source ID")
        require(value.get("provenance") == PROVENANCE, f"{path}: provenance must be third_party_reference")
        require(value.get("confidence") == "provisional", f"{path}: confidence must be provisional")
        require(value.get("verification_status") == STATUS, f"{path}: verification_status must be {STATUS}")
        require(value.get("unit") == unit, f"{path}: unit must be {unit}")
        number(value.get("value"), f"{path}.value")
        require(value["value"] > 0, f"{path}: reported value must be positive")
        nonempty(value.get("source_label"), f"{path}.source_label")

    totals = mapping(data.get("reported_totals"), "reported_totals")
    require(set(totals) == set(TOTALS), "Expected the three reported totals only")
    observed = mapping(source.get("observed_text"), "manifest source.observed_text")
    for key, (unit, manifest_key, _) in TOTALS.items():
        record(totals[key], f"reported_totals.{key}", unit)
        number(observed.get(manifest_key), f"manifest.{manifest_key}")
        require(totals[key]["value"] == observed[manifest_key], f"{key} differs from registered source report")

    record_ids = set(TOTALS)
    for collection, unit in (("areas", "sqm"), ("linear_dimensions", "mm")):
        items = data.get(collection)
        require(isinstance(items, list), f"{collection} must be a list")
        for index, item in enumerate(items):
            path = f"{collection}[{index}]"
            record(item, path, unit)
            nonempty(item.get("id"), f"{path}.id")
            require(item["id"] not in record_ids, f"{path}: duplicate measurement ID")
            record_ids.add(item["id"])
            # This source transcription has no defensible room associations yet.
            require(item.get("mapping_status") == "unresolved", f"{path}: source room mapping must remain unresolved")
            require("room_id" in item and item["room_id"] is None, f"{path}: unresolved item must have null room_id")
            if collection == "linear_dimensions":
                nonempty(item.get("source_location"), f"{path}.source_location")
    require(bool(data["areas"]), "At least one readable provisional area is required")
    return data


def load_measurements(data_path=DEFAULT_DATA, manifest_path=DEFAULT_MANIFEST):
    return validate_measurements(read_yaml(data_path), read_yaml(manifest_path))


def annotation_lines(data):
    """One ordered schedule for DXF and PNG; none of these rows locates a room."""
    rows = [
        ("warning", WARNING),
        ("source", f"Source: {data['source_id']} | B0.{data['version'].split('.')[-1]} | {data['artifact_date']}"),
        ("scope", "Similar remote showflat; NOT building 6 / unit 803"),
        ("status", "Provisional / pending onsite verification"),
        ("construction", "NOT FOR CONSTRUCTION / subject_unit_match: false"),
        ("totals_header", "REPORTED TOTALS OF REFERENCE UNIT"),
    ]
    for key, (_, _, label) in TOTALS.items():
        item = data["reported_totals"][key]
        rows.append((key, f"{label}: {item['value']} {item['unit']}"))
    rows.append(("areas_header", "UNMAPPED SOURCE AREAS (sqm)"))
    for item in data["areas"]:
        rows.append((item["id"], f"{item['id']}: {item['value']} sqm | unresolved"))
    rows.extend([
        ("mapping_note", "List labels are not room IDs or drawing locations."),
        ("sum_note", "Do not sum zones or reconcile reference totals to 803."),
        ("dimensions_header", "LINEAR DIMENSIONS (mm)"),
    ])
    if data["linear_dimensions"]:
        for item in data["linear_dimensions"]:
            rows.append((item["id"], f"{item['id']}: {item['value']} mm | unresolved"))
    else:
        rows.append(("no_dimensions", "None transcribed; survey missing values on site."))
    rows.append(("b1_note", "B1 requires new evidence from 803; keep this source."))
    return rows


def reference_tags(data, record_id):
    return [(1000, value) for value in (
        "B0", PROVENANCE, record_id, data["source_id"], "provisional", STATUS, "subject_unit_match:false",
    )]


def validate_overlay(doc, data, base_path=BASE_DXF, manifest_path=DEFAULT_MANIFEST):
    validate_measurements(data, read_yaml(manifest_path))
    base = ezdxf.readfile(base_path)
    validate_dxf(base, load_floorplan())
    require(not doc.audit().has_errors, "Provisional DXF audit failed")
    require(doc.units == base.units, "Overlay changed B0 storage units")
    require(LAYER in doc.layers, "Missing A-REF-PROVISIONAL layer")
    layer = doc.layers.get(LAYER)
    require(layer.dxf.color > 0 and not layer.is_frozen(), "Provisional annotation layer must be visible")
    original = [TagCollector.dxftags(e, base.dxfversion) for e in base.modelspace()]
    preserved = [TagCollector.dxftags(e, doc.dxfversion) for e in doc.modelspace() if e.dxf.layer != LAYER]
    require(preserved == original, "Overlay changed the canonical B0 entities")
    annotations = [e for e in doc.modelspace() if e.dxf.layer == LAYER]
    rows = annotation_lines(data)
    require(len(annotations) == len(rows), "Overlay annotation count differs from reference data")
    for entity, (record_id, text) in zip(annotations, rows):
        require(entity.dxftype() == "TEXT" and entity.dxf.text == text, f"Overlay reference text differs: {record_id}")
        require(entity.has_xdata(APP_ID), "Overlay entity is missing provisional provenance")
        require(not entity.has_xdata(B0_APP_ID), "Provisional entity must not carry B0 estimated-geometry provenance")
        require(list(entity.get_xdata(APP_ID)) == reference_tags(data, record_id), f"Invalid provisional XDATA: {record_id}")
        require(entity.dxf.height > 0 and not entity.dxf.invisible, "Provisional text must be visible")
    return doc
