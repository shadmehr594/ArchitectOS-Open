from core.bim.full_bim_pipeline import (
    FullBIMPipeline
)

from core.bim.ifc_integration_layer import (
    IFCIntegrationLayer
)



def test_bim_ifc_export_flow():

    print(
        "\n🌐 BIM → IFC EXPORT FLOW TEST START"
    )


    # ======================================
    # STEP 1
    # RUN BIM PIPELINE
    # ======================================

    pipeline = FullBIMPipeline()


    bim_result = pipeline.run(

        {

            "geometry":

            {

                "rooms":

                [

                    {

                        "id":
                        "Living",

                        "type":
                        "space",

                        "geometry":

                        {

                            "x":0,

                            "y":0,

                            "width":5,

                            "height":5

                        }

                    }

                ],


                "floors":

                [

                    "F1"

                ]

            }

        }

    )


    assert bim_result is not None


    assert (
        "bim_elements"
        in bim_result
    )


    print(
        "✅ BIM pipeline output validated"
    )



    # ======================================
    # STEP 2
    # IFC INTEGRATION
    # ======================================


    ifc_layer = IFCIntegrationLayer()


    ifc_result = ifc_layer.integrate(

        {

            "elements":
            bim_result.get(
                "bim_elements",
                []
            )

        },

        {

            "schema":
            "IFC4",

            "project":
            "ArchitectOS_Test"

        }

    )



    assert ifc_result is not None


    assert (
        ifc_result["ifc_ready"]
        is True
    )


    assert (
        ifc_result["ifc"]["schema"]
        ==
        "IFC4"
    )


    assert (
        "entities"
        in ifc_result["ifc"]
    )


    print(
        "✅ IFC contract validated"
    )



    print(
        "\n🎯 BIM → IFC EXPORT FLOW PASSED"
    )