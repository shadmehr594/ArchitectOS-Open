"""Focused acceptance tests for Architectural Vision Interpreter V1."""

from core.chat.response_adapter import ResponseAdapter
from core.vision.architectural_vision_interpreter_v1 import (
    CONTRACT,
    interpret_architectural_vision,
)


def test_bedroom_description_is_architectural_and_uncertain():
    result = interpret_architectural_vision(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["bed visible", "window visible", "seating element visible"],
            "inferred": [],
            "unresolved": ["private bathroom not visible"],
            "confidence": "MEDIUM",
            "architectural_elements": ["window", "room"],
        },
        user_text="این تصویر را فقط تحلیل کن",
    )

    assert result["contract"] == CONTRACT
    assert result["space_type"] == "bedroom"
    assert result["observed_elements"]
    assert result["unknowns"]
    assert result["geometry_authoritative"] is False
    assert not any("design" in value.lower() or "suggest" in value.lower() for value in result["architectural_interpretation"])


def test_facade_keeps_openings_balcony_entrance_without_inventing_floors():
    result = interpret_architectural_vision(
        {
            "image_type": "facade_or_elevation",
            "observed": ["facade visible", "openings visible", "balcony visible", "entrance visible"],
            "inferred": ["two floors"],
            "unresolved": [],
            "confidence": "HIGH",
            "architectural_elements": ["facade", "window", "balcony", "entrance"],
        }
    )

    assert result["space_type"] == "facade"
    joined = " ".join(result["observed_elements"])
    assert "opening" in joined
    assert "platform" in joined
    assert "entrance" in joined
    assert any("floor count" in value for value in result["unknowns"])
    assert not any("two floor" in value.lower() or "floor 2" in value.lower() for value in result["architectural_interpretation"])
    assert not any("two floor" in value.lower() or "floor 2" in value.lower() for value in result["possible_function"])


def test_user_question_does_not_override_unknown_image_evidence():
    result = interpret_architectural_vision(
        {
            "image_type": "unknown",
            "observed": [],
            "inferred": [],
            "unresolved": [],
            "confidence": "LOW",
            "architectural_elements": [],
        },
        user_text="این تصویر یک master bedroom است؟",
    )

    assert result["space_type"] == "unknown"
    assert result["possible_function"] == []


def test_unknown_image_does_not_hallucinate():
    result = interpret_architectural_vision(
        {
            "image_type": "unknown",
            "observed": [],
            "inferred": [],
            "unresolved": ["image content unclear"],
            "confidence": "LOW",
            "architectural_elements": [],
        }
    )

    assert result["space_type"] == "unknown"
    assert result["unknowns"]
    assert result["observed_elements"] == []
    assert result["architectural_interpretation"] == []
    assert result["possible_function"] == []


def test_master_bedroom_is_possible_function_without_unseen_private_spaces():
    result = interpret_architectural_vision(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["master bedroom", "large bed visible", "larger glazing visible"],
            "inferred": [],
            "unresolved": [],
            "confidence": "MEDIUM",
            "architectural_elements": ["bed", "window"],
        },
        user_text="این تصویر یک master bedroom را نشان می‌دهد",
    )

    assert result["space_type"] == "master bedroom"
    assert "possible private couple bedroom" in result["possible_function"]
    assert any("private bathroom" in value for value in result["unknowns"])
    assert any("closet" in value.lower() or "dressing" in value.lower() for value in result["unknowns"])
    assert not any("bathroom connection" in value and "visible" not in value for value in result["architectural_interpretation"])


def test_response_adapter_uses_four_section_architectural_message():
    interpretation = interpret_architectural_vision(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["bed visible"],
            "inferred": [],
            "unresolved": [],
            "confidence": "MEDIUM",
            "architectural_elements": ["bed"],
        }
    )
    response = ResponseAdapter().adapt(
        {
            "type": "image_analysis",
            "status": "success",
            "result": interpretation,
            "architectural_interpretation": interpretation,
        }
    )

    assert response["architectural_interpretation"] == interpretation
    assert response["result"] == response["message"]
    assert response["message"].startswith("1. Possible architectural space:")
    assert "2. Visible elements:" in response["message"]
    assert "3. Possible spatial relations:" in response["message"]
    assert "4. Uncertain or undetermined:" in response["message"]


def test_denied_sleeping_evidence_does_not_classify_bedroom():
    for phrase in (
        "بدون تخت",
        "تخت دیده نمی‌شود",
        "bedroom is not visible",
        "no bedroom",
        "not a bedroom",
    ):
        result = interpret_architectural_vision({"observed": [phrase]})
        assert result["space_type"] == "unknown"


def test_bare_persian_master_token_uses_lexical_boundary():
    assert interpret_architectural_vision({"observed": ["مسترپیس"]})["space_type"] == "unknown"
    assert interpret_architectural_vision({"observed": ["مسترکلاس"]})["space_type"] == "unknown"
    assert interpret_architectural_vision({"observed": ["مستر"]})["space_type"] == "master bedroom"


def test_large_bed_and_glazing_basis_is_truthful():
    result = interpret_architectural_vision(
        {"observed": ["large bed", "larger glazing"]}, ground=False
    )

    assert result["space_type"] == "master bedroom"
    assert "large bed + larger glazing/sitting-area inference" in result["classification_basis"][0]
    assert "explicit master-bedroom label" not in result["classification_basis"]


def test_architectural_element_master_label_identifies_its_source():
    result = interpret_architectural_vision(
        {"architectural_elements": ["master bedroom"]}, ground=False
    )

    assert result["space_type"] == "master bedroom"
    assert "architectural_elements" in result["classification_basis"][0]
    assert "text_labels_if_visible" not in result["classification_basis"][0]
