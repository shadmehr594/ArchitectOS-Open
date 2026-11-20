from core.geometry.mesh.architectural_mesh_adapter_v1 import (
    ArchitecturalMeshAdapterV1
)


def test_architectural_mesh_adapter_v1():


    adapter = ArchitecturalMeshAdapterV1()


    geometry = {

        "spaces": [

            {

                "name":
                    "living_room",

                "type":
                    "room_volume",

                "height":
                    3.2

            }

        ],


        "vertical_geometry": [

            {

                "name":
                    "stairs",

                "type":
                    "stair_core"

            }

        ]

    }


    output = adapter.generate(
        geometry
    )


    assert output["version"] == "1.0"


    assert len(
        output["meshes"]
    ) == 2


    assert (
        output["meshes"][0]["type"]
        ==
        "volume_mesh"
    )


    assert (
        output["meshes"][1]["type"]
        ==
        "vertical_mesh"
    )


    assert len(
        output["topology"]
    ) > 0