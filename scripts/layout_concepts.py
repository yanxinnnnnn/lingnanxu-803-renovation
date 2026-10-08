"""Issue #9 concept contract: room-bound labels, never new geometry or fit."""

from collections import Counter
from pathlib import Path
import re
import textwrap

import ezdxf
from ezdxf.enums import TextEntityAlignment
from ezdxf.lldxf.tagwriter import TagCollector

from floorplan import ROOT, APP_ID as B0_APP_ID, load_floorplan, require, nonempty, mapping, transform
from layout_input import BASE_DXF, load_layout_input
from provisional_measurements import read_yaml
from validate_floorplan import validate_dxf

DEFAULT_DATA = ROOT / "data/layout_concepts_v0.1.yaml"
PROGRAM_DATA = ROOT / "data/space_program_v0.1.yaml"
WARNING = "PROVISIONAL CONCEPT PLAN — B0 ESTIMATED GEOMETRY — VERIFY ON SITE BEFORE B1/L1"
APP_ID = "LN803_CONCEPT"
LAYERS = {"A-CONCEPT-ROLE": 3, "A-CONCEPT-ZONE": 5, "A-CONCEPT-PET": 6, "A-CONCEPT-NOTE": 1}
BEDROOMS = {"master_bedroom", "bedroom_south", "bedroom_north_1", "bedroom_north_2"}
SOURCE_INPUTS = ["data/b0_floorplan.yaml", "data/b0_layout_input.yaml", "data/space_program_v0.1.yaml",
                 "docs/SPACE_PROGRAM_v0.1.md", "measurements/onsite-survey-803.md"]
PRESERVED_FILES = tuple(ROOT / p for p in (
    "data/b0_floorplan.yaml", "data/b0_provisional_measurements.yaml", "data/b0_layout_input.yaml",
    "data/space_program_v0.1.yaml", "docs/SPACE_PROGRAM_v0.1.md", "docs/B0.3_LAYOUT_INPUT.md",
    "references/source-manifest.yaml", "measurements/onsite-survey-803.md",
    "cad/LN803_BASE_B0_v0.1_20261004.dxf", "artifacts/LN803_BASE_B0_v0.1_20261004_preview.png",
    "cad/LN803_REF_B0.2_provisional_20261004.dxf", "artifacts/LN803_REF_B0.2_provisional_20261004_preview.png",
    "cad/LN803_LAYOUT_INPUT_B0.3_provisional_20261004.dxf", "artifacts/LN803_LAYOUT_INPUT_B0.3_provisional_20261004_preview.png",
))


def fields(record, expected, path):
    mapping(record, path)
    require(set(record) == set(expected), f"{path}: incorrect fields; no dimensions, rescaling or wall geometry allowed")


def text(value, path):
    nonempty(value, path)
    require(not re.search(r"(?<![\w.])\d+(?:\.\d+)?", value),
            f"{path}: numeric targets belong only in source-checked requirement labels")


def text_list(value, path):
    require(isinstance(value, list) and bool(value), f"{path}: non-empty list required")
    for item in value:
        text(item, path)


def requirement_labels(program):
    """Render numeric requirements from the baseline, not from annotation coordinates."""
    desk = program["work_from_home"]["desk"]
    monitors = program["work_from_home"]["equipment"]["monitors"]
    parents = next(r for r in program["room_allocations"]["parents_room"]["requirements"] if r["id"] == "parents_bed")
    child = next(r for r in program["room_allocations"]["child_room"]["requirements"] if r["id"] == "child_furniture")
    tv = program["living_media"]["tv"]
    return {
        "desk": f"REQUIREMENT ONLY: preferred desk {desk['width_mm']['min']}–{desk['width_mm']['max']} mm; depth {' / '.join(map(str, desk['depth_options_mm']))} mm",
        "desk_fallback": f"REQUIREMENT ONLY: constrained desk fallback {desk['constrained_fallback']['width_mm']} mm",
        "monitors": f"REQUIREMENT ONLY: {monitors['count']} monitors, {monitors['diagonal_in']} inch each",
        "parents_bed": f"REQUIREMENT ONLY: parents bed width {parents['bed_width_m']} m",
        "child_bed": f"REQUIREMENT ONLY: child bed width {child['bed_width_m']['min']}–{child['bed_width_m']['max']} m",
        "tv": f"REQUIREMENT ONLY: TV target {tv['baseline_diagonal_in']} inch; future ~{tv['future_compatibility_diagonal_in_approx']} inch conditional",
    }


def validate_concepts(data):
    fields(data, {"version", "artifact_date", "status", "baseline", "construction_ready", "b1_status", "l1_status",
                  "selection_authority", "source_issue", "source_inputs", "warning", "linear_dimensions", "representation",
                  "zone_bindings", "shared_program", "requirement_labels", "concepts"}, "concept data")
    for key, expected in {"version": "0.1", "artifact_date": "20261008", "status": "provisional_concepts", "baseline": "B0",
                          "construction_ready": False, "b1_status": "pending", "l1_status": "pending_not_selected",
                          "selection_authority": "Product Owner", "warning": WARNING, "linear_dimensions": [],
                          "representation": "labels_only_no_furniture_fit", "source_inputs": SOURCE_INPUTS,
                          "source_issue": "https://github.com/yanxinnnnnn/lingnanxu-803-renovation/issues/9"}.items():
        require(data.get(key) == expected, f"{key}: must remain {expected}")
    trace, layout, program = load_floorplan(), load_layout_input(), read_yaml(PROGRAM_DATA)
    rooms = {r["id"] for r in trace["rooms"]}
    bindings = data["zone_bindings"]
    fields(bindings, {"master_suite", "parents", "family_flex", "entrance_right"}, "zone bindings")
    require(bindings["master_suite"] == ["master_bedroom", "walk_in_closet", "master_bathroom"], "Preserve master suite")
    require(bindings["parents"] == "bedroom_south" and bindings["family_flex"] == "flex_tea_room", "Preserve B0.3 role bindings")
    entry = bindings["entrance_right"]
    fields(entry, {"candidate_room_id", "status", "note"}, "entrance binding")
    require(entry["candidate_room_id"] == "entry_garden" and entry["status"] == "provisional_anchor_only", "Entrance correspondence is unverified")
    text(entry["note"], "entrance binding.note")
    mapped = {m["planning_zone_id"] for m in layout["zone_mappings"] if m["mapping_status"] == "mapped"}
    require({"bedroom_south", "flex_tea_room", "living", "dining", "kitchen"} <= mapped, "Missing B0.3 bindings")
    shared = data["shared_program"]
    fields(shared, {"bedroom_count", "bathroom_room_ids", "master_occupants", "parents_residency", "child_strategy",
                    "guest_strategy", "kitchen_strategy", "dining_strategy", "living_strategy", "laundry_strategy", "storage_strategy",
                    "bathtub_status", "bathtub_condition", "permanent_cat_wall", "gym_required", "enclosure_approved", "pet_safety"}, "shared program")
    require(shared["bedroom_count"] == program["household"]["bedroom_retention"]["count"] == 4, "Four bedrooms required")
    require(shared["bathroom_room_ids"] == ["bathroom_1", "bathroom_2", "master_bathroom"] and
            len(shared["bathroom_room_ids"]) == program["bathrooms"]["retained_count"] == 3, "Three bathrooms retained")
    require(shared["master_occupants"] == program["room_allocations"]["master_suite"]["occupants"], "Master occupants must remain homeowner and spouse")
    require(shared["parents_residency"] == "long_term", "Parents are long-term residents")
    require(shared["bathtub_status"] == program["bathrooms"]["master_bathtub"]["status"] == "optional", "Bathtub remains optional")
    require(all(shared[k] is False for k in ("permanent_cat_wall", "gym_required", "enclosure_approved")), "No forced cat wall, gym or enclosure")
    for key in ("child_strategy", "guest_strategy", "kitchen_strategy", "dining_strategy", "living_strategy", "laundry_strategy", "storage_strategy", "bathtub_condition", "pet_safety"):
        text(shared[key], key)
    require(data["requirement_labels"] == requirement_labels(program), "Numeric requirement labels must match Space Program only")
    concepts = data["concepts"]
    require(isinstance(concepts, list) and [c.get("id") for c in concepts] == ["A", "B", "C"], "Exactly three concepts A/B/C required")
    hypotheses = set()
    for concept in concepts:
        fields(concept, {"id", "name", "title", "intervention_level", "room_roles", "child_guest_status", "master_wfh", "parents_strategy",
                         "living_dining_strategy", "family_flex", "entrance_right", "pet_infrastructure", "zones", "assumptions", "strengths", "tradeoffs", "b1_blockers"}, "concept")
        cid = concept["id"]
        for key in ("name", "title", "parents_strategy", "living_dining_strategy"):
            text(concept[key], key)
        roles = concept["room_roles"]
        fields(roles, BEDROOMS, "room_roles")
        require(roles["master_bedroom"] == "master" and roles["bedroom_south"] == "parents", "Master/parents roles must remain")
        require(Counter(roles.values()) == Counter(["master", "parents", "child", "guest"]), "Four distinct bedroom roles required")
        require(concept["child_guest_status"] == "provisional_hypothesis", "Child/guest assignment stays provisional")
        hypotheses.add((roles["bedroom_north_1"], roles["bedroom_north_2"]))
        wfh = concept["master_wfh"]
        fields(wfh, {"first_attempt", "fallback", "fallback_condition", "strategy"}, "master_wfh")
        strategy = program["work_from_home"]["location_strategy"]
        require(all(wfh[k] == strategy[k] for k in ("first_attempt", "fallback", "fallback_condition")), "Master-suite-first WFH with explicit fallback condition required")
        text(wfh["strategy"], "WFH strategy")
        flex = concept["family_flex"]
        fields(flex, {"mode", "primary_use", "strategy", "opening_change", "functional_wall"}, "family_flex")
        expected = {
            "A": ("low", "glazed_quiet_family", "family_reading_drawing_quiet_activity", "none_assumed", "none_assumed", "neutral_flex_pet_candidate"),
            "B": ("medium_conditional", "semi_open_public_extension", "child_family_activity_toy_reset", "wide_living_facing_candidate", "solid_functional_wall_candidate", "pet_support_compact_activity_candidate"),
            "C": ("medium_conditional", "reversible_family_backup_office", "family_quiet_activity", "closable_connection_candidate", "reversible_storage_work_candidate", "deliberate_pet_activity_candidate"),
        }[cid]
        text(flex["strategy"], "Family Flex strategy")
        entrance = concept["entrance_right"]
        fields(entrance, {"mode", "status", "enclosure_approved", "condition", "strategy", "unsuitable_fallback"}, "entrance_right")
        actual = (concept["intervention_level"], flex["mode"], flex["primary_use"], flex["opening_change"], flex["functional_wall"], entrance["mode"])
        require(actual == expected, "A/B/C must retain differentiated intervention and family/entry strategies")
        require(entrance["status"] == "provisional_condition_dependent" and entrance["enclosure_approved"] is False, "Entrance use is conditional; enclosure unapproved")
        for key in ("condition", "strategy", "unsuitable_fallback"):
            text(entrance[key], key)
        pets = concept["pet_infrastructure"]
        fields(pets, {"cat_count", "status", "strategy", "indoor_fallback", "candidates"}, "pets")
        require(pets["cat_count"] == program["pets"]["cat_count"] == program["household"]["cat_count"] == 5, "Five-cat infrastructure required")
        require(pets["status"] == "candidate_locations_only", "Pet locations are candidates")
        text(pets["strategy"], "pet strategy")
        text(pets["indoor_fallback"], "indoor pet fallback")
        require(isinstance(pets["candidates"], list) and bool(pets["candidates"]), "Pet candidates required")
        ids, uses, indoor_litter = set(), Counter(), set()
        for candidate in pets["candidates"]:
            fields(candidate, {"id", "room_id", "use", "label", "condition"}, "pet candidate")
            require(candidate["id"] not in ids and candidate["room_id"] in rooms, "Unique pet IDs and known rooms required")
            ids.add(candidate["id"])
            require(candidate["use"] in {"litter_primary", "litter_backup", "water", "feeding", "scratch_rest_perch"}, "Unknown pet function")
            uses[candidate["use"]] += 1
            if candidate["use"].startswith("litter") and candidate["room_id"] != "entry_garden":
                indoor_litter.add(candidate["room_id"])
            text(candidate["label"], "pet label")
            text(candidate["condition"], "pet condition")
        require(all(uses[u] for u in ("litter_primary", "litter_backup", "water", "feeding", "scratch_rest_perch")), "All pet support functions and backup litter required")
        require(len(indoor_litter) >= 2, "Independent indoor litter alternatives required")
        zones = mapping(concept["zones"], "zones")
        require(set(zones) == {"master_bedroom", "walk_in_closet", "bedroom_south", "bedroom_north_1", "bedroom_north_2", "flex_tea_room", "living", "dining", "kitchen", "entry_garden", "service_balcony"}, "Required room-bound conceptual zones missing or unknown")
        for room, labels in zones.items():
            text_list(labels, room)
        for key in ("assumptions", "strengths", "tradeoffs", "b1_blockers"):
            text_list(concept[key], key)
    require(hypotheses == {("child", "guest"), ("guest", "child")}, "Opposite child/guest hypotheses required")
    return data


def load_concepts(path=DEFAULT_DATA):
    return validate_concepts(read_yaml(path))


def output_paths(cid, directory=ROOT):
    stem = f"LN803_LAYOUT_{cid}_B0_v0.1_20261008"
    return Path(directory) / "cad" / f"{stem}.dxf", Path(directory) / "artifacts" / f"{stem}_preview.png"


def annotations(data, concept):
    """Text only. Positions are typographic fractions of unchanged B0 bounds."""
    trace = load_floorplan()
    polygons = {r["id"]: [transform(p, trace["trace_coordinate_system"]) for p in r["polygon_px"]] for r in trace["rooms"]}
    specs = []
    def add(key, room, label, layer, fraction, kind="plan"):
        points = polygons[room]
        left, right = min(x for x, _ in points), max(x for x, _ in points)
        bottom, top = min(y for _, y in points), max(y for _, y in points)
        specs.append({"id": key, "room_id": room, "text": label, "layer": layer, "kind": kind,
                      "position": ((left + right) / 2, bottom + (top - bottom) * fraction)})
    for room, role in concept["room_roles"].items():
        add("role_" + room, room, role.upper() + (" ?" if role in ("child", "guest") else ""), "A-CONCEPT-ROLE", 0.80)
    for room in data["shared_program"]["bathroom_room_ids"]:
        add("retain_" + room, room, "BATH RETAINED", "A-CONCEPT-ROLE", 0.75)
    for room, labels in concept["zones"].items():
        for index, label in enumerate(labels):
            add(f"zone_{room}_{index}", room, label, "A-CONCEPT-ZONE", 0.61 - index * 0.18)
    by_room = {}
    for pet in concept["pet_infrastructure"]["candidates"]:
        by_room.setdefault(pet["room_id"], []).append(pet)
    for room, pets in by_room.items():
        if room == "entry_garden" and len(pets) > 1:
            # Small unverified entry anchor: one use label avoids implying that
            # multiple pet stations fit. Individual candidates remain in notes.
            add("pet_group_entry", room, "PRIMARY LITTER / PET REST CONDITIONAL", "A-CONCEPT-PET", 0.20)
            continue
        for index, pet in enumerate(pets):
            fraction = 0.06 if len(concept["zones"].get(room, [])) >= 3 else 0.20 - index * 0.12
            add("pet_" + pet["id"], room, pet["label"], "A-CONCEPT-PET", fraction)
    rows = [WARNING, f"LAYOUT {concept['id']} | {concept['title']}",
            f"Intervention: {concept['intervention_level']} | no geometry changes drawn",
            "B0 only / B1 pending / L1 pending; Product Owner selects or combines",
            "Labels indicate uses, never measured fit or construction locations.",
            "ROOM / WORK STRATEGY", concept["master_wfh"]["strategy"],
            "WFH fallback only if: " + concept["master_wfh"]["fallback_condition"],
            "Parents: " + concept["parents_strategy"],
            "Child/guest provisional: wait for B1 light, clear spans and furniture fit.",
            "FAMILY / PUBLIC STRATEGY", concept["family_flex"]["strategy"], concept["living_dining_strategy"],
            "ENTRANCE / PET STRATEGY", concept["entrance_right"]["strategy"], concept["entrance_right"]["condition"],
            "Entry-garden label is an unverified entrance-right anchor, not an enclosure boundary.",
            f"{concept['pet_infrastructure']['cat_count']} cats | " + concept["pet_infrastructure"]["strategy"],
            concept["pet_infrastructure"]["indoor_fallback"],
            *[p["label"] + " | " + p["room_id"] + " | " + p["condition"] for p in concept["pet_infrastructure"]["candidates"]],
            "REQUIREMENTS, NOT FIT", *data["requirement_labels"].values(),
            "Bathtub optional; no forced gym/cat wall; no enclosure approved.",
            "B0.3: flex/public connection, corridor/bath overlaps and suite scope unresolved.",
            "ASSUMPTIONS", *concept["assumptions"], "STRENGTHS", *concept["strengths"],
            "TRADEOFFS", *concept["tradeoffs"], "B1 BLOCKERS", *concept["b1_blockers"]]
    all_points = [p for poly in polygons.values() for p in poly]
    left, right, top = min(x for x, _ in all_points), max(x for x, _ in all_points), max(y for _, y in all_points)
    # Wrap long explanatory CAD text into two columns next to the intact trace.
    # These offsets and text heights are typography, never construction dimensions.
    specs.append({"id": "warning", "room_id": "", "text": WARNING, "layer": "A-CONCEPT-NOTE",
                  "kind": "panel", "position": (left, top + 2900)})
    wrapped = [line for row in rows[1:] for line in textwrap.wrap(row, width=105, break_long_words=False)]
    for index, label in enumerate(wrapped):
        specs.append({"id": f"note_{index}", "room_id": "", "text": label, "layer": "A-CONCEPT-NOTE",
                      "kind": "panel", "position": (right + 1600 + (index // 50) * 16000, top + 2200 - (index % 50) * 300)})
    return specs


def tags(spec, cid):
    return [(1000, value) for value in ("B0", "provisional_concepts", cid, spec["id"], spec["room_id"], spec["kind"], "issue-9")]


def validate_overlay(doc, data, concept):
    validate_concepts(data)
    base = validate_dxf(ezdxf.readfile(BASE_DXF), load_floorplan())
    require(doc.units == base.units, "Concept DXF units changed")
    require(doc.dxfversion == base.dxfversion, "DXF version changed")
    for name, color in LAYERS.items():
        require(name in doc.layers, f"Missing concept layer {name}")
        layer = doc.layers.get(name)
        require(layer.dxf.color == color and not layer.is_frozen(), "Concept layers must be visible with expected style")
    original = [TagCollector.dxftags(e, base.dxfversion) for e in base.modelspace()]
    preserved = [TagCollector.dxftags(e, doc.dxfversion) for e in doc.modelspace() if e.dxf.layer not in LAYERS]
    require(preserved == original, "Canonical B0 entities changed or new wall/dimension geometry introduced")
    entities = [e for e in doc.modelspace() if e.dxf.layer in LAYERS]
    specs = annotations(data, concept)
    require(len(entities) == len(specs), "Concept annotation count differs")
    for entity, spec in zip(entities, specs):
        require(entity.dxftype() == "TEXT", "Only conceptual TEXT allowed; no furniture rectangles or dimensions")
        require(entity.dxf.text == spec["text"] and entity.dxf.layer == spec["layer"], "Concept text/layer differs")
        require(entity.dxf.height == (160 if spec["kind"] == "plan" else 220) and not entity.dxf.invisible, "Concept text must be visible")
        require(entity.has_xdata(APP_ID) and list(entity.get_xdata(APP_ID)) == tags(spec, concept["id"]), "Concept provenance differs")
        require(not entity.has_xdata(B0_APP_ID), "Concept cannot become baseline geometry")
        alignment, point, _ = entity.get_placement()
        expected = TextEntityAlignment.MIDDLE_CENTER if spec["kind"] == "plan" else TextEntityAlignment.LEFT
        require(alignment == expected and tuple(point)[:2] == spec["position"], "Concept label placement changed")
    # Audit can repair/delete malformed entities. Compare first so repair cannot
    # silently discard an unauthorized dimension or other injected geometry.
    require(not doc.audit().has_errors, "Concept DXF audit failed")
    return doc
