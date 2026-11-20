from copy import deepcopy

from core.architecture.reasoning.pilotis_parking_design_producer_v1 import PilotisParkingDesignProducerV1
from core.architecture.reasoning.pilotis_parking_architectural_acceptance_v1 import PilotisParkingArchitecturalAcceptanceV1
from core.architecture.reasoning.pilotis_parking_validated_result_adapter_v1 import PilotisParkingValidatedResultAdapterV1
from core.architecture.reasoning.validated_design_result_authority_promotion_v1 import ValidatedDesignResultAuthorityPromotionV1


def raw(count=3):
    return {"candidate_id": "PILOTIS-GENERIC-01", "candidate_geometry_status": "candidate_complete",
            "stall_geometries": [{"stall_id": f"S{i+1}", "polygon": [[i, 0], [i+1, 0], [i+1, 2], [i, 2]]} for i in range(count)],
            "vehicle_access_evidence": {"status": "resolved", "endpoint": [0, 0], "evidence": [{"source": "generic_access"}]},
            "manoeuvre_aisle_circulation_evidence": {"status": "resolved", "connected": True, "evidence": [{"source": "generic_movement"}]},
            "stall_ingress_egress_evidence": {"status": "resolved", "all_stalls_independently_usable": True, "evidence": [{"source": "stall_validation"}]},
            "pedestrian_safety_evidence": {"status": "clear", "mandatory_route_blocked": False, "conflicts": [], "evidence": [{"source": "pedestrian_protection"}]},
            "compatibility_evidence": {"inventory_complete": True, "core": "clear", "entrance": "clear", "protected_zone": "clear", "commercial": "clear", "public_use": "clear", "private_use": "clear", "conflicts": [], "evidence": [{"source": "ground_program_ownership"}]}}


def produce(candidate=None):
    return PilotisParkingDesignProducerV1().produce("H1", "pilotis", [candidate or raw()],
        [{"source": "project_requirement", "id": "minimum_required_parking_capacity", "value": 3}],
        {"ramp_not_required": "same_level_vehicle_access_hypothesis"})


def accept(candidate=None):
    p = produce(candidate)
    return p, PilotisParkingArchitecturalAcceptanceV1().evaluate(p, "PILOTIS-GENERIC-01", 3)


def promote(p, a, selected=True):
    selection = {"candidate_id": "PILOTIS-GENERIC-01",
                 "selected_status": "selected" if selected else "not_selected",
                 "selection_evidence": ([{"source": "explicit_hypothesis_selection", "hypothesis_id": "H1"}] if selected else [])}
    adapted = PilotisParkingValidatedResultAdapterV1().adapt(p, a, selection)
    return adapted, ValidatedDesignResultAuthorityPromotionV1().promote(
        adapted.get("candidate"), 3, {"hypothesis_id": "H1", "target_capacity": 3})


def test_valid_three_accepts_and_promotes_only_after_explicit_selection():
    p, a = accept()
    assert a["validation_status"] == "accepted" and a["certified_achieved_capacity"] == 3
    _, forbidden = promote(p, a, False)
    assert forbidden["promotion_status"] == "forbidden"
    adapted, promoted = promote(p, a, True)
    assert adapted["geometry_copied"] is False
    assert promoted["authoritative_project_fact"]["value"] == 3
    assert p["basement_deleted"] is False and a["basement_necessity_evaluated"] is False


def test_two_stalls_fails_minimum():
    _, a = accept(raw(2))
    assert a["validation_status"] == "failed" and "minimum_capacity" in a["failed_checks"]


def test_mandatory_pedestrian_route_or_core_entrance_conflict_fails():
    for change in ("pedestrian", "core"):
        candidate = raw()
        if change == "pedestrian":
            candidate["pedestrian_safety_evidence"].update(status="conflict", mandatory_route_blocked=True, conflicts=["mandatory-route"])
        else:
            candidate["compatibility_evidence"].update(core="conflict", entrance="conflict", conflicts=["core", "entrance"])
        _, a = accept(candidate)
        assert a["validation_status"] == "failed"


def test_disconnected_manoeuvre_fails():
    candidate = raw(); candidate["manoeuvre_aisle_circulation_evidence"]["connected"] = False
    _, a = accept(candidate)
    assert "connected_manoeuvre_aisle_circulation" in a["failed_checks"]


def test_invalid_stall_ingress_egress_fails():
    candidate = raw(); candidate["stall_ingress_egress_evidence"]["all_stalls_independently_usable"] = False
    _, a = accept(candidate)
    assert "stall_ingress_egress" in a["failed_checks"]


def test_selected_but_failed_validation_cannot_promote():
    p, a = accept(raw(2))
    adapted, promoted = promote(p, a, True)
    assert adapted["status"] == "rejected" and promoted["promotion_status"] == "forbidden"


def test_forged_acceptance_or_capacity_mismatch_cannot_promote():
    p, a = accept()
    for change in ({"automated_geometry_pass": False},
                   {"accepted_result_evidence": []},
                   {"certified_achieved_capacity": 4}):
        forged = deepcopy(a); forged.update(change)
        adapted, promoted = promote(p, forged, True)
        assert adapted["status"] == "rejected"
        assert promoted["promotion_status"] == "forbidden"


def test_unknown_ground_use_conflict_fails_closed_and_inputs_are_not_mutated():
    candidate = raw(); candidate["compatibility_evidence"].pop("commercial")
    before = deepcopy(candidate); p, a = accept(candidate)
    assert candidate == before and a["validation_status"] == "failed"
    assert p["selection_status"] == "not_performed" and p["promotion_status"] == "not_performed"


def test_producer_ranking_is_deterministic_without_auto_selection():
    first = raw(3); first["candidate_id"] = "B"
    second = raw(3); second["candidate_id"] = "A"
    p = PilotisParkingDesignProducerV1().produce("H1", "ground_level_parking", [first, second],
        [{"source": "project_requirement"}], {"ramp_not_required": "same_level_vehicle_access_hypothesis"})
    assert [x["candidate_id"] for x in p["candidates"]] == ["A", "B"]
    assert p["selected_candidate"] is None and p["selection_status"] == "not_performed"
