"""
ArchitectOS Spatial Lightwell Aware Layout Test v1.0
"""


from core.spatial.lightwell_aware_layout import LightwellAwareLayout



def test_lightwell_spatial_layout():


    engine = LightwellAwareLayout()



    building = [

        [0,0],

        [20,0],

        [20,18],

        [0,18]

    ]



    lightwell = [

        [8.5,7],

        [11.5,7],

        [11.5,11],

        [8.5,11]

    ]



    result = engine.generate(

        building,

        lightwell,

        units=4

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    assert result.get(
        "lightwell"
    ).get(
        "access"
    ) == "corridor"



    spaces = result.get(
        "spaces"
    )



    assert len(
        spaces
    ) == 5



    assert spaces[0].get(
        "type"
    ) == "corridor"



    for unit in spaces[1:]:


        assert unit.get(
            "type"
        ) == "residential_unit"



        assert unit.get(
            "access_to_lightwell"
        ) is True



    print(
        "\n✅ SPATIAL LIGHTWELL AWARE LAYOUT TEST PASSED"
    )



if __name__ == "__main__":

    test_lightwell_spatial_layout()