from core.architecture_intelligence.architectural_context_registry_v1 import (
    ArchitecturalContextRegistryV1
)



def test_architectural_context_registry_v1():


    print(
        "\n====== ARCHITECTURAL CONTEXT REGISTRY V1 ======"
    )



    registry = (
        ArchitecturalContextRegistryV1()
    )



    context = {


        "building_type":

            "existing_building",


        "architectural_intent":

            "existing_building_preservation",


        "architectural_goal":

            "preserve_existing_shell",


        "target":

            "architectural_shell",


        "confidence":

            0.95,


        "source":

            "planner"

    }



    result = registry.register(
        context
    )



    print(
        "\n====== REGISTRY RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "ARCHITECTURAL_CONTEXT_REGISTRY_V1"
    )


    assert (
        result["registered"]
        ==
        True
    )


    assert (
        result["context"]["building_type"]
        ==
        "existing_building"
    )


    assert (
        result["context"]["confidence"]
        ==
        0.95
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_context_registry_v1()