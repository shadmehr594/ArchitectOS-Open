from __future__ import annotations

"""Semantic door/window intelligence with explicit provenance separation.

Nominal dimensions are drawing/design heuristics.  The only regulatory ratios
used here are supplied by a verified-rule input (the default profile references
the existing Topic 4 evidence registry); heuristics never masquerade as law.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass
from math import ceil

DESIGN_HEURISTIC = "DESIGN_HEURISTIC"
USER_PROJECT_RULE = "USER_PROJECT_RULE"
VERIFIED_REGULATION = "VERIFIED_REGULATION"

@dataclass(frozen=True)
class DoorTypeSpec:
    semantic_type: str
    nominal_width_m: float
    min_width_source: dict
    leaf_count: int
    leaf_style: str
    swing_type: str
    frame_jamb_style: str
    threshold_style: str
    graphical_symbol_class: str
    future_dwg_mapping: dict

@dataclass(frozen=True)
class WindowTypeSpec:
    semantic_type: str
    served_space_type: str
    nominal_width_m: float
    nominal_height_m: float
    daylight_target_relation: str
    sill_strategy: dict
    panel_count: int
    frame_style: str
    privacy_class: str
    host_wall_constraints: tuple[str, ...]
    furniture_cabinet_conflicts: tuple[str, ...]
    exposure_source_proof: str
    graphical_symbol_class: str
    future_dwg_mapping: dict

DOOR_TYPOLOGY_LIBRARY = {
    "MAIN_ENTRANCE_DOOR": dict(relative_width="XL", nominal_width_m=1.10, privacy_role="CONTROLLED_THRESHOLD", swing_preference="INWARD_IF_CLEAR", threshold_behavior="WEATHER_THRESHOLD", glazing="OPTIONAL", acoustic_privacy="HIGH", accessibility={"compatible": True, "verify_project_clear_width": True}),
    "BEDROOM_DOOR": dict(relative_width="M", nominal_width_m=.90, privacy_role="PRIVATE", swing_preference="INTO_ROOM_CLEAR_OF_FURNITURE", threshold_behavior="FLUSH", glazing="FORBIDDEN", acoustic_privacy="HIGH", accessibility={"compatible": "PROFILE_DEPENDENT", "verify_project_clear_width": True}),
    "MASTER_BEDROOM_DOOR": dict(relative_width="M", nominal_width_m=.95, privacy_role="PRIVATE", swing_preference="INTO_ROOM_CLEAR_OF_FURNITURE", threshold_behavior="FLUSH", glazing="FORBIDDEN", acoustic_privacy="HIGH", accessibility={"compatible": "PROFILE_DEPENDENT", "verify_project_clear_width": True}),
    "BATHROOM_DOOR": dict(relative_width="S", nominal_width_m=.80, privacy_role="HIGH_PRIVACY", swing_preference="OUTWARD_OR_CLEAR_SAFE_INWARD", threshold_behavior="WET_AREA_TRANSITION", glazing="FORBIDDEN", acoustic_privacy="HIGH", accessibility={"compatible": "VERIFY_MANEUVER_AND_CLEAR_WIDTH", "verify_project_clear_width": True}),
    "WC_DOOR": dict(relative_width="S", nominal_width_m=.75, privacy_role="HIGH_PRIVACY", swing_preference="OUTWARD_OR_CLEAR_SAFE_INWARD", threshold_behavior="WET_AREA_TRANSITION", glazing="FORBIDDEN", acoustic_privacy="HIGH", accessibility={"compatible": "VERIFY_MANEUVER_AND_CLEAR_WIDTH", "verify_project_clear_width": True}),
    "KITCHEN_DOOR": dict(relative_width="M", nominal_width_m=.90, privacy_role="SERVICE", swing_preference="CLEAR_OF_WORK_TRIANGLE", threshold_behavior="FLUSH", glazing="OPTIONAL", acoustic_privacy="MEDIUM", accessibility={"compatible": "PROFILE_DEPENDENT", "verify_project_clear_width": True}),
    "COURTYARD_YARD_DOOR": dict(relative_width="L", nominal_width_m=1.00, privacy_role="EXTERIOR_THRESHOLD", swing_preference="TO_CLEAR_SIDE", threshold_behavior="WEATHER_THRESHOLD", glazing="OPTIONAL", acoustic_privacy="MEDIUM", accessibility={"compatible": True, "verify_project_clear_width": True}),
    "TERRACE_BALCONY_DOOR": dict(relative_width="L", nominal_width_m=1.00, privacy_role="EXTERIOR_THRESHOLD", swing_preference="SLIDING_OR_CLEAR_SIDE", threshold_behavior="WEATHER_THRESHOLD", glazing="ALLOWED", acoustic_privacy="MEDIUM", accessibility={"compatible": True, "verify_project_clear_width": True}),
    "SERVICE_STORAGE_DOOR": dict(relative_width="S", nominal_width_m=.75, privacy_role="SERVICE", swing_preference="CLEAR_OF_STORAGE", threshold_behavior="FLUSH", glazing="FORBIDDEN", acoustic_privacy="LOW", accessibility={"compatible": "PROFILE_DEPENDENT", "verify_project_clear_width": True}),
    "COMMON_ENTRY_DOOR": dict(relative_width="XL", nominal_width_m=1.20, privacy_role="COMMON_CONTROLLED_THRESHOLD", swing_preference="EGRESS_AND_CODE_DEPENDENT", threshold_behavior="WEATHER_THRESHOLD", glazing="OPTIONAL", acoustic_privacy="HIGH", accessibility={"compatible": True, "verify_project_clear_width": True}),
    "PRIVACY_TRANSITION_DOOR": dict(relative_width="S", nominal_width_m=.78, privacy_role="PUBLIC_PRIVATE_FILTER", swing_preference="TO_CLEAR_SIDE", threshold_behavior="FLUSH", glazing="OPTIONAL", acoustic_privacy="MEDIUM", accessibility={"compatible":"PROJECT_REVIEW_REQUIRED", "verify_project_clear_width":True}),
}
for _id, _row in DOOR_TYPOLOGY_LIBRARY.items():
    _leaf_count = 2 if _id == "COMMON_ENTRY_DOOR" else 1
    _leaf_style = "GLAZED_SLIDING" if _id == "TERRACE_BALCONY_DOOR" else ("PROMINENT_ENTRY" if _id in {"MAIN_ENTRANCE_DOOR","COMMON_ENTRY_DOOR"} else "SOLID_PRIVACY" if _id in {"BEDROOM_DOOR","MASTER_BEDROOM_DOOR","BATHROOM_DOOR","WC_DOOR"} else "STANDARD")
    _symbol = "DOOR_MAIN_ENTRY" if _id in {"MAIN_ENTRANCE_DOOR","COMMON_ENTRY_DOOR"} else "DOOR_GLAZED_SLIDING" if _id == "TERRACE_BALCONY_DOOR" else "DOOR_COMPACT_SERVICE" if _id in {"BATHROOM_DOOR","WC_DOOR","SERVICE_STORAGE_DOOR"} else "DOOR_INTERIOR_PRIVATE"
    _row.update(semantic_role=_id, semantic_type=_id, height_m=2.10, leaf_count=_leaf_count,
        leaf_style=_leaf_style, swing_type=_row["swing_preference"], frame_jamb_style="HEAVY_ENTRY_JAMB" if "ENTRY" in _id or _id=="MAIN_ENTRANCE_DOOR" else "STANDARD_INTERIOR_JAMB",
        threshold_style=_row["threshold_behavior"], graphical_symbol_class=_symbol,
        min_width_source={"value_m":None,"classification":"UNRESOLVED","note":"No legal minimum asserted; resolve from verified regulation or project rule."},
        future_dwg_mapping={"block":_symbol,"layer":"A-DOOR-ENTRY" if "ENTRY" in _symbol else "A-DOOR-INTR"},
        provenance={"classification": USER_PROJECT_RULE, "relative_hierarchy": USER_PROJECT_RULE, "nominal_dimensions": DESIGN_HEURISTIC, "regulatory_status": "NOT_ASSERTED_AS_LAW"})

WINDOW_TYPOLOGY_LIBRARY = {
    "LIVING_RECEPTION_WINDOW": ("HIGH", "XL", "LOW", "FIXED_PLUS_OPERABLE", .60, "CLEAR_OR_SOLAR_CONTROL"),
    "DINING_WINDOW": ("HIGH", "L", "LOW", "WIDE_HORIZONTAL", .75, "CLEAR"),
    "BEDROOM_WINDOW": ("HIGH", "M", "HIGH", "TWO_LEAF_CASEMENT", .90, "PRIVACY_OPTIONAL"),
    "MASTER_BEDROOM_WINDOW": ("HIGH", "M", "HIGH", "TWO_LEAF_CASEMENT", .90, "PRIVACY_OPTIONAL"),
    "KITCHEN_WINDOW": ("MEDIUM_HIGH", "M", "MEDIUM", "WIDE_HORIZONTAL", 1.10, "CLEAR_ABOVE_COUNTER"),
    "BATHROOM_WINDOW": ("MEDIUM", "S", "HIGH", "HIGH_LEVEL_SERVICE_WINDOW", 1.50, "OBSCURE_PRIVACY_GLAZING"),
    "WC_WINDOW": ("MEDIUM", "S", "VERY_HIGH", "HIGH_LEVEL_SERVICE_WINDOW", 1.60, "OBSCURE_PRIVACY_GLAZING"),
    "STAIR_WINDOW": ("MEDIUM", "M", "MEDIUM", "VERTICAL", 1.00, "SAFETY_GLAZING_AS_APPLICABLE"),
    "COURTYARD_WINDOW": ("MEDIUM_HIGH", "M", "HIGH", "VERTICAL", .90, "PRIVACY_BY_OPPOSING_USE"),
    "TERRACE_GLAZED_OPENING": ("HIGH", "XL", "MEDIUM", "SLIDING_GLAZED_OPENING", .05, "SAFETY_GLAZING_AS_APPLICABLE"),
}
for _id, _values in list(WINDOW_TYPOLOGY_LIBRARY.items()):
    daylight, aperture, privacy, config, sill, glazing = _values
    _served=_id.removesuffix("_WINDOW").removesuffix("_GLAZED_OPENING")
    _height=1.20 if aperture not in {"S", "XL"} else (.60 if aperture == "S" else 1.50)
    _nominal_width={"S":.60,"M":1.20,"L":1.60,"XL":2.40}[aperture]
    _panels={"HIGH_LEVEL_SERVICE_WINDOW":1,"VERTICAL":1,"TWO_LEAF_CASEMENT":2,"WIDE_HORIZONTAL":2,"SLIDING_GLAZED_OPENING":2,"FIXED_PLUS_OPERABLE":3}.get(config,2)
    _symbol="WINDOW_LARGE_MULTI_PANEL" if aperture=="XL" else "WINDOW_PRIVACY_HIGH_LEVEL" if aperture=="S" else "WINDOW_STANDARD_RESIDENTIAL"
    WINDOW_TYPOLOGY_LIBRARY[_id] = dict(semantic_role=_id, semantic_type=_id, room_served=_served, served_space_type=_served,
        daylight_priority=daylight, daylight_target_relation="AREA_RATIO_PLUS_DEPTH_PLUS_SOURCE_QUALITY", privacy_sensitivity=privacy,
        privacy_class=privacy, preferred_relative_aperture=aperture, operable_fixed_preference=config,
        sill_behavior={"nominal_sill_m": sill, "classification": DESIGN_HEURISTIC}, sill_strategy={"nominal_sill_m":sill,"classification":DESIGN_HEURISTIC},
        glazing_privacy_behavior=glazing, furniture_wall_relationship="SELECT_ONLY_VALID_HOST_SEGMENT_FREE_OF_FURNITURE_AND_CABINETRY",
        furniture_cabinet_conflicts=["TALL_CABINET","WARDROBE","BED_HEADBOARD","TV_MEDIA_WALL","DOOR_SWING"],
        host_wall_constraints=["LEGAL_EXPOSURE","SUFFICIENT_CONTIGUOUS_LENGTH","NO_OPENING_PROHIBITION","FURNITURE_CLEAR"],
        preferred_configuration=config, panel_count=_panels, frame_style="RESIDENTIAL_THERMAL_FRAME", nominal_width_m=_nominal_width, nominal_height_m=_height,
        exposure_source_proof="REQUIRED_LEGAL_OPEN_SPACE_AND_SOURCE_QUALITY",
        graphical_symbol_class=_symbol, future_dwg_mapping={"block":_symbol,"layer":"A-WIND"},
        provenance={"classification": USER_PROJECT_RULE, "configuration_and_dimensions": DESIGN_HEURISTIC, "regulatory_status": "NOT_ASSERTED_AS_LAW"})

# Canonical public name requested by the opening contract.  The legacy
# LIVING_RECEPTION_WINDOW key remains active for backward compatibility.
WINDOW_TYPOLOGY_LIBRARY["LIVING_WINDOW"] = deepcopy(WINDOW_TYPOLOGY_LIBRARY["LIVING_RECEPTION_WINDOW"])
WINDOW_TYPOLOGY_LIBRARY["LIVING_WINDOW"].update(semantic_role="LIVING_WINDOW",semantic_type="LIVING_WINDOW",served_space_type="LIVING_RECEPTION")

ROOM_TO_DOOR = {"master":"MASTER_BEDROOM_DOOR", "bed":"BEDROOM_DOOR", "bath":"BATHROOM_DOOR", "guest_wc":"WC_DOOR", "wc":"WC_DOOR", "kitchen":"KITCHEN_DOOR", "storage":"SERVICE_STORAGE_DOOR", "terrace":"TERRACE_BALCONY_DOOR", "courtyard":"COURTYARD_YARD_DOOR"}
ROOM_TO_WINDOW = {"living":"LIVING_RECEPTION_WINDOW", "reception":"LIVING_RECEPTION_WINDOW", "dining":"DINING_WINDOW", "master":"MASTER_BEDROOM_WINDOW", "bed":"BEDROOM_WINDOW", "kitchen":"KITCHEN_WINDOW", "bath":"BATHROOM_WINDOW", "guest_wc":"WC_WINDOW", "wc":"WC_WINDOW", "stair":"STAIR_WINDOW", "courtyard":"COURTYARD_WINDOW", "terrace":"TERRACE_GLAZED_OPENING"}

def _match(mapping, value, fallback):
    key = (value or "").lower()
    for token, result in mapping.items():
        if token in key: return result
    return fallback

def door_type_for_connection(a: str, b: str, *, exterior=False, common=False, closed_kitchen=True) -> str:
    if common: return "COMMON_ENTRY_DOOR"
    if exterior or "SITE_ENTRY" in {a, b}: return "MAIN_ENTRANCE_DOOR"
    joined=f"{a} {b}".lower()
    if "private_hall" in joined and ("family" in joined or "foyer" in joined): return "PRIVACY_TRANSITION_DOOR"
    selected=_match(ROOM_TO_DOOR, joined, None)
    if selected == "KITCHEN_DOOR" and not closed_kitchen: raise ValueError("OPEN_KITCHEN_MUST_NOT_RECEIVE_DOOR")
    return selected or "BEDROOM_DOOR"

def window_type_for_room(room: str) -> str:
    return _match(ROOM_TO_WINDOW, room, "BEDROOM_WINDOW")

class SemanticOpeningEngine:
    failure_codes = {"GENERIC_EQUAL_DOOR_SIZING","DOOR_TYPE_WIDTH_MISMATCH","DOOR_GRAPHICS_NOT_MATCHING_CLEAR_WIDTH","DAYLIGHT_APERTURE_BELOW_REQUIRED","WINDOW_SIZE_NOT_SUPPORTED_BY_HOST_WALL","WINDOW_AREA_REQUIREMENT_NOT_REALIZABLE","WINDOW_SIZE_IGNORES_ROOM_FUNCTION","OPENING_FURNITURE_CONFLICT","WINDOW_CABINETRY_CONFLICT","DOOR_SWING_FUNCTION_CONFLICT"}
    def door_spec(self, type_id): return deepcopy(DOOR_TYPOLOGY_LIBRARY[type_id])
    def window_spec(self, type_id): return deepcopy(WINDOW_TYPOLOGY_LIBRARY[type_id])

    def resolved_door_spec(self, type_id, *, project_rule=None):
        raw=self.door_spec(type_id); rule=project_rule or {}
        width=float(rule.get("nominal_width_m",raw["nominal_width_m"]))
        source=rule.get("source") or {"classification":DESIGN_HEURISTIC,"rule":"FUNCTIONAL_RELATIVE_HIERARCHY","regulatory_status":"NOT_ASSERTED_AS_LAW"}
        return DoorTypeSpec(type_id,width,source,raw["leaf_count"],raw["leaf_style"],raw["swing_type"],raw["frame_jamb_style"],raw["threshold_style"],raw["graphical_symbol_class"],raw["future_dwg_mapping"])

    def resolved_window_spec(self, type_id):
        raw=self.window_spec(type_id)
        return WindowTypeSpec(type_id,raw["served_space_type"],raw["nominal_width_m"],raw["nominal_height_m"],raw["daylight_target_relation"],raw["sill_strategy"],raw["panel_count"],raw["frame_style"],raw["privacy_class"],tuple(raw["host_wall_constraints"]),tuple(raw["furniture_cabinet_conflicts"]),raw["exposure_source_proof"],raw["graphical_symbol_class"],raw["future_dwg_mapping"])

    @staticmethod
    def _free_runs(length, conflicts, clearance=.10):
        blocked=sorted((max(0,float(a)-clearance),min(length,float(b)+clearance)) for a,b in (conflicts or []) if b>0 and a<length)
        merged=[]
        for a,b in blocked:
            if merged and a<=merged[-1][1]: merged[-1]=(merged[-1][0],max(merged[-1][1],b))
            else: merged.append((a,b))
        runs=[]; cursor=0.0
        for a,b in merged:
            if a>cursor: runs.append((cursor,a))
            cursor=max(cursor,b)
        if cursor<length: runs.append((cursor,length))
        return runs

    def size_windows(self, room, floor_area_m2, host_segments_m, daylight_rule, *, conflicts_m=None, conflict_intervals=None, source_quality=1.0, room_depth_m=None):
        type_id=window_type_for_room(room); spec=self.window_spec(type_id)
        if "ratio" not in daylight_rule or "classification" not in daylight_rule:
            raise ValueError("DAYLIGHT_RULE_REQUIRES_RATIO_AND_PROVENANCE")
        ratio=float(daylight_rule["ratio"]); target=floor_area_m2*ratio
        height=spec["nominal_height_m"]; available=[x for x in host_segments_m if x > .35]
        intervals=conflict_intervals
        if intervals is None and conflicts_m: intervals=[(0,sum(conflicts_m))]
        free_by_host=[self._free_runs(x,intervals if len(available)==1 else []) for x in available]
        usable_runs=[(idx,a,b) for idx,runs in enumerate(free_by_host) for a,b in runs if b-a>.35]
        usable=sum(b-a for _,a,b in usable_runs)
        if usable <= 0: return {"status":"FAIL","type":type_id,"findings":[{"code":"WINDOW_AREA_REQUIREMENT_NOT_REALIZABLE","reason":"NO_FURNITURE_CLEAR_HOST_RUN"}]}
        adjusted=target/max(.25,source_quality); required_width=adjusted/height
        longest=max((b-a for _,a,b in usable_runs),default=0)
        if required_width>usable+1e-6 or not longest:
            return {"status":"FAIL","type":type_id,"target_glazing_area_m2":round(target,3),"quality_adjusted_target_m2":round(adjusted,3),"daylight_rule":deepcopy(daylight_rule),"findings":[{"code":"WINDOW_AREA_REQUIREMENT_NOT_REALIZABLE","required_width_m":round(required_width,3),"available_clear_width_m":round(usable,3)}]}
        count=max(1,ceil(required_width/longest))
        width=required_width/count
        findings=[]
        chosen=[]
        for idx,a,b in sorted(usable_runs,key=lambda x:x[2]-x[1],reverse=True):
            if len(chosen)==count: break
            if b-a+1e-6>=width: chosen.append({"host_segment_index":idx,"start_m":round(a+(b-a-width)/2,3),"end_m":round(a+(b-a+width)/2,3)})
        if len(chosen)<count: findings.append({"code":"WINDOW_AREA_REQUIREMENT_NOT_REALIZABLE","reason":"INSUFFICIENT_CONTIGUOUS_CLEAR_RUNS"})
        if count*width*height+1e-6 < adjusted: findings.append({"code":"DAYLIGHT_APERTURE_BELOW_REQUIRED"})
        return {"status":"FAIL" if findings else "PASS","type":type_id,"semantic_type":type_id,"served_space_type":spec["served_space_type"],"configuration":spec["preferred_configuration"],"graphical_symbol_class":spec["graphical_symbol_class"],"future_dwg_mapping":spec["future_dwg_mapping"],"count":count,"width_m":round(width,3),"height_m":height,"sill_m":spec["sill_behavior"]["nominal_sill_m"],"selected_clear_runs":chosen,"room_floor_area_m2":floor_area_m2,"room_depth_m":room_depth_m,"source_quality_factor":source_quality,"target_glazing_area_m2":round(target,3),"quality_adjusted_target_m2":round(adjusted,3),"achieved_glazing_area_m2":round(count*width*height,3),"daylight_rule":deepcopy(daylight_rule),"findings":findings}

    def validate(self, doors, windows):
        findings=[]
        resolved=[d for d in doors if d.get("type") in DOOR_TYPOLOGY_LIBRARY]
        if len(resolved)>1 and len({round(d["clear_width_m"],3) for d in resolved})==1 and len({d["type"] for d in resolved})>1: findings.append({"code":"GENERIC_EQUAL_DOOR_SIZING"})
        for d in resolved:
            expected=DOOR_TYPOLOGY_LIBRARY[d["type"]]["nominal_width_m"]
            if abs(d["clear_width_m"]-expected)>.011: findings.append({"code":"DOOR_TYPE_WIDTH_MISMATCH","id":d.get("id")})
            if abs(d.get("graphic_leaf_length_m",d["clear_width_m"])-d["clear_width_m"])>.001 or abs(d.get("graphic_arc_radius_m",d["clear_width_m"])-d["clear_width_m"])>.001: findings.append({"code":"DOOR_GRAPHICS_NOT_MATCHING_CLEAR_WIDTH","id":d.get("id")})
        if len(windows)>1 and len({round(w.get("width_m",0),3) for w in windows})==1 and len({w.get("type") for w in windows})>1: findings.append({"code":"WINDOW_SIZE_IGNORES_ROOM_FUNCTION"})
        for w in windows:
            if w.get("width_m",0)>w.get("host_available_m",float("inf"))+1e-6: findings.append({"code":"WINDOW_SIZE_NOT_SUPPORTED_BY_HOST_WALL","id":w.get("id")})
            if w.get("achieved_glazing_area_m2",float("inf"))+1e-6<w.get("required_glazing_area_m2",0): findings.append({"code":"DAYLIGHT_APERTURE_BELOW_REQUIRED","id":w.get("id")})
            if w.get("cabinetry_conflict"): findings.append({"code":"WINDOW_CABINETRY_CONFLICT","id":w.get("id")})
            if w.get("furniture_conflict"): findings.append({"code":"OPENING_FURNITURE_CONFLICT","id":w.get("id")})
        return {"status":"FAIL" if findings else "PASS","findings":findings,"failure_codes_supported":sorted(self.failure_codes)}

    def schedule(self, doors, windows):
        return {"doors":[{k:d.get(k) for k in ("id","type","semantic_type","from","to","clear_width_m","height_m","leaf_count","leaf_style","swing","frame_jamb_style","threshold_style","graphical_symbol_class","future_dwg_mapping","provenance")} for d in doors],"windows":[{k:w.get(k) for k in ("id","type","semantic_type","served_space_type","room","host_wall","source","width_m","height_m","sill_m","panel_count","configuration","privacy_class","graphical_symbol_class","future_dwg_mapping","provenance")} for w in windows]}

TOPIC4_GLAZING_DEFAULT = {"ratio":1/8,"classification":VERIFIED_REGULATION,"evidence_id":"T4-4-5-2-3-2","clause":"4-5-2-3-2","edition":"Topic 4, third edition 1396","pdf_page":66,"printed_page":53,"applicability":"HABITABLE_ROOM_DEFAULT"}
TOPIC4_GLAZING_DEEP_ROOM = {**TOPIC4_GLAZING_DEFAULT,"ratio":1/7,"applicability":"ONE_WINDOW_AND_ROOM_DEPTH_GT_4_5M"}
