"""
ArchitectOS Vertical Building Section Engine Test v1.0
"""


from core.architecture.vertical_building_section_engine import (
    VerticalBuildingSectionEngine
)


def test_vertical_organization_resolved_chain_has_resolved_roof_and_total_height():
    program = {
        "vertical_organization": {
            "ground": {},
            "residential_floor_1": {},
        },
        "floor_heights": {
            "ground": 4.2,
            "residential_floor_1": 3.2,
        },
    }

    result = VerticalBuildingSectionEngine().generate(program)

    assert [level["name"] for level in result["levels"]] == [
        "ground",
        "residential_floor_1",
    ]
    assert result["roof_level"] == 7.4
    assert result["roof_level_status"] == "resolved"
    assert result["total_height"] == 7.4


def test_vertical_organization_partial_chain_preserves_unresolved_levels_and_fails_closed():
    program = {
        "vertical_organization": {
            "ground": {},
            "residential_floor_1": {},
            "residential_floor_2": {},
        },
        "floor_heights": {
            "ground": 4.2,
            "residential_floor_2": 3.2,
        },
    }

    result = VerticalBuildingSectionEngine().generate(program)

    assert [level["name"] for level in result["levels"]] == [
        "ground",
        "residential_floor_1",
        "residential_floor_2",
    ]
    assert result["levels"][1]["height"] is None
    assert result["levels"][2]["bottom"] is None
    assert result["levels"][2]["top"] is None
    assert result["roof_level"] is None
    assert result["roof_level_status"] == "unresolved"
    assert result["total_height"] is None



def test_vertical_building_section_generation():


    engine = VerticalBuildingSectionEngine()


    program = {


        "floors": [


            {
                "name": "B1",
                "type": "basement",
                "height": 2.4
            },


            {
                "name": "F1",
                "type": "commercial",
                "height": 5.0
            },


            {
                "name": "F2",
                "type": "residential"
            },


            {
                "name": "F3",
                "type": "residential"
            }

        ],



        "vertical_elements": [


            {
                "type":
                    "stairs"
            },


            {
                "type":
                    "elevator_machine_room",

                "height":
                    1.0
            }

        ]

    }



    result = engine.generate(
        program
    )


    assert len(
        result["levels"]
    ) == 4


    assert result["levels"][0]["height"] == 2.4


    assert result["levels"][1]["height"] == 5.0


    assert result["levels"][2]["height"] is None


    assert result["levels"][3]["height"] is None



    assert result["roof_level"] is None
    assert result["roof_level_status"] == "unresolved"


    assert len(
        result["vertical_extensions"]
    ) == 2



    print(
        "VERTICAL BUILDING SECTION ENGINE TEST PASSED"
    )
