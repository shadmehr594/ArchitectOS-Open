"""
ArchitectOS Site Scenario 01

North Placement Residential Building
"""


def get_scenario():


    return {


        "name":
            "north_residential",



        "site":

        {

            "width": 20,

            "depth": 30,

            "roads":

            [

                {

                    "side":
                        "south",

                    "type":
                        "street"

                }

            ],


            "neighbors":

            [

                {

                    "side":
                        "east",

                    "type":
                        "building"

                },


                {

                    "side":
                        "west",

                    "type":
                        "building"

                }

            ]

        },



        "requirements":

        {

            "placement":
                "north",


            "floors":
                5,


            "coverage":
                60,


            "courtyard":

            {

                "enabled":
                    True,


                "side":
                    "north",


                "area":
                    12

            },


            "projection":

            {

                "enabled":
                    True,


                "side":
                    "south",


                "depth":
                    1.2

            }

        }

    }