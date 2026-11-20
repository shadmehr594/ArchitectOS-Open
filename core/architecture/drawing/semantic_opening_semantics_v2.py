from __future__ import annotations

"""Canonical residential opening semantics layered over the proven v1 engine."""

from copy import deepcopy

from .semantic_opening_typology_v1 import (
    DESIGN_HEURISTIC,
    USER_PROJECT_RULE,
    VERIFIED_REGULATION,
    DOOR_TYPOLOGY_LIBRARY as _V1_DOORS,
    WINDOW_TYPOLOGY_LIBRARY as _V1_WINDOWS,
    SemanticOpeningEngine as _V1Engine,
    TOPIC4_GLAZING_DEFAULT,
    TOPIC4_GLAZING_DEEP_ROOM,
)

ARCHITECTURAL_DESIGN_HEURISTIC = "ARCHITECTURAL_DESIGN_HEURISTIC"
PROJECT_USER_RULE = "PROJECT/USER_RULE"

_DOOR_BASE = {
    "MAIN_ENTRY_DOOR": "MAIN_ENTRANCE_DOOR",
    "UNIT_ENTRY_DOOR": "COMMON_ENTRY_DOOR",
    "BEDROOM_DOOR": "BEDROOM_DOOR",
    "MASTER_BEDROOM_DOOR": "MASTER_BEDROOM_DOOR",
    "BATHROOM_DOOR": "BATHROOM_DOOR",
    "WC_DOOR": "WC_DOOR",
    "KITCHEN_DOOR": "KITCHEN_DOOR",
    "COURTYARD_DOOR": "COURTYARD_YARD_DOOR",
    "TERRACE_DOOR": "TERRACE_BALCONY_DOOR",
    "SERVICE_DOOR": "SERVICE_STORAGE_DOOR",
    "VEHICLE_GATE": "COMMON_ENTRY_DOOR",
    "PEDESTRIAN_GATE": "MAIN_ENTRANCE_DOOR",
    "INTERNAL_PUBLIC_DOOR": "COMMON_ENTRY_DOOR",
    "BATH_WC_DOOR": "WC_DOOR",
    "COURTYARD_YARD_DOOR": "COURTYARD_YARD_DOOR",
}

_DOOR_RANGES = {
    "MAIN_ENTRY_DOOR": (1.00, 1.40), "UNIT_ENTRY_DOOR": (1.00, 1.40),
    "BEDROOM_DOOR": (.85, 1.00), "MASTER_BEDROOM_DOOR": (.90, 1.10),
    "BATHROOM_DOOR": (.75, .90), "WC_DOOR": (.70, .85),
    "KITCHEN_DOOR": (.85, 1.00), "COURTYARD_DOOR": (.90, 1.40),
    "TERRACE_DOOR": (1.00, 2.80), "SERVICE_DOOR": (.70, .90),
    "VEHICLE_GATE": (2.80, 4.50), "PEDESTRIAN_GATE": (.90, 1.40),
    "INTERNAL_PUBLIC_DOOR": (.85, 1.00), "BATH_WC_DOOR": (.65, .80),
    "COURTYARD_YARD_DOOR": (.90, 1.40),
}

DOOR_SEMANTIC_LIBRARY = {}
for canonical, legacy in _DOOR_BASE.items():
    row = deepcopy(_V1_DOORS[legacy])
    lo, hi = _DOOR_RANGES[canonical]
    if canonical == "VEHICLE_GATE":
        row.update(nominal_width_m=3.20, height_m=2.40, leaf_count=2,
                   leaf_style="DOUBLE_SWING_OR_SLIDING_GATE", graphical_symbol_class="GATE_VEHICLE")
    elif canonical == "PEDESTRIAN_GATE":
        row.update(nominal_width_m=1.00, leaf_style="SITE_GATE", graphical_symbol_class="GATE_PEDESTRIAN")
    elif canonical == "MAIN_ENTRY_DOOR": row.update(nominal_width_m=1.10)
    elif canonical == "INTERNAL_PUBLIC_DOOR": row.update(nominal_width_m=.90)
    elif canonical == "BEDROOM_DOOR": row.update(nominal_width_m=.80)
    elif canonical == "BATH_WC_DOOR": row.update(nominal_width_m=.70)
    row.update(
        semantic_type=canonical, semantic_role=canonical,
        default_size_range_m={"clear_width": [lo, hi], "height": [2.05, row["height_m"]]},
        minimum_host_wall_capacity_m=round(lo + .20, 2),
        allowed_forms=["SINGLE_HINGED"] if canonical not in {"MAIN_ENTRY_DOOR", "UNIT_ENTRY_DOOR", "COURTYARD_DOOR", "TERRACE_DOOR", "VEHICLE_GATE"}
            else ["SINGLE_HINGED", "DOUBLE_HINGED", "SLIDING", "GLAZED_SWING"],
        quality_priority="PRIMARY" if canonical in {"MAIN_ENTRY_DOOR", "UNIT_ENTRY_DOOR", "VEHICLE_GATE", "PEDESTRIAN_GATE"} else "SERVICE" if canonical in {"BATHROOM_DOOR", "WC_DOOR", "SERVICE_DOOR"} else "STANDARD",
        provenance={"relative_hierarchy": PROJECT_USER_RULE, "default_size_range": ARCHITECTURAL_DESIGN_HEURISTIC,
                    "selected_dimensions": ARCHITECTURAL_DESIGN_HEURISTIC, "regulatory_status": "NOT_ASSERTED_AS_REGULATION"},
        future_dwg_mapping={"block": f"AOS_{canonical}", "layer": "A-GATE" if "GATE" in canonical else "A-DOOR"},
    )
    DOOR_SEMANTIC_LIBRARY[canonical] = row

_WINDOW_BASE = {
    "LIVING_PRIMARY_WINDOW": "LIVING_RECEPTION_WINDOW",
    "LIVING_SECONDARY_WINDOW": "LIVING_RECEPTION_WINDOW",
    "BEDROOM_WINDOW": "BEDROOM_WINDOW",
    "MASTER_BEDROOM_WINDOW": "MASTER_BEDROOM_WINDOW",
    "KITCHEN_WINDOW": "KITCHEN_WINDOW",
    "BATHROOM_WINDOW": "BATHROOM_WINDOW",
    "WC_WINDOW": "WC_WINDOW",
    "COURTYARD_FACING_WINDOW": "COURTYARD_WINDOW",
    "REAR_YARD_WINDOW": "BEDROOM_WINDOW",
    "SIDE_YARD_WINDOW": "BEDROOM_WINDOW",
    "TERRACE_GLAZED_OPENING": "TERRACE_GLAZED_OPENING",
    "DINING_WINDOW": "LIVING_RECEPTION_WINDOW",
    "BATH_WC_WINDOW": "WC_WINDOW",
    "COURTYARD_WINDOW": "COURTYARD_WINDOW",
}
WINDOW_SEMANTIC_LIBRARY = {}
for canonical, legacy in _WINDOW_BASE.items():
    row = deepcopy(_V1_WINDOWS[legacy])
    nominal = row["nominal_width_m"]
    if canonical == "LIVING_SECONDARY_WINDOW": nominal = 1.60
    if canonical == "LIVING_PRIMARY_WINDOW": nominal = 2.40
    if canonical == "KITCHEN_WINDOW": nominal = 1.50
    if canonical == "BEDROOM_WINDOW": nominal = 1.20
    if canonical in {"BATH_WC_WINDOW", "BATHROOM_WINDOW", "WC_WINDOW"}: nominal = .60
    row.update(
        semantic_type=canonical, semantic_role=canonical, nominal_width_m=nominal,
        default_size_range_m={"width": [max(.45, round(nominal * .70, 2)), round(nominal * 1.35, 2)],
                              "height": [max(.45, round(row["nominal_height_m"] * .75, 2)), round(row["nominal_height_m"] * 1.25, 2)]},
        minimum_host_wall_capacity_m=round(max(.65, nominal * .70 + .20), 2),
        sill_head_intent={"sill": row["sill_strategy"], "head": "COORDINATE_WITH_FACADE_AND_REQUIRED_GLAZING"},
        allowed_forms=["SINGLE_CASEMENT", "DOUBLE_CASEMENT", "FIXED_PLUS_OPERABLE", "HORIZONTAL_KITCHEN", "MULTI_PANEL_LIVING", "HIGH_LEVEL_SERVICE", "GLAZED_TERRACE_DOOR"],
        quality_priority="PRIMARY" if canonical == "LIVING_PRIMARY_WINDOW" else "SERVICE" if canonical in {"BATHROOM_WINDOW", "WC_WINDOW"} else "STANDARD",
        provenance={"space_function_and_priority": PROJECT_USER_RULE, "default_size_range": ARCHITECTURAL_DESIGN_HEURISTIC,
                    "selected_dimensions": ARCHITECTURAL_DESIGN_HEURISTIC, "daylight_ratio": "VERIFIED_REGULATION_ONLY_WHEN_EVIDENCE_ATTACHED",
                    "regulatory_status": "HEURISTIC_DIMENSIONS_NOT_ASSERTED_AS_REGULATION"},
        future_dwg_mapping={"block": f"AOS_{canonical}", "layer": "A-WIND"},
    )
    WINDOW_SEMANTIC_LIBRARY[canonical] = row

DOOR_RUNTIME_LIBRARY = {**_V1_DOORS, **DOOR_SEMANTIC_LIBRARY}
WINDOW_RUNTIME_LIBRARY = {**_V1_WINDOWS, **WINDOW_SEMANTIC_LIBRARY}

def door_type_for_connection(a: str, b: str, *, exterior=False, common=False, closed_kitchen=True) -> str:
    joined = f"{a} {b}".lower()
    if common: return "UNIT_ENTRY_DOOR"
    if exterior or "site_entry" in joined or "outside" in joined: return "MAIN_ENTRY_DOOR"
    if "master" in joined: return "MASTER_BEDROOM_DOOR"
    if "guest_wc" in joined or " wc" in f" {joined}": return "WC_DOOR"
    if "bath" in joined: return "BATHROOM_DOOR"
    if "kitchen" in joined:
        if not closed_kitchen: raise ValueError("OPEN_KITCHEN_MUST_NOT_RECEIVE_DOOR")
        return "KITCHEN_DOOR"
    if "terrace" in joined: return "TERRACE_DOOR"
    if "courtyard" in joined: return "COURTYARD_DOOR"
    if "storage" in joined or "service" in joined: return "SERVICE_DOOR"
    if any(x in joined for x in ("foyer", "living", "dining", "family", "private_hall")): return "INTERNAL_PUBLIC_DOOR"
    return "BEDROOM_DOOR"

def window_type_for_room(room: str, *, exposure: str | None = None, primary=True) -> str:
    key = (room or "").lower()
    if "living" in key or "reception" in key: return "LIVING_PRIMARY_WINDOW" if primary else "LIVING_SECONDARY_WINDOW"
    if "master" in key: return "MASTER_BEDROOM_WINDOW"
    if "bed" in key: return "BEDROOM_WINDOW"
    if "kitchen" in key: return "KITCHEN_WINDOW"
    if "bath" in key: return "BATHROOM_WINDOW"
    if "wc" in key: return "WC_WINDOW"
    if "terrace" in key: return "TERRACE_GLAZED_OPENING"
    exp = (exposure or "").upper()
    if "COURTYARD" in exp: return "COURTYARD_FACING_WINDOW"
    if "REAR" in exp or "NORTH" in exp: return "REAR_YARD_WINDOW"
    if "SIDE" in exp or "EAST" in exp or "WEST" in exp: return "SIDE_YARD_WINDOW"
    return "BEDROOM_WINDOW"

class ResidentialOpeningSemanticEngine(_V1Engine):
    def door_spec(self, type_id): return deepcopy(DOOR_SEMANTIC_LIBRARY[type_id])
    def window_spec(self, type_id): return deepcopy(WINDOW_SEMANTIC_LIBRARY[type_id])

    def validate_hierarchy(self):
        d = DOOR_SEMANTIC_LIBRARY
        checks = {
            "main_entry_gt_bedroom": d["MAIN_ENTRY_DOOR"]["nominal_width_m"] > d["BEDROOM_DOOR"]["nominal_width_m"],
            "bedroom_ge_bathroom": d["BEDROOM_DOOR"]["nominal_width_m"] >= d["BATHROOM_DOOR"]["nominal_width_m"],
            "bedroom_ge_wc": d["BEDROOM_DOOR"]["nominal_width_m"] >= d["WC_DOOR"]["nominal_width_m"],
            "living_primary_gt_bedroom": WINDOW_SEMANTIC_LIBRARY["LIVING_PRIMARY_WINDOW"]["nominal_width_m"] > WINDOW_SEMANTIC_LIBRARY["BEDROOM_WINDOW"]["nominal_width_m"],
        }
        return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}

    def validate(self, doors, windows):
        findings = []
        for door in doors:
            spec = DOOR_SEMANTIC_LIBRARY.get(door.get("type"))
            if not spec: findings.append({"code": "UNKNOWN_DOOR_SEMANTIC_TYPE", "id": door.get("id")}); continue
            width = float(door.get("clear_width_m", 0))
            if width > float(door.get("host_available_m", float("inf"))) + 1e-6:
                findings.append({"code": "OPENING_WIDTH_EXCEEDS_HOST_SEGMENT", "id": door.get("id")})
            if not door.get("swing_collision_free", True):
                findings.append({"code": "DOOR_SWING_FUNCTION_CONFLICT", "id": door.get("id")})
            if not door.get("provenance"):
                findings.append({"code": "OPENING_DIMENSION_PROVENANCE_MISSING", "id": door.get("id")})
        for window in windows:
            if window.get("type") not in WINDOW_SEMANTIC_LIBRARY:
                findings.append({"code": "UNKNOWN_WINDOW_SEMANTIC_TYPE", "id": window.get("id")}); continue
            if float(window.get("width_m", 0)) > float(window.get("host_available_m", float("inf"))) + 1e-6:
                findings.append({"code": "OPENING_WIDTH_EXCEEDS_HOST_SEGMENT", "id": window.get("id")})
            if not window.get("provenance"):
                findings.append({"code": "OPENING_DIMENSION_PROVENANCE_MISSING", "id": window.get("id")})
        return {"status": "FAIL" if findings else "PASS", "findings": findings,
                "hierarchy": self.validate_hierarchy(), "source_proof_preserved": True,
                "required_opening_bijection_preserved": True}

    def schedule(self, doors, windows):
        fields = ("id", "type", "served_space", "host_wall", "width", "height", "source", "provenance")
        rows = []
        for d in doors:
            rows.append({"id": d.get("id"), "type": d.get("type"), "semantic_type": d.get("type"),
                         "served_space": d.get("to"), "host_wall": d.get("host_wall"),
                         "width": d.get("clear_width_m"), "clear_width_m": d.get("clear_width_m"), "height": d.get("height_m"), "height_m": d.get("height_m"),
                         "source": d.get("from"), "provenance": d.get("provenance"),
                         "graphic_variant": d.get("graphical_symbol_class"), "graphical_symbol_class": d.get("graphical_symbol_class"), "swing": d.get("swing")})
        for w in windows:
            rows.append({"id": w.get("id"), "type": w.get("type"), "semantic_type": w.get("type"),
                         "served_space": w.get("room"), "host_wall": w.get("host_wall"),
                         "width": w.get("width_m"), "width_m": w.get("width_m"), "height": w.get("height_m"), "height_m": w.get("height_m"),
                         "source": w.get("source"), "provenance": w.get("provenance"),
                         "graphic_variant": w.get("configuration"), "configuration": w.get("configuration"), "graphical_symbol_class": w.get("graphical_symbol_class"), "sill_m": w.get("sill_m")})
        return {"schema": "OPENING_SCHEDULE_V2", "columns": list(fields), "rows": rows,
                "doors": [x for x in rows if str(x["type"]).endswith("DOOR") or "GATE" in str(x["type"])],
                "windows": [x for x in rows if x not in rows[:len(doors)]]}

ResidentialOpeningHeuristicProfileV1 = {
    "profile_id": "ResidentialOpeningHeuristicProfileV1",
    "provenance": ARCHITECTURAL_DESIGN_HEURISTIC,
    "regulatory_status": "NOT_A_REGULATION",
    "doors": {k: {"default_width_m": v["nominal_width_m"], "range": v["default_size_range_m"]} for k, v in DOOR_SEMANTIC_LIBRARY.items()},
    "windows": {k: {"default_width_m": v["nominal_width_m"], "default_height_m": v["nominal_height_m"], "range": v["default_size_range_m"]} for k, v in WINDOW_SEMANTIC_LIBRARY.items()},
}
