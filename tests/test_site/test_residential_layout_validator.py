"""
ArchitectOS Residential Layout Validator Test v1.0
"""


from core.spatial.residential_layout_validator import (
    ResidentialLayoutValidator
)



def test_residential_layout_validator():


    engine = ResidentialLayoutValidator()



    layout = {


        "units":

        [

            {

                "id":
                    "unit_1",


                "rooms":

                [

                    {
                        "type":
                            "living",

                        "light_source":
                            "main_facade"

                    },


                    {
                        "type":
                            "bedroom",

                        "light_source":
                            "lightwell"

                    },


                    {
                        "type":
                            "bedroom",

                        "light_source":
                            "lightwell"

                    },


                    {
                        "type":
                            "bathroom",

                        "ventilation":
                            "duct_bathroom"

                    },


                    {
                        "type":
                            "kitchen",

                        "ventilation":
                            "duct_kitchen"

                    }

                ]

            }

        ]

    }



    lightwell = {


        "width":
            3,


        "depth":
            4,


        "area":
            12

    }



    result = engine.validate(

        layout,

        lightwell

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    assert result.get(
        "valid"
    ) is True



    assert result["checks"].get(
        "bedroom_light"
    ) is True



    assert result["checks"].get(
        "bathroom_ventilation"
    ) is True



    assert result["checks"].get(
        "kitchen_ventilation"
    ) is True



    assert result["checks"].get(
        "lightwell"
    ) is True



    print(
        "\n✅ RESIDENTIAL LAYOUT VALIDATOR TEST PASSED"
    )



if __name__ == "__main__":

    test_residential_layout_validator()