from core.geometry.escalator_3d_geometry_engine import (
    Escalator3DGeometryEngine
)



def test_escalator_3d_geometry():


    engine = Escalator3DGeometryEngine()



    escalator = {


        "height":
            3.2,


        "angle":
            30,


        "width":
            1.0

    }



    placement = {


        "polygon":

        [

            [0,0],

            [6.4,0],

            [6.4,1],

            [0,1]

        ]

    }



    result = engine.generate(

        escalator,

        placement

    )



    print(
        "\n===== ESCALATOR 3D RESULT ====="
    )


    print(result)



    assert result["type"]=="IfcTransportElement"

    assert len(
        result["steps"]
    ) > 0



    print(
        "\n✅ ESCALATOR 3D GEOMETRY TEST PASSED"
    )



if __name__=="__main__":

    test_escalator_3d_geometry()