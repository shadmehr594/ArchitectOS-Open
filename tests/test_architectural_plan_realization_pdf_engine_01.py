import json
from pathlib import Path
from core.architecture.drawing import ArchitecturalPlanRealizer

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'outputs'/'MULTI_CANDIDATE_RESIDENTIAL_DESIGN_TEST_20260920_01'

def candidates(): return [json.loads((SRC/f'CANDIDATE_{x}_FULL.json').read_text(encoding='utf-8')) for x in 'ABCD']
def test_topologies_distinct_and_unchanged(): assert len({c['family'] for c in candidates()})==4
def test_wall_graph_deduplicated_connected():
    for c in candidates():
        s=ArchitecturalPlanRealizer().realize(c); assert s.metadata['wall_audit']['shared_boundaries_deduplicated']; assert s.metadata['wall_audit']['junctions_connected']; assert not s.metadata['wall_audit']['duplicate_overlapping_walls']
def test_openings_and_symbols_realized():
    for c in candidates():
        s=ArchitecturalPlanRealizer().realize(c); assert any(p.layer=='DOORS' and p.kind=='ARC' for p in s.primitives); assert any(p.layer=='WINDOWS' and p.metadata['host_valid'] for p in s.primitives); assert any(p.layer=='FURNITURE' and p.geometry.get('symbol') for p in s.primitives)
def test_kitchen_configurations(): assert [c['kitchen'] for c in candidates()]==['L_SHAPED','U_SHAPED','PENINSULA','ISLAND']
