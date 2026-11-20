from core.geometry.moving_ramp_3d_geometry_engine import (
    MovingRamp3DGeometryEngine
)



def test_moving_ramp_3d_geometry():


    engine = MovingRamp3DGeometryEngine()



    ramp = {


        "height":
            3.2,


        "slope":
            10,


        "width":
            1.5,


        "segments":
            10

    }



    result = engine.generate(
        ramp
    )


    print(
        "\n===== MOVING RAMP 3D RESULT ====="
    )


    print(result)



    assert result["type"] == "IfcTransportElement"

    assert result["system"] == "moving_ramp"

    assert result["end_z"] == 3.2



    print(
        "\n✅ MOVING RAMP 3D GEOMETRY TEST PASSED"
    )



if __name__ == "__main__":

    test_moving_ramp_3d_geometry()