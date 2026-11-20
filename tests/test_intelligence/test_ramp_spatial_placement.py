from core.spatial.ramp_spatial_placement_engine import (
    RampSpatialPlacementEngine
)



def test_ramp_spatial_placement():


    engine = RampSpatialPlacementEngine()



    ramp = engine.generate(

        {
            "type":"vehicle_ramp",
            "shape":"L",
            "length":20,
            "width":6,
            "slope":15
        }

    )


    print(
        "\n===== RAMP GEOMETRY ====="
    )


    print(
        ramp
    )


    assert ramp["shape"] == "L"

    assert len(
        ramp["polygon"]
    ) > 0


    print(
        "\n✅ RAMP SPATIAL PLACEMENT TEST PASSED"
    )



if __name__ == "__main__":

    test_ramp_spatial_placement()