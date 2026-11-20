from core.tools.design_tool import DesignTool

from core.render.design_render_adapter import (
    DesignRenderAdapter
)


def test_full_design_to_render_contract():

    print(
        "\n🎨 FULL DESIGN → RENDER CONTRACT TEST START"
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


    print(
        "✅ Design contract validated"
    )


    # ======================================
    # DESIGN → RENDER ADAPTER
    # ======================================

    adapter = DesignRenderAdapter()


    prepared = adapter.prepare_design(
        design_result
    )


    assert prepared is not None


    assert (
        prepared.get("source")
        ==
        "design_runtime"
    )


    assert (
        "spatial"
        in prepared
    )


    assert (
        "site"
        in prepared
    )


    print(
        "🎨 Design Render contract validated"
    )


    # ======================================
    # RENDER CONTEXT CONTRACT
    # ======================================

    assert (
        prepared.get("type")
        is not None
    )


    assert (
        prepared.get("style")
        is not None
    )


    print(
        "🌉 Render handoff contract validated"
    )


    print(
        "\n🎯 FULL DESIGN → RENDER CONTRACT PASSED"
    )