from core.architecture_intelligence.architectural_proposal_generator_program_aware_v1 import (
    ArchitecturalProposalGeneratorProgramAwareV1
)



def test_architectural_proposal_generator_program_aware_v1():


    print(
        "\n====== ARCHITECTURAL PROPOSAL GENERATOR PROGRAM AWARE V1 ======"
    )



    generator = (
        ArchitecturalProposalGeneratorProgramAwareV1()
    )



    decision = {


        "decision_type":

            "existing_building_program_transformation",


        "target_program":

            "gym",


        "program_category":
            "commercial",


        "requirements":
        [
            "open_space",
            "equipment_area",
            "changing_room"
        ],


        "decisions":

        [

            "preserve_existing_shell",

            "adapt_existing_layout",

            "validate_gym_requirements"

        ]

    }



    result = generator.generate(

        decision

    )



    print(
        "\n====== PROPOSAL RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "ARCHITECTURAL_PROPOSAL_GENERATOR_PROGRAM_AWARE_V1"
    )


    assert (
        result["proposal_ready"]
        ==
        True
    )


    assert (
        result["proposal"]["target_program"]
        ==
        "gym"
    )


    assert (
        len(result["proposal"]["proposals"])
        ==
        3
    )


    assert (
        result["proposal"]["program_category"]
        ==
        "commercial"
    )


    assert (
        "open_space"
        in
        result["proposal"]["requirements"]
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_proposal_generator_program_aware_v1()