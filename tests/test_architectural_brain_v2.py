from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_architectural_brain_v2():


    print(
        "\n====== ARCHITECTURAL BRAIN V2 TEST ======"
    )


    intent = {

        "building_type": "villa",

        "spaces": [

            "living_room",

            "bedroom"

        ],

        "style": "modern"

    }


    brain = ArchitecturalBrain()


    result = brain.design(
        intent
    )


    print(
        "\n====== DESIGN MODEL ======"
    )


    print(
        result.to_dict()
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_brain_v2()