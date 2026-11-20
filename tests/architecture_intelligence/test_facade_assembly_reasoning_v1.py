from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_facade_assembly_reasoning_v1():

    print(
        "\n====== FACADE ASSEMBLY REASONING V1 ======"
    )


    brain = ArchitecturalBrain()


    intent = {

        "building_type":
        "villa",


        "style":
        "roman_classic",


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
        "\n====== FACADE ASSEMBLY RESULT ======"
    )


    print(
        model.facade_assembly
    )


    facade = model.facade_assembly[
        "facade_system"
    ]


    assert (
        "stone_plinth"
        ==
        facade["base"]["element"]
    )


    assert (
        "stone_window_frames"
        in
        facade["openings"]["elements"]
    )


    assert (
        "columns"
        in
        facade["vertical_elements"]["elements"]
    )


    print(
        "\n====== TEST PASSED ======"
    )