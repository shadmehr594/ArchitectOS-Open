# ==================================================
# ArchitectOS Design -> DAE Export Contract Test
# ==================================================


from core.integration.design_visualization_bridge import (
    DesignVisualizationBridge
)



def test_design_to_dae_export_contract():


    design = {

        "geometry":

        {

            "walls":

            [

                {

                    "id": 1,

                    "length": 10,

                    "height": 3

                }

            ],


            "slabs":

            [],


            "doors":

            []

        },


        "materials":

        {

            "wall":

            "concrete"

        },


        "facade":

        {

            "type":

            "modern"

        }

    }



    bridge = DesignVisualizationBridge()



    result = bridge.export_dae(
        design
    )


    assert result["status"] == "completed"


    assert (
        result["bridge"]
        ==
        "DesignVisualizationBridge_v1.0"
    )


    dae = result["dae_result"]


    assert dae["type"] == "dae"


    assert dae["format"] == "COLLADA"


    assert dae["status"] == "ready"



    print(
        "\n=== DESIGN TO DAE EXPORT CONTRACT PASSED ==="
    )



if __name__ == "__main__":

    test_design_to_dae_export_contract()