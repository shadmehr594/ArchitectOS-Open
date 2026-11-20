import os


from core.architecture.bim.architectural_ifc_exporter_v1 import (

    ArchitecturalIFCExporterV1

)



import ifcopenshell



def test_architectural_ifc_export():


    exporter = ArchitecturalIFCExporterV1()



    wall = exporter.model.create_entity(

        "IfcWall",

        GlobalId="wall001",

        Name="Main Wall"

    )



    exporter.add_element(

        wall

    )



    path = (

        "exports/ArchitectOS_Architectural.ifc"

    )


    exporter.export(

        path

    )



    assert os.path.exists(

        path

    )


    model = ifcopenshell.open(

        path

    )


    walls = model.by_type(

        "IfcWall"

    )


    assert len(walls) == 1



    print(

        "\n✅ ARCHITECTURAL IFC EXPORT PASSED"

    )