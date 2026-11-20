from core.architecture.material.library.architectural_material_library_bridge_v1 import (
    ArchitecturalMaterialLibraryBridgeV1
)



def test_architectural_material_library_bridge_v1():


    bridge = ArchitecturalMaterialLibraryBridgeV1()


    material_output = {


        "materials":[


            {

                "surface":
                    "front_facade",

                "material":
                    "architectural_wall_finish"

            }

        ]

    }


    output = bridge.resolve(
        material_output
    )


    assert output["version"] == "1.0"


    assert len(
        output["assets"]
    ) == 1


    assert (
        output["assets"][0]["asset"]["category"]
        ==
        "facade"
    )


    assert (
        output["assets"][0]["asset"]["id"]
        ==
        "facade_brick_modern_001"
    )