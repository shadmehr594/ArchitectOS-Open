from core.bim.semantic_vertical_mapping_engine import (
    SemanticBIMVerticalMappingEngine
)



def test_semantic_vertical_mapping():


    engine = SemanticBIMVerticalMappingEngine()



    geometry = {


        "level":
            "G",


        "elements":

            [

                {

                    "system":
                        "escalator",

                    "geometry":
                        [
                            [5,5],
                            [11,6]
                        ]

                },


                {

                    "system":
                        "elevator_core",

                    "geometry":
                        [
                            [10,10],
                            [14,14]
                        ]

                },


                {

                    "system":
                        "stair_core",

                    "geometry":
                        [
                            [0,10],
                            [4,14]
                        ]

                }

            ]

    }



    result = engine.generate(

        geometry

    )


    print(
        "\n===== SEMANTIC BIM VERTICAL RESULT ====="
    )


    print(result)



    assert len(

        result["semantic_elements"]

    ) == 3



    print(
        "\n✅ SEMANTIC BIM VERTICAL MAPPING TEST PASSED"
    )



if __name__=="__main__":

    test_semantic_vertical_mapping()