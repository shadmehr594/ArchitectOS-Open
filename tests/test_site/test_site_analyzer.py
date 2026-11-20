from core.site.model.site_model import SiteModel
from core.site.site_analyzer import SiteAnalyzer



def test_site_analysis():


    site = SiteModel(

        boundary=[

            [0, 0],
            [20, 0],
            [20, 30],
            [0, 30]

        ],


        roads=[

            {

                "side": "south",

                "type": "street",

                "width": 12

            }

        ],


        location="test_site"

    )


    site.neighbors = [

        {

            "side": "east",

            "type": "building"

        },

        {

            "side": "west",

            "type": "building"

        }

    ]


    analyzer = SiteAnalyzer()


    result = analyzer.analyze(
        site
    )


    print("\n========== RESULT ==========")

    print(result)



if __name__ == "__main__":

    test_site_analysis()