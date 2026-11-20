from core.architecture.material.architectural_material_intelligence_v1 import (
    ArchitecturalMaterialIntelligenceV1
)



def test_architectural_material_intelligence_v1():


    engine = ArchitecturalMaterialIntelligenceV1()


    surface_output = {


        "surfaces":[


            {

                "name":
                    "living_room",

                "surface_type":
                    "room_surface"

            },


            {

                "name":
                    "stairs",

                "surface_type":
                    "vertical_surface"

            }


        ]

    }


    output = engine.generate(
        surface_output
    )


    assert output["version"] == "1.0"


    assert len(
        output["materials"]
    ) == 2


    assert (
        output["materials"][0]["material"]
        ==
        "architectural_wall_finish"
    )


    assert len(
        output["material_rules"]
    ) > 0