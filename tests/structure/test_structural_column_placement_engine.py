from core.structure.structural_column_placement_engine import (
    StructuralColumnPlacementEngine
)


def test_structural_column_placement_engine():

    engine = StructuralColumnPlacementEngine()


    architectural_model = {

        "building": {

            "width": 12,

            "depth": 10

        }

    }


    protected_zones = [

        {

            "type":
                "stairs",

            "bounds":
                [
                    5,
                    4,
                    2,
                    2
                ],

            "allow_column":
                False

        }

    ]


    columns = [

        # valid interior column
        {
            "x": 2,
            "y": 2,
            "width": 0.30,
            "depth": 0.30,
            "reference": "corner"
        },

        # right property boundary
        {
            "x": 12,
            "y": 2,
            "width": 0.30,
            "depth": 0.30,
            "reference": "corner"
        },

        # top property boundary
        {
            "x": 2,
            "y": 10,
            "width": 0.30,
            "depth": 0.30,
            "reference": "corner"
        },

        # protected stair zone
        {
            "x": 5.5,
            "y": 4.5,
            "width": 0.30,
            "depth": 0.30,
            "reference": "corner"
        }

    ]


    result = engine.place(
        columns,
        architectural_model,
        protected_zones
    )


    placed = result[
        "columns"
    ]


    assert len(
        placed
    ) >= 3


    assert all(

        column[
            "reference"
        ] == "corner"

        for column in placed

    )


    assert all(

        column["x"] >= 0
        and
        column["y"] >= 0
        and
        column["x"] + column["width"] <= 12
        and
        column["y"] + column["depth"] <= 10

        for column in placed

    )


    assert any(

        round(
            column["x"],
            3
        ) == 11.7

        for column in placed

    )


    assert any(

        round(
            column["y"],
            3
        ) == 9.7

        for column in placed

    )


    assert not any(

        5 < column["x"] < 7
        and
        4 < column["y"] < 6

        for column in placed

    )


    print(
        "STRUCTURAL COLUMN PLACEMENT ENGINE TEST PASSED"
    )