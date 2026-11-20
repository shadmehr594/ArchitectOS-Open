from copy import deepcopy
from core.architecture.reasoning.generic_access_first_pilotis_search_v1 import GenericAccessFirstPilotisSearchV1

def test_access_first_is_deterministic_non_mutating_and_enforces_gates():
    domain={"polygon":[[0,0],[10,0],[10,20],[0,20]],"floor_scope":"ground_pilotis","evidence_status":"resolved","provenance":[{"source":"test-domain"}]}
    frontage={"segment":[[0,0],[10,0]],"status":"confirmed","provenance":[{"source":"test-frontage"}]}
    access={"vehicle_clear_width":3.5,"pedestrian_clear_width":1.2,"commercial_candidate_depth":4.0}
    cores=[{"candidate_id":"CORE-A","polygon":[[5.5,13],[9.5,13],[9.5,17],[5.5,17]]}]
    parking={"minimum_required_capacity":3,"stall_width":2.5,"stall_depth":5.0,"aisle_width":5.0,"vehicle_clear_width":3.5,"provenance":[{"source":"test-parking"}]}
    args=(domain,frontage,access,cores,parking,{"hypothesis_id":"H1","provenance":[{"source":"test"}]})
    frozen=deepcopy(args); a=GenericAccessFirstPilotisSearchV1().produce(*args); b=GenericAccessFirstPilotisSearchV1().produce(*args)
    assert args == frozen and a["input_mutated"] is False and a == b
    assert a["candidate_count"] >= 1 and a["selected_candidate"] is None
    assert all(all(c["gates"].values()) and c["parking_count"] >= 3 for c in a["candidates"])
