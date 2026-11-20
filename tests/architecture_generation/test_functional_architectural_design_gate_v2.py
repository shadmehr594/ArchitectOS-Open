import pytest
from core.architecture.reasoning.functional_architectural_design_gate_v2 import Parcel2FunctionalArchitecturalGateV2, rev02_negative_fixture

@pytest.fixture
def c():
    return Parcel2FunctionalArchitecturalGateV2().build()

def test_01_commercial_south(c): assert c['validation']['checks']['commercial_south_frontage']
def test_02_access_south(c): assert c['validation']['checks']['access_begins_south']
def test_03_core_aligned(c): assert c['validation']['checks']['vertical_core_stack']
def test_04_same_level_landings(c): assert all(c['validation']['checks'][f'safe_landing_{x}'] for x in ('G','R1','R2','ROOF'))
def test_05_no_entry_to_void(c): assert all(v for k,v in c['validation']['checks'].items() if k.startswith('entry_landing_'))
def test_06_terraces_not_neighbor(c): assert c['validation']['checks']['terraces_valid']
def test_07_lightwell_not_south(c): assert c['validation']['checks']['lightwell_not_south']
def test_08_lightwell_aligned(c): assert c['validation']['checks']['lightwell_aligned']
def test_09_public_south_or_terrace(c): assert all(s.get('exposure') in {'SOUTH_STREET','SOUTH_TERRACE'} for s in c['spaces'] if s['semantic'] in {'LIVING_RECEPTION','OPEN_LIVING_KITCHEN','OPEN_KITCHEN_DINING'})
def test_10_bed_window_touches_lightwell(c): assert all(v for k,v in c['validation']['checks'].items() if k.startswith('window_host_'))
def test_11_room_to_room_window_rejected(c): assert all(w['exposure']=='SOUTH_STREET' or 'LIGHTWELL' in w['exposure'] for w in c['window_intents'])
def test_12_bed_to_bed_window_rejected(c): assert not any('BED' in w['exposure'] for w in c['window_intents'])
def test_13_no_neighbor_windows(c): assert all(v for k,v in c['validation']['checks'].items() if k.startswith('window_constrained_'))
def test_14_door_threshold_shared(c): assert all(v for k,v in c['validation']['checks'].items() if k.startswith('door_host_'))
def test_15_open_plan_no_door(c): assert c['validation']['checks']['open_plan_no_fake_doors']
def test_16_south_paths(c): assert all(v for k,v in c['validation']['checks'].items() if k.startswith('south_path_'))
def test_17_r1_graph(c): assert all(v for k,v in c['validation']['checks'].items() if k.startswith('r1_path_'))
def test_18_r2_independent(c): assert all(v for k,v in c['validation']['checks'].items() if k.startswith('r2_path_'))
def test_19_no_cross_unit(c): assert c['validation']['checks']['no_cross_unit_private_opening']
def test_20_rev02_fixture_fails():
    f=rev02_negative_fixture(); assert f['must_fail_readiness'] and f['status']=='REJECTED' and 'VERTICAL_CORE_STACK_MISALIGNMENT' in f['failure_family']
def test_21_candidate_passes_but_human_pending(c): assert c['validation']['passed'] and c['acceptance']['software_architectural_readiness']=='PASS' and c['acceptance']['human_architectural_acceptance']=='PENDING'
def test_22_four_floors(c): assert c['validation']['checks']['four_floor_complete']
def test_23_width_contract(c): assert c['validation']['checks']['shared_route_contract']
def test_24_guides_are_not_walls(c): assert all(g['render_as']=='GUIDE_ONLY' for g in c['access_guide_overlays'])
def test_25_access_route_geometrically_clear(c): assert c['validation']['checks']['continuous_free_access_route']
def test_26_maneuver_touches_all_bays(c): assert c['validation']['checks']['maneuver_reaches_all_bays']
