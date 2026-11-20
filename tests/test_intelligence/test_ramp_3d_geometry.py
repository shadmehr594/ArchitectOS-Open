from core.geometry.ramp_3d_geometry_engine import (
    Ramp3DGeometryEngine
)



def test_ramp_3d_geometry():


    engine = Ramp3DGeometryEngine()



    ramp_geometry = {


        "shape":"L",


        "polygon":

        [

            [0,0],

            [10,0],

            [10,6],

            [10,16],

            [0,16],

            [0,6]

        ]

    }



    decision = {


        "type":"vehicle_ramp",

        "height":3,

        "slope":15,

        "width":6

    }



    result = engine.generate(

        ramp_geometry,

        decision

    )



    print(
        "\n===== 3D RAMP RESULT ====="
    )


    print(
        result
    )



    assert result["type"] == "IfcRamp"


    assert result["end_z"] == -3


    assert len(
        result["geometry"]
    ) > 0



    print(
        "\n✅ RAMP 3D GEOMETRY TEST PASSED"
    )



if __name__ == "__main__":

    test_ramp_3d_geometry()