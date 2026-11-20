"""
ArchitectOS IFC Export Engine Real Test v1.0
"""


import os


from core.export.ifc_export_engine import (
    IFCExportEngine
)



def test_ifc_export_engine_real():


    engine = IFCExportEngine()



    output_path = (

        "exports"

        "\\"

        "ArchitectOS_Real_Test.ifc"

    )



    geometry_input = {


        "ifc_entities":[


            {

                "entity":
                    "IfcSpace",

                "level":
                    "F1",

                "geometry":

                {

                    "polygon":[

                        [0,0],

                        [4,0],

                        [4,5],

                        [0,5]

                    ],

                    "height":
                        3.2

                }

            },


            {

                "entity":
                    "IfcWall",

                "level":
                    "F1",

                "geometry":

                {

                    "start":[

                        0,

                        0

                    ],

                    "end":[

                        4,

                        0

                    ],

                    "height":
                        3.2,

                    "thickness":
                        0.2

                }

            }


        ]

    }



    result = engine.export(

        geometry_input,

        output_path

    )



    print(

        "\n========== IFC EXPORT RESULT =========="

    )


    print(

        result

    )



    assert os.path.exists(

        output_path

    )



    assert os.path.getsize(

        output_path

    ) > 0



    print(

        "\n✅ IFC EXPORT ENGINE REAL TEST PASSED"

    )



if __name__ == "__main__":

    test_ifc_export_engine_real()