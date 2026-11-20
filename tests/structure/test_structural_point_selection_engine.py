from core.structure.structural_point_selection_engine import (
    StructuralPointSelectionEngine
)


def test_structural_point_selection_engine():


    engine = StructuralPointSelectionEngine()


    candidates = []


    x_values = [
        0,
        3,
        6,
        9,
        12
    ]


    y_values = [
        0,
        5,
        10
    ]


    for y in y_values:

        for x in x_values:

            candidates.append(

                {

                    "x": x,

                    "y": y,

                    "reference": "corner",

                    "source":
                        "test_grid"

                }

            )


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


    result = engine.select(

        candidates,

        architectural_model=
            architectural_model,

        protected_zones=
            protected_zones,

        constraints={

            "max_span":
                6.5

        }

    )


    selected = result[
        "selected_points"
    ]


    assert result[
        "selected_count"
    ] < result[
        "candidate_count"
    ]


    assert all(

        point[
            "reference"
        ] == "corner"

        for point in selected

    )


    assert not any(

        point["x"] == 6
        and
        point["y"] == 5

        for point in selected

    )


    assert any(

        point["x"] == 0
        and
        point["y"] == 0

        for point in selected

    )


    assert any(

        point["x"] == 12
        and
        point["y"] == 10

        for point in selected

    )


    print(
        "STRUCTURAL POINT SELECTION ENGINE TEST PASSED"
    )