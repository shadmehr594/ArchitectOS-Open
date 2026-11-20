from core.site.model.site_model import SiteModel
from core.architecture.intent.architectural_intent import ArchitecturalIntent
from core.architecture.model.architectural_design import ArchitecturalDesign



def test_architecture_core_v1():

    print(
        "\n====== ARCHITECTURE CORE V1 TEST ======"
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


    design = ArchitecturalDesign()


    print(
        "\n====== SITE MODEL ======"
    )

    print(
        site.to_dict()
    )


    print(
        "\n====== ARCHITECTURAL INTENT ======"
    )

    print(
        intent.to_dict()
    )


    print(
        "\n====== EMPTY DESIGN MODEL ======"
    )

    print(
        design.to_dict()
    )


    print(
        "\n====== ARCHITECTURE CORE V1 PASSED ======"
    )


    return {

        "site": site.to_dict(),

        "intent": intent.to_dict(),

        "design": design.to_dict()

    }