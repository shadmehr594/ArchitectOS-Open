from core.spatial.vertical_circulation_intelligence import (
    VerticalCirculationIntelligence
)



def test_vertical_circulation_intelligence():


    engine = VerticalCirculationIntelligence()



    stair = engine.create_stair(

        "stair_core_001",

        [

            "F1",

            "F2",

            "F3"

        ],

        location_reason=[

            "central_core",

            "efficient_distribution"

        ]

    )



    ramp = engine.create_ramp(

        "main_ramp_001",

        [

            "street",

            "entrance"

        ],

        slope=0.08

    )



    print(stair)

    print(ramp)



    assert engine.validate(stair)

    assert engine.validate(ramp)


    assert stair["type"] == "stair"

    assert ramp["type"] == "ramp"