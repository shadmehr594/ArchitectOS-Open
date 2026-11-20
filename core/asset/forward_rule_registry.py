"""Versioned Forward Rule Registry loader (Phase 3D-U).

Declarative forward-rule knowledge only.

CRITICAL BOUNDARY: geometry never originates semantic forward. This module does
not measure geometry, does not import the geometry gate, does not inspect
category names heuristically, and never chooses a forward direction. It stores
and returns rules that a caller supplied, so that a caller can then:

    rule = registry.get_forward_rule(family_id)
    ... build a forward_contract from that rule ...
    ... run the Phase 3D-S geometry agreement gate ...
    ... run resolve_forward_contract(...) ...
    ... pass the resolved contract to build_mesh_transform_spec(...)

Each stage stays separable; nothing here executes that chain.

Category membership is EXACT canonical-string matching only. Substring, regex,
fuzzy and keyword-heuristic matching are deliberately absent.
"""

from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from core.asset.mesh_transform_spec import FORWARD_AXES


FORMAT_VERSION = "forward_rule_registry_v1"
DEFAULT_REGISTRY_PATH = Path(__file__).with_name("forward_rules.json")

# A family rule may be supported, unresolved, or unsupported.
RULE_STATUSES = ("supported", "unresolved", "unsupported")
# `verified` would overstate a family rule (Phase 3D-Q). `unobservable` and
# `ambiguous` are per-asset result states, not registry-rule authority states.
FORBIDDEN_RULE_STATUSES = ("verified", "unobservable", "ambiguous")

TOP_LEVEL_KEYS = ("format_version", "rules")
RULE_KEYS = (
    "status",
    "semantic_forward_axis",
    "expected_geometry_direction",
    "geometry_gate_required",
    "scope",
    "evidence",
)
SCOPE_KEYS = ("include_categories", "exclude_categories")
EVIDENCE_KEYS = ("rule_id", "source_checkpoint", "agreement", "notes")

NOTE_MAX_CHARS = 200

_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_PATH_PATTERN = re.compile(r"\\|^[A-Za-z]:[\\/]")


# ---------------------------------------------------------------------------
# validation helpers
# ---------------------------------------------------------------------------

def _unknown_fields(mapping, allowed, label):
    unknown = sorted(set(mapping) - set(allowed))
    if unknown:
        raise ValueError(
            f"unknown {label} field(s): " + ", ".join(unknown)
        )


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    if _UUID_PATTERN.match(value):
        raise ValueError(f"{label} must not contain a sample model id")
    if _PATH_PATTERN.search(value):
        raise ValueError(f"{label} must not contain a machine-specific path")

    return value


def _category_list(value, label, required):
    if value is None:
        if required:
            raise ValueError(f"{label} is required")
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{label} must be an array of strings")

    items = []
    seen = set()
    for entry in value:
        item = _text(entry, f"{label} entry")
        if item in seen:
            raise ValueError(f"{label} contains a duplicate entry: {item!r}")
        seen.add(item)
        items.append(item)

    if required and not items:
        raise ValueError(f"{label} must contain at least one entry")

    return items


def _evidence(value):
    if not isinstance(value, Mapping):
        raise ValueError("evidence must be a mapping")
    _unknown_fields(value, EVIDENCE_KEYS, "evidence")

    for key in EVIDENCE_KEYS:
        if key not in value:
            raise ValueError(f"evidence is missing: {key}")

    agreement = value["agreement"]
    if agreement is not None:
        if isinstance(agreement, bool) or not isinstance(agreement, (int, float)):
            raise ValueError("evidence agreement must be a number or null")
        agreement = float(agreement)
        if not math.isfinite(agreement) or not 0.0 <= agreement <= 1.0:
            raise ValueError("evidence agreement must be within [0, 1]")

    notes = value["notes"]
    if isinstance(notes, (str, bytes)) or not isinstance(notes, Sequence):
        raise ValueError("evidence notes must be an array of strings")
    cleaned_notes = []
    for note in notes:
        text = _text(note, "evidence note")
        if len(text) > NOTE_MAX_CHARS:
            raise ValueError("evidence notes must stay compact")
        cleaned_notes.append(text)

    return {
        "rule_id": _text(value["rule_id"], "evidence rule_id"),
        "source_checkpoint": _text(
            value["source_checkpoint"], "evidence source_checkpoint"
        ),
        "agreement": agreement,
        "notes": cleaned_notes,
    }


def _rule(family_id, value):
    if not isinstance(value, Mapping):
        raise ValueError(f"rule {family_id!r} must be a mapping")
    _unknown_fields(value, RULE_KEYS, f"rule {family_id!r}")

    for key in RULE_KEYS:
        if key not in value:
            raise ValueError(f"rule {family_id!r} is missing: {key}")

    status = value["status"]
    if status in FORBIDDEN_RULE_STATUSES:
        raise ValueError(
            f"rule {family_id!r} status {status!r} is not a valid family-rule "
            "authority state"
        )
    if status not in RULE_STATUSES:
        raise ValueError(
            "rule status must be one of: " + ", ".join(RULE_STATUSES)
        )

    forward = value["semantic_forward_axis"]
    if forward not in FORWARD_AXES:
        raise ValueError(
            "semantic_forward_axis must be one of: " + ", ".join(FORWARD_AXES)
        )

    expected = value["expected_geometry_direction"]
    if expected not in FORWARD_AXES:
        raise ValueError(
            "expected_geometry_direction must be one of: "
            + ", ".join(FORWARD_AXES)
        )

    gate = value["geometry_gate_required"]
    if not isinstance(gate, bool):
        raise ValueError("geometry_gate_required must be a boolean")

    scope = value["scope"]
    if not isinstance(scope, Mapping):
        raise ValueError("scope must be a mapping")
    _unknown_fields(scope, SCOPE_KEYS, "scope")
    if "include_categories" not in scope:
        raise ValueError("scope is missing: include_categories")

    include = _category_list(
        scope["include_categories"], "include_categories", True
    )
    exclude = _category_list(
        scope.get("exclude_categories"), "exclude_categories", False
    )

    overlap = sorted(set(include) & set(exclude))
    if overlap:
        raise ValueError(
            "include_categories and exclude_categories must be disjoint: "
            + ", ".join(overlap)
        )

    return {
        "status": status,
        "semantic_forward_axis": forward,
        "expected_geometry_direction": expected,
        "geometry_gate_required": gate,
        "scope": {
            "include_categories": include,
            "exclude_categories": exclude,
        },
        "evidence": _evidence(value["evidence"]),
    }


def validate_registry(data):
    """Validate and normalize a forward rule registry mapping.

    Raises ``ValueError`` on any violation. Returns a normalized copy; the input
    mapping is never modified.
    """

    if not isinstance(data, Mapping):
        raise ValueError("forward rule registry must be a mapping")
    _unknown_fields(data, TOP_LEVEL_KEYS, "registry")

    for key in TOP_LEVEL_KEYS:
        if key not in data:
            raise ValueError(f"registry is missing: {key}")

    if data["format_version"] != FORMAT_VERSION:
        raise ValueError(f"format_version must be {FORMAT_VERSION!r}")

    rules = data["rules"]
    if not isinstance(rules, Mapping) or not rules:
        raise ValueError("rules must be a non-empty mapping")

    validated = {}
    owner = {}
    for family_id, raw_rule in rules.items():
        _text(family_id, "family id")
        if family_id != family_id.strip():
            raise ValueError(
                f"family id {family_id!r} must not have surrounding whitespace"
            )

        rule = _rule(family_id, raw_rule)
        for category in rule["scope"]["include_categories"]:
            if category in owner:
                raise ValueError(
                    f"category {category!r} is included by two families: "
                    f"{owner[category]!r} and {family_id!r}"
                )
            owner[category] = family_id
        validated[family_id] = rule

    return {"format_version": FORMAT_VERSION, "rules": validated}


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

class ForwardRuleRegistry:
    """Declarative forward rule store. Validation happens at construction."""

    def __init__(self, data):
        validated = validate_registry(data)
        self._format_version = validated["format_version"]
        self._rules = validated["rules"]

    @classmethod
    def from_mapping(cls, data):
        return cls(data)

    @classmethod
    def from_file(cls, path):
        registry_path = Path(path)
        with registry_path.open("r", encoding="utf-8") as handle:
            return cls(json.load(handle))

    @classmethod
    def load_default(cls):
        return cls.from_file(DEFAULT_REGISTRY_PATH)

    @property
    def format_version(self):
        return self._format_version

    @property
    def family_ids(self):
        return tuple(sorted(self._rules))

    def get_forward_rule(self, family_id):
        """Exact family-id lookup only. Returns a defensive copy, or ``None``.

        No category inference happens here: an unknown family id returns
        ``None`` rather than a best guess.
        """

        rule = self._rules.get(family_id)

        return copy.deepcopy(rule) if rule is not None else None

    def find_rules_for_category(self, category):
        """Explicit registry membership lookup, NOT semantic inference.

        Exact canonical-string membership only - no substring, regex or fuzzy
        matching. Excluded categories never match (include and exclude lists are
        validated disjoint), and an unknown category returns ``[]``.

        Returns ``[{"family_id": ..., "rule": {...}}]``; at most one entry can
        match because include lists are validated disjoint across families.
        """

        if not isinstance(category, str):
            return []

        matches = []
        for family_id in sorted(self._rules):
            rule = self._rules[family_id]
            if category in rule["scope"]["include_categories"]:
                matches.append(
                    {"family_id": family_id, "rule": copy.deepcopy(rule)}
                )

        return matches
