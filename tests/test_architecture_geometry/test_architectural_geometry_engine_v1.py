from core.architecture.geometry.architectural_geometry_engine_v1 import (
    ArchitecturalGeometryEngineV1
)


def test_architectural_geometry_engine_v1():


    engine = ArchitecturalGeometryEngineV1()


    geometry_intent = {


        "spaces": [

            {

                "name": "living_room",

                "floor": "F1",

                "shape_intent":
                    "open_rectangular_space"

            },

            {

                "name": "kitchen",

                "floor": "F1",

                "shape_intent":
                    "compact_service_space"

            }

        ],


        "vertical_elements": [

            {

                "name": "stairs",

                "geometry_type":
                    "stair_core"

            },

            {

                "name": "ramp",

                "geometry_type":
                    "ramp_geometry"

            }

        ]

    }


    output = engine.generate(
        geometry_intent
    )


    assert output["version"] == "1.0"


    assert len(
        output["spaces"]
    ) == 2


    assert output["spaces"][0]["type"] == (
        "room_volume"
    )


    assert len(
        output["vertical_geometry"]
    ) == 2


    assert (
        output["vertical_geometry"][0]["type"]
        ==
        "stair_core"
    )


    assert len(
        output["boundaries"]
    ) > 0