from __future__ import annotations

"""Reusable interior fixture, wet-finish and in-room movement contracts.

All numeric dimensions in this module are DESIGN_HEURISTIC values.  They are
not regulations and may be overridden by a verified project/program source.
"""

from collections import deque
from dataclasses import dataclass, asdict
from typing import Any

PROVENANCE = {"classification": "DESIGN_HEURISTIC", "claim": "NOT_REGULATION",
              "note": "Replace with verified project/user/authority evidence when supplied."}


def _fixture(sid, fa, purpose, footprint, clearance, wall=False, wet="REQUIRED",
             drainage="REQUIRED", ventilation="ROOM_RULE", symbol=None):
    return {"semantic_id": sid, "persian_label": fa, "functional_purpose": purpose,
            "nominal_footprint_m": list(footprint), "clearance_envelope_m": list(clearance),
            "required_wall_adjacency": wall, "door_swing_conflict_rule": "CRITICAL_SOLID_AND_APPROACH_EXCLUSION",
            "wet_zone_relation": wet, "drainage_intent": drainage, "ventilation_intent": ventilation,
            "svg_vector_representation": symbol or sid, "pdf_vector_representation": symbol or sid,
            "future_dwg_mapping": {"block": f"AOS_{sid}", "layer": "A-FIXT-WET"},
            "numeric_provenance": PROVENANCE.copy()}


INTERIOR_FIXTURE_KNOWLEDGE = {
    "BATHTUB": _fixture("BATHTUB", "وان", "استحمام در وان", (1.70, .75), (.70, .75), True),
    "SHOWER_ZONE": _fixture("SHOWER_ZONE", "محدوده دوش", "استحمام ایستاده", (.90, .90), (.70, .70)),
    "SHOWER_TRAY": _fixture("SHOWER_TRAY", "زیردوشی", "جمع‌آوری آب دوش", (.90, .90), (.70, .70)),
    "WASHBASIN": _fixture("WASHBASIN", "روشویی", "شست‌وشوی دست و صورت", (.60, .50), (.70, .65), True),
    "WC_IRANIAN": _fixture("WC_IRANIAN", "سرویس ایرانی", "توالت زمینی با جهت استفاده مستقل", (.60, .80), (.70, .80)),
    "WC_WESTERN": _fixture("WC_WESTERN", "سرویس فرنگی", "توالت نشسته با مخزن/دیوار سرویس", (.70, .80), (.75, .80), True),
    "FLOOR_DRAIN": _fixture("FLOOR_DRAIN", "کفشور", "تخلیه آب کف", (.15, .15), (0, 0), False, drainage="REQUIRED"),
    "WASHING_MACHINE": _fixture("WASHING_MACHINE", "ماشین لباسشویی", "شست‌وشوی لباس", (.65, .65), (.70, .70), True),
    "WET_SHAFT": _fixture("WET_SHAFT", "داکت تأسیسات تر", "تهویه/رایزر خدمات تر", (.40, .40), (0, 0), True,
                              drainage="SERVICE_INTENT", ventilation="REQUIRED_WHEN_ROOM_RULE_REQUIRES"),
    "BIDET": _fixture("BIDET", "بیده", "شست‌وشوی بهداشتی؛ فقط با انتخاب برنامه", (.60, .60), (.70, .70), True),
}

WET_SPACE_FINISH_CONTRACT = {
    "FLOOR_TILE_ZONE": {"semantic_id": "FLOOR_TILE_ZONE", "persian_label": "سرامیک کف",
        "material_semantic": "CERAMIC_TILE", "surface": "FLOOR", "wet_zone": True,
        "geometry_rule": "POLYGON_MUST_BE_WITHIN_REFERENCED_WET_ROOM", "height_m": None,
        "render": "LIGHT_VECTOR_HATCH", "provenance": PROVENANCE.copy()},
    "WALL_TILE_ZONE": {"semantic_id": "WALL_TILE_ZONE", "persian_label": "کاشی/سرامیک دیوار",
        "material_semantic": "CERAMIC_TILE", "surface": "WALL", "wet_zone": True,
        "geometry_rule": "HOSTED_ON_REFERENCED_WET_ROOM_WALL_FACE", "height_m": None,
        "render": "LIGHT_VECTOR_HATCH", "provenance": PROVENANCE.copy()},
    "FLOOR_SLOPE_INTENT": {"semantic_id": "FLOOR_SLOPE_INTENT", "detail_scope": "SEMANTIC_PLACEHOLDER_ONLY",
        "requires_drain_target": True, "numeric_slope": None, "provenance": PROVENANCE.copy()},
}

CLEARANCE_RULES = {
    "BED": {"zones": ["SIDE_ACCESS", "FOOT_CIRCULATION"], "default_depth_m": .60},
    "WARDROBE": {"zones": ["STANDING_OPENING"], "default_depth_m": .90},
    "SOFA": {"zones": ["SEATING_ACCESS", "PRIMARY_ROUTE_BYPASS"], "default_depth_m": .60},
    "DINING": {"zones": ["CHAIR_PULL_OUT", "OCCUPIED_CHAIR_BYPASS"], "default_depth_m": .75},
    "KITCHEN": {"zones": ["COUNTER_WORK", "APPLIANCE_DOOR", "AISLE"], "default_depth_m": 1.00},
    "WET_FIXTURE": {"zones": ["APPROACH_STANDING", "ENTRY_USE"], "default_depth_m": .70},
    "DOOR": {"zones": ["SWING_CLEARANCE"], "default_depth_m": None},
}

FAILURE_CODES = ("WET_FIXTURE_OVERLAP", "WET_FIXTURE_CLEARANCE_FAIL", "DOOR_SWING_FIXTURE_CONFLICT",
                 "NO_CLEAR_APPROACH_TO_FIXTURE", "WET_SPACE_USE_PATH_BLOCKED",
                 "FURNITURE_CLEARANCE_OVERLAP_CRITICAL", "ACTIVITY_ZONE_BLOCKS_PRIMARY_ROUTE",
                 "PRIMARY_ROUTE_INTERSECTS_FURNITURE", "WARDROBE_USE_ZONE_BLOCKED",
                 "DINING_CHAIR_USE_ZONE_CONFLICT")


def overlap(a, b, strict=True):
    op = min(a[2], b[2]) - max(a[0], b[0])
    oq = min(a[3], b[3]) - max(a[1], b[1])
    return op > (1e-9 if strict else -1e-9) and oq > (1e-9 if strict else -1e-9)


def inside(a, b): return a[0] >= b[0] and a[1] >= b[1] and a[2] <= b[2] and a[3] <= b[3]


class InteriorFixtureFinishValidator:
    wet_rooms = {"BATHROOM", "FAMILY_BATHROOM", "ENSUITE", "GUEST_WC", "WC", "SEPARATE_WC", "LAUNDRY_UTILITY"}

    def validate(self, room, fixtures, door_swings=(), finishes=(), routes=(), room_walls=()):
        findings = []
        room_box = room["polygon"]
        for i, a in enumerate(fixtures):
            if a["semantic_id"] not in INTERIOR_FIXTURE_KNOWLEDGE:
                continue
            if not inside(a["footprint"], room_box): findings.append(self._f("WET_FIXTURE_CLEARANCE_FAIL", a))
            for b in fixtures[i + 1:]:
                if overlap(a["footprint"], b["footprint"]): findings.append(self._f("WET_FIXTURE_OVERLAP", a, b))
            if any(overlap(a["footprint"], z) for z in door_swings): findings.append(self._f("DOOR_SWING_FIXTURE_CONFLICT", a))
            approach = a.get("approach_zone")
            if a["semantic_id"] not in {"FLOOR_DRAIN", "WET_SHAFT"}:
                if not approach or not inside(approach, room_box): findings.append(self._f("NO_CLEAR_APPROACH_TO_FIXTURE", a))
                elif any(overlap(approach, b["footprint"]) for b in fixtures if b is not a): findings.append(self._f("WET_FIXTURE_CLEARANCE_FAIL", a))
        for f in finishes:
            if f["type"] == "FLOOR_TILE_ZONE" and (room["type"] not in self.wet_rooms or not inside(f["extent"], room_box)):
                findings.append({"code": "FLOOR_TILE_ZONE_NOT_IN_WET_ROOM", "finish_id": f["id"]})
            if f["type"] == "WALL_TILE_ZONE" and (room["type"] not in self.wet_rooms or f.get("host_wall_id") not in set(room_walls)):
                findings.append({"code": "WALL_TILE_ZONE_NOT_HOSTED", "finish_id": f["id"]})
        for route in routes:
            if any(overlap(seg, x["footprint"]) for seg in route["segments"] for x in fixtures):
                findings.append({"code": "WET_SPACE_USE_PATH_BLOCKED", "route_id": route["id"]})
        ventilation_required = room.get("ventilation_required", False)
        shaft = any(x["semantic_id"] == "WET_SHAFT" for x in fixtures)
        if ventilation_required and not shaft and not room.get("exterior_ventilation", False):
            findings.append({"code": "WET_SHAFT_INTENT_MISSING", "room_id": room["id"]})
        return {"status": "PASS" if not findings else "FAIL", "findings": findings,
                "failure_code_contract": list(FAILURE_CODES), "fixture_driven": True}

    @staticmethod
    def _f(code, a, b=None):
        out = {"code": code, "fixture_id": a.get("id"), "semantic_id": a["semantic_id"]}
        if b: out["other_fixture_id"] = b.get("id")
        return out


class FurnitureClearanceValidator:
    def validate(self, objects, primary_routes=()):
        findings = []
        for i, a in enumerate(objects):
            fp, zone = a["footprint"], a.get("activity_zone")
            if zone:
                for b in objects:
                    if b is not a and overlap(zone, b["footprint"]):
                        code = "WARDROBE_USE_ZONE_BLOCKED" if a["semantic_id"] == "WARDROBE" else (
                               "DINING_CHAIR_USE_ZONE_CONFLICT" if a["semantic_id"].startswith("DINING") else "FURNITURE_CLEARANCE_OVERLAP_CRITICAL")
                        findings.append({"code": code, "object_id": a["id"], "other_id": b["id"]})
            for route in primary_routes:
                if any(overlap(seg, fp) for seg in route["segments"]):
                    findings.append({"code": "PRIMARY_ROUTE_INTERSECTS_FURNITURE", "object_id": a["id"], "route_id": route["id"]})
                if zone and route.get("critical") and any(overlap(seg, zone) for seg in route["segments"]):
                    findings.append({"code": "ACTIVITY_ZONE_BLOCKS_PRIMARY_ROUTE", "object_id": a["id"], "route_id": route["id"]})
        return {"status": "PASS" if not findings else "FAIL", "findings": findings,
                "failure_code_contract": list(FAILURE_CODES)}


def add_review_graphics(scene, fixtures, finishes=(), clearance_guides=(), use_paths=()):
    """Add vector-only review primitives. Guides never use wall/opening layers."""
    from .architectural_symbol_library_v1 import get_symbol
    for f in finishes:
        if f["type"] == "FLOOR_TILE_ZONE":
            scene.add("HATCH", "FLOOR_HATCH", {"rect": f["extent"], "spacing": .25, "angle": 45},
                      {"stroke": "#b8c4c9", "line_width": .012}, {"finish_id": f["id"], "extract_as_wall": False})
        else:
            scene.add("HATCH", "WALL_FINISH_HATCH", {"rect": f["extent"], "spacing": .18, "angle": -45},
                      {"stroke": "#9fb0b8", "line_width": .012}, {"finish_id": f["id"], "extract_as_wall": False})
    for f in fixtures:
        rec = get_symbol(f["semantic_id"]); x1, y1, x2, y2 = f["footprint"]
        scene.add("GROUP", "FIXTURES", {"symbol": f["semantic_id"], "x": x1, "y": y1, "w": x2-x1, "h": y2-y1,
                  "vector_primitives": rec["vector_primitives"]}, {}, {"fixture_id": f["id"], "solid": True})
    for z in clearance_guides:
        x1,y1,x2,y2=z["extent"]
        scene.add("POLYGON", "CLEARANCE_GUIDES", {"rect":{"x":x1,"y":y1,"w":x2-x1,"h":y2-y1}},
                  {"fill":"none","stroke":"#8a6aa8","line_width":.018,"dash":True},
                  {"guide_id":z["id"],"validation_only":True,"extract_as_wall":False,"extract_as_opening":False})
    for path in use_paths:
        scene.add("POLYLINE", "CLEARANCE_GUIDES", {"points":path["points"]},
                  {"stroke":"#3b82a0","line_width":.025,"dash":True},
                  {"path_id":path["id"],"semantic":"INTERIOR_USE_PATH","extract_as_wall":False})
    return scene


def contracts():
    return {"fixtures": INTERIOR_FIXTURE_KNOWLEDGE, "finishes": WET_SPACE_FINISH_CONTRACT,
            "clearance_rules": CLEARANCE_RULES, "failure_codes": list(FAILURE_CODES),
            "interior_use_path": {"semantic_id": "INTERIOR_USE_PATH", "granularity": "WITHIN_ROOM",
              "origins": ["ROOM_ENTRY"], "destinations": ["PRIMARY_USE_ZONE", "REQUIRED_FIXTURE_APPROACH"],
              "obstacles": ["WALL", "FURNITURE_SOLID", "CRITICAL_DOOR_SWING", "FIXED_CABINETRY", "SANITARY_FIXTURE"],
              "proof": "COLLISION_FREE_SEGMENTS", "numeric_provenance": PROVENANCE.copy()}}
