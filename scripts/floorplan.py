"""Small B0 data contract shared by the three CLI entry points."""

from datetime import datetime
import math
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data/b0_floorplan.yaml"
DEFAULT_DXF = ROOT / "cad/LN803_BASE_B0_v0.1_20261004.dxf"
DEFAULT_PREVIEW = ROOT / "artifacts/LN803_BASE_B0_v0.1_20261004_preview.png"
WARNING = "B0 ESTIMATED PLAN - NOT FOR CONSTRUCTION"
APP_ID = "LN803_B0"
LAYERS = {
    "A-WALL-EXT": 7,
    "A-WALL-INT": 8,
    "A-GLAZ": 4,
    "A-DOOR": 3,
    "A-FURN": 9,
    "A-ROOM": 2,
    "A-NOTE": 7,
    "A-UNVERIFIED": 1,
}
ROOM_IDS = frozenset({
    "utility", "shoe_storage", "entry_garden", "service_balcony",
    "bedroom_north_1", "bedroom_north_2", "bathroom_1", "corridor_entry",
    "master_bathroom", "walk_in_closet", "master_bedroom", "flex_tea_room",
    "bathroom_2", "bedroom_south", "kitchen", "dining", "living",
})


class ValidationError(ValueError):
    """Invalid structured B0 input or generated artifact."""


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys instead of silently overwriting geometry."""


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str):
            raise ValidationError("YAML mapping keys must be strings")
        if key in result:
            raise ValidationError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def mapping(value, path):
    require(isinstance(value, dict), f"{path}: expected a mapping")
    return value


def nonempty(value, path):
    require(isinstance(value, str) and bool(value.strip()), f"{path}: expected non-empty text")


def number(value, path):
    require(
        type(value) in (int, float) and math.isfinite(value),
        f"{path}: expected a finite numeric coordinate or calibration",
    )


def point(value, path):
    require(isinstance(value, list) and len(value) == 2, f"{path}: expected [x, y]")
    for coordinate in value:
        number(coordinate, path)


def geometry(record, field, path, source_ids):
    mapping(record, path)
    nonempty(record.get("id"), f"{path}.id")
    require(record.get("provenance") == "estimated", f"{path}: B0 geometry must be estimated")
    require(record.get("source") in source_ids, f"{path}: unknown or missing source")
    points = record.get(field)
    require(isinstance(points, list), f"{path}.{field}: expected a list")
    if field == "polygon_px":
        require(len(points) >= 3, f"{path}: polygon needs at least 3 points")
    else:
        require(len(points) == 2, f"{path}: segment needs exactly 2 points")
    for index, value in enumerate(points):
        point(value, f"{path}.{field}[{index}]")
    if field == "polygon_px":
        require(len(set(map(tuple, points))) >= 3, f"{path}: polygon needs 3 distinct points")
        twice_area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1]))
        require(twice_area != 0, f"{path}: polygon has zero area")
    else:
        require(points[0] != points[1], f"{path}: segment has zero length")


def validate_data(data):
    mapping(data, "root")
    metadata = mapping(data.get("metadata"), "metadata")
    for key in ("project_code", "version", "artifact_date", "warning", "note"):
        nonempty(metadata.get(key), f"metadata.{key}")
    require(metadata.get("baseline") == "B0", "metadata.baseline must be B0")
    require(metadata.get("provenance") == "estimated", "metadata.provenance must be estimated")
    require(metadata.get("cad_unit") == "mm", "metadata.cad_unit must be mm (estimated CAD units)")
    require(metadata.get("construction_ready") is False, "B0 construction_ready must be false")
    require(metadata["warning"] == WARNING, "B0 accuracy warning must be preserved")
    try:
        datetime.strptime(metadata["artifact_date"], "%Y%m%d")
    except ValueError as exc:
        raise ValidationError("metadata.artifact_date must be YYYYMMDD") from exc

    calibration = mapping(data.get("trace_coordinate_system"), "trace_coordinate_system")
    require(calibration.get("unit") == "px", "trace unit must be px")
    require(calibration.get("provenance") == "estimated", "trace calibration must be estimated")
    nonempty(calibration.get("note"), "trace_coordinate_system.note")
    point(calibration.get("origin_px"), "trace_coordinate_system.origin_px")
    for key in ("scale_x_mm_per_px", "scale_y_mm_per_px"):
        number(calibration.get(key), key)
        require(calibration[key] > 0, f"{key} must be positive")

    sources = data.get("sources")
    require(isinstance(sources, list) and len(sources) > 0, "sources must be a non-empty list")
    source_ids = set()
    for index, source in enumerate(sources):
        path = f"sources[{index}]"
        mapping(source, path)
        for key in ("id", "type", "reference", "note"):
            nonempty(source.get(key), f"{path}.{key}")
        require(source.get("provenance") == "estimated", f"{path}: B0 source must be estimated")
        require(source["id"] not in source_ids, f"{path}: duplicate source ID")
        source_ids.add(source["id"])

    geometry(data.get("perimeter"), "polygon_px", "perimeter", source_ids)
    ids = {data["perimeter"]["id"]}
    for collection, field in (("rooms", "polygon_px"), ("glazing", "segment_px")):
        records = data.get(collection)
        require(isinstance(records, list) and len(records) > 0, f"{collection} must be a non-empty list")
        for index, record in enumerate(records):
            path = f"{collection}[{index}]"
            geometry(record, field, path, source_ids)
            require(record["id"] not in ids, f"{path}: duplicate geometry ID {record['id']}")
            ids.add(record["id"])
            if collection == "rooms":
                nonempty(record.get("display_name"), f"{path}.display_name")
    room_ids = {room["id"] for room in data["rooms"]}
    require(ROOM_IDS <= room_ids, f"Missing required rooms: {sorted(ROOM_IDS - room_ids)}")
    return data


def load_floorplan(path=DEFAULT_DATA):
    try:
        with Path(path).open(encoding="utf-8") as stream:
            data = yaml.load(stream, Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ValidationError(f"Invalid YAML: {exc}") from exc
    return validate_data(data)


def transform(point_px, calibration):
    """Estimated millimetre-like coordinates, never a measured scale."""
    x, y = point_px
    origin_x, origin_y = calibration["origin_px"]
    return (
        (x - origin_x) * calibration["scale_x_mm_per_px"],
        (origin_y - y) * calibration["scale_y_mm_per_px"],
    )


def tag_entity(entity, record_id, source="issue-1-trace"):
    entity.set_xdata(APP_ID, [(1000, "B0"), (1000, "estimated"), (1000, record_id), (1000, source)])
