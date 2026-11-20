from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_facade_language_reasoning_v1():


    print(
        "\n====== FACADE LANGUAGE REASONING V1 ======"
    )


    brain = ArchitecturalBrain()


    intent = {

        "building_type":
        "villa",

        "style":
        "roman_classic"

    }



    model = brain.design(
        intent
    )


    print(
        "\n====== FACADE RESULT ======"
    )


    print(
        model.facade_language
    )


    assert (
        "stone window frames"
        in
        model.facade_language[
            "elements"
        ]
    )


    assert (
        "travertine"
        in
        model.facade_language[
            "materials"
        ]
    )


    print(
        "\n====== TEST PASSED ======"
    )