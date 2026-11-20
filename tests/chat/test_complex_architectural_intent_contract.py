from core.prompt_intelligence.architectural_intent import ArchitecturalIntent


def test_mixed_use_site_parking_basement_request_is_preserved():
    text = (
        "ساختمان مختلط تجاری مسکونی در زمین 20 در 30 با سطح اشغال 60 درصد "
        "و تراکم 240 درصد، بنا در شمال زمین، حیاط خلوت 3 متر، "
        "دو طبقه زیرزمین و 18 پارکینگ با رمپ طراحی کن"
    )
    intent = ArchitecturalIntent().extract(text)

    assert intent["building_type"] == "mixed_use_commercial_residential"
    assert intent["site"] | {"width": 20.0, "depth": 30.0, "area": 600.0} == intent["site"]
    assert intent["site_constraints"]["coverage"] == 0.60
    assert intent["site_constraints"]["density"] == 240
    assert intent["site_constraints"]["building_position"]["side"] == "north"
    assert intent["site_constraints"]["setbacks"].get("north") is None
    assert {"type": "حیاط خلوت", "width": 3.0} in intent["site_constraints"]["open_spaces"]
    assert intent["levels"]["basement"] == 2
    assert intent["parking"]["required_spaces"] == 18
    assert intent["parking"]["ramp_required"] is True
