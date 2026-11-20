"""
ArchitectOS Neighbor Detector Test v1.0
"""


from core.site.neighbor_detector import NeighborDetector



def test_neighbor_detection():


    site = {

        "boundary":

        [

            [0,0],
            [20,0],
            [20,30],
            [0,30]

        ],


        "neighbors":

        [

            {
                "side": "east",
                "type": "building"
            },


            {
                "side": "west",
                "type": "building"
            }

        ],


        "roads":

        [

            {
                "side": "south",
                "type": "street"
            }

        ]

    }



    detector = NeighborDetector()


    result = detector.analyze(
        site
    )


    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )


    # ==========================
    # ASSERTIONS
    # ==========================


    assert result["east"]["exists"] is True

    assert result["east"]["shared_wall"] is True

    assert result["east"]["light_allowed"] is False



    assert result["west"]["exists"] is True

    assert result["west"]["shared_wall"] is True

    assert result["west"]["light_allowed"] is False



    assert result["south"]["road"] is True

    assert result["south"]["access"] is True



    assert result["north"]["exists"] is False

    assert result["north"]["light_allowed"] is True



    print(
        "\n✅ Neighbor Detector TEST PASSED"
    )



if __name__ == "__main__":

    test_neighbor_detection()