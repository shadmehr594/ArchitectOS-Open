"""
ArchitectOS IFC Material Validation
"""


import ifcopenshell


from core.architecture.bim.architectural_ifc_exporter_v2 import (
    ArchitecturalIFCExporterV2
)



def test_ifc_architectural_material_validation():


    geometry = {


        "spaces":[

            {
                "name":"Room",
                "floor":"F1",
                "height":3.2
            }

        ],


        "boundaries":[

            {
                "space":"Room",
                "floor":"F1"
            }

        ],


        "slabs":[

            {
                "space":"Room",
                "floor":"F1"
            }

        ],


        "openings":[],


        "vertical_geometry":[]

    }



    path = (
        "exports/"
        "ArchitectOS_Material_Test.ifc"
    )


    ArchitecturalIFCExporterV2().export(
        geometry,
        path
    )


    model = ifcopenshell.open(
        path
    )


    materials = model.by_type(
        "IfcMaterial"
    )


    layers = model.by_type(
        "IfcMaterialLayer"
    )


    print(
        "\nMATERIAL CHECK:"
    )


    print(
        "Materials:",
        len(materials)
    )


    print(
        "Layers:",
        len(layers)
    )


    assert len(materials) >= 1

    assert len(layers) >= 1


    print(
        "\n✅ IFC MATERIAL VALIDATION PASSED"
    )