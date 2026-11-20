from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_exterior_detail_reasoning_v1():


    print(
        "\n====== EXTERIOR DETAIL REASONING V1 ======"
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
        "\n====== EXTERIOR DETAIL RESULT ======"
    )


    print(
        model.exterior_details
    )



    details = model.exterior_details["exterior_details"]



    assert (
        "stone_window_frames"
        in
        details["windows"]
    )


    assert (
        "arched_openings"
        in
        details["windows"]
    )


    assert (
        "columns"
        in
        details["vertical_elements"]
    )


    assert (
        "classical_capitals"
        in
        details["vertical_elements"]
    )


    assert (
        "cornice"
        in
        details["horizontal_elements"]
    )


    assert (
        "balustrade"
        in
        details["ornaments"]
    )



    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_exterior_detail_reasoning_v1()