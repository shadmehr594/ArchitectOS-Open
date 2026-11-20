"""Declarative furniture support policy contract (Phase 3D-AM).

Answers, as pure semantic metadata:

1. What support mode is intended for an object?
2. Is that mode explicitly known, or unresolved?
3. Does the policy require a future physical contact check?
4. Which surface would that check eventually target?

This module is POLICY ONLY. It deliberately does NOT:

- move, snap, shift or correct anything in X, Y or Z
- snap to a floor, a ceiling or a wall
- modify vertices, bounds, centers or scale
- apply or recompose any transform
- reinterpret ``center_xyz`` or derive ``bottom`` / ``top`` from a center and a
  half extent (that arithmetic belongs to a later physical-validation phase)
- validate collision, clearance, room containment or support contact
- insert anything into a scene, renderer, BIM or export structure
- import ``FurnitureAdapter``, ``furniture_unit_contract``, ``raw_obj_loader``,
  ``mesh_transform_spec`` or ``mesh_transform_executor``
- read any OBJ file, the asset registry, or any other external data
- access the filesystem, use randomness, UUIDs, timestamps or global counters

RULE STORAGE - why a Python constant rather than a JSON registry
---------------------------------------------------------------
The package does contain a JSON registry precedent (``forward_rules.json`` plus
``forward_rules.schema.json``). That registry is an externally-authored,
data-driven rule table large enough to warrant a separate JSON-Schema contract.
The support policy is the opposite: a small, closed, semantic vocabulary of four
rules. Encoding it as JSON would add a runtime file dependency, a second schema
to maintain and a fail-closed file-loading path, and would weaken the
no-filesystem guarantee for no benefit. The rules therefore live in this module
as an immutable constant, validated at import time, and are never handed out by
reference.

EVIDENCE BASIS AND ITS LIMITS
-----------------------------
Support modes are only assigned where current repository/data evidence exists:

- ``diffuscene_bedroom_floor_contact_measurement``: Phase 3D-AK measured, over
  400 real processed scenes, that these categories have their bounding-box
  bottom at Y = 0 (i.e. the object stands on the floor), while ``pendant_lamp``
  (0/260) and ``ceiling_lamp`` (1/126) do not.
- ``3d_future_category_taxonomy``: the remaining categories are the exact
  strings shipped in the local 3D-FUTURE registry, all of them ordinary
  floor-standing furniture types.
- ``architectos_furniture_adapter_category_contract``: the remaining category
  strings that the existing ``FurnitureAdapter`` category contract already
  recognises.

Categories with NO evidence of floor standing are deliberately left
``unresolved`` rather than guessed:

- ``wall_lamp`` - the only wall-mounting candidate. Its taxonomy name suggests a
  wall, but no geometric evidence corroborates wall contact, so it is NOT
  classified as ``wall``. Failing to ``unresolved`` is the safe outcome.
- ``hanging_chair`` - hangs; neither floor- nor ceiling-confirmed.
- ``""`` (empty category) - not a category at all; rejected as input.

There are NO ``wall`` and NO ``free`` rules. The vocabulary still admits both
values so a future evidence-backed rule needs no contract change.
"""

from __future__ import annotations

from typing import Any, Mapping


OUTPUT_TYPE = "furniture_support_policy"
OUTPUT_VERSION = "furniture_support_policy_v1"

SUPPORT_MODES = ("floor", "ceiling", "wall", "free")

SUPPORT_MODE_FLOOR = "floor"
SUPPORT_MODE_CEILING = "ceiling"

SUPPORT_STATUS_RESOLVED = "resolved"
SUPPORT_STATUS_UNRESOLVED = "unresolved"

CONTACT_CHECK_PENDING = "pending"
CONTACT_CHECK_UNRESOLVED = "unresolved"

STATE_RESOLVED = "support_policy_resolved"
STATE_UNRESOLVED = "support_policy_unresolved"

RULE_KEYS = (
    "rule_id",
    "categories",
    "support_mode",
    "source",
    "physical_contact_required",
)

# Source vocabulary. Kept as constants so the provenance strings cannot drift.
SOURCE_DIFFUSCENE_MEASURED = "diffuscene_bedroom_floor_contact_measurement"
SOURCE_3D_FUTURE_TAXONOMY = "3d_future_category_taxonomy"
SOURCE_ADAPTER_CATEGORY_CONTRACT = (
    "architectos_furniture_adapter_category_contract"
)


# ---------------------------------------------------------------------------
# the rule set (immutable constant; categories are exact strings only)
# ---------------------------------------------------------------------------

# DiffuScene object classes with MEASURED floor contact (bottom Y == 0).
_FLOOR_MEASURED = (
    "armchair",
    "bookshelf",
    "cabinet",
    "chair",
    "children_cabinet",
    "coffee_table",
    "desk",
    "double_bed",
    "dressing_chair",
    "dressing_table",
    "kids_bed",
    "nightstand",
    "shelf",
    "single_bed",
    "sofa",
    "stool",
    "table",
    "tv_stand",
    "wardrobe",
)

# Remaining exact 3D-FUTURE registry categories that are ordinary floor-standing
# furniture. Deliberately EXCLUDES "", "wall_lamp" and "hanging_chair".
_FLOOR_3D_FUTURE_TAXONOMY = (
    "bar",
    "barstool",
    "bed",
    "bed_frame",
    "bookcase_/_jewelry_armoire",
    "bunk_bed",
    "chaise_longue_sofa",
    "classic_chinese_chair",
    "corner/side_table",
    "couch_bed",
    "drawer_chest_/_corner_cabinet",
    "floor_lamp",
    "folding_chair",
    "footstool_/_sofastool_/_bed_end_stool_/_stool",
    "king_size_bed",
    "l_shaped_sofa",
    "lazy_sofa",
    "loveseat_sofa",
    "lounge_chair_/_book_chair_/_computer_chair",
    "lounge_chair_/_cafe_chair_/_office_chair",
    "round_end_table",
    "shoe_cabinet",
    "sideboard_/_side_cabinet_/_console",
    "sideboard_/_side_cabinet_/_console_table",
    "tea_table",
    "three_seat_/_multi_person_sofa",
    "three_seat_/_multi_seat_sofa",
    "two_seat_sofa",
    "u_shaped_sofa",
    "wine_cabinet",
    "wine_cooler",
)

# Exact category strings already recognised by the existing FurnitureAdapter
# category contract but absent from the two data vocabularies above.
_FLOOR_ADAPTER_CATEGORY_CONTRACT = (
    "bedside_table",
    "dining_chair",
    "dining_table",
    "lounge_chair",
    "master_bed",
    "side_table",
)

# Ceiling-hung lamps. Measured to NOT stand on the floor.
_CEILING_TAXONOMY = (
    "ceiling_lamp",
    "pendant_lamp",
)


SUPPORT_RULES = (
    {
        "rule_id": "floor_support_measured",
        "categories": _FLOOR_MEASURED,
        "support_mode": SUPPORT_MODE_FLOOR,
        "source": SOURCE_DIFFUSCENE_MEASURED,
        "physical_contact_required": True,
    },
    {
        "rule_id": "floor_support_3d_future_taxonomy",
        "categories": _FLOOR_3D_FUTURE_TAXONOMY,
        "support_mode": SUPPORT_MODE_FLOOR,
        "source": SOURCE_3D_FUTURE_TAXONOMY,
        "physical_contact_required": True,
    },
    {
        "rule_id": "floor_support_adapter_category_contract",
        "categories": _FLOOR_ADAPTER_CATEGORY_CONTRACT,
        "support_mode": SUPPORT_MODE_FLOOR,
        "source": SOURCE_ADAPTER_CATEGORY_CONTRACT,
        "physical_contact_required": True,
    },
    {
        "rule_id": "ceiling_support_3d_future_taxonomy",
        "categories": _CEILING_TAXONOMY,
        "support_mode": SUPPORT_MODE_CEILING,
        "source": SOURCE_3D_FUTURE_TAXONOMY,
        "physical_contact_required": True,
    },
)


# ---------------------------------------------------------------------------
# rule validation (fails closed)
# ---------------------------------------------------------------------------

def validate_support_rules(rules):
    """Validate a rule collection and return a NEW normalized list.

    Fails closed on: a non-sequence container, an empty collection, a
    non-mapping rule, unknown or missing rule keys, a malformed ``rule_id``, a
    duplicate ``rule_id``, an out-of-vocabulary ``support_mode``, a malformed
    ``source``, a non-boolean ``physical_contact_required``, an empty or
    malformed ``categories`` list, and any category assigned to more than one
    rule (so no category can silently acquire two support modes).
    """

    if isinstance(rules, (str, bytes)) or not isinstance(rules, (list, tuple)):
        raise ValueError("support rules must be a list or tuple of mappings")
    if not rules:
        raise ValueError("support rules must not be empty")

    normalized = []
    rule_ids = set()
    assigned = {}

    for position, rule in enumerate(rules):
        if not isinstance(rule, Mapping):
            raise ValueError(f"support rules[{position}] must be a mapping")

        unknown = set(rule) - set(RULE_KEYS)
        if unknown:
            raise ValueError(
                f"unknown support rules[{position}] key(s): "
                + ", ".join(sorted(unknown))
            )

        for key in RULE_KEYS:
            if key not in rule:
                raise ValueError(f"support rules[{position}] is missing: {key}")

        rule_id = rule["rule_id"]
        if (
            isinstance(rule_id, bool)
            or not isinstance(rule_id, str)
            or not rule_id.strip()
        ):
            raise ValueError(
                f"support rules[{position}].rule_id must be a non-empty string"
            )
        if rule_id in rule_ids:
            raise ValueError(f"duplicate support rule_id: {rule_id!r}")
        rule_ids.add(rule_id)

        support_mode = rule["support_mode"]
        if isinstance(support_mode, bool) or support_mode not in SUPPORT_MODES:
            raise ValueError(
                f"support rules[{position}].support_mode must be one of: "
                + ", ".join(SUPPORT_MODES)
            )

        source = rule["source"]
        if (
            isinstance(source, bool)
            or not isinstance(source, str)
            or not source.strip()
        ):
            raise ValueError(
                f"support rules[{position}].source must be a non-empty string"
            )

        required = rule["physical_contact_required"]
        if not isinstance(required, bool):
            raise ValueError(
                f"support rules[{position}].physical_contact_required must be "
                "a boolean"
            )

        categories = rule["categories"]
        if isinstance(categories, (str, bytes)) or not isinstance(
            categories, (list, tuple)
        ):
            raise ValueError(
                f"support rules[{position}].categories must be a list or tuple"
            )
        if not categories:
            raise ValueError(
                f"support rules[{position}].categories must not be empty"
            )

        cleaned_categories = []
        for category in categories:
            if (
                isinstance(category, bool)
                or not isinstance(category, str)
                or not category.strip()
            ):
                raise ValueError(
                    f"support rules[{position}].categories entries must be "
                    "non-empty strings"
                )
            if category in assigned:
                raise ValueError(
                    f"category {category!r} is assigned to both "
                    f"{assigned[category]!r} and {rule_id!r}; a category may be "
                    "assigned exactly one support rule"
                )
            assigned[category] = rule_id
            cleaned_categories.append(category)

        normalized.append(
            {
                "rule_id": rule_id,
                "categories": cleaned_categories,
                "support_mode": support_mode,
                "source": source,
                "physical_contact_required": required,
            }
        )

    return normalized


# Validated once at import time: an invalid rule set fails closed immediately.
_CATEGORY_RULE_INDEX = {}
for _rule in validate_support_rules(SUPPORT_RULES):
    for _category in _rule["categories"]:
        _CATEGORY_RULE_INDEX[_category] = {
            "rule_id": _rule["rule_id"],
            "support_mode": _rule["support_mode"],
            "source": _rule["source"],
            "physical_contact_required": _rule["physical_contact_required"],
        }
del _rule, _category


# ---------------------------------------------------------------------------
# contract builders
# ---------------------------------------------------------------------------

def _semantics():
    """Static, declarative facts. Every geometry action stays False."""

    return {
        "metadata_only": True,
        "geometry_modified": False,
        "floor_snap_applied": False,
        "ceiling_snap_applied": False,
        "wall_snap_applied": False,
        "collision_validated": False,
        "containment_validated": False,
    }


def _resolved_contract(category, rule):
    return {
        "type": OUTPUT_TYPE,
        "version": OUTPUT_VERSION,
        "category": category,
        "support": {
            "status": SUPPORT_STATUS_RESOLVED,
            "mode": rule["support_mode"],
            "rule_id": rule["rule_id"],
            "source": rule["source"],
            "reasons": [f"matched_support_rule:{rule['rule_id']}"],
        },
        "physical_validation": {
            "required": rule["physical_contact_required"],
            "contact_target": rule["support_mode"],
            # Never "complete": no physical check has been performed.
            "contact_check_status": CONTACT_CHECK_PENDING,
            "geometry_adjustment_authorized": False,
        },
        "semantics": _semantics(),
        "status": {
            "state": STATE_RESOLVED,
            "reasons": [
                f"support_mode_resolved:{rule['support_mode']}",
                "physical_contact_check_pending",
            ],
        },
    }


def _unresolved_contract(category):
    return {
        "type": OUTPUT_TYPE,
        "version": OUTPUT_VERSION,
        "category": category,
        "support": {
            "status": SUPPORT_STATUS_UNRESOLVED,
            "mode": None,
            "rule_id": None,
            "source": None,
            "reasons": ["no_support_rule_for_category"],
        },
        "physical_validation": {
            # No contact target is known, so no contact check can be required
            # yet. This is "unresolved", never "not needed".
            "required": False,
            "contact_target": None,
            "contact_check_status": CONTACT_CHECK_UNRESOLVED,
            "geometry_adjustment_authorized": False,
        },
        "semantics": _semantics(),
        "status": {
            "state": STATE_UNRESOLVED,
            "reasons": [
                "category_support_mode_unknown",
                "contact_target_unresolved_until_support_mode_known",
            ],
        },
    }


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def resolve_furniture_support_policy(*, category):
    """Resolve the support policy for one EXACT canonical category string.

    ``category`` must be a non-empty string (``bool`` is rejected). Matching is
    EXACT membership only: no case folding, no whitespace trimming, no
    substring matching, no plural/singular guessing and no alias inference.

    A category with no rule resolves to ``support.status = "unresolved"`` with
    ``mode = null`` - it is never guessed.

    Pure function: no filesystem, no registry or dataset lookup, no geometry,
    no randomness. Malformed input raises ``ValueError``.
    """

    if (
        isinstance(category, bool)
        or not isinstance(category, str)
        or not category.strip()
    ):
        raise ValueError("category must be a non-empty string")

    rule = _CATEGORY_RULE_INDEX.get(category)

    if rule is None:
        return _unresolved_contract(category)

    return _resolved_contract(category, rule)
