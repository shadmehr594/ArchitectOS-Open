# ==========================================================
# PHASE 2D-3 — ARCHITECTURAL PROMPT COMPILER / ENGLISH PROJECTION
# Deterministic English compilation of canonical architectural semantics.
#
# No translation. No LLM. No render execution. No image understanding.
# ==========================================================

import json
import re

from core.prompt_intelligence.persian_architectural_understanding import (
    understand,
)
from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
    CONTRACT,
    VERSION,
    ArchitecturalCompiledPromptV1,
    ArchitecturalPromptCompiler,
    architectural_prompt_compiler,
    compile_prompt,
)

_PERSIAN_RE = re.compile(r"[\u0600-\u06FF]")


def _compile(text, mode=None, context=None):
    return compile_prompt(understand(text), mode=mode, context=context)


# ==========================================================
# REQUIRED CASES A–P
# ==========================================================

def test_A_low_modern_increase():
    r = _compile("یه کم مدرن‌ترش کن")
    assert r["status"] == "COMPILED"
    assert "slightly more contemporary" in r["positive_prompt"]


def test_B_preserve_windows():
    r = _compile("پنجره‌ها همون بمونه")
    assert "Preserve the current window locations" in r["positive_prompt"]
    assert r["preservation_instructions"]


def test_C_facade_only_with_massing_preserved():
    r = _compile("خود ساختمون تغییر نکنه فقط نما رو عوض کن")
    assert r["mode"] == "FACADE_REFINEMENT"
    assert r["scope"] == "facade"
    assert "Preserve the existing building massing." in r["positive_prompt"]
    assert "Preserve the existing building geometry." in r["positive_prompt"]


def test_D_entrance_emphasis():
    r = _compile("ورودیش قوی‌تر شه")
    assert "Increase the architectural emphasis of the main entrance." in r["positive_prompt"]


def test_E_negative_ornament():
    r = _compile("خیلی شلوغ نشه")
    assert "Avoid heavy ornamentation." in r["negative_prompt"]
    assert "restrained" in r["positive_prompt"]


def test_F_lighter_stone():
    r = _compile("سنگش روشن‌تر شه")
    assert "lighter natural stone tone" in r["positive_prompt"]


def test_G_reduce_arches():
    r = _compile("قوس‌ها کمتر شه")
    assert "Reduce the use and visual dominance of arches." in r["positive_prompt"]


def test_H_reference_inspiration_no_geometry_copy():
    r = _compile("مثل این عکس ولی ساده‌تر")
    assert "reference image" in r["positive_prompt"]
    assert "Do not copy the reference image geometry." in r["positive_prompt"]
    assert "Reduce overall visual complexity" in r["positive_prompt"]


def test_I_reference_material_only():
    r = _compile("از این عکس فقط متریالش رو بگیر")
    assert "material/finish reference" in r["positive_prompt"]


def test_J_preserve_massing_and_windows_facade_modern():
    r = _compile("همین حجم و پنجره‌ها بمونه فقط نما مدرن‌تر شه")
    assert "Preserve the existing building massing." in r["positive_prompt"]
    assert "Preserve the current window locations" in r["positive_prompt"]
    assert "more contemporary" in r["positive_prompt"]
    assert r["mode"] == "FACADE_REFINEMENT"


def test_K_light_stone_negative_roman():
    r = _compile("یه نمای سنگ روشن میخوام ولی خیلی رومی نشه")
    assert "light natural stone" in r["positive_prompt"]
    assert "Avoid excessive Roman/classical styling." in r["negative_prompt"]


def test_L_ambiguous_needs_clarification():
    r = _compile("بهترش کن")
    assert r["status"] == "NEEDS_CLARIFICATION"
    assert r["positive_prompt"] == ""
    assert r["negative_prompt"] == ""
    assert r["unresolved_items"]


def test_M_mixed_modern_light_stone():
    r = _compile("facade رو modern تر کن با light stone")
    assert "contemporary" in r["positive_prompt"]
    assert "light natural stone" in r["positive_prompt"]
    assert r["mode"] == "FACADE_REFINEMENT"


def test_N_conflict_preservation_wins():
    u = understand("پنجره‌ها همون بمونه")
    # inject a contradictory change targeting a hard-preserved element
    u["change_operations"].append({"operation": "replace", "target": "windows"})
    r = compile_prompt(u)
    assert r["status"] == "COMPILED_WITH_CONFLICTS"
    assert r["conflicts"], "conflict must be structured"
    assert r["conflicts"][0]["resolution"] == "preservation_authoritative"
    # no silent contradiction: the conflicting change is not compiled
    assert "Replace the windows" not in r["positive_prompt"]


def test_O_image_edit_strong_preservation():
    r = _compile("خود ساختمون تغییر نکنه فقط نما رو عوض کن", mode="IMAGE_EDIT")
    assert r["mode"] == "IMAGE_EDIT"
    assert "authoritative geometry reference" in r["positive_prompt"]
    assert "Do not redesign the plan." in r["positive_prompt"]
    assert "Do not add or remove floors." in r["positive_prompt"]


def test_P_text_to_image_no_false_preservation():
    r = _compile("یه نمای سنگ روشن میخوام", mode="TEXT_TO_IMAGE")
    assert r["mode"] == "TEXT_TO_IMAGE"
    assert "preserve" not in r["positive_prompt"].lower()
    assert "existing building" not in r["positive_prompt"].lower()


# ==========================================================
# CONTRACT / DETERMINISM / SERIALIZATION
# ==========================================================

def test_contract_identity_and_fields():
    r = _compile("ورودیش قوی‌تر شه")
    assert isinstance(r, ArchitecturalCompiledPromptV1)
    assert r["contract"] == CONTRACT
    assert r["version"] == VERSION
    for key in (
        "contract", "version", "compiler_version",
        "source_semantic_contract", "source_semantic_version",
        "raw_text", "normalized_text", "mode", "scope", "status",
        "positive_prompt", "negative_prompt",
        "preservation_instructions", "change_instructions",
        "material_instructions", "style_instructions",
        "composition_instructions", "reference_instructions",
        "hard_constraints", "soft_preferences",
        "required_context", "unresolved_items", "warnings", "conflicts",
        "prompt_sections", "provenance", "deterministic_hash",
    ):
        assert key in r, key


def test_json_round_trip():
    r = _compile("همین حجم و پنجره‌ها بمونه فقط نما مدرن‌تر شه")
    restored = json.loads(json.dumps(r, ensure_ascii=False))
    assert restored == r


def test_determinism_and_hash():
    text = "یه نمای سنگ روشن میخوام ولی خیلی رومی نشه"
    a = _compile(text)
    b = _compile(text)
    assert a == b
    assert a["deterministic_hash"] == b["deterministic_hash"]
    assert len(a["deterministic_hash"]) == 64


def test_different_input_different_hash():
    a = _compile("ورودیش قوی‌تر شه")
    b = _compile("قوس‌ها کمتر شه")
    assert a["deterministic_hash"] != b["deterministic_hash"]


def test_no_persian_leaks_into_prompts():
    for text in (
        "یه نمای سنگ روشن میخوام ولی خیلی رومی نشه",
        "خود ساختمون تغییر نکنه فقط نما رو عوض کن",
        "ورودیش قوی‌تر شه",
    ):
        r = _compile(text)
        assert not _PERSIAN_RE.search(r["positive_prompt"])
        assert not _PERSIAN_RE.search(r["negative_prompt"])
        # raw Persian retained for audit only
        assert r["raw_text"] == text


def test_positive_and_negative_are_separated():
    r = _compile("یه نمای سنگ روشن میخوام ولی خیلی رومی نشه")
    assert "Avoid excessive Roman/classical styling." in r["negative_prompt"]
    assert "Avoid excessive Roman/classical styling." not in r["positive_prompt"]


def test_no_overprompting_for_simple_request():
    r = _compile("سنگش روشن‌تر شه")
    assert len(r["positive_prompt"].split()) < 40


def test_provenance_mode_policy_tagging():
    r = _compile("خود ساختمون تغییر نکنه فقط نما رو عوض کن", mode="IMAGE_EDIT")
    assert "preservation" in r["provenance"]["mode_policy_sections"]
    assert r["provenance"]["mode"] == "IMAGE_EDIT"


def test_mode_inference_facade_scope():
    r = _compile("فقط نما رو مدرن‌تر کن")
    assert r["mode"] == "FACADE_REFINEMENT"


def test_engine_is_constructible_and_stable():
    a = ArchitecturalPromptCompiler()
    b = ArchitecturalPromptCompiler()
    u = understand("قوس‌ها کمتر شه")
    assert a.compile(u) == b.compile(u)


def test_no_signal_returns_no_intent():
    # a plain conversational line has no architectural semantics
    r = compile_prompt({})
    assert r["status"] == "NO_ARCHITECTURAL_INTENT"
    assert r["positive_prompt"] == ""
