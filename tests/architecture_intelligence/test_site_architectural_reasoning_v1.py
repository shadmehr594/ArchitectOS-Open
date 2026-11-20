from core.architecture.brain.architectural_brain import ArchitecturalBrain



def test_site_architectural_reasoning_v1():


    print(
        "\n====== SITE ARCHITECTURAL REASONING V1 ======"
    )


    site = {


        "boundary": [

            (0,0),
            (20,0),
            (20,30),
            (0,30)

        ],


        "orientation": {

            "north": "top",

            "south": "street"

        },


        "neighbors": {

            "east": True,

            "west": True

        },


        "climate": {

            "type": "hot_dry"

        },


        "access": {

            "main_access": "south"

        }


    }



    intent = {


        "building_type": "villa",


        "floors": 2,


        "style": "modern",


        "requirements": [

            "pool",

            "garden",

            "parking"

        ]

    }



    brain = ArchitecturalBrain()



    result = brain.design(

        {

            "site": site,

            "intent": intent

        }

    )



    print(
        "\n====== ARCHITECTURAL DECISION MODEL ======"
    )


    print(
        result.to_dict()
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_site_architectural_reasoning_v1()