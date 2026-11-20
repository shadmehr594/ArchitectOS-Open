from core.site.site_intelligence_contract import (
    SiteIntelligenceContract
)



def test_site_intelligence_contract():


    engine = SiteIntelligenceContract()



    site = engine.create(

        boundary=[

            [0,0],

            [20,0],

            [20,30],

            [0,30]

        ],


        access={

            "main_entry":

                "south"

        },


        orientation={

            "north":

                "up"

        }

    )



    site = engine.add_constraint(

        site,

        "setback_required"

    )



    site = engine.add_constraint(

        site,

        "street_front_priority"

    )



    print(site)



    assert engine.validate(site)


    assert site["type"] == "site"


    assert (
        "setback_required"
        in
        site["constraints"]
    )