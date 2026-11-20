from core.intelligence.vertical_accessibility_intelligence import (
    VerticalAccessibilityIntelligence
)



def test_vertical_accessibility_intelligence():


    engine = VerticalAccessibilityIntelligence()



    accessible = engine.create_accessible_ramp(

        0.8

    )



    vehicle = engine.create_vehicle_ramp(

        3.0

    )



    print(
        "\n===== ACCESSIBLE RAMP ====="
    )

    print(accessible)



    print(
        "\n===== VEHICLE RAMP ====="
    )

    print(vehicle)



    assert accessible["type"] == "accessible_ramp"

    assert accessible["length"] > 0

    assert accessible["handrail"]



    assert vehicle["type"] == "vehicle_ramp"

    assert vehicle["slope"] == 15



    print(
        "\n✅ VERTICAL ACCESSIBILITY INTELLIGENCE TEST PASSED"
    )



if __name__ == "__main__":

    test_vertical_accessibility_intelligence()