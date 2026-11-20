"""Human interaction entry (V1) — isolated end-to-end path self-checks.

Proves the entry wiring:

    1. a human statement reaches the conversation interpretation
    2. the claim_type_hint reaches the material
    3. the gateway receives the MATERIAL and does NOT re-materialise
    4. no confidence leakage anywhere on the path
    5. no governance dependency (the entry imports none)
    6. the frozen surfaces are unchanged
    7. the token stays contained; the nonce lifecycle is unchanged
    8. the existing gateway contract is preserved (`submit(request)` alone)
    9. an unclassifiable statement yields no hint and NO default
"""

from __future__ import annotations


import ast
from pathlib import Path

import pytest

import core.runtime.human_interaction_entry_v1 as entry_module
import core.runtime.interactive_runtime_gateway_v1 as gateway_module
from core.runtime.human_interaction_entry_v1 import (
    HumanInteraction,
    HumanInteractionEntry,
    HumanInteractionError,
    REASON_MISSING_FIELD,
    REASON_NOT_AN_INTERACTION,
    human_interaction_entry,
)
from core.runtime.interactive_runtime_gateway_v1 import (
    GatewayResult,
    InteractiveRuntimeGateway,
    STAGE_G1,
    STAGE_G1M,
    STATUS_ADMITTED,
    STATUS_ERROR,
    STATUS_REFUSED,
    build_gateway_request,
)
from core.runtime.interaction_nonce_v1 import interaction_nonce_state


MODULE = Path(__file__).resolve().parents[1] / "human_interaction_entry_v1.py"

GATEWAY_MODULE = (
    Path(__file__).resolve().parents[1] / "interactive_runtime_gateway_v1.py"
)

ROOT = Path(__file__).resolve().parents[3]

SESSION = "session_alpha"

CLASSIFIED = "the bedroom is next to the living room"

UNCLASSIFIABLE = "a random sentence about nothing at all"


FROZEN_PACKAGES = ("conversation", "vision", "governance")

NEW_LAYER_TOKENS = (
    "core.interpretation",
    "conversation_claim_type_hint",
    "conversation_interaction_carrier",
    "conversation_interpretation_adapter",
    "human_interaction_entry",
)


def _interaction(entry, statement=CLASSIFIED, **overrides):

    fields = {
        "session_reference": SESSION,
        "statement": statement,
        "turn_kind": "TEACHING_STATEMENT",
        "language": "en",
        "interaction_nonce": entry.request_nonce(SESSION),
    }

    fields.update(overrides)

    return HumanInteraction(**fields)


def _imported_roots(path):

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    roots = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            roots.extend(alias.name for alias in node.names)

        elif isinstance(node, ast.ImportFrom):

            if node.module:

                roots.append(node.module)

    return roots


# ==========================================================
# 1. the human statement reaches the interpretation
# ==========================================================

def test_the_statement_reaches_the_interpretation(monkeypatch):

    captured = {}

    real = entry_module.to_interaction_carrier

    def _spy(statement, **kwargs):

        captured["statement"] = statement

        return real(statement, **kwargs)

    monkeypatch.setattr(entry_module, "to_interaction_carrier", _spy)

    entry = HumanInteractionEntry()

    entry.submit(_interaction(entry))

    assert captured["statement"] == CLASSIFIED


# ==========================================================
# 2. the claim_type_hint reaches the material
# ==========================================================

def test_the_hint_reaches_the_material(monkeypatch):

    captured = {}

    real = entry_module.to_claim_request_material

    def _spy(source):

        captured["source"] = source

        material = real(source)

        captured["material"] = material

        return material

    monkeypatch.setattr(entry_module, "to_claim_request_material", _spy)

    entry = HumanInteractionEntry()

    entry.submit(_interaction(entry))

    # the source is the clean carrier, and it carries the interpretation hint
    assert captured["source"].claim_type_hint == "spatial_relationship"

    # the material carries it
    assert captured["material"].claim_type_hint == "spatial_relationship"


# ==========================================================
# 3. the gateway receives the material and does not re-materialise
# ==========================================================

def test_the_gateway_receives_the_material(monkeypatch):

    captured = {}

    real_submit = gateway_module.InteractiveRuntimeGateway.submit

    def _spy(self, request, *, material=None):

        captured["material"] = material

        captured["request"] = request

        return real_submit(self, request, material=material)

    monkeypatch.setattr(
        gateway_module.InteractiveRuntimeGateway, "submit", _spy
    )

    entry = HumanInteractionEntry()

    result = entry.submit(_interaction(entry))

    assert result.completed is True

    assert captured["material"].claim_type_hint == "spatial_relationship"

    # the gateway received the five-field request contract unchanged
    assert captured["request"].raw_statement == CLASSIFIED


def test_the_gateway_does_not_materialise_when_a_material_is_supplied(monkeypatch):

    def _boom(source):

        raise AssertionError(
            "the gateway must not materialise when a material is supplied"
        )

    monkeypatch.setattr(gateway_module, "to_claim_request_material", _boom)

    entry = HumanInteractionEntry()

    result = entry.submit(_interaction(entry))

    # the flow completed WITHOUT the gateway ever calling the producer
    assert result.completed is True

    assert result.status == STATUS_ADMITTED


# ==========================================================
# 4. no confidence leakage
# ==========================================================

def test_no_confidence_leakage_on_the_path():

    entry = HumanInteractionEntry()

    result = entry.submit(_interaction(entry))

    payload = result.to_dict()

    for forbidden in (
        "confidence",
        "confidence_kind",
        "score",
        "truth",
        "truth_status",
        "approval",
        "is_true",
    ):

        assert forbidden not in payload

    # the gateway's own `status` is its FLOW outcome, not a claim status
    assert payload["status"] in ("admitted", "denied", "refused", "error")

    # the material itself carries no confidence
    material = entry_module.to_claim_request_material(
        entry_module.to_interaction_carrier(CLASSIFIED)
    )

    assert not hasattr(material, "confidence")

    assert "confidence" not in material.to_dict()


# ==========================================================
# 5. no governance dependency
# ==========================================================

def test_the_entry_has_no_governance_import():

    roots = _imported_roots(MODULE)

    for root in roots:

        assert not root.startswith("core.governance"), root

        for frozen in ("core.conversation", "core.vision"):

            assert not root.startswith(frozen), root


def test_the_entry_imports_only_the_expected_modules():

    core_roots = sorted(
        {root for root in _imported_roots(MODULE) if root.startswith("core.")}
    )

    assert core_roots == [
        "core.interpretation.conversation_interpretation_adapter_v1",
        "core.runtime.claim_request_material_adapter_v1",
        "core.runtime.interactive_runtime_gateway_v1",
    ]


# ==========================================================
# 6. the frozen surfaces are unchanged
# ==========================================================

def test_the_frozen_packages_do_not_reference_the_new_layer():

    for package in FROZEN_PACKAGES:

        for path in sorted((ROOT / "core" / package).rglob("*.py")):

            source = path.read_text(encoding="utf-8", errors="ignore")

            for token in NEW_LAYER_TOKENS:

                assert token not in source, (str(path), token)


def test_app_py_does_not_reference_the_new_layer():

    source = (ROOT / "app.py").read_text(encoding="utf-8", errors="ignore")

    for token in NEW_LAYER_TOKENS:

        assert token not in source, token


# ==========================================================
# 7. the token stays contained; the nonce lifecycle is unchanged
# ==========================================================

def test_the_token_is_never_exposed():

    entry = HumanInteractionEntry()

    result = entry.submit(_interaction(entry))

    blob = repr(result.to_dict()).lower()

    assert "hat_" not in blob

    assert "token_reference" not in blob


def test_a_successful_flow_consumes_the_nonce():

    entry = HumanInteractionEntry()

    interaction = _interaction(entry)

    entry.submit(interaction)

    assert interaction_nonce_state(interaction.interaction_nonce) == "consumed"


def test_a_nonce_failure_does_not_burn_the_nonce():

    entry = HumanInteractionEntry()

    interaction = _interaction(entry, turn_kind="QUESTION")

    result = entry.submit(interaction)

    assert result.status == STATUS_REFUSED

    assert interaction_nonce_state(interaction.interaction_nonce) == "issued"


# ==========================================================
# 8. the existing gateway contract is preserved
# ==========================================================

def test_submit_with_a_request_alone_still_works(monkeypatch):

    calls = []

    real = gateway_module.to_claim_request_material

    def _spy(source):

        calls.append(source)

        return real(source)

    monkeypatch.setattr(gateway_module, "to_claim_request_material", _spy)

    gateway = InteractiveRuntimeGateway()

    request = build_gateway_request(
        session_reference=SESSION,
        raw_statement=CLASSIFIED,
        turn_kind="TEACHING_STATEMENT",
        language="en",
        interaction_nonce=gateway.request_nonce(SESSION),
    )

    result = gateway.submit(request)

    # the gateway materialised from the request exactly as before
    assert len(calls) == 1

    assert isinstance(result, GatewayResult)


def test_a_bogus_material_is_refused_at_g1m():

    gateway = InteractiveRuntimeGateway()

    request = build_gateway_request(
        session_reference=SESSION,
        raw_statement=CLASSIFIED,
        turn_kind="TEACHING_STATEMENT",
        language="en",
        interaction_nonce=gateway.request_nonce(SESSION),
    )

    result = gateway.submit(request, material="not a material")

    assert result.status == STATUS_REFUSED

    assert result.stage == STAGE_G1M


def test_the_gateway_does_not_select_a_claim_type():

    source = GATEWAY_MODULE.read_text(encoding="utf-8")

    assert "INTERACTIVE_CLAIM_TYPE" not in source


# ==========================================================
# 9. an unclassifiable statement yields no hint and no default
# ==========================================================

def test_an_unclassifiable_statement_has_no_hint_and_no_default():

    entry = HumanInteractionEntry()

    interaction = _interaction(entry, statement=UNCLASSIFIABLE)

    result = entry.submit(interaction)

    # the flow reaches the executor, which denies the absent type at mint
    assert result.completed is False

    assert result.status == STATUS_ERROR

    assert "unknown claim_type" in result.reason


def test_a_classified_statement_is_admitted():

    entry = HumanInteractionEntry()

    result = entry.submit(_interaction(entry))

    assert result.completed is True

    assert result.status == STATUS_ADMITTED

    assert result.lifecycle_result.claim_reference.startswith("clm_")


# ==========================================================
# 10. the interaction value object
# ==========================================================

def test_a_malformed_interaction_is_rejected():

    entry = HumanInteractionEntry()

    for overrides in (
        {"session_reference": ""},
        {"statement": ""},
        {"statement": 42},
        {"turn_kind": ""},
        {"language": ""},
    ):

        with pytest.raises(HumanInteractionError) as error:

            _interaction(entry, **overrides)

        assert REASON_MISSING_FIELD in str(error.value)


def test_a_mapping_interaction_is_accepted():

    entry = HumanInteractionEntry()

    result = entry.submit(
        {
            "session_reference": SESSION,
            "statement": CLASSIFIED,
            "turn_kind": "TEACHING_STATEMENT",
            "language": "en",
            "interaction_nonce": entry.request_nonce(SESSION),
        }
    )

    assert result.completed is True


def test_a_non_interaction_is_refused():

    entry = HumanInteractionEntry()

    result = entry.submit("nope")

    assert result.status == STATUS_REFUSED

    assert result.stage == STAGE_G1


def test_the_singleton_works():

    result = human_interaction_entry.submit(
        _interaction(human_interaction_entry, statement="there is a bed")
    )

    assert result.completed is True
