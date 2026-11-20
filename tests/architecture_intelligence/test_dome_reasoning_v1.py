from core.architecture.brain.architectural_brain import ArchitecturalBrain


def test_dome_reasoning_v1():

    print(
        "\n====== DOME REASONING V1 ======"
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
            "pool"

        ]

    }



    model = brain.design(
        intent
    )



    print(
        "\n====== DOME RESULT ======"
    )


    print(
        model.dome_strategy
    )



    assert (
        model.dome_strategy["dome_type"]
        ==
        "roman_classical_dome"
    )


    assert (
        "stone_dome"
        in
        model.dome_strategy["elements"]
    )


    assert (
        "lantern"
        in
        model.dome_strategy["elements"]
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_dome_reasoning_v1()