from copy import deepcopy

from core.architecture.reasoning.ramp_slope_profile_validation_v1 import RampSlopeProfileValidationV1


def binding(start=0.0, end=-2.4):
    return {"contract": "AuthoritativeRampEndpointBindingContractV1", "status": "resolved",
            "binding_resolved": True, "expected_start_z": start, "expected_end_z": end}


def constraint(value=0.15):
    return {"contract": "RampMaximumSlopeConstraintV1", "status": "resolved",
            "maximum_slope": value, "authority_class": "PROJECT_REQUIREMENT",
            "provenance": [{"source": "synthetic_acceptance", "key": "maximum_slope"}]}


def segment(start, end, length, role="main", segment_id="S"):
    return {"segment_id": segment_id, "role": role, "start_z": start, "end_z": end,
            "length": length, "provenance": [{"source": "synthetic_profile", "segment": segment_id}]}


def profile(path_id, segments):
    return {"contract": "RampPathProfileEvidenceV1", "status": "resolved", "path_id": path_id,
            "provenance": [{"source": "synthetic_path", "path": path_id}], "segments": segments}


def validate(profiles, start=0.0, end=-2.4, maximum=0.15, transitions=None, **kwargs):
    return RampSlopeProfileValidationV1().resolve(
        binding(start, end), constraint(maximum), profiles, transitions, **kwargs)


def test_straight_profile_with_sufficient_length_passes_and_flags_stay_separate():
    result = validate([profile("center", [segment(0.0, -2.4, 16.0)])])
    assert result["status"] == "validated"
    assert result["slope_validated"] is True
    assert result["placement_validated"] is False
    assert result["parking_integration_validated"] is False
    assert result["geometry_generated"] is False


def test_profile_over_authoritative_maximum_fails():
    result = validate([profile("center", [segment(0.0, -2.4, 15.0)])])
    assert result["status"] == "invalid"
    assert "center_segment_0_slope_exceeds_maximum" in result["failure_reasons"]


def test_multi_segment_profile_with_reduced_slope_tail_passes():
    segments = [segment(0.0, -2.1, 14.0, segment_id="main"),
                segment(-2.1, -2.4, 4.0, role="reduced_slope_tail", segment_id="tail")]
    assert validate([profile("center", segments)])["status"] == "validated"


def test_endpoint_mismatch_fails():
    result = validate([profile("center", [segment(-0.1, -2.4, 16.0)])])
    assert "center_start_endpoint_mismatch" in result["failure_reasons"]


def test_discontinuity_fails():
    segments = [segment(0.0, -1.2, 8.0, segment_id="a"),
                segment(-1.1, -2.4, 9.0, segment_id="b")]
    result = validate([profile("center", segments)])
    assert "center_elevation_discontinuity_at_segment_1" in result["failure_reasons"]


def test_reverse_bump_fails_unless_explicitly_allowed():
    segments = [segment(0.0, -1.0, 8.0, segment_id="a"),
                segment(-1.0, -0.9, 1.0, segment_id="b"),
                segment(-0.9, -2.4, 10.0, segment_id="c")]
    rejected = validate([profile("center", segments)])
    accepted = validate([profile("center", segments)], allow_non_monotonic=True)
    assert "center_segment_1_non_monotonic_reverse" in rejected["failure_reasons"]
    assert accepted["status"] == "validated"


def test_each_supplied_path_is_checked_and_one_failure_invalidates_all():
    paths = [profile("inner", [segment(0.0, -2.4, 16.0)]),
             profile("center", [segment(0.0, -2.4, 17.0)]),
             profile("outer", [segment(0.0, -2.4, 15.5)])]
    result = validate(paths)
    assert [item["path_id"] for item in result["path_results"]] == ["inner", "center", "outer"]
    assert result["status"] == "invalid"
    assert "outer_segment_0_slope_exceeds_maximum" in result["failure_reasons"]


def test_nonstandard_authoritative_endpoints_pass():
    result = validate([profile("center", [segment(1.25, -1.75, 20.0)])], start=1.25, end=-1.75)
    assert result["status"] == "validated"


def test_transition_requires_its_own_constraint_and_then_passes():
    segments = [segment(0.0, -0.1, 2.0, role="transition_start", segment_id="entry"),
                segment(-0.1, -2.3, 15.0, segment_id="main"),
                segment(-2.3, -2.4, 2.0, role="transition_end", segment_id="exit")]
    unresolved = validate([profile("center", segments)])
    transitions = {"transition_start": constraint(0.08), "transition_end": constraint(0.08)}
    resolved = validate([profile("center", segments)], transitions=transitions)
    assert unresolved["status"] == "unresolved"
    assert resolved["status"] == "validated"


def test_missing_slope_authority_is_unresolved_not_defaulted_to_fifteen_percent():
    result = RampSlopeProfileValidationV1().resolve(
        binding(), None, [profile("center", [segment(0.0, -2.4, 16.0)])])
    assert result["status"] == "unresolved"
    assert "maximum_slope_constraint_missing" in result["failure_reasons"]


def test_deterministic_and_does_not_mutate_inputs():
    inputs = (binding(), constraint(), [profile("center", [segment(0.0, -2.4, 16.0)])])
    before = deepcopy(inputs)
    first = RampSlopeProfileValidationV1().resolve(*inputs)
    second = RampSlopeProfileValidationV1().resolve(*inputs)
    assert first == second
    assert inputs == before
    assert first["input_mutated"] is False
