from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_complete_exterior_design_reasoning_v1():


    print(
        "\n====== COMPLETE EXTERIOR DESIGN REASONING V1 ======"
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
        "\n====== COMPLETE EXTERIOR RESULT ======"
    )


    print(
        model.complete_exterior_design
    )



    exterior = model.complete_exterior_design[
        "exterior_design"
    ]



    assert (
        exterior["style"]
        ==
        "roman_classic"
    )



    assert (
        "travertine"
        in
        exterior["materials"]["primary_materials"]
    )



    assert (
        exterior["roof"]["roof_strategy"]["roof_type"]
        ==
        "classical_dome"
    )



    assert (
        "stone_window_frames"
        in
        exterior["details"]["exterior_details"]["windows"]
    )



    assert (
        "balustrade"
        in
        exterior["details"]["exterior_details"]["ornaments"]
    )



    assert (
        exterior["landscape"]["landscape_strategy"]["type"]
        ==
        "classical_formal_garden"
    )



    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_complete_exterior_design_reasoning_v1()