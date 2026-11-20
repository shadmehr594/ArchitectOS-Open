from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_architectural_style_reasoning_v1():


    print(
        "\n====== ARCHITECTURAL STYLE REASONING V1 ======"
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
        "\n====== STYLE RESULT ======"
    )


    print(
        model.style_analysis
    )


    assert (
        "roman_classic"
        in
        model.style_analysis[
            "style_candidates"
        ]
    )


    print(
        "\n====== TEST PASSED ======"
    )