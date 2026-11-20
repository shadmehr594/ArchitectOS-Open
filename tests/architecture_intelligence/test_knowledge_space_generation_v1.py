from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_knowledge_space_generation_v1():


    print(
        "\n====== KNOWLEDGE SPACE GENERATION V1 ======"
    )


    brain = ArchitecturalBrain()



    intent = {


        "building_type":
        "villa",


        "requirements":
        [

            "pool",

            "garden"

        ]

    }



    model = brain.design(
        intent
    )


    print(
        "\n====== KNOWLEDGE RESULT ======"
    )


    print(
        model.knowledge_spaces
    )



    assert (
        model.knowledge_spaces["source"]
        ==
        "architectural_knowledge"
    )


    print(
        "\n====== TEST PASSED ======"
    )