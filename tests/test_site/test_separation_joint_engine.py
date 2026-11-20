"""
ArchitectOS Separation Joint Engine Test v1.0
"""


from core.site.separation_joint_engine import SeparationJointEngine



def test_separation_joint():


    engine = SeparationJointEngine()



    building = {


        "height": 15


    }



    neighbors = {


        "north": False,


        "south": False,


        "east": True,


        "west": True


    }



    requirement = {


        "enabled": True


    }



    result = engine.analyze(

        building,

        neighbors,

        requirement

    )



    print(

        "\n========== RESULT =========="

    )


    print(

        result

    )



    joints = result.get(

        "separation_joints",

        {}

    )



    # ----------------------------------
    # CHECK EAST/WEST
    # ----------------------------------

    assert joints.get(

        "east",

        {}

    ).get(

        "joint"

    ) > 0



    assert joints.get(

        "west",

        {}

    ).get(

        "joint"

    ) > 0



    # ----------------------------------
    # CHECK NORTH/SOUTH
    # ----------------------------------

    assert joints.get(

        "north",

        {}

    ).get(

        "joint"

    ) == 0



    assert joints.get(

        "south",

        {}

    ).get(

        "joint"

    ) == 0



    # ----------------------------------
    # CHECK HEIGHT
    # ----------------------------------

    assert result.get(

        "height"

    ) == 15



    print(

        "\n✅ Separation Joint Engine TEST PASSED"

    )



def test_real_parcel2_polygon_edge_offsets_resolve_without_side_name_guessing():
    parcel = [
        [9.495348, 22.127313], [0.0, 18.990695],
        [6.273236, 0.0], [15.768583, 3.136618],
    ]
    result = SeparationJointEngine().resolve_buildable_envelope(
        parcel,
        {"edge_offsets": [0.0, 0.10, 0.10, 0.10],
         "source": "user_project_requirement",
         "evidence_status": "authoritative_for_current_test"},
    )
    assert result["status"] == "resolved"
    assert result["edge_offsets"] == [0.0, 0.10, 0.10, 0.10]
    assert result["buildable_area"] < 200.000122
    assert len(result["buildable_boundary"]) == 4

    centerline = SeparationJointEngine().resolve_buildable_envelope(
        parcel, {"edge_offsets": [0.10, 0.20, 0.20, 0.20]}
    )
    inner_face = SeparationJointEngine().resolve_buildable_envelope(
        parcel, {"edge_offsets": [0.20, 0.30, 0.30, 0.30]}
    )
    assert centerline["status"] == "resolved"
    assert inner_face["status"] == "resolved"
    assert centerline["buildable_area"] < result["buildable_area"]
    assert inner_face["buildable_area"] < centerline["buildable_area"]


def test_non_axis_aligned_parcel_without_explicit_edge_offsets_fails_closed():
    result = SeparationJointEngine().resolve_buildable_envelope(
        [[0, 0], [8, 1], [7, 10], [-1, 9]], {}
    )
    assert result["status"] == "pending"
    assert result["buildable_boundary"] is None
    assert result["reason"] == "axis_aligned_rectangular_parcel_required"


if __name__ == "__main__":

    test_separation_joint()
