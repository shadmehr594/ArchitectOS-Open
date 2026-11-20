"""
ArchitectOS Design Geometry Adapter Test

Validates:

DesignTool
      |
      v
DesignGeometryAdapter
      |
      v
BIM Geometry Contract

No BIM pipeline execution.
"""


from core.tools.design_tool import DesignTool

from core.bim.design_geometry_adapter import (
    DesignGeometryAdapter
)



def test_design_geometry_adapter():


    print(
        "\n📐 DESIGN GEOMETRY ADAPTER TEST START"
    )


    # ======================================
    # DESIGN OUTPUT
    # ======================================

    design_tool = DesignTool()


    design_result = design_tool.execute(
        state="modern villa 12x10"
    )


    assert design_result is not None


    assert (
        "spatial"
        in design_result
    )


    print(
        "✅ DesignTool spatial output validated"
    )



    # ======================================
    # ADAPTER
    # ======================================

    adapter = DesignGeometryAdapter()


    project = {

        "spatial":
        design_result.get(
            "spatial",
            {}
        )

    }


    geometry_result = adapter.convert(
        project
    )


    assert geometry_result is not None


    assert (
        "geometry"
        in geometry_result
    )


    print(
        "✅ Geometry conversion completed"
    )



    # ======================================
    # GEOMETRY CONTRACT
    # ======================================

    geometry = geometry_result.get(
        "geometry"
    )


    assert geometry is not None


    assert (
        "rooms"
        in geometry
    )


    assert (
        "levels"
        in geometry
    )


    assert (
        isinstance(
            geometry["rooms"],
            list
        )
    )


    assert (
        isinstance(
            geometry["levels"],
            list
        )
    )


    print(
        "✅ BIM geometry contract validated"
    )


    print(
        "\n🎯 DESIGN GEOMETRY ADAPTER TEST PASSED"
    )