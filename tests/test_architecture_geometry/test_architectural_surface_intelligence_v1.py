from core.architecture.material.architectural_surface_intelligence_v1 import (
    ArchitecturalSurfaceIntelligenceV1
)



def test_architectural_surface_intelligence_v1():


    engine = ArchitecturalSurfaceIntelligenceV1()


    mesh_output = {


        "meshes":[


            {

                "name":
                    "living_room",

                "type":
                    "volume_mesh"

            },


            {

                "name":
                    "stairs",

                "type":
                    "vertical_mesh"

            }


        ]

    }


    output = engine.generate(
        mesh_output
    )


    assert output["version"] == "1.0"


    assert len(
        output["surfaces"]
    ) == 2


    assert (
        output["surfaces"][0]["surface_type"]
        ==
        "room_surface"
    )


    assert len(
        output["materials"]
    ) > 0


    assert len(
        output["finish_rules"]
    ) > 0