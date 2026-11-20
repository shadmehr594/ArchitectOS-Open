import json
from pathlib import Path

from tools.rerender_parcel2_ns_hybrid_human_review_v1 import (
    _digest, _geometry, build_audit, load_frozen_candidates, render_candidate_review,
    render_comparison, render_vehicle_diagnostic,
)


def test_frozen_candidates_are_exactly_ns_hybrid_and_render_without_mutation():
    report,candidates=load_frozen_candidates();before={k:_digest(_geometry(v)) for k,v in candidates.items()}
    assert "swept-validation" not in render_candidate_review(candidates["NS"])
    assert "Vehicle movement and swept-path lines intentionally omitted" in render_candidate_review(candidates["HYBRID"])
    render_comparison(candidates);render_vehicle_diagnostic(candidates)
    after={k:_digest(_geometry(v)) for k,v in candidates.items()}
    audit=build_audit(report,candidates,before,after,["a.svg","b.svg","c.svg","d.svg","audit.json"])
    assert set(candidates)=={"NS","HYBRID"} and audit["geometry_invariance_passed"]
    assert audit["parking_requirement_trace"]["minimum_count"]==2


def test_audit_preserves_architecture_only_stop_flags():
    report,candidates=load_frozen_candidates();fingerprints={k:_digest(_geometry(v)) for k,v in candidates.items()}
    audit=build_audit(report,candidates,fingerprints,fingerprints,[])
    assert audit["winner"] is None and not audit["final_selection_performed"]
    assert not audit["room_layout_generated"] and not audit["final_windows_generated"]
    assert not audit["structure_executed"] and not audit["bim_executed"] and not audit["ifc_executed"]
