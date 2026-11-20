from core.site.model.site_model import SiteModel

from core.architecture.intent.architectural_intent import (
    ArchitecturalIntent
)

from core.architecture.planner.architectural_planner import (
    ArchitecturalPlanner
)



def test_architectural_planner_v1():

    print(
        "\n====== ARCHITECTURAL PLANNER V1 TEST ======"
    )


    site = SiteModel(

        boundary=[

            (0, 0),
            (20, 0),
            (20, 30),
            (0, 30)

        ],

        north="N",

        climate={

            "type": "hot_dry"

        }

    )


    intent = ArchitecturalIntent(

        building_type="residential",

        area=400,

        floors=2,

        style="modern",

        requirements=[

            "4 bedrooms",

            "parking",

            "pool"

        ]

    )


    planner = ArchitecturalPlanner()


    design = planner.plan(

        site,

        intent

    )


    print(
        "\n====== SITE STRATEGY ======"
    )

    print(
        design.site_strategy
    )


    print(
        "\n====== LEVELS ======"
    )


    for level in design.levels:

        print(
            "\nLEVEL:",
            level["name"]
        )

        for space in level["spaces"]:

            print(
                " -",
                space
            )


    print(
        "\n====== RELATIONSHIPS ======"
    )

    for relation in design.relationships:

        print(
            relation
        )


    print(
        "\n====== FACADE STRATEGY ======"
    )

    print(
        design.facade_strategy
    )


    print(
        "\n====== ARCHITECTURAL PLANNER V1 PASSED ======"
    )


    return design