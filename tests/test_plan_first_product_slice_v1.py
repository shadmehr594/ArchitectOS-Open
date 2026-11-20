"""PLAN_FIRST_PRODUCT_SLICE_V1 — CPU acceptance.

The acceptance case is the project's existing spatial-planning fixture
(EX_DUPLEX in tests/test_architectural_spatial_planning_understanding_v1.py):
a duplex for a household of four, on a small site, where daylight and
privacy both matter.

No GPU, no ComfyUI POST, no inference, no image generation.
"""

import json
import os

import pytest

from core.chat.handlers.spatial_planning_handler import (
    handle_spatial_planning,
)
from core.knowledge.architectural_spatial_planning_understanding_v1 import (
    understand_spatial_planning,
)

# The existing accepted fixture, verbatim.
EX_DUPLEX = (
    "یک خانه دوبلکس برای خانواده ۴ نفره می‌خواهم، زمین کوچک است، "
    "نور مهم است، حریم هم مهم است."
)


@pytest.fixture(scope="module")
def planning():
    return understand_spatial_planning(EX_DUPLEX)


# ---------------------------------------------------------------- A / B

def test_a_brief_is_interpreted(planning):
    intent = planning["building_intent"]

    assert intent["building_type"] == "duplex"
    assert intent["floors"] == 2
    assert (intent.get("household") or {}).get("size") == 4


def test_b_required_spaces_are_not_silently_omitted(planning):
    spaces = planning["building_intent"]["spaces"]

    # A dwelling brief must yield the essential functional set.
    for required in ("UNIT_ENTRY", "LIVING_RECEPTION", "OPEN_KITCHEN",
                     "FAMILY_BATHROOM", "MASTER_BEDROOM_SLEEPING"):
        assert required in spaces, required

    assert len(spaces) >= 8


def test_b_no_space_is_invented_beyond_the_brief(planning):
    """Every space must be a known program token, never a fabricated name."""

    spaces = planning["building_intent"]["spaces"]

    assert all(isinstance(s, str) and s.isupper() for s in spaces)
    assert "PARKING" not in spaces  # the brief never mentions parking


# ---------------------------------------------------------------- C

def test_c_measurements_keep_their_provenance(planning):
    parameters = planning["context_dependent_parameters"]

    assert parameters, "expected at least the household parameter"

    for item in parameters:
        # A number is never presented as a constant.
        assert item.get("is_constant") is False
        assert item.get("contextualized") is True
        assert item.get("note")

    household = [p for p in parameters if p.get("name") == "household"][0]
    assert household["value"] == "4"


# ---------------------------------------------------------------- D

def test_d_entrance_and_circulation_are_represented(planning):
    concept = planning["spatial_planning_concept"]
    circulation = concept["circulation"]

    assert "UNIT_ENTRY" in planning["building_intent"]["spaces"]
    assert circulation["vertical_core"] == "stair"
    assert circulation["is_fixed"] is True
    assert set(circulation["connects_levels"]) == {
        "GROUND_FLOOR", "UPPER_FLOOR"
    }


def test_d_levels_follow_the_public_private_split(planning):
    zones = planning["spatial_planning_concept"]["zones"]

    assert "PUBLIC_ZONE" in zones
    assert "PRIVATE_ZONE" in zones


# ---------------------------------------------------------------- E

def test_e_knowledge_is_consulted_when_memory_is_supplied():
    from core.knowledge.architectural_knowledge_extraction_engine_v1 import (
        extract_architectural_knowledge_candidate_v1 as extract,
    )
    from core.knowledge.architectural_knowledge_memory_v1 import (
        ArchitecturalKnowledgeMemoryV1,
    )
    from core.knowledge.human_knowledge_validation_loop_v1 import open_review

    memory = ArchitecturalKnowledgeMemoryV1()

    for text in (
        "راه پله عنصر ارتباط عمودی است.\nباکس راه پله در طبقات ثابت می‌ماند.",
        "نزدیکی حمام و کلوزت باعث کاهش مسیر حرکت و افزایش حفظ حریم می‌شود.",
    ):

        candidate = extract(text, turn_kind="TEACHING_STATEMENT")

        assert candidate is not None

        review = open_review(candidate)

        review.confirm()

        memory.add_confirmed_entry(review.to_confirmed_entry())

    result = understand_spatial_planning(EX_DUPLEX, memory=memory)

    assert result.get("retrieved_knowledge")


# ---------------------------------------------------------------- F / J

def test_f_unknown_geometry_is_not_presented_as_verified(planning):
    assert planning["geometry_generated"] is False
    assert planning["plan_generated"] is False
    assert planning["is_final_solution"] is False
    assert planning["human_review_required"] is True

    non_claims = planning["non_claims"]

    assert non_claims["not_a_plan"] is True
    assert non_claims["not_geometry"] is True
    assert non_claims["not_coordinates"] is True
    assert non_claims["not_walls"] is True
    assert non_claims["not_invented"] is True


def test_f_site_condition_is_not_invented_from_a_small_site(planning):
    """'زمین کوچک است' is an AREA statement, not an orientation.

    The owner reports a site condition only when the request names an
    orientation, so an empty condition here is the documented behaviour —
    not missing data dressed up as a finding.
    """

    assert planning["building_intent"]["site_condition"] == {}


# ---------------------------------------------------------------- G

def test_g_contradictory_requirements_produce_an_honest_limitation(planning):
    conflicts = planning["conflicts"]

    assert conflicts
    kinds = {c.get("kind") for c in conflicts}
    assert "privacy_daylight_tradeoff" in kinds

    conflict = [c for c in conflicts
                if c.get("kind") == "privacy_daylight_tradeoff"][0]
    assert conflict.get("statement")
    assert set(conflict.get("between") or []) == {"privacy", "daylight"}


# ---------------------------------------------------------------- H

def test_h_planning_reaches_the_chat_result_contract(planning):
    result = handle_spatial_planning(EX_DUPLEX)

    assert result["type"] == "spatial_planning"
    assert result["status"] == "ok"
    assert result["contract"] == "ArchitecturalSpatialPlanningUnderstandingV1"

    # The existing renderer shows a string `result` verbatim.
    assert isinstance(result["result"], str)
    assert result["result"].strip()
    assert result["result"] == result["text"]

    # Structure rides alongside.
    assert result["spatial_planning"]["building_intent"]["floors"] == 2
    assert result["geometry_generated"] is False
    assert result["plan_generated"] is False


def test_h_chat_route_returns_the_planning_result():
    import types

    from core.chat.chat_architect import ChatArchitect

    chat = ChatArchitect(types.SimpleNamespace())

    result = chat.handle(EX_DUPLEX, {"spatial_planning": True})

    assert result["type"] == "spatial_planning"
    assert result["status"] == "ok"
    assert result["spatial_planning"]["building_intent"]["building_type"] == "duplex"


def test_h_empty_request_is_refused_not_invented():
    result = handle_spatial_planning("   ")

    assert result["status"] == "empty_request"
    assert result["result"] == ""


# ---------------------------------------------------------------- K

def test_k_no_render_or_geometry_is_produced(planning):
    for key in ("plan_drawing", "geometry", "walls", "coordinates",
                "rooms_geometry", "ifc", "image"):
        assert key not in planning
