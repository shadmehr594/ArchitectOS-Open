from core.memory.architectural_decision_memory_writer_v1 import (
    ArchitecturalDecisionMemoryWriterV1
)



def test_architectural_decision_memory_writer_v1():


    print(
        "\n====== ARCHITECTURAL DECISION MEMORY WRITER V1 ======"
    )



    writer = (
        ArchitecturalDecisionMemoryWriterV1()
    )



    decision = {


        "selected_decision":

        {

            "proposal":

                "architectural_preservation",


            "target":

                "architectural_shell",


            "priority":

                "high",


            "confidence":

                0.95

        }

    }



    result = writer.write(
        decision
    )



    print(
        "\n====== MEMORY RESULT ======"
    )


    print(
        result
    )



    assert (
        result["engine"]
        ==
        "ARCHITECTURAL_DECISION_MEMORY_WRITER_V1"
    )


    assert (
        result["stored"]
        ==
        True
    )


    assert (
        result["memory"]["target"]
        ==
        "architectural_shell"
    )


    assert (
        result["memory"]["confidence"]
        ==
        0.95
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_architectural_decision_memory_writer_v1()