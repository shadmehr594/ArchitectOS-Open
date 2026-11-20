from core.architecture.reasoning.far_end_operational_turn_v2 import FarEndOperationalTurnV2


def test_maneuver_field_interval_events_include_asymmetric_positions():
    events=FarEndOperationalTurnV2._interval_events(0,8)
    assert events==[0,2,4,6,8]


def test_interval_events_are_geometry_derived_and_deterministic():
    assert FarEndOperationalTurnV2._interval_events(1.2,5.2)==FarEndOperationalTurnV2._interval_events(1.2,5.2)
    assert FarEndOperationalTurnV2._interval_events(1.2,5.2)==[1.2,2.2,3.2,4.2,5.2]
