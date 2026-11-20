# ==========================================================
# PHASE 2D-5 — REFERENCE IMAGE ARCHITECTURAL UNDERSTANDING
# Canonical contract + provider boundary + validation.
#
# No fabricated vision. No image generation. No render. No plan/BIM/IFC.
# ==========================================================

import inspect
import json

from core.prompt_intelligence.reference_image_architectural_understanding_v1 import (
    CONTRACT,
    VERSION,
    ArchitecturalVisionProvider,
    NullVisionProvider,
    ReferenceArchitecturalAnalysisV1,
    ReferenceImageArchitecturalUnderstandingV1,
)
from core.prompt_intelligence.persian_architectural_understanding import understand


class FakeProvider(ArchitecturalVisionProvider):
    name = "fake"
    model = "fake-v1"

    def __init__(self, raw):
        self.raw = raw
        self.calls = 0

    def is_available(self):
        return True

    def analyze(self, image_asset):
        self.calls += 1
        return self.raw


class BoomProvider(ArchitecturalVisionProvider):
    name = "boom"
    model = "boom-v1"

    def is_available(self):
        return True

    def analyze(self, image_asset):
        raise RuntimeError("provider down")


def _img(tmp_path, name="a.bin", data=b"IMG-AAA"):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


# ==========================================================
# A / B — no image, no provider
# ==========================================================

def test_A_no_image_no_analysis_call(tmp_path):
    provider = FakeProvider({"facade_style": "modern"})
    analyzer = ReferenceImageArchitecturalUnderstandingV1(provider)
    r = analyzer.analyze(None)
    assert r["analysis_status"] == "UNSUPPORTED_IMAGE"
    assert provider.calls == 0
    assert r["facade_style"] is None
    assert r["materials"] == []
    assert analyzer.analyze_if_present(None) == {}


def test_B_no_provider_returns_provider_unavailable(tmp_path):
    analyzer = ReferenceImageArchitecturalUnderstandingV1()  # Null provider
    assert isinstance(analyzer.provider, NullVisionProvider)
    r = analyzer.analyze(_img(tmp_path))
    assert r["analysis_status"] == "PROVIDER_UNAVAILABLE"
    assert r["facade_style"] is None
    assert r["materials"] == []
    assert r["style_candidates"] == []


def test_no_fabrication_from_filename(tmp_path):
    """A suggestive filename must NOT produce semantics."""
    analyzer = ReferenceImageArchitecturalUnderstandingV1()
    r = analyzer.analyze(_img(tmp_path, "modern_travertine_neoclassical.png"))
    assert r["analysis_status"] == "PROVIDER_UNAVAILABLE"
    assert r["facade_style"] is None
    assert r["materials"] == []


# ==========================================================
# C / D — canonical semantics
# ==========================================================

def test_C_modern_light_stone_dark_metal(tmp_path):
    raw = {
        "facade_style": "modern",
        "materials": [
            {"type": "stone", "confidence": 0.82,
             "evidence": "dominant light beige panelized facade surface"},
            {"type": "metal", "confidence": 0.5},
        ],
        "windows": {"frame": "thin", "palette": "dark_metal"},
    }
    analyzer = ReferenceImageArchitecturalUnderstandingV1(FakeProvider(raw))
    r = analyzer.analyze(_img(tmp_path))
    assert r["analysis_status"] == "ANALYZED"
    assert r["facade_style"] == "modern"
    assert [m["type"] for m in r["materials"]] == ["stone", "metal"]
    assert r["materials"][0]["confidence"] == 0.82
    assert r["windows"]["frame"] == "thin"


def test_D_neoclassical_candidates_arches_ornament(tmp_path):
    raw = {
        "facade_style": "neoclassical",
        "style_candidates": [
            {"style": "neoclassical", "confidence": 0.6},
            {"style": "modern_classic", "confidence": 0.3},
        ],
        "arches": {"present": True, "intensity": "HIGH"},
        "ornament_level": "HIGH",
    }
    analyzer = ReferenceImageArchitecturalUnderstandingV1(FakeProvider(raw))
    r = analyzer.analyze(_img(tmp_path))
    assert r["analysis_status"] == "ANALYZED_WITH_UNCERTAINTY"
    assert len(r["style_candidates"]) == 2
    assert r["arches"]["present"] is True
    assert r["ornament_level"] == "HIGH"
    assert "multiple_style_candidates" in r["uncertainties"]


# ==========================================================
# E / F — textual policy remains authoritative
# ==========================================================

def test_E_material_only_policy_not_overridden(tmp_path):
    u = understand("از این عکس فقط متریالش رو بگیر")
    assert u["reference_image_policy"]["role"] == "material_only"

    raw = {"facade_style": "neoclassical", "arches": {"present": True, "intensity": "HIGH"}}
    analyzer = ReferenceImageArchitecturalUnderstandingV1(FakeProvider(raw))
    r = analyzer.analyze(_img(tmp_path))
    # analysis may describe the full facade ...
    assert r["facade_style"] == "neoclassical"
    # ... but it carries no role/copy authority
    assert "role" not in r
    assert "copy_reference_geometry" not in r
    # textual policy unchanged
    assert u["reference_image_policy"]["role"] == "material_only"


def test_F_geometry_copy_stays_false(tmp_path):
    u = understand("مثل این عکس باشه ولی فرمش رو کپی نکن")
    assert u["reference_image_policy"]["referenced"] is True
    assert u["reference_image_policy"]["copy_reference_geometry"] is False

    raw = {"facade_rhythm": "regular", "facade_depth": "deep_relief"}
    analyzer = ReferenceImageArchitecturalUnderstandingV1(FakeProvider(raw))
    r = analyzer.analyze(_img(tmp_path))
    # geometry descriptions are evidence only; no mutation/copy field
    assert r["facade_rhythm"] == "regular"
    assert "copy_reference_geometry" not in r


# ==========================================================
# G / H / I / J — limitations and no overreach
# ==========================================================

def test_G_partial_occluded(tmp_path):
    raw = {"occlusions": ["partial_facade"], "facade_style": "modern"}
    analyzer = ReferenceImageArchitecturalUnderstandingV1(FakeProvider(raw))
    r = analyzer.analyze(_img(tmp_path))
    assert r["analysis_status"] == "PARTIAL"
    assert "partial_facade" in r["occlusions"]
    # no invisible facade inferred
    assert r["balconies"] is None
    assert r["entrance"] is None


def test_H_low_resolution(tmp_path):
    raw = {"reference_quality": "low", "facade_style": "modern"}
    analyzer = ReferenceImageArchitecturalUnderstandingV1(FakeProvider(raw))
    r = analyzer.analyze(_img(tmp_path))
    assert r["analysis_status"] == "ANALYZED_WITH_UNCERTAINTY"
    assert r["reference_quality"] == "low"


def test_I_no_scale_no_metric_dimensions(tmp_path):
    raw = {"facade_style": "modern", "windows": {"aspect": "tall", "width_m": 2.4}}
    analyzer = ReferenceImageArchitecturalUnderstandingV1(FakeProvider(raw))
    r = analyzer.analyze(_img(tmp_path))
    assert r["windows"]["aspect"] == "tall"
    assert "width_m" not in r["windows"]
    assert any(u["reason"] == "non_canonical_numeric_measurement" for u in r["unsupported_inferences"])


def test_J_no_orientation_inference(tmp_path):
    raw = {"facade_style": "modern", "orientation": "north"}
    analyzer = ReferenceImageArchitecturalUnderstandingV1(FakeProvider(raw))
    r = analyzer.analyze(_img(tmp_path))
    assert "orientation" not in r
    assert any(u["reason"] == "unsupported_orientation" for u in r["unsupported_inferences"])


def test_no_structural_system_claim(tmp_path):
    raw = {"surface": "visible reinforced concrete frame"}
    analyzer = ReferenceImageArchitecturalUnderstandingV1(FakeProvider(raw))
    r = analyzer.analyze(_img(tmp_path))
    assert any(u["reason"] == "unsupported_structural_claim" for u in r["unsupported_inferences"])


# ==========================================================
# K — invalid narrative
# ==========================================================

def test_K_invalid_free_form_narrative(tmp_path):
    raw = {"description": "A beautiful 1920s villa in Tehran"}
    analyzer = ReferenceImageArchitecturalUnderstandingV1(FakeProvider(raw))
    r = analyzer.analyze(_img(tmp_path))
    assert r["analysis_status"] == "INSUFFICIENT_VISUAL_EVIDENCE"
    assert any(u["reason"] == "free_form_narrative_rejected" for u in r["unsupported_inferences"])
    assert r["facade_style"] is None


def test_provider_error_and_non_dict(tmp_path):
    analyzer = ReferenceImageArchitecturalUnderstandingV1(BoomProvider())
    assert analyzer.analyze(_img(tmp_path))["analysis_status"] == "FAILED"

    analyzer = ReferenceImageArchitecturalUnderstandingV1(FakeProvider("not a dict"))
    assert analyzer.analyze(_img(tmp_path))["analysis_status"] == "FAILED"


# ==========================================================
# L / M — cache determinism
# ==========================================================

def test_L_same_hash_cached(tmp_path):
    provider = FakeProvider({"facade_style": "modern"})
    analyzer = ReferenceImageArchitecturalUnderstandingV1(provider)
    p = _img(tmp_path)
    a = analyzer.analyze(p)
    b = analyzer.analyze(p)
    assert provider.calls == 1
    assert a["analysis_hash"] == b["analysis_hash"]


def test_M_different_hash_separate_record(tmp_path):
    provider = FakeProvider({"facade_style": "modern"})
    analyzer = ReferenceImageArchitecturalUnderstandingV1(provider)
    p1 = _img(tmp_path, "a.bin", b"IMG-AAA")
    p2 = _img(tmp_path, "b.bin", b"IMG-BBB")
    a = analyzer.analyze(p1)
    b = analyzer.analyze(p2)
    assert provider.calls == 2
    assert a["source_hash"] != b["source_hash"]


# ==========================================================
# N — contract / serialization / determinism
# ==========================================================

def test_N_contract_and_round_trip(tmp_path):
    raw = {"facade_style": "modern", "materials": [{"type": "stone"}]}
    analyzer = ReferenceImageArchitecturalUnderstandingV1(FakeProvider(raw))
    r = analyzer.analyze(_img(tmp_path))
    assert isinstance(r, ReferenceArchitecturalAnalysisV1)
    assert r["contract"] == CONTRACT
    assert r["version"] == VERSION
    for key in (
        "contract", "version", "image_id", "source_type", "source_hash",
        "analysis_status", "facade_style", "style_candidates", "materials",
        "color_palette", "arches", "windows", "balconies", "entrance",
        "facade_rhythm", "ornament_level", "symmetry",
        "occlusions", "perspective_limitations", "uncertainties",
        "unsupported_inferences", "evidence", "provider", "model",
        "provenance", "analysis_hash",
    ):
        assert key in r, key
    assert json.loads(json.dumps(r, ensure_ascii=False)) == r
    assert len(r["analysis_hash"]) == 64


def test_determinism_same_input_same_hash(tmp_path):
    raw = {"facade_style": "modern", "materials": [{"type": "brick"}]}
    a = ReferenceImageArchitecturalUnderstandingV1(FakeProvider(raw)).analyze(_img(tmp_path))
    b = ReferenceImageArchitecturalUnderstandingV1(FakeProvider(raw)).analyze(_img(tmp_path))
    assert a["analysis_hash"] == b["analysis_hash"]


def test_register_provider(tmp_path):
    analyzer = ReferenceImageArchitecturalUnderstandingV1()
    assert analyzer.analyze(_img(tmp_path))["analysis_status"] == "PROVIDER_UNAVAILABLE"
    analyzer.register_provider(FakeProvider({"facade_style": "modern"}))
    assert analyzer.analyze(_img(tmp_path, "c.bin", b"IMG-CCC"))["facade_style"] == "modern"


# ==========================================================
# O / P — isolation
# ==========================================================

def test_O_no_render_or_generation_side_effect():
    source = inspect.getsource(
        inspect.getmodule(ReferenceImageArchitecturalUnderstandingV1)
    ).lower()
    for forbidden in (
        "import requests",
        "from core.render",
        "import comfy",
        "from comfy",
        "comfyui_bridge",
        "workflow_executor",
        "render_runtime(",
        "text2img(",
        "img2img(",
    ):
        assert forbidden not in source, forbidden


def test_P_no_structure_bim_ifc_dependency():
    source = inspect.getsource(
        inspect.getmodule(ReferenceImageArchitecturalUnderstandingV1)
    ).lower()
    for forbidden in ("core.structure", "core.bim", "core.ifc", "ifc_standard"):
        assert forbidden not in source, forbidden


def test_no_face_or_person_identification():
    source = inspect.getsource(
        inspect.getmodule(ReferenceImageArchitecturalUnderstandingV1)
    ).lower()
    for forbidden in ("face_recognition", "identify_person", "person_id", "gender", "ethnicity"):
        assert forbidden not in source, forbidden
