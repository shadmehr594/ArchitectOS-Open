"""Project-agnostic architectural intelligence contracts (geometry-generation free)."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json


TOPOLOGY_DEFINING = {
    "core", "stair", "elevator", "daylight_court", "main_circulation",
    "vehicle_access", "parking_field", "building_entrance", "service_shaft",
    "road", "frontage", "neighbors", "program", "requirements", "regulations",
    "access_requirement", "vertical_scope", "daylight_deficit",
}


class ResourcePriorityReasoning:
    """Allocate scarce architectural resources by need, never by input order."""
    DEFAULT_NEEDS = {
        "commercial": {"frontage": 1.0, "access": .9, "daylight": .45, "privacy": .1},
        "public": {"frontage": .75, "access": .8, "daylight": .8, "privacy": .3},
        "private": {"frontage": .35, "access": .45, "daylight": 1.0, "privacy": 1.0},
        "service": {"frontage": .05, "access": .65, "daylight": .1, "privacy": .2},
        "circulation": {"frontage": .05, "access": 1.0, "daylight": .15, "privacy": .1},
    }

    def rank(self, spaces, resource_values=None):
        values = {"frontage": 1.0, "access": 1.0, "daylight": 1.0, "privacy": 1.0}
        values.update(resource_values or {})
        ranked = []
        for space in spaces:
            zone = space.get("zone", "service")
            needs = deepcopy(self.DEFAULT_NEEDS.get(zone, self.DEFAULT_NEEDS["service"]))
            needs.update(space.get("resource_needs", {}))
            scores = {key: round(float(need) * float(values.get(key, 0)), 6) for key, need in needs.items()}
            ranked.append({"space_id": space["space_id"], "zone": zone, "resource_scores": scores,
                           "total_priority": round(sum(scores.values()), 6)})
        ranked.sort(key=lambda item: (-item["total_priority"], item["space_id"]))
        return {"contract": "ArchitecturalResourcePriorityV1", "ranked_spaces": ranked,
                "principle": "scarce_resources_follow_architectural_need"}


class TopologyInvalidationEngine:
    DEPENDENCIES = {
        "road": {"site_resource_region_derivation", "site_resource_map", "pre_realization_daylight_deficit", "scarcity_model", "allocation_plan", "opportunity_cost", "geometry_realization", "ownership_gate", "operational_feasibility", "contextual_quality", "architectural_critic", "decision_support_shortlist", "placement", "topology"},
        "frontage": {"site_resource_region_derivation", "site_resource_map", "pre_realization_daylight_deficit", "scarcity_model", "allocation_plan", "opportunity_cost", "geometry_realization", "ownership_gate", "operational_feasibility", "contextual_quality", "architectural_critic", "decision_support_shortlist", "placement", "topology"},
        "neighbors": {"site_resource_region_derivation", "site_resource_map", "pre_realization_daylight_deficit", "scarcity_model", "allocation_plan", "opportunity_cost", "geometry_realization", "ownership_gate", "operational_feasibility", "contextual_quality", "architectural_critic", "decision_support_shortlist", "placement", "topology"},
        "program": {"program_demand_profile", "pre_realization_daylight_deficit", "scarcity_model", "allocation_plan", "opportunity_cost", "operational_relationship_requirements", "geometry_realization", "ownership_gate", "operational_feasibility", "contextual_quality", "architectural_critic", "decision_support_shortlist", "placement", "topology"},
        "requirements": {"program_demand_profile", "pre_realization_daylight_deficit", "scarcity_model", "allocation_plan", "opportunity_cost", "operational_relationship_requirements", "geometry_realization", "ownership_gate", "operational_feasibility", "contextual_quality", "architectural_critic", "decision_support_shortlist", "placement", "topology"},
        "regulations": {"program_demand_profile", "pre_realization_daylight_deficit", "scarcity_model", "allocation_plan", "opportunity_cost", "operational_relationship_requirements", "geometry_realization", "ownership_gate", "operational_feasibility", "contextual_quality", "architectural_critic", "decision_support_shortlist", "placement", "topology"},
        "access_requirement": {"operational_relationship_requirements", "geometry_realization", "ownership_gate", "operational_feasibility", "contextual_quality", "architectural_critic", "decision_support_shortlist", "placement", "topology"},
        "vertical_scope": {"operational_relationship_requirements", "geometry_realization", "ownership_gate", "operational_feasibility", "contextual_quality", "architectural_critic", "decision_support_shortlist", "placement", "topology"},
        "daylight_deficit": {"operational_relationship_requirements", "geometry_realization", "ownership_gate", "operational_feasibility", "contextual_quality", "architectural_critic", "decision_support_shortlist", "placement", "topology"},
        "core": {"all_floors", "parking", "commercial", "pedestrian_access", "residential_access", "main_circulation"},
        "stair": {"all_floors", "core", "egress", "main_circulation", "parking", "commercial", "residential_access"},
        "elevator": {"all_floors", "core", "accessible_route", "main_circulation", "parking", "commercial", "residential_access"},
        "daylight_court": {"all_served_floors", "daylight", "privacy", "residential_envelopes", "terraces", "maintenance_access"},
        "main_circulation": {"all_connected_floors", "access", "zoning", "parking", "commercial", "residential_envelopes"},
        "vehicle_access": {"ground_floor", "parking", "approach", "continuous_maneuvering_field", "pedestrian_access", "commercial"},
        "parking_field": {"ground_floor", "stalls", "approach", "continuous_maneuvering_field", "pedestrian_access", "commercial", "core"},
        "building_entrance": {"ground_floor", "pedestrian_access", "commercial", "lobby", "main_circulation"},
        "service_shaft": {"all_served_floors", "service_zones", "wet_spaces", "residential_envelopes"},
    }

    def analyze(self, changes, floors):
        impacted, changed = set(), []
        for change in changes:
            element = change["element_type"]
            changed.append(element)
            impacted.update(self.DEPENDENCIES.get(element, {"local_geometry"}))
        topology_changed = bool(TOPOLOGY_DEFINING.intersection(changed))
        affected_floors = list(floors) if topology_changed and any(x.startswith("all_") for x in impacted) else sorted(
            {c.get("floor") for c in changes if c.get("floor") is not None})
        whole = any(x in changed for x in ("core", "stair", "elevator", "main_circulation"))
        multi = topology_changed and (whole or any(x.startswith("all_") for x in impacted))
        scope = "WHOLE_BUILDING" if whole else ("MULTI_FLOOR" if multi else ("FLOOR" if affected_floors else "LOCAL"))
        return {"contract": "TopologyInvalidationV1", "topology_changed": topology_changed,
                "changed_elements": changed, "invalidated_dependencies": sorted(impacted),
                "affected_floors": affected_floors, "dependency_scope": scope,
                "local_patch_allowed": not topology_changed}


class RedesignScopeResolver:
    def resolve(self, impact, requirements):
        cross_floor = len(impact.get("affected_floors", [])) > 1
        major = cross_floor or len(impact.get("invalidated_dependencies", [])) >= 5
        scope = "affected_topology_from_requirements" if major else (
            "affected_system_regeneration" if impact.get("topology_changed") else "local_reconsideration")
        return {"contract": "ArchitecturalRedesignScopeV1", "major_impact": major,
                "scope": scope, "geometry_reuse_allowed": not major,
                "regeneration_seed": deepcopy(requirements) if major else None,
                "instruction": "regenerate_from_requirements" if major else "re_evaluate_affected_dependencies"}


class DaylightDeficitIntelligence:
    def evaluate(self, spaces, daylight_sources, minimum_ratio=.12):
        deficits = []
        source_ids = {source["source_id"] for source in daylight_sources if source.get("active", True)}
        for space in spaces:
            if not space.get("daylight_required", False):
                continue
            served = set(space.get("daylight_source_ids", [])).intersection(source_ids)
            ratio = float(space.get("daylight_ratio", 0))
            if not served or ratio < minimum_ratio:
                deficits.append({"space_id": space["space_id"], "served_sources": sorted(served),
                                 "daylight_ratio": ratio, "deficit": round(max(0, minimum_ratio-ratio), 6)})
        return {"contract": "DaylightDeficitIntelligenceV1", "deficits": deficits,
                "new_daylight_source_required": bool(deficits),
                "required_action": "generate_daylight_source_alternatives" if deficits else "preserve_sources"}


class PublicPrivateServiceZoning:
    def classify(self, spaces):
        zones = {"PUBLIC": [], "TRANSITION": [], "PRIVATE": [], "SERVICE": []}
        for space in spaces:
            zone = space.get("zone") or self._infer(space.get("space_type", ""))
            canonical = {"public":"PUBLIC", "private":"PRIVATE", "service":"SERVICE",
                         "circulation":"TRANSITION", "transition":"TRANSITION"}.get(str(zone).lower(), str(zone).upper())
            zones.setdefault(canonical, []).append(space["space_id"])
        conflicts = []
        by_id = {s["space_id"]: s for s in spaces}
        for space in spaces:
            if (space.get("zone") or self._infer(space.get("space_type", ""))) != "private":
                continue
            for neighbor in space.get("adjacent_to", []):
                other = by_id.get(neighbor, {})
                if (other.get("zone") or self._infer(other.get("space_type", ""))) == "public" and not space.get("privacy_buffer"):
                    conflicts.append({"private_space": space["space_id"], "public_space": neighbor,
                                      "reason": "public_private_contact_without_buffer"})
        legacy = {"public": list(zones["PUBLIC"]), "private": list(zones["PRIVATE"]),
                  "service": list(zones["SERVICE"]), "circulation": list(zones["TRANSITION"])}
        return {"contract": "PublicPrivateServiceZoningV1", "zones": legacy,
                "canonical_zones": zones, "sequence": "before_room_geometry", "privacy_conflicts": conflicts}

    @staticmethod
    def _infer(space_type):
        value = space_type.lower()
        if any(x in value for x in ("bed", "private", "master")): return "private"
        if any(x in value for x in ("living", "reception", "commercial", "shop")): return "public"
        if any(x in value for x in ("corridor", "lobby", "stair", "elevator")): return "circulation"
        return "service"


class ArchitecturalCritic:
    """Critique architectural evidence; polygon validity alone can never pass."""
    REQUIRED_EVIDENCE = ("parking", "vehicle_movement", "pedestrian", "daylight", "privacy", "commercial", "core")

    CONTEXTUAL_CONTRACTS = ("ContextualSiteResourceMapV1", "ContextualProgramDemandProfileV1",
        "ResourceScarcityAndCompetitionV1", "ContextualSpatialAllocationPlannerV1", "OpportunityCostEvaluatorV1")

    def review(self, evidence, zoning, daylight, contextual=None, ownership=None, operational=None):
        issues = []
        for capability in self.REQUIRED_EVIDENCE:
            if capability not in evidence:
                issues.append({"severity": "hard", "code": f"missing_{capability}_reasoning"})
        parking = evidence.get("parking", {})
        if parking and not all(parking.get(k) for k in ("stalls", "access", "approach", "continuous_maneuvering_field")):
            issues.append({"severity": "hard", "code": "parking_is_not_complete_operational_field"})
        if parking.get("swept_path_role") not in (None, "validator_only"):
            issues.append({"severity": "hard", "code": "swept_path_used_as_generator"})
        commercial = evidence.get("commercial", {})
        required = ("frontage", "access", "effective_depth", "largest_usable_rectangle", "coherence", "fragmentation")
        if commercial and not all(k in commercial for k in required):
            issues.append({"severity": "hard", "code": "commercial_viability_evidence_incomplete"})
        if commercial and (not commercial.get("viable", True) or commercial.get("largest_usable_rectangle", 0) <= 0):
            issues.append({"severity": "hard", "code": "commercial_not_architecturally_viable"})
        issues += [{"severity": "hard", "code": "daylight_deficit_unresolved", "space_id": x["space_id"]}
                   for x in daylight.get("deficits", [])]
        issues += [{"severity": "quality", "code": x["reason"], **x} for x in zoning.get("privacy_conflicts", [])]
        if contextual is not None:
            seen={value.get("contract"):value for value in contextual.values()}
            for contract in self.CONTEXTUAL_CONTRACTS:
                if contract not in seen:
                    issues.append({"severity":"quality","code":"missing_contextual_contract","contract":contract})
                elif not seen[contract].get("complete", False):
                    issues.append({"severity":"quality","code":"incomplete_contextual_contract","contract":contract})
        if ownership and ownership.get("hard_validation_status") != "hard_valid":
            issues.append({"severity":"hard","code":"ownership_not_feasible",
                           "hard_failure_codes":ownership.get("hard_failure_codes",[])})
        if operational and operational.get("hard_validation_status") != "hard_valid":
            issues.append({"severity":"hard","code":"operational_feasibility_failed",
                           "hard_failure_codes":operational.get("hard_failure_codes",[])})
        return {"contract": "ArchitecturalCriticV1", "status": "pass" if not issues else "revise",
                "issues": issues, "polygon_validity_is_sufficient": False,
                "contextual_weakness_is_hard_ownership_failure":False}


class CaseLessonMemory:
    def record(self, case_id, decision, rationale, source, approved=False):
        payload = {"case_id": case_id, "decision": decision, "rationale": rationale,
                   "provenance": {"source": source, "recorded_at": datetime.now(timezone.utc).isoformat()},
                   "approved_for_consolidation": bool(approved), "stable_knowledge_written": False}
        payload["lesson_id"] = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
        return payload
