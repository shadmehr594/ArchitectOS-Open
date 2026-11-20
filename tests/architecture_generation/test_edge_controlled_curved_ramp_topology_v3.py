import json
from pathlib import Path

from core.architecture.reasoning.edge_controlled_curved_ramp_topology_v3 import EdgeControlledCurvedRampTopologyV3
from core.architecture.reasoning.authoritative_ramp_endpoint_binding_contract_v1 import AuthoritativeRampEndpointBindingContractV1
from core.architecture.reasoning.project_level_contract_v1 import ProjectLevelContractV1


def binding():
    confirmations=[{"kind":"level_elevation","level":key,"value":value,"unit":"m",
        "authority_class":"PROJECT_REQUIREMENT","provenance":["test_project_requirement"]}
        for key,value in (("ramp_start",0.0),("ramp_arrival",-2.4))]
    return AuthoritativeRampEndpointBindingContractV1().resolve(
        ProjectLevelContractV1().resolve(confirmations=confirmations))


def real_result():
    root=Path(__file__).resolve().parents[2]
    source=sorted((root/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1]
    data=json.loads(source.read_text());data['requirements']['ramp']['minimum_inner_turn_radius']=5.
    return EdgeControlledCurvedRampTopologyV3().resolve(data['site']['parcel'],data['site']['frontage'],data['physical_basement_wall'],data['requirements'],{'status':'required','slope':.15,'authoritative_ramp_endpoint_binding':binding()})


def test_new_generator_never_reuses_old_candidate_set():
    result=real_result()
    assert result['old_candidates_reused'] is False
    assert result['new_search_source']!='FarEndOperationalTurnV2_198_candidates'
    assert all(c['candidate_id'].startswith('ECV3-') for c in result['candidates'])


def test_generation_is_controlled_by_shortest_physical_edge():
    result=real_result();valid=[c for c in result['candidates'] if c['candidate_id'] in result['length_valid_candidates']]
    assert valid
    assert all(c['physical_path_length']['shortest_physical_path']>=16-1e-7 for c in valid)
    assert any(c['physical_path_length']['centerline_length']>16 for c in valid)


def test_operational_candidates_have_full_interface_and_parking_still_waits_by_scope():
    result=real_result()
    valid=[c for c in result['candidates'] if c['candidate_id'] in result['operational_candidates']]
    assert valid
    assert all(c['operational_end']['interface_length']>=3-1e-7 for c in valid)
    assert all(c['maneuvering_dimensions'] in ([5.0,5.0],[4.5,4.5]) for c in valid)
    assert all(c['parking_search_status']=='not_run_by_scope' for c in valid)


def test_terminal_leg_is_a_real_search_variable():
    result=real_result();valid=[c for c in result['candidates'] if c['candidate_id'] in result['operational_candidates']]
    assert any(c['topology']['leg_2_length']>.5 for c in valid)


def test_repeat_is_deterministic():
    a=real_result();b=real_result()
    assert a['length_valid_candidates']==b['length_valid_candidates']
    assert a['geometric_maximum']==b['geometric_maximum']
