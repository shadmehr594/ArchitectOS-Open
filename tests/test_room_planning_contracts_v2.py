from copy import deepcopy
from pathlib import Path
import hashlib, json, sys

ROOT = Path(r"<repo-root>")
sys.path.insert(0, str(ROOT))
from core.architecture.contracts.room_planning_contracts_v2 import *


def evidence(status=EvidenceStatus.VERIFIED_APPLICABLE):
    return EvidenceRef("e", ProvenanceClass.REGULATION, status, "c", 1, 2, "applicable")


def valid_contract():
    room = ResolvedRoom("bed", "bedroom", True, True, True, True, True, True, None)
    return RoomPlanningContract(
        rooms=(room,),
        doors=(Door("entry", "common", "threshold", "hb0", {"type":"segment"}, True), Door("bed-door", "bed", "private", "hb1", {"type":"segment"}, True)),
        sources=(DaylightSource("ext", "EXTERIOR_EDGE", {"type":"segment"}, "natural"),),
        windows=(Window("win", "bed", "ext", "hb2", {"type":"segment"}, None, True, None),),
        voids=(),
        allocation=AllocationAccounting(10, 8, 1, 0, 1),
        unit_threshold_space_id="threshold", common_corridor_space_id="common",
        private_circulation_space_ids=("private",),
        building_program_provenance=ProvenanceClass.DESIGN_KNOWLEDGE_NON_AUTHORITATIVE,
    )


def test_contract_pass_and_no_mutation():
    c=valid_contract(); before=deepcopy(c); a=validate_contract(c); b=validate_contract(c)
    assert a==b and c==before and a["status"]=="PASS"
    assert a["room_source_window_graph"] == (("bed", "ext", "win"),)


def test_fail_closed_no_numeric_promotion_and_no_fake_daylight():
    c=valid_contract(); bad_window=Window("win", "bed", "ext", "hb2", {"type":"segment"}, 1.0, True, evidence(EvidenceStatus.UNVERIFIED_AUTHORITY))
    bad=RoomPlanningContract(**{**c.__dict__, "windows":(bad_window,)})
    assert "UNAUTHORIZED_NUMERIC_OPENING_PROMOTION:win" in validate_contract(bad)["errors"]
    missing=RoomPlanningContract(**{**c.__dict__, "windows":()})
    assert "NO_ROOM_SOURCE_WINDOW_CHAIN:bed" in validate_contract(missing)["errors"]


def test_door_graph_habitable_access_and_threshold_gate():
    c=valid_contract(); doors=(Door("entry", "common", "threshold", "h", {"type":"segment"}, True), Door("bad", "bed", "living", "h2", {"type":"segment"}, True))
    living=ResolvedRoom("living", "living", True, True, True, True, False, True, None)
    bad=RoomPlanningContract(**{**c.__dict__, "rooms":c.rooms+(living,), "doors":doors})
    errors=validate_contract(bad)["errors"]
    assert "HABITABLE_ROOM_ACCESS_ONLY_THROUGH_HABITABLE_ROOM:bed" in errors


def test_lightwell_served_room_and_allocation_accounting():
    c=valid_contract(); src=DaylightSource("lw", "LIGHTWELL", {"type":"polygon"}, "natural")
    void=LightwellPatioVoid("lw", "LIGHTWELL", {"type":"polygon"}, 2, ("bed",), True, True, True)
    good=RoomPlanningContract(**{**c.__dict__, "sources":(src,), "windows":(Window("w","bed","lw","h",{"type":"segment"},None,True,None),), "voids":(void,), "allocation":AllocationAccounting(10,6,1,2,1)})
    assert validate_contract(good)["status"]=="PASS"
    bad_void=LightwellPatioVoid("lw", "LIGHTWELL", {"type":"polygon"}, 2, ("bed",), False, True, True)
    bad=RoomPlanningContract(**{**good.__dict__, "voids":(bad_void,)})
    assert "VOID_NOT_COUNTED_IN_ALLOCATION:lw" in validate_contract(bad)["errors"]


def test_no_promotion_no_geometry_and_authority_evidence_fail_closed():
    c=valid_contract()
    promoted=RoomPlanningContract(**{**c.__dict__, "building_program_provenance":ProvenanceClass.REGULATION})
    assert "BUILDING_PROGRAM_KNOWLEDGE_PROMOTED" in validate_contract(promoted)["errors"]
    geom=RoomPlanningContract(**{**c.__dict__, "room_level_v2_geometry_generated":True})
    assert "ROOM_LEVEL_V2_GEOMETRY_FORBIDDEN_AT_CONTRACT_GATE" in validate_contract(geom)["errors"]
    ev=json.loads((ROOT/"core/architecture/contracts/room_daylight_authority_evidence_v2.json").read_text(encoding="utf-8"))
    assert ev["national_authority"]["repository_file_status"]=="ABSENT"
    assert all(r["status"]=="UNVERIFIED_AUTHORITY" for r in ev["national_authority"]["records"])
    assert ev["local_authority"]["override_status"]=="NOT_APPLIED"
    assert ev["resolved_regulatory_values"]=={}


def test_historical_targets_match_pretest_manifest():
    manifest=json.loads((ROOT/"core/architecture/contracts/room_planning_v2_immutability_baseline.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        data=(ROOT/item["path"]).read_bytes()
        assert len(data)==item["size"] and hashlib.sha256(data).hexdigest()==item["sha256"]
