from shapely.geometry import Polygon

from core.architecture.reasoning.architectural_reasoning_upgrade_v1 import (
    ArchitecturalConstraintPropagationGraph, ArchitecturalSpaceRoleInference,
    CommercialViabilityIntelligence, CorePlacementReasoning,
    ParkingFieldTopologyIntelligence, ResidentialEnvelopeQualityIntelligence,
)


def stalls(count, horizontal=True):
    if horizontal:
        return [[(0,i*2.5),(5,i*2.5),(5,(i+1)*2.5),(0,(i+1)*2.5)] for i in range(count)]
    return [[(i*2.5,0),((i+1)*2.5,0),((i+1)*2.5,5),(i*2.5,5)] for i in range(count)]


def test_parking_field_scales_continuously_for_one_to_four_stalls():
    intel=ParkingFieldTopologyIntelligence()
    areas=[]
    for n in (1,2,3,4):
        r=intel.derive(stalls(n),"west",(5,2.5),{"turning_depth":4.8})
        f=Polygon(r["circulation_field"]);areas.append(f.area)
        assert r["stall_count"]==n and len(r["groups"])==1
        assert abs((f.bounds[3]-f.bounds[1])-n*2.5)<1e-6
        assert r["dimension_source"]=="stall_array_plus_vehicle_turning_requirements"
    assert areas==sorted(areas) and len(set(areas))==4


def test_parking_field_changes_axis_with_stall_orientation_and_access():
    r=ParkingFieldTopologyIntelligence().derive(stalls(3,False),"south",(5,2.5),{"aisle_depth":5.2})
    f=Polygon(r["circulation_field"])
    assert r["orientation"]=="long_axis_north_south"
    assert abs((f.bounds[2]-f.bounds[0])-7.5)<1e-6
    assert abs((f.bounds[3]-f.bounds[1])-5.2)<1e-6


def test_commercial_requires_frontage_access_and_usable_shape():
    good=[(0,0),(6,0),(6,5),(0,5)]
    no_front=[(0,2),(6,2),(6,5),(0,5)]
    sliver=[(0,0),(6,0),(6,.25),(1,.25),(1,5),(0,5)]
    r=CommercialViabilityIntelligence().evaluate([good,no_front,sliver],[(0,0),(8,0)],[(1,0)])
    assert r["components"][0]["viable"]
    assert "no_frontage" in r["components"][1]["reasons"]
    assert not r["components"][2]["viable"]


def test_role_inference_does_not_treat_vehicle_or_core_leftover_as_commercial():
    leftovers=[Polygon([(0,0),(4,0),(4,2),(0,2)]),Polygon([(5,1),(6,1),(6,4),(5,4)])]
    r=ArchitecturalSpaceRoleInference().infer(leftovers,[(0,0),(4,0),(4,2),(0,2)],[(6,1),(7,1),(7,4),(6,4)],[(0,0),(8,0)])
    assert [x["role"] for x in r["spaces"]]==["vehicle_circulation","common_service"]


def test_residential_envelope_quality_distinguishes_good_direct_and_bad_angled():
    intel=ResidentialEnvelopeQualityIntelligence();court=[(8,2),(9,2),(9,5),(8,5)]
    good=intel.evaluate([(0,0),(8,0),(8,7),(0,7)],[[(0,0),(8,0)]],court,[(0,3),(4,3),(8,3)])
    bad=intel.evaluate([(0,0),(8,0),(8,1),(2,1),(2,7),(0,7)],[[(0,0),(8,0)]],court,[(0,3),(1,3),(2,4),(5,4),(8,3)])
    assert good["quality_score"]>bad["quality_score"]
    assert "artificial_angled_court_access" in bad["quality_penalties"]
    assert "court_not_directly_accessible" in bad["quality_penalties"]


def test_core_reasoning_uses_shared_cross_floor_feasible_region():
    core={"polygon":[(0,0),(3,0),(3,3),(0,3)],"stair":[(0,0),(1.5,0),(1.5,3),(0,3)],"elevator":[(1.5,0),(3,0),(3,1.5),(1.5,1.5)],"lobby":[(1.5,1.5),(3,1.5),(3,3),(1.5,3)]}
    r=CorePlacementReasoning().generate([(0,0),(12,0),(12,12),(0,12)],core,[[(0,4),(12,4),(12,8),(0,8)]],[[(0,8),(4,8),(4,12),(0,12)]],step=1)
    assert r["candidates"]
    for c in r["candidates"][:5]:
        assert set(("stair","elevator","lobby"))<=set(c["core"])


def test_constraint_graph_regenerates_every_dependency_in_order():
    callbacks={n:(lambda state,n=n:{"node":n,"upstream_count":len(state)}) for n in ArchitecturalConstraintPropagationGraph.ORDER}
    r=ArchitecturalConstraintPropagationGraph().regenerate({"seed":1},callbacks)
    assert r["all_dependencies_regenerated"] and list(r["revisions"])==list(ArchitecturalConstraintPropagationGraph.ORDER)


def test_unified_parking_field_covers_full_array_for_ns_ew_one_to_four():
    intel=ParkingFieldTopologyIntelligence()
    for horizontal,direction in ((True,"west"),(True,"east"),(False,"south"),(False,"north")):
        for count in (1,2,3,4):
            raw=stalls(count,horizontal);array=Polygon(raw[0])
            for item in raw[1:]:array=array.union(Polygon(item))
            result=intel.derive(raw,direction,(5,2.5),{"turning_depth":4.8})
            field=Polygon(result["circulation_field"])
            assert result["stall_count"]==count
            if horizontal: assert abs((field.bounds[3]-field.bounds[1])-(array.bounds[3]-array.bounds[1]))<1e-6
            else: assert abs((field.bounds[2]-field.bounds[0])-(array.bounds[2]-array.bounds[0]))<1e-6


def test_propagation_executes_fresh_callbacks_for_each_candidate():
    calls=[]
    def run(candidate):
        callbacks={node:(lambda state,node=node:(calls.append((candidate,node)),{"candidate":candidate,"node":node,"upstream":len(state)})[1]) for node in ArchitecturalConstraintPropagationGraph.ORDER}
        return ArchitecturalConstraintPropagationGraph().regenerate({"candidate_id":candidate},callbacks)
    first,second=run("A"),run("B")
    assert len(calls)==2*len(ArchitecturalConstraintPropagationGraph.ORDER)
    assert not first["candidate_state_reuse"] and not second["candidate_state_reuse"]
    assert first["revisions"]!=second["revisions"]
    assert all(v["executed"] for v in second["executions"].values())
