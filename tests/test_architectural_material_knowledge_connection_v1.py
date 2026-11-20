# -*- coding: utf-8 -*-
"""CPU-only material-replacement knowledge connection regressions.

The authentic vision fixture is the accepted facade observation already used by
``test_vision_architectural_knowledge_handoff_v1``. Synthetic data is labelled
explicitly and is used only to test the beige descriptor boundary.

No model, renderer, ComfyUI, network, BIM, CAD, mask, or segmentation path is
reachable from this test.
"""

from __future__ import annotations

import copy
import json
import os

from core.vision.architectural_material_knowledge_connection_v1 import (
    build_architectural_material_knowledge_connection,
)
from core.vision.architectural_vision_interpreter_v1 import (
    interpret_architectural_vision,
)
from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT
from core.vision.image_understanding_v1 import build_understanding


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEMANTICS = os.path.join(
    ROOT, "runs", "vision_facade_evidence_semantics_v1", "live_semantics_v1.json"
)
COMPOUND = os.path.join(
    ROOT, "runs", "vision_facade_compound_v1", "live_compound_v1.json"
)

REQUEST = (
    "Replace beige brick on exposed architectural wall surfaces with natural "
    "cream travertine. Preserve windows, doors, railings, balconies, roof and "
    "other non-target components."
)


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _understanding():
    semantics = _load(SEMANTICS)
    compound = _load(COMPOUND)
    structured = copy.deepcopy(semantics["normalization"]["structured"])
    return build_understanding(
        {
            "contract": BRIDGE_CONTRACT,
            "raw_observer": compound["raw_observer"],
            "normalization": {"status": "NORMALIZED", "structured": structured},
        },
        provider="ollama",
        model="qwen3.8:27b",
        image_id="V3",
        source_type="other",
    )


def _connection():
    return interpret_architectural_vision(
        _understanding(), user_text=REQUEST
    )["architectural_material_knowledge_connection"]


def test_real_observation_and_user_instruction_are_connected_without_merging():
    baseline = interpret_architectural_vision(_understanding())
    connected = interpret_architectural_vision(_understanding(), user_text=REQUEST)

    assert connected["architectural_observation"] == baseline["architectural_observation"]
    assert connected["architectural_knowledge"] == baseline["architectural_knowledge"]

    connection = connected["architectural_material_knowledge_connection"]
    assert connection["contract"] == "ArchitecturalMaterialKnowledgeConnectionV1"
    assert connection["status"] == "CONNECTED"
    assert connection["observed_facts"]["source"] == "VISION_OBSERVATION"
    assert connection["user_instruction"]["source"] == "USER_INSTRUCTION"


def test_brick_and_travertine_remain_distinct_material_identities():
    connection = _connection()
    existing = connection["observed_facts"]["existing_materials"]
    requested = connection["architectural_interpretation"]["requested_material"]

    assert any(item["ontology_id"] == "brick" for item in existing)
    assert requested["ontology_id"] == "travertine"
    assert requested["ontology_id"] not in {
        item["ontology_id"] for item in existing
    }
    assert requested["ontology_normalized"] == "travertine stone facade"


def test_material_replacement_is_not_recoloring_and_scope_is_explicit():
    interpretation = _connection()["architectural_interpretation"]

    assert interpretation["operation"] == "MATERIAL_REPLACEMENT"
    assert interpretation["recoloring_only"] is False
    assert interpretation["target_surfaces"] == [
        "exposed architectural wall surfaces"
    ]
    assert interpretation["protected_elements"] == [
        "windows",
        "doors",
        "railings",
        "balconies",
        "roof",
        "other non-target components",
    ]


def test_user_material_wording_is_preserved_as_instruction_provenance():
    instruction = _connection()["user_instruction"]

    assert instruction["verbatim"] == REQUEST
    assert "natural cream travertine" in instruction["verbatim"].lower()
    assert instruction["preservation_clauses"] == [
        "Preserve windows, doors, railings, balconies, roof and other non-target components"
    ]


def test_spatial_coordinates_and_execution_capability_are_honestly_unknown():
    connection = _connection()
    spatial = connection["architectural_interpretation"]["spatial_grounding"]
    execution = connection["execution_capability"]

    assert spatial == {
        "status": "UNKNOWN",
        "coordinates": None,
        "mask": None,
        "grounded": False,
    }
    assert execution["status"] == "NOT_YET_AVAILABLE"
    assert execution["precise_facade_material_transfer"] is False
    assert execution["authorized"] is False


def test_supported_beige_brick_descriptor_survives_without_subtype_invention():
    synthetic_observation = {
        "contract": "ArchitecturalObservationV1",
        "material_observations": [
            {
                "descriptor": "beige brick on exposed facade wall surfaces",
                "materials": ["brick"],
                "evidence_phrase": "beige brick on exposed facade wall surfaces",
                "confidence": "MEDIUM",
            }
        ],
        "provenance": {
            "provider": "SYNTHETIC_TEST_FIXTURE",
            "image_id": "SYNTHETIC-BEIGE-BRICK",
        },
    }

    connection = build_architectural_material_knowledge_connection(
        synthetic_observation, REQUEST
    )
    existing = connection["observed_facts"]["existing_materials"]

    assert existing[0]["ontology_id"] == "brick"
    assert existing[0]["descriptor"] == "beige brick on exposed facade wall surfaces"
    assert existing[0]["source_quote"] == "beige brick on exposed facade wall surfaces"
    assert existing[0]["verification"] == "UNVERIFIED"
    assert existing[0]["ontology_id"] not in ("brick_red", "fire_brick")


def test_non_replacement_instruction_does_not_manufacture_a_change():
    observation = interpret_architectural_vision(_understanding())["architectural_observation"]
    connection = build_architectural_material_knowledge_connection(
        observation, "What material is visible?"
    )

    assert connection["status"] == "NO_MATERIAL_REPLACEMENT"
    assert connection["architectural_interpretation"] is None
    assert connection["execution_capability"]["authorized"] is False
