import ifcopenshell


from core.architecture.bim.architectural_ifc_exporter_v2 import (
    ArchitecturalIFCExporterV2
)



def test_ifc_architectural_space_boundary_validation():


    geometry = {


        "spaces":[

            {
                "name":"Main_Hall",
                "floor":"F1",
                "height":3.2
            }

        ],


        "boundaries":[

            {
                "space":"Main_Hall",
                "floor":"F1"
            }

        ],


        "slabs":[

            {
                "space":"Main_Hall",
                "floor":"F1"
            }

        ],


        "openings":[],

        "vertical_geometry":[]

    }



    path = (
        "exports/"
        "ArchitectOS_Space_Boundary.ifc"
    )



    ArchitecturalIFCExporterV2().export(
        geometry,
        path
    )



    model = ifcopenshell.open(
        path
    )



    spaces = model.by_type(
        "IfcSpace"
    )


    boundaries = model.by_type(
        "IfcRelSpaceBoundary"
    )



    print(
        "\nSPACE BOUNDARY CHECK:"
    )


    print(
        "Spaces:",
        len(spaces)
    )


    print(
        "Boundaries:",
        len(boundaries)
    )



    assert len(spaces)==1

    assert len(boundaries)>=1



    print(
        "\n✅ IFC SPACE BOUNDARY VALIDATION PASSED"
    )