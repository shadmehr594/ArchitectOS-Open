from core.architecture.reasoning.architectural_brain_orchestrator_v1 import ArchitecturalBrainOrchestratorV1


def context(change="core", mandatory_pedestrian=False):
    return {"case_id": "SYNTHETIC-01", "floors": ["basement", "ground", "first", "second"],
            "changes": [{"element_type": change, "floor": "ground"}],
            "requirements": {"units_per_floor": 2, "dedicated_pedestrian_entrance_mandatory": mandatory_pedestrian},
            "spaces": [
                {"space_id": "SHOP", "space_type": "commercial", "zone": "public", "daylight_required": False},
                {"space_id": "LIVING", "space_type": "living", "zone": "public", "daylight_required": True,
                 "daylight_source_ids": ["COURT"], "daylight_ratio": .16},
                {"space_id": "BED", "space_type": "bedroom", "zone": "private", "daylight_required": True,
                 "daylight_source_ids": ["COURT"], "daylight_ratio": .14, "adjacent_to": ["LIVING"], "privacy_buffer": True},
                {"space_id": "STAIR", "space_type": "stair", "zone": "circulation", "daylight_required": False}],
            "daylight_sources": [{"source_id": "COURT", "active": True}],
            "lessons": [{"decision": "reject", "rationale": "core consumed valuable frontage",
                         "source": "architect_review", "approved": False}]}


def reasoners(mandatory=False):
    calls = []
    def runner(name, payload):
        def run(ctx, prior):
            calls.append(name)
            result = {"contract": name + "V1", **payload}
            if name == "pedestrian":
                result.update({"mode": "dedicated" if mandatory else "design_alternative",
                               "mandatory": mandatory})
            return result
        return run
    mapping = {
        "parking": runner("parking", {"stalls": [[0, 0]], "access": [[0, 0]], "approach": [[0, 0]],
                                        "continuous_maneuvering_field": [[0, 0]], "swept_path_role": "validator_only"}),
        "vehicle_movement": runner("vehicle_movement", {"status": "validated"}),
        "pedestrian": runner("pedestrian", {}), "daylight": runner("daylight", {"status": "evaluated"}),
        "privacy": runner("privacy", {"status": "evaluated"}),
        "commercial": runner("commercial", {"frontage": 6, "access": True, "effective_depth": 5,
                                                "largest_usable_rectangle": 24, "coherence": .9, "fragmentation": .1}),
        "core": runner("core", {"status": "evaluated"})}
    return mapping, calls


def test_core_change_invalidates_all_floors_and_regenerates_from_requirements():
    runners, calls = reasoners()
    result = ArchitecturalBrainOrchestratorV1().run(context(), runners)
    assert calls == list(ArchitecturalBrainOrchestratorV1.CAPABILITY_ORDER)
    assert result["topology_invalidation"]["affected_floors"] == context()["floors"]
    assert not result["topology_invalidation"]["local_patch_allowed"]
    assert result["redesign_scope"]["scope"] == "affected_topology_from_requirements"
    assert result["regeneration"]["seed"] == context()["requirements"]
    assert not result["regeneration"]["prior_geometry_used_as_seed"]


def test_daylight_court_removal_creates_deficits_and_cross_floor_invalidation():
    source = context("daylight_court"); source["daylight_sources"][0]["active"] = False
    result = ArchitecturalBrainOrchestratorV1().run(source, reasoners()[0])
    assert {x["space_id"] for x in result["daylight_deficit"]["deficits"]} == {"LIVING", "BED"}
    assert result["daylight_deficit"]["new_daylight_source_required"]
    assert result["architectural_critic"]["status"] == "revise"


def test_complete_parking_commercial_and_pedestrian_policy_are_preserved():
    optional = ArchitecturalBrainOrchestratorV1().run(context(), reasoners(False)[0])
    mandatory = ArchitecturalBrainOrchestratorV1().run(context(mandatory_pedestrian=True), reasoners(True)[0])
    assert optional["reasoner_evidence"]["parking"]["swept_path_role"] == "validator_only"
    assert optional["reasoner_evidence"]["pedestrian"]["mode"] == "design_alternative"
    assert mandatory["reasoner_evidence"]["pedestrian"]["mode"] == "dedicated"
    assert optional["architectural_critic"]["status"] == "pass"


def test_zoning_priority_memory_provenance_and_no_final_outputs():
    result = ArchitecturalBrainOrchestratorV1().run(context(), reasoners()[0])
    assert result["zoning"]["zones"]["private"] == ["BED"]
    assert result["resource_priority"]["ranked_spaces"][0]["space_id"] in {"BED", "LIVING", "SHOP"}
    assert result["case_lessons"][0]["provenance"]["source"] == "architect_review"
    assert not result["case_lessons"][0]["stable_knowledge_written"] and not result["stable_knowledge_mutated"]
    assert not result["final_selection_performed"] and not result["room_layout_generated"]
    assert not result["final_windows_generated"] and not result["bim_executed"] and not result["ifc_executed"]


def test_missing_healthy_reasoner_is_rejected_instead_of_silent_parallel_pipeline():
    runners, _ = reasoners(); runners.pop("privacy")
    try:
        ArchitecturalBrainOrchestratorV1().run(context(), runners)
    except ValueError as exc:
        assert "privacy" in str(exc)
    else:
        raise AssertionError("missing capability must fail closed")
