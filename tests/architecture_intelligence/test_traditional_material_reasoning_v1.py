from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_traditional_material_reasoning_v1():


    print(
        "\n====== TRADITIONAL MATERIAL REASONING V1 ======"
    )


    brain = ArchitecturalBrain()


    intent = {

        "building_type":
        "villa",


        "style":
        "iranian_traditional",


        "site":

        {

            "climate":

            {

                "type":
                "hot_dry"

            }

        }

    }


    model = brain.design(
        intent
    )


    print(
        "\n====== MATERIAL RESULT ======"
    )


    print(
        model.material_strategy
    )


    materials = model.material_strategy[
        "primary_materials"
    ]


    assert (
        "kahgel" in materials
        or
        "traditional_brick" in materials
        or
        "mud_brick" in materials
    )


    print(
        "\n====== TEST PASSED ======"
    )