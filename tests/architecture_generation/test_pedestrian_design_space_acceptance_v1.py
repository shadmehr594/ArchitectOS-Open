from shapely.geometry import box

from core.architecture.reasoning.architectural_reasoning_upgrade_v1 import (
    ArchitecturalConstraintPropagationGraph,
    EntranceImpactEvaluation,
)


def _impact(corridor, vehicle=()):
    commercial = [box(0, 0, 12, 8)]
    after = [box(0, 0, 12, 8).difference(corridor)]
    return EntranceImpactEvaluation().evaluate(
        commercial, after, {"frontage_edge": [[0, 0], [12, 0]]},
        [[corridor.centroid.x, 0], [corridor.centroid.x, 8]], corridor,
        box(10, 6, 12, 8), (), vehicle, True,
    )


def test_no_dedicated_family_remains_and_has_detectable_advantage_when_it_preserves_commercial():
    evaluator = EntranceImpactEvaluation()
    no_dedicated = evaluator.evaluate([box(0, 0, 12, 8)], [box(0, 0, 12, 8)], {"frontage_edge": [[0, 0], [12, 0]]})
    damaging = _impact(box(5, 0, 7, 8))
    ranked = evaluator.rank_design_space(no_dedicated, [damaging], mandatory=False)
    assert ranked[0]["pedestrian_mode"] == "NO_DEDICATED_PEDESTRIAN_ENTRANCE"
    assert {x["pedestrian_mode"] for x in ranked} == {"NO_DEDICATED_PEDESTRIAN_ENTRANCE", "DEDICATED_PEDESTRIAN_ENTRANCE"}


def test_mandatory_dedicated_hard_rejects_mode_a_and_ranks_least_damage_candidate_first():
    evaluator = EntranceImpactEvaluation()
    no_dedicated = evaluator.evaluate([box(0, 0, 12, 8)], [box(0, 0, 12, 8)], {"frontage_edge": [[0, 0], [12, 0]]})
    low_damage = _impact(box(10.5, 0, 11.5, 8))
    high_damage = _impact(box(4, 0, 8, 8))
    ranked = evaluator.rank_design_space(no_dedicated, [high_damage, low_damage], mandatory=True)
    assert ranked[0]["impact_score"] == low_damage["impact_score"]
    rejected = next(x for x in ranked if x["pedestrian_mode"] == "NO_DEDICATED_PEDESTRIAN_ENTRANCE")
    assert rejected["hard_reject"] and rejected["hard_rejection_reason"] == "dedicated_pedestrian_entrance_mandatory"


def test_frontage_cut_is_penalized_and_swept_overlap_is_hard_rejected():
    shallow_front_cut = _impact(box(0, 0, 6, 1))
    narrow_side_cut = _impact(box(11, 0, 12, 8))
    swept = box(5, 0, 7, 8)
    conflict = _impact(box(5, 0, 7, 8), [swept])
    assert shallow_front_cut["metrics"]["frontage_loss"] > narrow_side_cut["metrics"]["frontage_loss"]
    assert shallow_front_cut["impact_score"] > narrow_side_cut["impact_score"]
    assert conflict["hard_reject"] and conflict["metrics"]["vehicle_swept_conflict"] > 0


def test_entrance_geometry_regenerates_downstream_fingerprints_and_audit_is_complete():
    graph = ArchitecturalConstraintPropagationGraph()
    def run(corridor):
        impact = _impact(corridor)
        values = {name: {"corridor": list(corridor.bounds), "node": name, "impact": impact}
                  for name in graph.ORDER}
        return graph.regenerate({"candidate_id": "synthetic"}, {k: (lambda state, k=k: values[k]) for k in graph.ORDER})
    first, second = run(box(1, 0, 2, 8)), run(box(9, 0, 10, 8))
    for node in ("functional_subtraction", "space_roles", "commercial_viability", "residential_envelopes"):
        assert first["revisions"][node] != second["revisions"][node]
    audit = _impact(box(1, 0, 2, 8))
    assert set(audit["before"]) >= {"commercial_area", "frontage", "largest_usable_rectangle_area", "coherence", "fragment_count"}
    assert set(audit["after"]) >= set(audit["before"])
