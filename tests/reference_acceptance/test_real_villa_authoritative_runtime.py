import json
from pathlib import Path

import ezdxf
import ifcopenshell

from core.app_boot import AppBoot
from core.bim.design_geometry_adapter import DesignGeometryAdapter
from core.bim.full_bim_pipeline import FullBIMPipeline
from core.export.ifc_export_engine import IFCExportEngine
from core.integration.design_bim_bridge import DesignBIMBridge
from core.reference_acceptance.reference_acceptance_comparator import (
    ReferenceAcceptanceComparator,
)


BRIEF = "یک ویلای مسکونی یک طبقه طراحی کن."
REFERENCE_CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "exports" / "DEFAULT" / "reference_analysis" / "reference_contract_villa.json"
)
GEOMETRY_KEYS = (
    "physical_walls", "boundary_segments", "openings", "floors",
    "floor_geometry", "slabs", "vertical_geometry", "stairs", "ramps",
    "site_geometry", "spaces", "rooms", "levels",
)


def _summary(value):
    value = value if isinstance(value, dict) else {}
    geometry = value.get("architectural_geometry")
    if not isinstance(geometry, dict):
        geometry = value.get("geometry", {})
    if not isinstance(geometry, dict):
        geometry = {}
    return {
        "architecture_first": value.get("architecture_first"),
        "architectural_geometry": bool(value.get("architectural_geometry")),
        "geometry": {key: len(geometry.get(key, []) or []) if isinstance(geometry.get(key, []), list)
                     else bool(geometry.get(key)) for key in GEOMETRY_KEYS},
        "vertical_section": bool(value.get("vertical_section")),
        "geometry_intent": bool(value.get("geometry_intent")),
    }


def _run_real_villa(monkeypatch):
    trace = {}
    original_convert = DesignGeometryAdapter.convert
    original_run_bim = DesignBIMBridge.run_bim
    original_pipeline = FullBIMPipeline.generate

    def traced_convert(self, project=None):
        trace["DesignGeometryAdapter.input"] = _summary(project)
        result = original_convert(self, project)
        trace["DesignGeometryAdapter.output"] = _summary(result)
        return result

    def traced_run_bim(self, design_result):
        trace["DesignBIMBridge.input"] = _summary(design_result)
        result = original_run_bim(self, design_result)
        trace["DesignBIMBridge.output"] = _summary(result.get("bim_result", {}))
        return result

    def traced_pipeline(self, project=None):
        trace["FullBIMPipeline.input"] = _summary(project)
        result = original_pipeline(self, project)
        trace["FullBIMPipeline.output"] = _summary(result)
        return result

    monkeypatch.setattr(DesignGeometryAdapter, "convert", traced_convert)
    monkeypatch.setattr(DesignBIMBridge, "run_bim", traced_run_bim)
    monkeypatch.setattr(FullBIMPipeline, "generate", traced_pipeline)

    design = AppBoot().get_brain().run(BRIEF)
    trace["GOD_CORE.output"] = _summary(design)
    result = design["execution_bridge"]
    trace["ArchitectOSDesignExecutionBridge.output"] = _summary(result["design"])
    return trace, design, result


def test_real_villa_preserves_authoritative_geometry_before_export(monkeypatch):
    trace, design, result = _run_real_villa(monkeypatch)
    assert trace, "runtime trace must expose every architecture/BIM boundary"
    final_design = result["design"]
    geometry = final_design["architectural_geometry"]
    assert final_design["architecture_first"] is True
    assert geometry["physical_walls"]
    assert len(geometry["floor_geometry"]) == 1
    assert len(geometry["slabs"]) == 1
    assert [level["name"] for level in final_design["vertical_section"]["levels"]] == ["F1"]
    assert not geometry.get("vertical_geometry")
    assert len(final_design.get("geometry", {}).get("rooms", [])) != 2
    assert final_design["vertical_section"]
    assert final_design["geometry_intent"]
    adapter_input = trace["DesignGeometryAdapter.input"]["geometry"]
    assert adapter_input["physical_walls"] == len(geometry["physical_walls"])
    assert adapter_input["openings"] == len(geometry.get("openings", []))
    assert adapter_input["vertical_geometry"] == len(geometry.get("vertical_geometry", []))

    pipeline = result["bim_result"]["bim_result"]
    exports = pipeline["exports"]
    export_files = {
        "ifc": exports["ifc"]["path"],
        "dxf": exports["cad"]["file"]["file"],
        "dwg": exports.get("dwg", {}).get("file"),
    }
    runtime_summary = {
        "prompt": BRIEF,
        "architectural_intent": design["architectural_intent"],
        "architecture_first": final_design["architecture_first"],
        "vertical_section": final_design["vertical_section"],
        "geometry": pipeline["geometry"],
        "exports": exports,
        "export_files": export_files,
        "output_dir": exports["output_dir"],
        "boundary_trace": trace,
    }
    output_dir = Path(exports["output_dir"])
    ifc_model = ifcopenshell.open(export_files["ifc"])
    dxf_document = ezdxf.readfile(export_files["dxf"])
    dxf_entities = list(dxf_document.modelspace())
    runtime_summary["artifact_inspection"] = {
        "ifc": {
            "storeys": [
                {"name": item.Name, "elevation": item.Elevation}
                for item in ifc_model.by_type("IfcBuildingStorey")
            ],
            "entity_counts": {
                name: len(ifc_model.by_type(name))
                for name in ("IfcWall", "IfcSlab", "IfcDoor", "IfcWindow")
            },
        },
        "dxf": {
            "version": dxf_document.dxfversion,
            "entity_counts": {
                entity_type: sum(item.dxftype() == entity_type for item in dxf_entities)
                for entity_type in {item.dxftype() for item in dxf_entities}
            },
            "layers": sorted({item.dxf.layer for item in dxf_entities}),
            "elevation_view_count": 0,
        },
        "dwg": {
            "header": Path(export_files["dwg"]).read_bytes()[:6].decode("ascii")
            if export_files["dwg"] else None,
        },
    }
    (output_dir / "generated_runtime_summary.json").write_text(
        json.dumps(runtime_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    reference = json.loads(REFERENCE_CONTRACT.read_text(encoding="utf-8"))
    comparison = ReferenceAcceptanceComparator().compare(reference, runtime_summary)
    (output_dir / "villa_reference_divergence_report.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    assert Path(export_files["ifc"]).is_file()
    assert Path(export_files["dxf"]).is_file()
    assert (output_dir / "generated_runtime_summary.json").is_file()
    assert (output_dir / "villa_reference_divergence_report.json").is_file()


def test_ifc_empty_storey_state_fails_closed_without_fake_f1(tmp_path):
    try:
        IFCExportEngine().export({}, output_path=tmp_path / "empty.ifc")
    except RuntimeError as error:
        assert str(error) == (
            "ifc_export_unresolved: no BIM elements or authoritative level evidence"
        )
    else:
        raise AssertionError("empty IFC state must fail closed")
    assert not (tmp_path / "empty.ifc").exists()
