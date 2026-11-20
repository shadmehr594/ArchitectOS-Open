"""
ArchitectOS IFC Export Engine v28 Real Test v1.0
"""


import os


from core.export.ifc_export_engine import (
    IFCExportEngine
)



def test_ifc_export_engine_v28_real():


    engine = IFCExportEngine()



    bim_model = {


        "bim_elements":[


            {


                "ifc_type":
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


                "ifc_type":
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

            },


            {
                "ifc_type":
                    "IfcBeam",

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

                    "width":
                        0.3,

                    "depth":
                        0.5

                }
            },


            {


                "ifc_type":
                    "IfcDoor",

                "level":
                    "F1",

                "host_room":
                    "living"

            },


            {


                "ifc_type":
                    "IfcWindow",

                "level":
                    "F1",

                "host_room":
                    "living"

            }


        ]

    }



    result = engine.export(

        bim_model

    )



    print(

        "\n========== IFC EXPORT RESULT =========="

    )


    print(

        result

    )



    assert result is not None



    if isinstance(
        result,
        dict
    ):


        if "path" in result:


            ifc_path = result.get(
                "path"
            )


            assert os.path.exists(

                ifc_path

            )


            assert os.path.getsize(

                ifc_path

            ) > 0



    print(

        "\n✅ IFC EXPORT ENGINE V28 REAL TEST PASSED"

    )



if __name__ == "__main__":

    test_ifc_export_engine_v28_real()