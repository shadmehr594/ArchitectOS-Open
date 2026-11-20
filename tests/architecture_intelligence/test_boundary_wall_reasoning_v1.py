from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_boundary_wall_reasoning_v1():


    print(
        "\n====== BOUNDARY WALL REASONING V1 ======"
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
        "\n====== BOUNDARY WALL RESULT ======"
    )


    print(
        model.boundary_wall
    )



    assert (
        model.boundary_wall["boundary_wall"]["type"]
        ==
        "classical_stone_wall"
    )


    assert (
        "stone_columns"
        in
        model.boundary_wall["boundary_wall"]["elements"]
    )


    assert (
        "cornice"
        in
        model.boundary_wall["boundary_wall"]["elements"]
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_boundary_wall_reasoning_v1()