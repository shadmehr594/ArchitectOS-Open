from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_bim_enrichment_bridge_v1():


    print(
        "\n====== BIM ENRICHMENT BRIDGE V1 ======"
    )


    brain = ArchitecturalBrain()



    intent = {


        "style": "roman_classic",


        "site": {

            "climate": {

                "type": "hot_dry"

            },

            "orientation": {

                "north": False,
                "south": True,
                "east": False,
                "west": False

            }

        },


        "spaces": [

            "living_room",
            "bedroom",
            "kitchen",
            "terrace",
            "pool",
            "garden"

        ]

    }



    model = brain.design(
        intent
    )



    print(
        "\n====== BIM ENRICHMENT RESULT ======"
    )


    print(
        model.bim_enriched
    )



    elements = model.bim_enriched[
        "bim_elements"
    ]



    assert (
        len(elements)
        > 
        0
    )



    wall = None

    boundary_wall = None

    roof = None



    for element in elements:


        if (
            element["type"] == "IfcWall"
            and
            element["name"] == "Facade Stone Wall"
        ):

            wall = element



        if (
            element["type"] == "IfcWall"
            and
            element["name"] == "Boundary Wall"
        ):

            boundary_wall = element



        if element["type"] == "IfcRoof":

            roof = element



    assert (
        wall is not None
    )


    assert (
        boundary_wall is not None
    )


    assert (
        boundary_wall["level"]
        ==
        "Site"
    )


    assert (
        roof is not None
    )



    assert (
        "level"
        in
        wall
    )


    assert (
        wall["level"]
        ==
        "F1"
    )



    assert (
        "geometry_intent"
        in
        wall
    )


    assert (
        wall["geometry_intent"]["height"]
        ==
        3.2
    )



    assert (
        "material_layer"
        in
        wall
    )



    assert (
        roof["level"]
        ==
        "Roof"
    )



    assert (
        roof["geometry_intent"]["shape"]
        ==
        "dome"
    )



    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_bim_enrichment_bridge_v1()