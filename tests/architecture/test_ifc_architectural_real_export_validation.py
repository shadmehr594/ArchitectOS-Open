"""
ArchitectOS Architectural IFC Real Export Validation Test

Pipeline:

Architecture
    |
    v
IFC Entity Model
    |
    v
IFC Export
    |
    v
IFC Reload
    |
    v
Validation
"""


import os
import ifcopenshell


from core.architecture.bim.architectural_ifc_exporter_v1 import (
    ArchitecturalIFCExporterV1
)



def test_ifc_architectural_real_export_validation():


    print(
        "\n"
        "================================\n"
        "IFC REAL EXPORT VALIDATION TEST\n"
        "================================\n"
    )


    export_path = (
        "exports/ArchitectOS_Architectural_Final.ifc"
    )


    os.makedirs(
        "exports",
        exist_ok=True
    )


    exporter = ArchitecturalIFCExporterV1()



    exporter.export(
        export_path
    )


    assert os.path.exists(
        export_path
    )


    model = ifcopenshell.open(
        export_path
    )


    projects = model.by_type(
        "IfcProject"
    )


    assert len(projects) > 0



    walls = model.by_type(
        "IfcWall"
    )


    slabs = model.by_type(
        "IfcSlab"
    )


    spaces = model.by_type(
        "IfcSpace"
    )


    print(
        "\nIFC VALIDATION:"
    )

    print(
        "Projects:",
        len(projects)
    )

    print(
        "Walls:",
        len(walls)
    )

    print(
        "Slabs:",
        len(slabs)
    )

    print(
        "Spaces:",
        len(spaces)
    )


    print(
        "\n✅ REAL IFC EXPORT VALIDATION PASSED"
    )