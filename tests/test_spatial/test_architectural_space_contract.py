from core.spatial.architectural_space_contract import (
    ArchitecturalSpaceContract
)



def test_courtyard_contract():


    engine = ArchitecturalSpaceContract()


    courtyard = {


        "polygon":

        [

            [0,0],

            [4,0],

            [4,5],

            [0,5]

        ],


        "area":
            20

    }



    result = engine.from_courtyard(
        courtyard
    )


    print(
        result
    )


    assert result["type"] == "courtyard"

    assert (
        result["requirements"]
        ["open_to_sky"]
        is True
    )