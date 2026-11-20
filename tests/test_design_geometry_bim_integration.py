"""
ArchitectOS Design Geometry BIM Integration Test

Flow:

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

Validates integration contract only.
"""


from core.tools.design_tool import DesignTool

from core.bim.design_geometry_adapter import (
    DesignGeometryAdapter
)

from core.integration.design_bim_bridge import (
    DesignBIMBridge
)



def test_design_geometry_bim_integration():


    print(
        "\n🏗️ DESIGN → GEOMETRY → BIM INTEGRATION TEST START"
    )


    # ======================================
    # STEP 1
    # DESIGN
    # ======================================

    design_tool = DesignTool()


    design_result = design_tool.execute(
        state="modern villa 12x10"
    )


    assert design_result is not None


    assert (
        design_result.get("type")
        ==
        "design"
    )


    print(
        "✅ Design output generated"
    )



    # ======================================
    # STEP 2
    # GEOMETRY ADAPTER
    # ======================================

    adapter = DesignGeometryAdapter()


    geometry_result = adapter.convert(

        {

            "spatial":
            design_result.get(
                "spatial",
                {}
            )

        }

    )


    assert geometry_result is not None


    geometry = geometry_result.get(
        "geometry"
    )


    assert geometry is not None


    assert (
        "rooms"
        in geometry
    )


    print(
        "✅ Design geometry contract created"
    )



    # ======================================
    # STEP 3
    # BIM BRIDGE
    # ======================================

    bridge = DesignBIMBridge()


    bim_result = bridge.run_bim(

        {

            **design_result,

            "geometry":
            geometry

        }

    )


    assert bim_result is not None


    assert (
        bim_result.get("status")
        ==
        "completed"
    )


    print(
        "✅ BIM bridge completed"
    )



    # ======================================
    # STEP 4
    # BIM OUTPUT
    # ======================================

    final_bim = bim_result.get(
        "bim_result"
    )


    assert final_bim is not None


    assert (
        "bim_elements"
        in final_bim
    )


    assert (
        "ifc_model"
        in final_bim
    )


    print(
        "✅ BIM output contract validated"
    )


    print(
        "\n🎯 DESIGN → GEOMETRY → BIM INTEGRATION PASSED"
    )