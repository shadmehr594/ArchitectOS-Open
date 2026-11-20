from core.spatial.architectural_space_contract_v2 import (
    ArchitecturalSpaceContractV2
)



def test_universal_space_contract():


    engine = ArchitecturalSpaceContractV2()



    courtyard = engine.create(

        "courtyard_001",

        "courtyard",

        requirements={

            "open_sky": True,

            "daylight": True

        }

    )



    stair = engine.create(

        "stair_001",

        "stair",

        role="vertical_circulation",

        requirements={

            "connects":

            [

                "F1",

                "F2"

            ]

        }

    )



    ramp = engine.create(

        "ramp_001",

        "ramp",

        role="accessibility",

        requirements={

            "accessible":

                True

        }

    )



    assert engine.validate(
        courtyard
    )


    assert engine.validate(
        stair
    )


    assert engine.validate(
        ramp
    )


    assert courtyard["type"] == "courtyard"

    assert stair["type"] == "stair"

    assert ramp["type"] == "ramp"