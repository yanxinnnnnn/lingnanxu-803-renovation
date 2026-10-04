"""Issue #5's explicit semantic contract; no calibration or dimension inference."""

from datetime import datetime

import ezdxf
from ezdxf.enums import TextEntityAlignment
from ezdxf.lldxf.tagwriter import TagCollector

from floorplan import (
    APP_ID as B0_APP_ID, DEFAULT_DATA as BASE_DATA, DEFAULT_DXF as BASE_DXF,
    DEFAULT_PREVIEW as BASE_PREVIEW, ROOT, ValidationError, load_floorplan, mapping, nonempty, number, require, transform,
)
from provisional_measurements import (
    DEFAULT_DATA as REF_DATA, DEFAULT_DXF as REF_DXF, DEFAULT_PREVIEW as REF_PREVIEW,
    DEFAULT_MANIFEST, PROVENANCE, SOURCE_ID, STATUS, load_measurements, read_yaml,
)
from validate_floorplan import validate_dxf

DEFAULT_DATA = ROOT / "data/b0_layout_input.yaml"
DEFAULT_DXF = ROOT / "cad/LN803_LAYOUT_INPUT_B0.3_provisional_20261004.dxf"
DEFAULT_PREVIEW = ROOT / "artifacts/LN803_LAYOUT_INPUT_B0.3_provisional_20261004_preview.png"
AUTHORITY = "https://github.com/yanxinnnnnn/lingnanxu-803-renovation/issues/5"
WARNING = "PROVISIONAL LAYOUT INPUT - VERIFY AGAINST 803 ONSITE MEASUREMENTS BEFORE B1"
LAYER = "A-LAYOUT-INPUT"
APP_ID = "LN803_LAYOUT_INPUT"
PRESERVED_FILES = (BASE_DATA, BASE_DXF, BASE_PREVIEW, REF_DATA, REF_DXF, REF_PREVIEW)
# Area -> semantic association explicitly authorized by Issue #5, not derived from B0.
AUTHORIZED = {
    "ref_area_01": (5.143, None, [], "unresolved", "low"),
    "ref_area_02": (2.202, None, [], "unresolved", "low"),
    "ref_area_03": (2.515, None, [], "unresolved", "low"),
    "ref_area_04": (7.743, "corridor_entry", ["corridor_entry"], "candidate", "medium"),
    "ref_area_05": (7.029, "flex_tea_room", ["flex_tea_room"], "mapped", "high"),
    "ref_area_06": (24.345, "master_suite_reference", ["master_bedroom", "walk_in_closet", "master_bathroom"], "candidate", "medium"),
    "ref_area_07": (13.398, "bedroom_south", ["bedroom_south"], "mapped", "high"),
    "ref_area_08": (10.419, "kitchen", ["kitchen"], "mapped", "high"),
    "ref_area_09": (11.326, "dining", ["dining"], "mapped", "high"),
    "ref_area_10": (15.139, "living", ["living"], "mapped", "high"),
}
COMMON = {"source_id", "provenance", "confidence", "verification_status"}
CATEGORY_COLORS = {"mapped:high": 3, "candidate:medium": 30, "unresolved:low": 6, "note": 7}


def fields(record, allowed, path):
    mapping(record, path)
    require(set(record) <= allowed, f"{path}: unsupported fields (no linear dimensions or new geometry)")


def provenance(record, path):
    for key, expected in (("source_id", SOURCE_ID), ("provenance", PROVENANCE),
                          ("confidence", "provisional"), ("verification_status", STATUS)):
        require(record.get(key) == expected, f"{path}.{key} must be {expected}")


def validate_layout_data(data):
    fields(data, COMMON | {"baseline", "status", "construction_ready", "subject_unit_match", "artifact_date",
                          "base_geometry", "reference_measurements", "mapping_authority", "warning",
                          "zone_mappings", "topology_findings", "layout_constraints", "linear_dimensions"}, "layout input")
    provenance(data, "layout input")
    for key, expected in (("baseline", "B0.3"), ("status", "provisional_layout_input"),
                          ("mapping_authority", AUTHORITY), ("warning", WARNING),
                          ("base_geometry", "data/b0_floorplan.yaml"),
                          ("reference_measurements", "data/b0_provisional_measurements.yaml")):
        require(data.get(key) == expected, f"{key} must be {expected}")
    require(data.get("construction_ready") is False, "Layout input is not for construction")
    require(data.get("subject_unit_match") is False, "Reference is not subject unit 803")
    require(data.get("linear_dimensions") == [], "No linear dimension may be created")
    nonempty(data.get("artifact_date"), "artifact_date")
    try:
        datetime.strptime(data["artifact_date"], "%Y%m%d")
    except ValueError as exc:
        raise ValidationError("artifact_date must be YYYYMMDD") from exc
    trace = load_floorplan()
    reference = load_measurements()
    require(reference["linear_dimensions"] == [], "This baseline has no human-confirmed linear dimensions")
    ref_areas = {item["id"]: item["value"] for item in reference["areas"]}
    rooms = {room["id"] for room in trace["rooms"]}

    mappings = data.get("zone_mappings")
    require(isinstance(mappings, list), "zone_mappings must be a list")
    by_zone = {}
    for record in mappings:
        fields(record, COMMON | {"reference_zone_id", "planning_zone_id", "candidate_room_ids", "mapping_status",
                                 "mapping_confidence", "area_sqm", "rationale"}, "zone mapping")
        provenance(record, "zone mapping")
        zone_id = record.get("reference_zone_id")
        nonempty(zone_id, "reference_zone_id")
        require(zone_id in AUTHORIZED and zone_id not in by_zone, "Unknown or duplicate reference zone ID")
        number(record.get("area_sqm"), "area_sqm")
        expected = AUTHORIZED[zone_id]
        actual = (record["area_sqm"], record.get("planning_zone_id"), record.get("candidate_room_ids"),
                  record.get("mapping_status"), record.get("mapping_confidence"))
        require(actual == expected, f"{zone_id}: mapping must match Issue #5 exactly")
        require(record["area_sqm"] == ref_areas.get(zone_id), f"{zone_id}: area differs from B0.2 reference")
        nonempty(record.get("rationale"), f"{zone_id}.rationale")
        by_zone[zone_id] = record
    require(set(by_zone) == set(ref_areas) == set(AUTHORIZED), "Every B0.2 area must remain represented exactly once")

    def room_list(value, path):
        require(isinstance(value, list) and all(isinstance(room, str) and room in rooms for room in value),
                f"{path}: expected known B0 room IDs")
        require(len(value) == len(set(value)), f"{path}: duplicate room IDs")

    findings = data.get("topology_findings")
    require(isinstance(findings, list), "topology_findings must be a list")
    by_finding = {}
    for record in findings:
        fields(record, COMMON | {"id", "severity", "affected_room_ids", "description", "onsite_question"}, "topology finding")
        provenance(record, "topology finding")
        nonempty(record.get("id"), "finding.id")
        require(record["id"] not in by_finding, "Duplicate topology finding ID")
        require(record.get("severity") in ("info", "review_required"), "Unknown topology severity")
        room_list(record.get("affected_room_ids"), "affected_room_ids")
        for key in ("description", "onsite_question"):
            nonempty(record.get(key), f"finding.{key}")
        by_finding[record["id"]] = record
    required_findings = {"public_zone_sequence", "separate_flex_zone", "distinct_south_bedroom",
                         "master_suite_boundary", "left_central_unresolved", "preserve_trace_geometry"}
    require(required_findings <= set(by_finding), "Required topology reconciliation finding is missing")

    constraints = data.get("layout_constraints")
    require(isinstance(constraints, list), "layout_constraints must be a list")
    constraint_ids, constrained_zones = set(), set()
    for record in constraints:
        fields(record, COMMON | {"id", "type", "reference_zone_id", "room_ids", "area_sqm",
                                 "topology_finding_id", "description"}, "layout constraint")
        provenance(record, "layout constraint")
        nonempty(record.get("id"), "constraint.id")
        require(record["id"] not in constraint_ids, "Duplicate layout constraint ID")
        constraint_ids.add(record["id"])
        nonempty(record.get("description"), "constraint.description")
        room_list(record.get("room_ids"), "constraint.room_ids")
        kind = record.get("type")
        require(kind in ("area", "adjacency", "unknown"), "Only provisional area/adjacency/unknown constraints are allowed")
        if kind == "area":
            zone_id = record.get("reference_zone_id")
            nonempty(zone_id, "constraint.reference_zone_id")
            require(zone_id in by_zone and by_zone[zone_id]["mapping_status"] == "mapped", "Only high mapped zones may be area constraints")
            require(zone_id not in constrained_zones, "Duplicate area constraint")
            constrained_zones.add(zone_id)
            number(record.get("area_sqm"), "constraint.area_sqm")
            require(record["area_sqm"] == by_zone[zone_id]["area_sqm"] and
                    record["room_ids"] == by_zone[zone_id]["candidate_room_ids"], "Area constraint differs from authorized mapping")
            require("topology_finding_id" not in record, "Area constraint must reference its source area only")
        else:
            require("area_sqm" not in record and "reference_zone_id" not in record, "No area budget may be assigned to an unresolved/candidate topology constraint")
            finding_id = record.get("topology_finding_id")
            nonempty(finding_id, "topology_finding_id")
            require(finding_id in by_finding, "Unknown topology finding")
            require(record["room_ids"] == by_finding[finding_id]["affected_room_ids"], "Constraint room group differs from its topology finding")
            if kind == "adjacency":
                require(finding_id in ("public_zone_sequence", "separate_flex_zone"), "Adjacency must be authorized by Issue #5")
    require(constrained_zones == {key for key, record in by_zone.items() if record["mapping_status"] == "mapped"},
            "All five high mappings require conceptual area constraints")
    return data


def load_layout_input(path=DEFAULT_DATA):
    return validate_layout_data(read_yaml(path))


def annotations(data):
    """TEXT anchors use existing B0 coordinates for placement, never for measurement."""
    trace = load_floorplan()
    polygons = {room["id"]: [transform(p, trace["trace_coordinate_system"]) for p in room["polygon_px"]]
                for room in trace["rooms"]}
    specs = []

    def add(record_id, text, category, role, position):
        specs.append({"id": record_id, "text": text, "category": category, "role": role,
                      "position": position, "color": CATEGORY_COLORS[category]})

    for record in data["zone_mappings"]:
        category = f"{record['mapping_status']}:{record['mapping_confidence']}"
        if record["mapping_status"] == "unresolved":
            continue
        points = [point for room in record["candidate_room_ids"] for point in polygons[room]]
        centre_x = (min(x for x, _ in points) + max(x for x, _ in points)) / 2
        if record["planning_zone_id"] == "master_suite_reference":
            top = max(y for _, y in points)
            add(record["reference_zone_id"], f"SUITE CANDIDATE | {record['area_sqm']} sqm", category, "plan", (centre_x, top + 650))
            add("suite_scope", "bedroom + closet + bathroom? Inclusion unresolved", category, "plan", (centre_x, top + 350))
        else:
            prefix = "REF HIGH" if record["mapping_status"] == "mapped" else "CANDIDATE"
            add(record["reference_zone_id"], f"{prefix} | {record['area_sqm']} sqm", category, "plan",
                (centre_x, min(y for _, y in points) + 425))
    rows = [
        ("warning", WARNING, "note"),
        ("source", "B0.3 | measurement-ref-001 | not subject unit 803", "note"),
        ("provenance", "third_party_reference / provisional", "note"),
        ("status", "Pending onsite verification / NOT FOR CONSTRUCTION", "note"),
        ("meaning", "Mapping confidence is semantic, not field accuracy.", "note"),
        ("high_header", "HIGH: CONCEPTUAL AREA BUDGETS ONLY", "mapped:high"),
    ]
    for record in data["zone_mappings"]:
        if record["mapping_status"] == "mapped":
            rows.append(("panel_" + record["reference_zone_id"], f"{record['planning_zone_id']}: {record['area_sqm']} sqm", "mapped:high"))
    rows.append(("medium_header", "MEDIUM: CANDIDATES / BOUNDARIES UNRESOLVED", "candidate:medium"))
    for record in data["zone_mappings"]:
        if record["mapping_status"] == "candidate":
            rows.append(("panel_" + record["reference_zone_id"], f"{record['planning_zone_id']}: {record['area_sqm']} sqm", "candidate:medium"))
    rows.extend([
        ("suite_note", "24.345 is suite-level, not master_bedroom alone.", "candidate:medium"),
        ("unresolved_header", "UNRESOLVED: NO ROOM ASSIGNMENTS", "unresolved:low"),
    ])
    for record in data["zone_mappings"]:
        if record["mapping_status"] == "unresolved":
            rows.append(("panel_" + record["reference_zone_id"], f"{record['reference_zone_id']}: {record['area_sqm']} sqm", "unresolved:low"))
    rows.extend([
        ("trace_header", "TOPOLOGY QUESTIONS / NO LENGTHS SUPPLIED", "note"),
        ("flex_note", "Flex/public connection is unverified in the trace.", "note"),
        ("overlap_note", "Corridor/bath trace overlaps need onsite evidence.", "note"),
        ("b1_note", "Spans, openings, glazing, clearances: wait for B1.", "note"),
        ("preserve_note", "Keep B0 polygons; no area matching or scaling.", "note"),
    ])
    all_points = [point for polygon in polygons.values() for point in polygon]
    right, top = max(x for x, _ in all_points), max(y for _, y in all_points)
    for index, (record_id, text, category) in enumerate(rows):
        add(record_id, text, category, "panel", (right + 1500, top + 2200 - index * 500))
    return specs


def layout_tags(spec):
    return [(1000, value) for value in ("B0.3", PROVENANCE, spec["id"], SOURCE_ID, "provisional", STATUS,
                                       spec["category"], spec["role"])]


def validate_overlay(doc, data):
    validate_layout_data(data)
    base = ezdxf.readfile(BASE_DXF)
    validate_dxf(base, load_floorplan())
    require(not doc.audit().has_errors, "Layout-input DXF audit failed")
    require(doc.units == base.units, "Layout overlay changed B0 storage units")
    require(LAYER in doc.layers, "Missing A-LAYOUT-INPUT layer")
    layer = doc.layers.get(LAYER)
    require(layer.dxf.color > 0 and not layer.is_frozen(), "Layout-input layer must be visible")
    original = [TagCollector.dxftags(e, base.dxfversion) for e in base.modelspace()]
    preserved = [TagCollector.dxftags(e, doc.dxfversion) for e in doc.modelspace() if e.dxf.layer != LAYER]
    require(preserved == original, "Layout overlay changed canonical B0 entities")
    entities = [entity for entity in doc.modelspace() if entity.dxf.layer == LAYER]
    specs = annotations(data)
    require(len(entities) == len(specs), "Layout annotation count differs from input")
    for entity, spec in zip(entities, specs):
        require(entity.dxftype() == "TEXT" and entity.dxf.text == spec["text"], "Invalid layout annotation text")
        require(entity.dxf.color == spec["color"], "High/medium/unresolved styles must remain distinct")
        require(entity.has_xdata(APP_ID) and list(entity.get_xdata(APP_ID)) == layout_tags(spec), "Invalid layout-input provenance/category")
        require(not entity.has_xdata(B0_APP_ID), "Layout reference must not become estimated B0 geometry")
        require(entity.dxf.height > 0 and not entity.dxf.invisible, "Layout warning/annotations must be visible")
        alignment, point, _ = entity.get_placement()
        expected_alignment = TextEntityAlignment.MIDDLE_CENTER if spec["role"] == "plan" else TextEntityAlignment.LEFT
        require(alignment == expected_alignment and tuple(point)[:2] == spec["position"], "Layout annotation placement differs from input")
    return doc
