"""
ArchitectOS Design → BIM Pipeline Contract Lock Test

Purpose:
Freeze validated connection between:

DesignTool
    |
DesignGeometryAdapter
    |
DesignBIMBridge
    |
FullBIMPipeline

No Intent / Chat / Render modification.
"""


from core.tools.design_tool import DesignTool

from core.bim.design_geometry_adapter import (
    DesignGeometryAdapter
)

from core.integration.design_bim_bridge import (
    DesignBIMBridge
)

from core.bim.full_bim_pipeline import (
    FullBIMPipeline
)



def test_design_bim_pipeline_contract_lock():

    print(
        "\n🔒 DESIGN → BIM CONTRACT LOCK TEST START"
    )


    # ======================================
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


    assert (
        "spatial"
        in design_result
    )


    print(
        "✅ Design contract locked"
    )



    # ======================================
    # GEOMETRY
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


    geometry = geometry_result.get(
        "geometry"
    )


    assert geometry is not None

    assert (
        "rooms"
        in geometry
    )


    print(
        "📐 Geometry contract locked"
    )



    # ======================================
    # BRIDGE
    # ======================================

    bridge = DesignBIMBridge()


    project = bridge.prepare_bim_project(
        {
            **design_result,
            "geometry": geometry
        }
    )


    assert (
        project.get("geometry")
        ==
        geometry
    )


    print(
        "🔗 BIM bridge contract locked"
    )



    # ======================================
    # BIM
    # ======================================

    pipeline = FullBIMPipeline()


    result = pipeline.run(
        project
    )


    assert result is not None

    assert (
        result.get("status")
        ==
        "completed"
    )


    assert (
        "bim_elements"
        in result
    )


    assert (
        "ifc_model"
        in result
    )


    print(
        "🏗️ BIM pipeline contract locked"
    )


    print(
        "\n🎯 DESIGN → BIM CONTRACT LOCK PASSED"
    )