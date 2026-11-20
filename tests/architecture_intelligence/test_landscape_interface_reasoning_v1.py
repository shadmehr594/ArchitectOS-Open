from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_landscape_interface_reasoning_v1():


    print(
        "\n====== LANDSCAPE INTERFACE REASONING V1 ======"
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
        "\n====== LANDSCAPE RESULT ======"
    )


    print(
        model.landscape_strategy
    )



    assert (
        model.landscape_strategy["landscape_strategy"]["type"]
        ==
        "classical_formal_garden"
    )


    assert (
        "central_axis"
        in
        model.landscape_strategy["landscape_strategy"]["elements"]
    )


    assert (
        "fountain"
        in
        model.landscape_strategy["landscape_strategy"]["elements"]
    )


    assert (
        "formal_entrance_path"
        in
        model.landscape_strategy["landscape_strategy"]["elements"]
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_landscape_interface_reasoning_v1()