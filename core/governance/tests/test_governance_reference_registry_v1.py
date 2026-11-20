"""Reference Registry Boundary V1 — isolated self-checks.

Proves the registry contract:
    1. append and lookup work; an empty registry is empty
    2. append-only: no delete / no update API; duplicates are idempotent
    3. a conflicting entry is returned explicitly and never overwrites
    4. client-generated ids, unknown shapes and injected objects are rejected
    5. truth / confidence / approval fields are rejected
    6. a snapshot is immutable and unaffected by later appends
    7. known_claim_references / known_licence_references return only stored
       governance references
    8. no identity is minted: no uuid4 / mint_id / factory calls
    9. AST: no client imports, no reverse imports
"""

from __future__ import annotations


import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.governance import FORBIDDEN_IMPORT_ROOTS
from core.governance.registry import (
    STATUS_APPENDED,
    STATUS_CONFLICT,
    STATUS_DUPLICATE,
    STATUS_FORBIDDEN_FIELD,
    STATUS_INVALID,
    ReferenceRegistry,
    ReferenceRegistryEntry,
    ReferenceRegistryError,
)


GOVERNANCE_DIR = Path(__file__).resolve().parents[1]

REGISTRY_DIR = GOVERNANCE_DIR / "registry"

REGISTRY_MODULE = REGISTRY_DIR / "reference_registry_v1.py"


def _entry(**overrides):

    fields = dict(claim_reference="clm_a")

    fields.update(overrides)

    return ReferenceRegistryEntry(**fields)


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


def _called_names(path):

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    names = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Call):

            func = node.func

            if isinstance(func, ast.Name):

                names.append(func.id)

            elif isinstance(func, ast.Attribute):

                names.append(func.attr)

    return names


# ----------------------------------------------------------
# 1. append and lookup
# ----------------------------------------------------------

def test_empty_registry_is_empty():

    registry = ReferenceRegistry()

    assert registry.count() == 0

    assert registry.known_claim_references() == ()

    assert registry.known_licence_references() == ()

    assert registry.snapshot() == ()


def test_append_and_lookup():

    registry = ReferenceRegistry()

    entry = _entry(
        licence_reference="lic_b",
        derivation_event_reference="dev_c",
        scope="single_case",
    )

    result = registry.append(entry)

    assert result.appended is True

    assert result.status == STATUS_APPENDED

    assert registry.lookup_by_claim("clm_a") == entry

    assert registry.lookup_by_claim("clm_missing") is None


def test_append_accepts_a_mapping():

    registry = ReferenceRegistry()

    result = registry.append(
        {
            "claim_reference": "clm_a",
            "proposal_reference": "prp_x",
            "knowledge_candidate_reference": "kcd_y",
        }
    )

    assert result.status == STATUS_APPENDED

    entry = registry.lookup_by_claim("clm_a")

    assert entry.proposal_reference == "prp_x"

    assert entry.knowledge_candidate_reference == "kcd_y"


def test_a_mapping_is_copied_so_later_mutation_is_immune():

    registry = ReferenceRegistry()

    source = {"claim_reference": "clm_a", "licence_reference": "lic_original"}

    registry.append(source)

    source["licence_reference"] = "lic_mutated"

    assert registry.lookup_by_claim("clm_a").licence_reference == "lic_original"


# ----------------------------------------------------------
# 2. append-only behaviour
# ----------------------------------------------------------

def test_registry_exposes_no_delete_or_update():

    registry = ReferenceRegistry()

    for name in ("delete", "remove", "update", "clear", "pop", "set"):

        assert not hasattr(registry, name)


def test_duplicate_identical_entry_is_deterministic():

    registry = ReferenceRegistry()

    entry = _entry(licence_reference="lic_b")

    assert registry.append(entry).status == STATUS_APPENDED

    second = registry.append(entry)

    assert second.appended is False

    assert second.status == STATUS_DUPLICATE

    assert registry.count() == 1


def test_a_different_entry_for_the_same_claim_is_a_conflict():

    registry = ReferenceRegistry()

    first = _entry(licence_reference="lic_b")

    second = _entry(licence_reference="lic_c")

    assert registry.append(first).status == STATUS_APPENDED

    result = registry.append(second)

    assert result.appended is False

    assert result.status == STATUS_CONFLICT

    # the stored entry is untouched
    assert registry.lookup_by_claim("clm_a").licence_reference == "lic_b"

    assert registry.count() == 1


def test_append_result_is_immutable():

    result = ReferenceRegistry().append(_entry())

    with pytest.raises(FrozenInstanceError):

        result.appended = False


# ----------------------------------------------------------
# 3. input ownership
# ----------------------------------------------------------

def test_client_generated_claim_id_is_rejected():

    registry = ReferenceRegistry()

    result = registry.append({"claim_reference": "au2_claim_001"})

    assert result.status == STATUS_INVALID

    assert registry.count() == 0


def test_missing_claim_reference_is_rejected():

    registry = ReferenceRegistry()

    assert registry.append({"licence_reference": "lic_b"}).status == STATUS_INVALID

    with pytest.raises(ReferenceRegistryError):

        ReferenceRegistryEntry(claim_reference="")


def test_unknown_identity_shapes_are_rejected():

    registry = ReferenceRegistry()

    for payload in (
        {"claim_reference": "clm_a", "licence_reference": "not_a_licence"},
        {"claim_reference": "clm_a", "derivation_event_reference": "clm_a"},
        {"claim_reference": "clm_a", "proposal_reference": "clm_a"},
        {"claim_reference": "clm_a", "knowledge_candidate_reference": "clm_a"},
        {"claim_reference": "clm_a", "scope": "universal"},
    ):

        assert registry.append(payload).status == STATUS_INVALID

    assert registry.count() == 0


def test_mutable_injected_object_is_rejected():

    registry = ReferenceRegistry()

    for payload in (["clm_a"], "clm_a", 42, object()):

        assert registry.append(payload).status == STATUS_INVALID


def test_derived_references_are_stored_as_opaque_non_empty_references():

    registry = ReferenceRegistry()

    result = registry.append(
        {
            "claim_reference": "clm_a",
            "proposal_reference": "prp_1234567890abcdef",
            "knowledge_candidate_reference": "kcd_1234567890abcdef",
        }
    )

    assert result.status == STATUS_APPENDED

    entry = registry.lookup_by_claim("clm_a")

    assert entry.proposal_reference == "prp_1234567890abcdef"

    assert entry.knowledge_candidate_reference == "kcd_1234567890abcdef"


def test_truth_fields_are_rejected():

    registry = ReferenceRegistry()

    for field in ("truth", "confidence", "certainty", "probability", "approval"):

        result = registry.append({"claim_reference": "clm_a", field: "x"})

        assert result.status == STATUS_FORBIDDEN_FIELD

    assert registry.count() == 0


def test_unknown_entry_field_is_rejected():

    registry = ReferenceRegistry()

    assert (
        registry.append({"claim_reference": "clm_a", "made_up": 1}).status
        == STATUS_INVALID
    )


def test_entry_declares_no_authority_and_stores_no_truth():

    entry = _entry()

    assert ReferenceRegistryEntry.CREATES_IDENTITY is False

    assert ReferenceRegistryEntry.OWNS_REFERENCE is False

    assert ReferenceRegistryEntry.STORES_OBJECTS is False

    payload = entry.to_dict()

    for field in ("truth", "confidence", "certainty", "approval"):

        assert field not in payload


# ----------------------------------------------------------
# 4. snapshot immutability
# ----------------------------------------------------------

def test_snapshot_is_unaffected_by_later_appends():

    registry = ReferenceRegistry()

    registry.append(_entry(claim_reference="clm_a"))

    snapshot = registry.snapshot()

    registry.append(_entry(claim_reference="clm_b"))

    assert len(snapshot) == 1

    assert registry.count() == 2

    assert isinstance(snapshot, tuple)


def test_stored_entries_are_immutable():

    registry = ReferenceRegistry()

    registry.append(_entry())

    entry = registry.lookup_by_claim("clm_a")

    with pytest.raises(FrozenInstanceError):

        entry.licence_reference = "lic_x"


# ----------------------------------------------------------
# 5. known reference sets
# ----------------------------------------------------------

def test_known_claim_references_returns_only_stored_governance_references():

    registry = ReferenceRegistry()

    registry.append(_entry(claim_reference="clm_a"))

    registry.append(_entry(claim_reference="clm_b"))

    registry.append({"claim_reference": "au2_claim_001"})  # rejected

    references = registry.known_claim_references()

    assert references == ("clm_a", "clm_b")

    assert all(reference.startswith("clm_") for reference in references)


def test_known_licence_references_returns_only_stored_governance_references():

    registry = ReferenceRegistry()

    registry.append(_entry(claim_reference="clm_a", licence_reference="lic_1"))

    registry.append(_entry(claim_reference="clm_b"))  # no licence

    registry.append(_entry(claim_reference="clm_c", licence_reference="lic_2"))

    references = registry.known_licence_references()

    assert references == ("lic_1", "lic_2")

    assert all(reference.startswith("lic_") for reference in references)


# ----------------------------------------------------------
# 6. no identity minting
# ----------------------------------------------------------

def test_registry_calls_no_identity_factory():

    forbidden_calls = (
        "uuid4",
        "uuid1",
        "mint_id",
        "new_claim_id",
        "new_licence_id",
        "new_derivation_event_id",
        "new_endorsement_event_id",
        "mint_claim",
        "mint_licence_record",
        "record_derivation_event",
        "record_endorsement_event",
        "reserve_claim_id",
        "reserve_licence_id",
        "reserve_derivation_event_id",
        "reserve_endorsement_event_id",
    )

    called = _called_names(REGISTRY_MODULE)

    offenders = [name for name in called if name in forbidden_calls]

    assert offenders == []


def test_registry_never_imports_identity_minting():

    roots = _imported_roots(REGISTRY_MODULE)

    assert "uuid" not in roots

    assert "core.governance.identity.reservation_v1" not in roots


# ----------------------------------------------------------
# 7. AST dependency checks
# ----------------------------------------------------------

def test_registry_has_no_client_imports():

    offenders = []

    for path in sorted(REGISTRY_DIR.rglob("*.py")):

        for root in _imported_roots(path):

            for forbidden in FORBIDDEN_IMPORT_ROOTS:

                if root == forbidden or root.startswith(forbidden + "."):

                    offenders.append((path.name, root))

    assert offenders == []


def test_registry_imports_only_governance_areas():

    allowed = (
        "core.governance",
        "core.governance.claim",
        "core.governance.identity_v1",
        "core.governance.registry",
    )

    offenders = []

    for path in sorted(REGISTRY_DIR.rglob("*.py")):

        for root in _imported_roots(path):

            if not root.startswith("core."):

                continue

            if not any(root == area or root.startswith(area + ".") for area in allowed):

                offenders.append((path.name, root))

    assert offenders == []


def test_no_governance_module_imports_registry():

    offenders = []

    for path in sorted(GOVERNANCE_DIR.rglob("*.py")):

        parts = path.parts

        if "registry" in parts or "tests" in parts:

            continue

        for root in _imported_roots(path):

            if root == "core.governance.registry" or root.startswith(
                "core.governance.registry."
            ):

                offenders.append((path.name, root))

    assert offenders == []


def test_registry_duplicates_no_prefix_literal():

    literals = [
        node.value
        for node in ast.walk(
            ast.parse(REGISTRY_MODULE.read_text(encoding="utf-8"))
        )
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]

    for literal in ("clm_", "lic_", "dev_", "eev_", "prp_", "kcd_"):

        assert literal not in literals
