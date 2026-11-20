from core.architecture.reasoning.boundary_entrance_reasoner import (
    BoundaryEntranceReasoner
)


def test_boundary_entrance_reasoning_v1():

    print(
        "\n====== BOUNDARY ENTRANCE REASONING V1 ======"
    )


    reasoner = BoundaryEntranceReasoner()


    result = reasoner.analyze(

        style=
            "roman_classic",

        facade_language=
            {},

        materials=
            []

    )


    print(
        "\n====== RESULT ======"
    )


    print(
        result
    )


    # ==================================================
    # CONTRACT VALIDATION
    # ==================================================

    assert isinstance(
        result,
        dict
    )


    assert (
        result["source"]
        ==
        "architectural_reasoning"
    )


    # ==================================================
    # BOUNDARY SYSTEM
    # ==================================================

    assert (
        result[
            "boundary_system"
        ][
            "type"
        ]
        ==
        "classical_stone_boundary"
    )


    assert (
        "stone_plinth"
        in
        result[
            "boundary_system"
        ][
            "elements"
        ]
    )


    assert (
        "classical_balustrade"
        in
        result[
            "boundary_system"
        ][
            "elements"
        ]
    )


    # ==================================================
    # VEHICLE ENTRANCE
    # ==================================================

    assert (
        result[
            "vehicle_entrance"
        ][
            "type"
        ]
        ==
        "monumental_gate"
    )


    assert (
        "stone_columns"
        in
        result[
            "vehicle_entrance"
        ][
            "elements"
        ]
    )


    assert (
        "arched_gate"
        in
        result[
            "vehicle_entrance"
        ][
            "elements"
        ]
    )


    # ==================================================
    # PEDESTRIAN ENTRANCE
    # ==================================================

    assert (
        result[
            "pedestrian_entrance"
        ][
            "type"
        ]
        ==
        "classical_entry"
    )


    assert (
        "arched_door"
        in
        result[
            "pedestrian_entrance"
        ][
            "elements"
        ]
    )


    assert (
        "entrance_canopy"
        in
        result[
            "pedestrian_entrance"
        ][
            "elements"
        ]
    )


    print(
        "\n====== TEST PASSED ======"
    )


if __name__ == "__main__":

    test_boundary_entrance_reasoning_v1()