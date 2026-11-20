"""
ArchitectOS IFC Element Placement Builder Test
"""


from core.architecture.bim.ifc_element_placement_builder_v1 import (
    IFCElementPlacementBuilderV1
)



def test_ifc_element_placement_builder():


    print(
        "\n"
        "================================\n"
        "IFC ELEMENT PLACEMENT BUILDER TEST\n"
        "================================\n"
    )


    context = {

        "level_elevations":

        {

            "F1": 0.0,

            "F2": 3.6,

            "F3": 7.2

        }

    }



    elements = [

        {

            "ifc_class":
                "IfcWall",

            "name":
                "Wall_F1",

            "level":
                "F1"

        },


        {

            "ifc_class":
                "IfcSlab",

            "name":
                "Slab_F2",

            "level":
                "F2"

        },


        {

            "ifc_class":
                "IfcSpace",

            "name":
                "Space_F3",

            "level":
                "F3"

        }

    ]



    builder = IFCElementPlacementBuilderV1(
        context=context
    )



    result = builder.build(
        elements
    )



    assert (
        result["element_count"]
        ==
        3
    )


    assert (
        result["placements"][0]["placement"]["location"][2]
        ==
        0.0
    )


    assert (
        result["placements"][1]["placement"]["location"][2]
        ==
        3.6
    )


    assert (
        result["placements"][2]["placement"]["location"][2]
        ==
        7.2
    )



    print(
        "\n✅ IFC ELEMENT PLACEMENT BUILDER PASSED"
    )