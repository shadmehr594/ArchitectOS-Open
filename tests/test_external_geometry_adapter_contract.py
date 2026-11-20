from core.bim.external_geometry_adapter import (
    ExternalGeometryAdapter
)


def test_external_geometry_adapter_contract():

    print(
        "\n🔌 EXTERNAL GEOMETRY ADAPTER CONTRACT TEST START"
    )


    adapter = ExternalGeometryAdapter()


    # ======================================
    # TEST 1
    # CAD INPUT
    # ======================================

    cad_input = {

        "source":
        "DWG",

        "rooms":[

            {

                "id":
                "Living",

                "geometry":

                {

                    "x":0,

                    "y":0,

                    "width":6,

                    "height":5

                }

            }

        ],

        "floors":[

            "F1"

        ]

    }



    result = adapter.convert(
        cad_input
    )


    assert result is not None


    assert (
        "rooms"
        in result
    )


    assert (
        len(result["rooms"])
        ==
        1
    )


    print(
        "✅ CAD geometry contract converted"
    )



    # ======================================
    # TEST 2
    # INTERNAL BIM FORMAT
    # ======================================


    bim_input = {

        "source":
        "BIM",


        "rooms":[

            {

                "id":
                "Room01",

                "x":
                0,

                "y":
                0,

                "w":
                5,

                "h":
                5

            }

        ]

    }



    result = adapter.convert(
        bim_input
    )


    assert (
        result["rooms"][0]["x"]
        ==
        0
    )


    assert (
        result["rooms"][0]["w"]
        ==
        5
    )


    print(
        "✅ Internal BIM geometry preserved"
    )



    # ======================================
    # TEST 3
    # FALLBACK
    # ======================================


    result = adapter.convert(
        {}
    )


    assert (
        "rooms"
        in result
    )


    assert (
        len(result["rooms"])
        >
        0
    )


    print(
        "✅ Fallback geometry preserved"
    )



    print(
        "\n🎯 EXTERNAL GEOMETRY ADAPTER CONTRACT PASSED"
    )