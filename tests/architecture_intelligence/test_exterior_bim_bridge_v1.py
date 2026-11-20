from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_exterior_bim_bridge_v1():


    print(
        "\n====== EXTERIOR BIM BRIDGE V1 ======"
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
        "\n====== EXTERIOR BIM RESULT ======"
    )


    print(
        model.exterior_bim
    )



    elements = model.exterior_bim[
        "bim_elements"
    ]



    assert (
        len(elements)
        > 
        0
    )



    element_types = [

        element["type"]

        for element in elements

    ]



    assert (
        "IfcWall"
        in
        element_types
    )



    assert (
        "IfcWindow"
        in
        element_types
    )



    assert (
        "IfcColumn"
        in
        element_types
    )



    assert (
        "IfcRoof"
        in
        element_types
    )



    names = [

        element["name"]

        for element in elements

    ]



    assert (
        "Classical Dome"
        in
        names
    )



    assert (
        "Boundary Wall"
        in
        names
    )



    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_exterior_bim_bridge_v1()