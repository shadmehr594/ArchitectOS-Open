from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_material_selection_reasoning_v1():


    print(
        "\n====== MATERIAL SELECTION REASONING V1 ======"
    )


    brain = ArchitecturalBrain()


    intent = {


        "building_type":
        "villa",


        "style":
        "roman_classic",


        "site":{

            "climate":{

                "type":
                "hot_dry"

            },

            "orientation":{

                "south":
                "street"

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


    assert (
        "travertine"
        in
        model.material_strategy[
            "primary_materials"
        ]
    )


    print(
        "\n====== TEST PASSED ======"
    )