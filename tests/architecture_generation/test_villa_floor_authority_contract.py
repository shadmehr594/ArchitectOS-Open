import pytest

from core.architecture.brain.architectural_brain import ArchitecturalBrain
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent


def _design(brief):
    intent = ArchitecturalIntent().extract({"prompt": brief})
    model = ArchitecturalBrain().design(intent)
    return intent, model, model.architectural_geometry


def test_explicit_one_storey_villa_does_not_receive_typology_upper_floor():
    intent, model, geometry = _design("یک ویلای مسکونی یک طبقه طراحی کن.")
    assert intent["levels"] == {
        "basement": 0, "ground": 1, "above_ground": 1,
        "mezzanine": 0, "total": 1,
    }
    generated = model.knowledge_spaces["generated_spaces"]
    assert {space.get("floor") for space in generated} == {"ground_floor"}
    assert not any(space.get("name") == "stairs" for space in generated)
    assert [level["name"] for level in model.vertical_section["levels"]] == ["F1"]
    assert [floor["floor"] for floor in geometry["floor_geometry"]] == ["F1"]
    assert [slab["floor"] for slab in geometry["slabs"]] == ["F1"]
    assert geometry["vertical_geometry"] == []


def test_two_storey_villa_preserves_ground_and_upper_floor():
    intent, model, geometry = _design("یک ویلای دو طبقه طراحی کن.")
    assert intent["levels"]["above_ground"] == 2
    assert {space.get("floor") for space in model.knowledge_spaces["generated_spaces"]} == {
        "ground_floor", "upper_floor",
    }
    assert [level["name"] for level in model.vertical_section["levels"]] == ["F1", "F2"]
    assert [floor["floor"] for floor in geometry["floor_geometry"]] == ["F1", "F2"]


def test_one_storey_with_basement_has_no_fake_upper_residential_floor():
    _, model, geometry = _design("یک ویلای یک طبقه با زیرزمین طراحی کن.")
    floors = {space.get("floor") for space in model.knowledge_spaces["generated_spaces"]}
    assert floors == {"basement", "ground_floor"}
    levels = model.vertical_section["levels"]
    assert [level["name"] for level in levels] == ["basement", "F1"]
    assert levels[0]["type"] == "basement"
    assert levels[0]["top"] == pytest.approx(0.0)
    assert not any(level["name"] == "F2" for level in levels)
    assert {floor["floor"] for floor in geometry["floor_geometry"]} == {"basement", "F1"}


def test_one_storey_with_mezzanine_preserves_distinct_mezzanine_contract():
    intent, model, geometry = _design("یک ویلای یک طبقه با نیم طبقه طراحی کن.")
    assert intent["levels"]["above_ground"] == 1
    assert intent["levels"]["mezzanine"] == 1
    floors = {space.get("floor") for space in model.knowledge_spaces["generated_spaces"]}
    assert floors == {"ground_floor", "mezzanine"}
    levels = model.vertical_section["levels"]
    assert [level["name"] for level in levels] == ["F1", "mezzanine"]
    assert levels[1]["type"] == "mezzanine"
    assert levels[1]["is_mezzanine"] is True
    assert not any(level["name"] == "F2" for level in levels)
    assert {floor["floor"] for floor in geometry["floor_geometry"]} == {"F1", "mezzanine"}
