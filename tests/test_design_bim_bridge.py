"""
ArchitectOS Design → BIM Bridge Test

Validates:

DesignTool
      |
      v
DesignGeometryAdapter
      |
      v
DesignBIMBridge
      |
      v
FullBIMPipeline

No Intent / Chat / Render dependency.
"""


from core.tools.design_tool import DesignTool

from core.bim.design_geometry_adapter import (
    DesignGeometryAdapter
)

from core.integration.design_bim_bridge import (
    DesignBIMBridge
)



def test_design_to_bim_bridge():

    print(
        "\n🏗️ DESIGN → BIM BRIDGE TEST START"
    )


    # ======================================
    # DESIGN GENERATION
    # ======================================

    design_tool = DesignTool()


    design_result = design_tool.execute(
        state="modern villa 12x10"
    )


    print(
        "DESIGN RESULT KEYS:",
        design_result.keys()
    )

    print(
        "DESIGN SPATIAL:",
        bool(design_result.get("spatial"))
    )

    print(
        "DESIGN GEOMETRY:",
        bool(design_result.get("geometry"))
    )


    assert design_result is not None


    assert (
        design_result.get("type")
        ==
        "design"
    )


    assert (
        "spatial"
        in design_result
    )


    print(
        "✅ DesignTool output validated"
    )



    # ======================================
    # DESIGN → GEOMETRY
    # ======================================

    adapter = DesignGeometryAdapter()


    geometry_result = adapter.convert(
        design_result
    )


    assert geometry_result is not None


    assert (
        "geometry"
        in geometry_result
    )


    design_result["geometry"] = (
        geometry_result.get(
            "geometry",
            {}
        )
    )


    print(
        "✅ Design geometry generated"
    )


    print(
        "ROOMS:",
        len(
            design_result["geometry"].get(
                "rooms",
                []
            )
        )
    )


    print(
        "WALLS:",
        len(
            design_result["geometry"].get(
                "walls",
                []
            )
        )
    )


    # ======================================
    # BRIDGE
    # ======================================

    bridge = DesignBIMBridge()


    bim_result = bridge.run_bim(
        design_result
    )


    assert bim_result is not None


    assert (
        bim_result.get("status")
        ==
        "completed"
    )


    print(
        "✅ BIM Bridge executed"
    )



    # ======================================
    # BIM RESULT
    # ======================================

    result = bim_result.get(
        "bim_result"
    )


    assert result is not None


    assert (
        "bim_elements"
        in result
    )


    assert (
        "ifc_model"
        in result
    )


    print(
        "BIM ELEMENTS:",
        len(
            result.get(
                "bim_elements",
                []
            )
        )
    )


    print(
        "✅ BIM pipeline output validated"
    )


    print(
        "\n🎯 DESIGN → BIM BRIDGE TEST PASSED"
    )