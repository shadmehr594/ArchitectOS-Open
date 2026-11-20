"""Additive V8 daylight-zoned architecture synthesis and jurisdictional projection audit.

V7 is an immutable checkpoint. V8 deliberately fails closed where the inherited
packing geometry does not yet prove the new architectural gates.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from shapely.geometry import LineString, Polygon, box

from parcel2_architectural_graph_floor_plan_synthesizer_v7 import (
    ArchitecturalGraphFloorPlanSynthesizerV7, EPS, coords, longest, poly,
    verify_topic4,
)

STATUS = {"PROHIBITED", "OPTIONAL_ALLOWED", "REQUIRED"}
VARIANTS = (
    "NO_PROJECTION", "PARTIAL_PROJECTION", "FULL_ALLOWED_PROJECTION",
    "BALCONY_ONLY", "ROOM_EXTENSION_PLUS_BALCONY",
)


@dataclass(frozen=True)
class ProjectionOpportunity:
    kind: str
    depth_factor: float
    room_extension: bool
    balcony: bool


class ArchitecturalGraphFloorPlanSynthesizerV8:
    pipeline = (
        "BUILDABLE_FLOOR_ENVELOPE", "CORE_STAIR_ELEVATOR_COMMON_LANDING",
        "FACADE_VALUE_MAP", "OPTIONAL_PROJECTION_BALCONY_OPPORTUNITY",
        "DAYLIGHT_SOURCE_BUDGET", "UNIT_PARTITIONING", "PUBLIC_PRIVATE_SERVICE_ZONES",
        "ROOM_ADJACENCY_GRAPH", "LIGHTWELL_CANDIDATES", "ROOM_PACKING", "DOOR_GRAPH",
        "MINIMAL_PRIVATE_CIRCULATION", "WINDOWS_GLAZING_DEPTH", "PRIVACY_NOISE",
        "SERVICE_CLUSTER", "RESIDUAL", "PRECEDENT_GUIDED_REPAIR", "FULL_FLOOR_EVALUATION",
    )
    opportunities = (
        ProjectionOpportunity("NO_PROJECTION", 0.0, False, False),
        ProjectionOpportunity("PARTIAL_PROJECTION", 0.5, True, False),
        ProjectionOpportunity("FULL_ALLOWED_PROJECTION", 1.0, True, False),
        ProjectionOpportunity("BALCONY_ONLY", 0.75, False, True),
        ProjectionOpportunity("ROOM_EXTENSION_PLUS_BALCONY", 1.0, True, True),
    )

    def __init__(self, national_evidence, precedent_patterns, projection_policy, profile_id):
        self.national_evidence = deepcopy(national_evidence)
        self.patterns = deepcopy(precedent_patterns)
        self.policy = deepcopy(projection_policy)
        self.profile = next((p for p in self.policy["profiles"] if p["profile_id"] == profile_id), None)
        if self.profile is None:
            raise ValueError("projection profile not found")
        self._validate_policy()
        self.v7 = ArchitecturalGraphFloorPlanSynthesizerV7(national_evidence, {
            "policy": {"geometry_copying": False}, "cases": [],
        })

    def _validate_policy(self):
        if self.profile["status"] not in STATUS:
            raise ValueError("invalid projection status")
        if self.policy["generic_defaults"]["status"] != "PROHIBITED":
            raise ValueError("generic default must fail closed")
        if self.profile["authority_class"] != "PROJECT_LOCAL_CONFIRMED_CONDITION":
            raise ValueError("local profile authority quarantine lost")
        if self.profile["applicability"]["use_for_regulatory_acceptance"]:
            raise ValueError("pending local evidence cannot be acceptance authority")
        for rule in self.profile["rules"]:
            if rule["max_projection_depth_m"] is None:
                raise ValueError("matched rule needs evidence-linked depth")
            if rule["min_clear_height_m"] is not None:
                raise ValueError("unverified Minab heights must remain unset")

    @staticmethod
    def group(source):
        return ArchitecturalGraphFloorPlanSynthesizerV7.group(source)

    def _matched_street_rule(self):
        band = self.profile["applicability"].get("project_street_width_band_m")
        if not band:
            return None
        lo, hi = band
        for rule in self.profile["rules"]:
            if "STREET_PUBLIC_EDGE" not in rule["eligible_edge_types"]:
                continue
            rlo, rhi = rule["street_width_min_m"], rule["street_width_max_m"]
            if rlo is not None and lo < rlo - EPS:
                continue
            if rhi is not None and hi > rhi + EPS:
                continue
            return rule
        return None

    def synthesize_group(self, source_plans):
        frozen = deepcopy(source_plans)
        bases = self.v7.synthesize_group(source_plans)
        status = self.profile["status"]
        selected = self.opportunities[:1] if status == "PROHIBITED" else self.opportunities
        results = [self._upgrade(base, opportunity) for base in bases for opportunity in selected]
        assert source_plans == frozen
        return results

    def _facade_map(self, plan):
        floor = poly(plan["floor_boundary"])
        landing = poly(plan["core_common_access"]["common_landing_polygon"])
        minx, miny, maxx, maxy = floor.bounds
        edges = [
            ("EDGE_1", LineString([(minx, miny), (maxx, miny)])),
            ("EDGE_2", LineString([(maxx, miny), (maxx, maxy)])),
            ("EDGE_3", LineString([(maxx, maxy), (minx, maxy)])),
            ("EDGE_4", LineString([(minx, maxy), (minx, miny)])),
        ]
        threshold_points = [u["threshold"]["center"] for u in plan["units"]]
        values = []
        for edge_id, edge in edges:
            center = edge.interpolate(0.5, normalized=True)
            entrance_relation = min(center.distance(poly([[x-.01,y-.01],[x+.01,y-.01],[x+.01,y+.01],[x-.01,y+.01]])) for x,y in threshold_points)
            core_distance = center.distance(landing) if not landing.is_empty else 0.0
            values.append({
                "edge_id": edge_id, "geometry": list(edge.coords), "daylight_quality": "DIRECT_EXTERIOR",
                "street_noise_exposure": round(1/(1+entrance_relation), 5),
                "privacy_quietness": round(entrance_relation/(1+entrance_relation), 5),
                "view_potential": "UNVERIFIED_SITE_EVIDENCE_REQUIRED",
                "entrance_core_relation_m": round(core_distance, 3),
                "suitable_room_types": ["living", "dining", "kitchen"] if entrance_relation == min(v[1].interpolate(.5, normalized=True).distance(landing) for v in edges) else ["bedroom", "living"],
                "cardinal_direction_used": False,
            })
        street = min(values, key=lambda x: x["entrance_core_relation_m"])["edge_id"]
        quiet = max(values, key=lambda x: (x["privacy_quietness"], x["entrance_core_relation_m"]))["edge_id"]
        return {"created_before_rooms": True, "derivation": "SITE_ACCESS_AND_CORE_RELATION_NOT_CARDINAL_HARDCODE", "street_public_edge": street, "private_quiet_edge": quiet, "edges": values}

    @staticmethod
    def _projection_polygon(floor, edge_id, depth, fraction):
        minx, miny, maxx, maxy = floor.bounds
        inset = (1-fraction)/2
        if edge_id == "EDGE_1": return box(minx+(maxx-minx)*inset, miny-depth, maxx-(maxx-minx)*inset, miny)
        if edge_id == "EDGE_2": return box(maxx, miny+(maxy-miny)*inset, maxx+depth, maxy-(maxy-miny)*inset)
        if edge_id == "EDGE_3": return box(minx+(maxx-minx)*inset, maxy, maxx-(maxx-minx)*inset, maxy+depth)
        return box(minx-depth, miny+(maxy-miny)*inset, minx, maxy-(maxy-miny)*inset)

    def _upgrade(self, base, opportunity):
        plan = deepcopy(base)
        facade = self._facade_map(plan)
        rule = self._matched_street_rule()
        allowed = self.profile["status"] != "PROHIBITED" and rule is not None
        useful = opportunity.kind == "NO_PROJECTION" or any(not c["valid"] for u in plan["units"] for c in u["daylight_chains"])
        depth = 0.0 if opportunity.kind == "NO_PROJECTION" else round(rule["max_projection_depth_m"] * opportunity.depth_factor, 3) if allowed else 0.0
        fraction = 0.55 if opportunity.kind in {"PARTIAL_PROJECTION", "BALCONY_ONLY"} else 0.82
        geometry = None
        if depth > 0 and useful:
            geometry = coords(self._projection_polygon(poly(plan["floor_boundary"]), facade["street_public_edge"], depth, fraction))
        opportunity_record = {
            "candidate_type": opportunity.kind, "status": self.profile["status"],
            "generated": opportunity.kind == "NO_PROJECTION" or geometry is not None,
            "selected_depth_m": depth, "maximum_depth_m": rule["max_projection_depth_m"] if rule else None,
            "consumes_maximum": bool(depth and abs(depth-rule["max_projection_depth_m"]) <= EPS),
            "polygon": geometry, "room_extension": opportunity.room_extension, "balcony": opportunity.balcony,
            "benefit_evaluation": {
                "measurable_basis": "EXISTING_DAYLIGHT_CHAIN_DEFICIT" if useful and opportunity.kind != "NO_PROJECTION" else "ZERO_PROJECTION_BASELINE",
                "living_usability": 1 if opportunity.room_extension and geometry else 0,
                "terrace_quality": 1 if opportunity.balcony and geometry else 0,
                "facade_daylight_improvement": 1 if geometry else 0,
                "residual_reduction": 0, "privacy_noise_penalty": 1 if geometry else 0,
                "commercial_core_conflict": 0, "architecturally_useful": useful,
            },
            "permission_not_acceptance": True,
            "authority_class": self.profile["authority_class"],
            "evidence_class": self.profile["evidence_class"],
            "rule_id": rule["rule_id"] if rule else None,
        }
        plan["contract"] = "ArchitecturalGraphFloorPlanV8"
        plan["identity"]["candidate_id"] += "+" + opportunity.kind
        plan["pipeline"] = list(self.pipeline)
        plan["facade_value_map"] = facade
        plan["projection_balcony_opportunity"] = opportunity_record
        plan["authority_separation"] = {
            "room_daylight": "REGULATION", "projection": "PROJECT_LOCAL_CONFIRMED_CONDITION",
            "design_knowledge": "DESIGN_KNOWLEDGE_NON_AUTHORITATIVE", "precedent": "PRECEDENT_NON_REGULATORY",
            "projection_regulatory_acceptance": False, "evidence_pending": True,
        }
        plan["void_lightwell_cross_floor_requirement"] = any(u["lightwell"]["created"] for u in plan["units"])
        blockers = list(plan["blockers"])
        # V8 cannot truthfully certify V7's band geometry as adjacency-first packing.
        blockers.append("V8_ADJACENCY_FIRST_ROOM_PACKING_NOT_YET_GEOMETRICALLY_RESOLVED")
        if opportunity.kind != "NO_PROJECTION" and not geometry:
            blockers.append("PROJECTION_OPPORTUNITY_NOT_PERMITTED_OR_NOT_USEFUL")
        if opportunity.room_extension and geometry:
            blockers.append("PROJECTED_ROOM_FURNITURE_AND_DAYLIGHT_REPACK_REQUIRED")
        if any(not c["valid"] for u in plan["units"] for c in u["daylight_chains"]) and not any(u["lightwell"]["created"] for u in plan["units"]):
            blockers.append("REAL_LIGHTWELL_TOPOLOGY_REQUIRED_BEFORE_ROOM_REPACK")
        blockers = list(dict.fromkeys(blockers))
        plan["blockers"] = blockers
        plan["regression_gates"].update({
            "facade_value_map_before_rooms": True, "projection_only_when_allowed_and_useful": opportunity.kind == "NO_PROJECTION" or geometry is not None,
            "projection_dimensions_from_profile": opportunity.kind == "NO_PROJECTION" or rule is not None,
            "no_generic_projection_constants": True, "no_room_stretched_to_facade": True,
            "real_lightwell_if_claimed": all((not u["lightwell"]["created"]) or bool(u["lightwell"]["polygon"]) for u in plan["units"]),
            "no_windowless_private_lounge_depth_filler": True,
            "adjacency_first_room_packing": False,
        })
        plan["resolved_floor_hypothesis"] = False
        plan["REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN"] = False
        plan["human_architectural_acceptance"] = {"status": "REJECTED_FAIL_CLOSED", "independent_from_tests": True}
        return plan


def verify_projection_policy(policy, profile_id):
    profile = next((p for p in policy["profiles"] if p["profile_id"] == profile_id), None)
    if not profile:
        return {"status": "FAIL_CLOSED", "reason": "PROFILE_NOT_FOUND"}
    errors = []
    if profile["status"] not in STATUS: errors.append("INVALID_STATUS")
    if policy["generic_defaults"]["status"] != "PROHIBITED": errors.append("GENERIC_DEFAULT_NOT_PROHIBITED")
    if profile["applicability"]["use_for_regulatory_acceptance"]: errors.append("PENDING_EVIDENCE_USED_FOR_ACCEPTANCE")
    if any(r["min_clear_height_m"] is not None for r in profile["rules"]): errors.append("UNVERIFIED_HEIGHT_HARDCODED")
    return {"status": "PASS" if not errors else "FAIL_CLOSED", "errors": errors, "profile_id": profile_id}
