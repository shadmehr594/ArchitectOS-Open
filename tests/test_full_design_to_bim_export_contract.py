from core.tools.design_tool import DesignTool
from core.bim.design_geometry_adapter import DesignGeometryAdapter
from core.integration.design_bim_bridge import DesignBIMBridge
from core.bim.ifc_integration_layer import IFCIntegrationLayer
from core.bim.revit_export_engine import RevitExportEngine


def test_full_design_to_bim_export_contract():

    print(
        "\n🏗️ FULL DESIGN → BIM EXPORT CONTRACT TEST START"
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

    print(
        "📐 Geometry contract validated"
    )


    # ======================================
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
        bim_result.get(
            "status"
        )
        ==
        "completed"
    )

    print(
        "🏗️ BIM contract validated"
    )


    bim_output = bim_result.get(
        "bim_result"
    )


    # ======================================
    # IFC
    # ======================================

    ifc = IFCIntegrationLayer()

    ifc_result = ifc.integrate(
        {
            "elements":
            bim_output.get(
                "bim_elements",
                []
            )
        }
    )


    assert (
        ifc_result.get(
            "ifc_ready"
        )
        is True
    )


    print(
        "🌐 IFC contract validated"
    )


    # ======================================
    # REVIT
    # ======================================

    exporter = RevitExportEngine()

    revit_result = exporter.export(
        bim_output
    )

    assert (
        revit_result.get(
            "status"
        )
        in
        [
            "success",
            "export_ready",
            "completed"
        ]
    )

    print(
        "🏢 Revit contract validated"
    )


    print(
        "\n🎯 FULL DESIGN → BIM EXPORT CONTRACT PASSED"
    )