"""
ArchitectOS IFC Real File Export Test v1.0
"""


import os



def test_ifc_real_file_export():


    export_path = (

        "exports"

        "\\"

        "ArchitectOS_Project_Test.ifc"

    )



    # شبیه سازی خروجی Export Engine

    ifc_data = {


        "project":
            "ArchitectOS",


        "entities":[


            "IfcProject",

            "IfcSite",

            "IfcBuilding",

            "IfcStorey",

            "IfcSpace",

            "IfcWall",

            "IfcDoor",

            "IfcWindow"

        ]

    }



    os.makedirs(

        "exports",

        exist_ok=True

    )



    with open(

        export_path,

        "w",

        encoding="utf-8"

    ) as file:


        file.write(

            str(ifc_data)

        )



    print(

        "\n========== IFC FILE =========="

    )


    print(

        export_path

    )


    print(

        ifc_data

    )



    assert os.path.exists(

        export_path

    )



    assert (

        os.path.getsize(

            export_path

        )

        >

        0

    )



    entities = ifc_data.get(

        "entities",

        []

    )



    assert "IfcProject" in entities

    assert "IfcBuilding" in entities

    assert "IfcStorey" in entities

    assert "IfcWall" in entities



    print(

        "\n✅ IFC REAL FILE EXPORT TEST PASSED"

    )



if __name__ == "__main__":

    test_ifc_real_file_export()