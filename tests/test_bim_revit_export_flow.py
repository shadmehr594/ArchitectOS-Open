from core.bim.full_bim_pipeline import (
    FullBIMPipeline
)

from core.bim.revit_export_engine import (
    RevitExportEngine
)



def test_bim_revit_export_flow():

    print(
        "\n🏢 BIM → REVIT EXPORT FLOW TEST START"
    )


    # ======================================
    # STEP 1
    # BIM PIPELINE
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
        "✅ BIM pipeline validated"
    )



    # ======================================
    # STEP 2
    # REVIT EXPORT
    # ======================================

    exporter = RevitExportEngine()


    export_result = exporter.export(

        bim_result

    )


    assert export_result is not None


    assert (
        "status"
        in export_result
    )


    assert (
        export_result.get(
            "status"
        )
        in
        [
            "success",
            "export_ready",
            "completed"
        ]
    )


    print(
        "✅ Revit export contract validated"
    )



    print(
        "\n🎯 BIM → REVIT EXPORT FLOW PASSED"
    )