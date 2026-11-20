from core.architecture.geometry.facade_material_bridge_v1 import (
    FacadeMaterialBridgeV1
)



def test_facade_material_bridge_v1():


    bridge = FacadeMaterialBridgeV1()


    output = bridge.resolve(

        {

            "style":
                "modern",

            "climate":
                "hot_dry"

        }

    )


    print(output)


    assert output is not None

    assert "materials" in output

    assert "strategies" in output