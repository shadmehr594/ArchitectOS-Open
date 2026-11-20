"""Focused CPU checks for architectural knowledge/material fidelity review.

These checks exercise the existing delta, source-bound intent normalizer,
facade resolver and ImageEditPromptBuilder.  They do not execute a model.
"""

import re

from core.architecture.knowledge.resolved_facade_knowledge import (
    SharedFacadeKnowledgeResolverV1,
)
from core.chat.handlers.image_handler import ImageHandler
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta
from core.prompt_intelligence.image_edit_prompt_builder import ImageEditPromptBuilder


SOURCE_INTENT = {
    "building_type": "villa",
    "style": "modern",
    "materials": ["brick"],
    "windows": {"layout": "source_fixed"},
    "roof_geometry": {"type": "source_fixed"},
    "massing": {"form": "source_fixed"},
    "preserve_geometry": True,
    "preserve_constraints": [
        "building_silhouette",
        "overall_massing",
        "number_of_floors",
        "roof_shape",
        "main_window_positions",
        "main_door_positions",
        "main_balconies",
        "camera",
        "perspective",
    ],
}


def _compiled(text):
    delta = compile_edit_delta(text, image_edit=True)
    current = ArchitecturalIntent().extract({"prompt": text})
    normalized = ImageHandler.__new__(ImageHandler).normalize_edit_intent(
        current,
        previous_intent=SOURCE_INTENT,
        edit_delta=delta,
    )
    normalized["normalized_prompt"] = text
    normalized["preserve_geometry"] = True
    normalized["preserve_constraints"] = list(
        SOURCE_INTENT["preserve_constraints"]
    )
    normalized["edit_delta"] = delta
    normalized["resolved_facade_knowledge"] = (
        SharedFacadeKnowledgeResolverV1().resolve(normalized)
    )
    prompt = ImageEditPromptBuilder().build(normalized)
    return delta, normalized, prompt.lower()


def _word(text, value):
    return re.search(r"(?<![a-z])" + re.escape(value) + r"(?![a-z])", text)


def test_generic_stone_remains_unspecified_and_does_not_expand_scope():
    delta, _, prompt = _compiled("Replace the brick facade with stone")

    assert delta["material"] == "stone"
    assert "stone species" in delta["delta_prompt"].lower()
    assert "unspecified" in delta["delta_prompt"].lower()
    assert not any(x in delta["delta_prompt"].lower() for x in (
        "travertine", "marble", "limestone", "warm light-coloured",
        "stone base", "feature wall", "window surrounds",
    ))
    assert "only to the facade surfaces whose finish is being replaced" in (
        delta["delta_prompt"].lower()
    )
    assert "travertine" not in prompt


def test_explicit_travertine_retains_specificity_but_not_unrelated_surfaces():
    delta, _, prompt = _compiled(
        "Replace the brick facade with light travertine stone"
    )

    assert delta["material"] == "travertine"
    assert delta["material_tone"] == "light"
    assert "light natural travertine" in delta["delta_prompt"].lower()
    assert "window surrounds" not in delta["delta_prompt"].lower()
    assert "stone base" not in delta["delta_prompt"].lower()
    assert "only to the facade surfaces whose finish is being replaced" in (
        delta["delta_prompt"].lower()
    )
    assert "travertine" in prompt


def test_neoclassical_style_projects_safe_surface_knowledge_not_only_label():
    delta, normalized, prompt = _compiled(
        "Convert this facade to neoclassical style and keep the roof, geometry and windows"
    )

    assert delta["style"] == "neoclassical"
    assert normalized["materials"] == ["brick"]
    assert "refined details" in prompt
    assert not any(_word(prompt, term) for term in (
        "columns", "pilasters", "cornices", "pediment", "dormer",
        "classical windows", "stone frames", "travertine", "marble",
    ))


def test_roman_style_keeps_material_and_uses_only_surface_expression():
    _, normalized, prompt = _compiled(
        "Convert this facade to Roman classic style, preserve the existing materials, geometry and windows"
    )

    # The source-bound intent carries the known original brick material rather
    # than replacing it with a generic preservation sentinel.
    assert normalized["materials"] == ["brick"]
    assert "roman classic" in prompt
    assert "luxury appearance" in prompt
    assert "monumental expression" not in prompt
    assert not any(_word(prompt, term) for term in (
        "columns", "arches", "balustrades", "cornice", "stone base",
        "window frames", "travertine", "marble",
    ))


def test_iranian_traditional_preserves_brick_and_windows_with_surface_cues():
    delta, normalized, prompt = _compiled(
        "این نما را به سبک سنتی ایرانی بازسازی کن ولی مصالح آجر موجود و پنجره‌ها را حفظ کن"
    )

    assert delta["material"] is None
    assert normalized["windows"] == {"layout": "source_fixed"}
    assert "local identity" in prompt
    assert "ornamental patterns" in prompt
    assert not any(term in prompt for term in (
        "central courtyard", "introverted layout", "orsi window",
        "tile work", "kahgel", "natural stone base",
    ))


def test_islamic_fixed_geometry_uses_surface_ornament_not_new_structure():
    _, _, prompt = _compiled(
        "این نما را به معماری اسلامی بازسازی کن، حجم و بازشوها ثابت بماند"
    )

    assert "islamic architecture" in prompt
    assert "ornament" in prompt
    assert "calligraphy" in prompt
    assert "geometric patterns" in prompt
    assert not any(_word(prompt, term) for term in (
        "arches", "dome", "vault", "courtyard", "columns",
    ))


def test_combined_style_material_keeps_both_and_only_safe_surface_knowledge():
    delta, _, prompt = _compiled(
        "Convert this facade to neoclassical style and use light travertine"
    )

    assert delta["style"] == "neoclassical"
    assert delta["material"] == "travertine"
    assert "neoclassical" in prompt
    assert "travertine" in prompt
    assert "refined details" in prompt
    assert "modern luxury" not in prompt
    assert not any(_word(prompt, term) for term in (
        "marble", "columns", "pilasters", "cornices", "stone frames",
    ))


def test_material_only_has_no_style_family_or_internal_metadata():
    _, _, prompt = _compiled("Replace the brick facade with natural stone")

    assert "natural stone" in prompt
    assert not any(_word(prompt, term) for term in (
        "neoclassical", "classic", "modern", "roman", "islamic",
    ))
    assert not any(term in prompt for term in (
        "selection_specificity", "family_or_unknown", "provenance",
        "architectural knowledge", "unknown", "compatible_options",
    ))


def test_style_delta_retains_source_bound_protected_facts():
    _, normalized, _ = _compiled(
        "Convert this facade to neoclassical style and keep the windows and geometry"
    )

    assert normalized["style"] == "neoclassical"
    assert normalized["materials"] == ["brick"]
    assert normalized["windows"] == SOURCE_INTENT["windows"]
    assert normalized["roof_geometry"] == SOURCE_INTENT["roof_geometry"]
    assert normalized["massing"] == SOURCE_INTENT["massing"]
