# -*- coding: utf-8 -*-
"""VISUAL_REFERENCE_UX_V2 — DESIGN CONSTRAINT FIDELITY.

WHY THIS MODULE EXISTS
----------------------
The accepted USO experiment produced two designs whose storey count did not
match the request, while ComfyUI history proved the requested count HAD reached
the sampler. Two different facts were being reported as one:

    "the prompt said 5 storeys"          (instruction)
    "the building has 5 storeys"         (observation)

This module keeps three properties permanently separate and never lets one
stand in for another:

    1. REQUESTED  — what the user asked for (building type, storeys)
    2. EXECUTED   — the exact text submitted to the model
    3. OBSERVED   — what can actually be seen in the produced image

A prompt that contains "5 storeys" is evidence about (2) ONLY. It is never
evidence about (3), and it can never produce a PASS on its own.

NO NEW VISION CAPABILITY
------------------------
Observation is read from the EXISTING facade contract
(``facade_reference_vision_provider_v1.map_to_contract``), which already emits
``visible_floor_count`` and ``building_type``. This module adds no detector, no
counter and no CV code — it only compares what that contract reports against
what was requested, and reports UNVERIFIED when the contract says nothing.
"""

import re

CONTRACT = "DesignConstraintFidelityV1"
VERSION = "1.0"

# ---- floor status ------------------------------------------------------
FLOOR_VERIFIED = "FLOOR_COUNT_VERIFIED"
FLOOR_MISMATCH = "FLOOR_COUNT_MISMATCH"
FLOOR_UNVERIFIED = "FLOOR_COUNT_UNVERIFIED"
FLOOR_NOT_REQUESTED = "FLOOR_COUNT_NOT_REQUESTED"

# ---- building type status ----------------------------------------------
TYPE_VERIFIED = "BUILDING_TYPE_VERIFIED"
TYPE_MISMATCH = "BUILDING_TYPE_MISMATCH"
TYPE_UNVERIFIED = "BUILDING_TYPE_UNVERIFIED"
TYPE_NOT_REQUESTED = "BUILDING_TYPE_NOT_REQUESTED"

#: Families used for comparison only. This is NOT a new building taxonomy —
#: it exists so "apartment" and "villa" are not called a mismatch merely
#: because the words differ.
_RESIDENTIAL = {
    "villa", "house", "home", "residence", "residential", "apartment",
    "apartment building", "apartment block", "flat", "dwelling", "housing",
    "townhouse", "duplex", "building",
}
_COMMERCIAL = {"commercial", "retail", "shop", "store", "office", "showroom", "mall"}
_INSTITUTIONAL = {"institutional", "civic", "public", "school", "museum", "government", "temple"}
_MIXED = {"mixed", "mixed use", "mixed-use"}

_FLOOR_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _family(building_type):
    text = _norm(building_type)
    if not text:
        return None
    if text in _MIXED:
        return "mixed"
    if text in _COMMERCIAL:
        return "commercial"
    if text in _INSTITUTIONAL:
        return "institutional"
    if text in _RESIDENTIAL:
        return "residential"
    for word, family in (
        ("apartment", "residential"), ("villa", "residential"),
        ("residen", "residential"), ("hous", "residential"),
        ("commercial", "commercial"), ("retail", "commercial"),
        ("office", "commercial"), ("institut", "institutional"),
        ("civic", "institutional"),
    ):
        if word in text:
            return family
    return None


# ==========================================================
# 1. REQUESTED
# ==========================================================

def requested_constraints(architectural_intent):
    """What the user asked for. Read from the existing intent contract."""
    intent = architectural_intent if isinstance(architectural_intent, dict) else {}
    building = intent.get("building") if isinstance(intent.get("building"), dict) else {}

    floors = intent.get("floors")
    if floors is None:
        floors = building.get("floors")
    try:
        floors = int(floors) if floors is not None else None
    except (TypeError, ValueError):
        floors = None

    building_type = (
        intent.get("building_type")
        or building.get("type")
        or intent.get("type")
    )

    return {
        "floors": floors,
        "building_type": building_type,
        "building_type_family": _family(building_type),
        "source": "architectural_intent",
    }


def requested_floors_from_text(text):
    """Fallback only: the storey count the user typed, when intent has none.

    Used to REPORT a request the intent contract failed to carry — never to
    decide that the request was met.
    """
    low = _norm(text)
    if not low:
        return None
    match = re.search(
        r"\b(\d{1,2})\s*[- ]?\s*(?:storey|storeys|story|stories|floor|floors|طبقه)\b",
        low,
    )
    if match:
        return int(match.group(1))
    for word, count in _FLOOR_WORDS.items():
        if re.search(r"\b%s\s*[- ]?\s*(?:storey|storeys|story|stories|floor|floors)\b" % word, low):
            return count
    return None


# ==========================================================
# 2. EXECUTED
# ==========================================================

def executed_instruction(prompt_text):
    """The exact text the sampler consumed. Evidence about the INSTRUCTION."""
    text = prompt_text if isinstance(prompt_text, str) else ""
    low = _norm(text)
    mentioned = None
    if low:
        match = re.search(
            r"\b(\d{1,2})\s*[- ]?\s*(?:storey|storeys|story|stories|floor|floors)\b", low
        )
        if match:
            mentioned = int(match.group(1))
        else:
            for word, count in _FLOOR_WORDS.items():
                if re.search(r"\b%s\s*[- ]?\s*(?:storey|storeys|story|stories|floor|floors)\b" % word, low):
                    mentioned = count
                    break
    return {
        "chars": len(text),
        "floors_mentioned": mentioned,
        "source": "sampler_positive_prompt",
    }


# ==========================================================
# 3. OBSERVED
# ==========================================================

# ==========================================================
# ARCHITECTURAL_VISION_RUNTIME_COMPLETION_V1 — PARTIAL VIEW
#
# A vision provider reports the floors it can SEE. When the building is
# cropped, that number is a LOWER BOUND, not a total. The Krea night
# benchmark (architectos_v11_00260_.png) returned visible_floor_count = 4
# together with
#     occlusions = ["ground floor obscured by framing"]
#     perspective_limitations = ["view is cropped, showing only a section…"]
# and the previous code turned that into FLOOR_COUNT_MISMATCH against a
# five-floor request — asserting the building HAS four floors.
#
# "rear of building not visible" is NOT a partial view: no photograph shows
# a rear from the front, so the markers are deliberately about framing.
# ==========================================================

_PARTIAL_VIEW_MARKERS = (
    "cropped", "crop", "obscured", "cut off", "only a section",
    "partial view", "partial framing", "truncated", "out of frame",
    "off-frame", "not fully in frame", "not fully visible", "partially visible",
)


def _view_is_partial(contract):
    """True when the observation itself says the building is not fully shown."""

    if not isinstance(contract, dict):
        return False

    for field in ("occlusions", "perspective_limitations"):

        for item in contract.get(field) or []:

            text = str(item).lower()

            if any(marker in text for marker in _PARTIAL_VIEW_MARKERS):
                return True

    return False


def _floor_evidence_consistency(floor_observation, visible_floor_count):
    """Validate provider-declared level evidence without recounting pixels.

    This consumes only the optional V4 structure emitted by the existing
    provider.  Legacy observations remain LEGACY and retain their V2/V3
    behavior.  No free-text geometry heuristic or expected-answer rewrite is
    performed here.
    """

    if not isinstance(floor_observation, dict) \
            or "per_level_evidence" not in floor_observation:
        return {
            "status": "LEGACY",
            "reason": "per-level evidence was not supplied",
            "contributing_level_count": None,
        }

    levels = floor_observation.get("per_level_evidence")
    if not isinstance(levels, list) or not levels:
        return {
            "status": "UNVERIFIED",
            "reason": "per-level evidence is present but contains no classified levels",
            "contributing_level_count": None,
        }

    allowed = {
        "principal_storey", "roof_opening", "attic_or_roof_storey",
        "mezzanine", "ambiguous",
    }
    contributing = 0
    incomplete = []

    for index, level in enumerate(levels):
        if not isinstance(level, dict):
            incomplete.append(index)
            continue

        category = level.get("category")
        contributes = level.get("contributes_to_floor_count")
        confidence = level.get("confidence")
        uncertainty = level.get("uncertainty")

        if category not in allowed or not isinstance(contributes, bool):
            incomplete.append(index)
            continue
        if confidence is None and not uncertainty:
            incomplete.append(index)
            continue

        # A provider may emit a confident-looking category while explicitly
        # saying the same level could be something else (the V4 Kontext-D
        # observation did exactly this for the gable opening).  The stated
        # uncertainty is evidence against verification; do not average it
        # away or rewrite the category to an expected answer.
        if uncertainty:
            return {
                "status": "UNVERIFIED",
                "reason": (
                    "per-level evidence states classification uncertainty "
                    "at index %d: %s" % (index, uncertainty)
                ),
                "contributing_level_count": None,
            }

        if category == "ambiguous":
            return {
                "status": "UNVERIFIED",
                "reason": "per-level evidence contains an ambiguous level",
                "contributing_level_count": None,
            }
        if category == "roof_opening" and contributes:
            return {
                "status": "CONTRADICTORY",
                "reason": "a roof opening is marked as contributing to the floor count",
                "contributing_level_count": None,
            }
        if category == "principal_storey" and not contributes:
            return {
                "status": "CONTRADICTORY",
                "reason": "a principal storey is marked as excluded from the floor count",
                "contributing_level_count": None,
            }
        if contributes:
            contributing += 1

    if incomplete:
        return {
            "status": "UNVERIFIED",
            "reason": "per-level evidence has incomplete classification at index(es) %s"
                      % ", ".join(str(index) for index in incomplete),
            "contributing_level_count": None,
        }

    reported_count = floor_observation.get("count")
    count_type = floor_observation.get("count_type")
    legible = floor_observation.get("storey_divisions_legible")

    if count_type == "TOTAL" and legible is not True:
        return {
            "status": "CONTRADICTORY",
            "reason": "TOTAL was declared while storey divisions were not legible",
            "contributing_level_count": contributing,
        }
    if count_type == "TOTAL" and reported_count != contributing:
        return {
            "status": "CONTRADICTORY",
            "reason": (
                "reported total %r conflicts with %d contributing level(s)"
                % (reported_count, contributing)
            ),
            "contributing_level_count": contributing,
        }
    if isinstance(visible_floor_count, int) and not isinstance(
        visible_floor_count, bool
    ) and reported_count is not None and visible_floor_count != reported_count:
        return {
            "status": "CONTRADICTORY",
            "reason": (
                "visible_floor_count %d conflicts with floor_observation count %d"
                % (visible_floor_count, reported_count)
            ),
            "contributing_level_count": contributing,
        }

    return {
        "status": "CONSISTENT",
        "reason": "per-level contributions agree with the reported count",
        "contributing_level_count": contributing,
    }


def observed_constraints(contract):
    """What the EXISTING facade contract reports about the produced image.

    Accepts either the facade contract (``visible_floor_count`` /
    ``building_type``) or an architectural observation (``visible_floors``).
    Returns ``None`` values when the provider said nothing — which is the
    normal, honest case and must not be read as agreement.
    """
    if not isinstance(contract, dict):
        return {
            "floors": None,
            "building_type": None,
            "building_type_family": None,
            "evidence": None,
            "available": False,
            "source": "none",
        }

    floors = contract.get("visible_floor_count")
    visible_floor_count = floors
    evidence = None

    if floors is None:
        visible = contract.get("visible_floors")
        if isinstance(visible, dict):
            floors = visible.get("count")
            evidence = visible.get("evidence_phrase")
        elif isinstance(visible, int) and not isinstance(visible, bool):
            floors = visible

    if not (isinstance(floors, int) and not isinstance(floors, bool) and 0 < floors <= 200):
        floors = None

    building_type = contract.get("building_type")

    # ==================================================
    # VISION_LIGHTING_OUTPUT_VERIFICATION_V2 — COUNT CONFIDENCE
    #
    # `visible_floor_count` alone cannot say whether the number is a TOTAL or
    # just what happens to be in frame. The additive `floor_observation` block
    # states which it is, so the verdict no longer has to guess:
    #
    #   TOTAL          -> the number may verify the request
    #   VISIBLE_LEVELS -> whole building visible, storey divisions illegible
    #   LOWER_BOUND    -> cropped/occluded, the number is a minimum
    #   AMBIGUOUS      -> the observer itself could not decide
    #
    # A contract WITHOUT the block keeps the V1 behaviour (partial-view guard
    # below), so older recorded observations still evaluate identically.
    # ==================================================

    floor_observation = contract.get("floor_observation")
    floor_observation = floor_observation if isinstance(floor_observation, dict) else None

    count_type = None
    if floor_observation:
        count_type = floor_observation.get("count_type")
        observed_count = floor_observation.get("count")
        if isinstance(observed_count, int) and not isinstance(observed_count, bool) \
                and 0 < observed_count <= 200:
            floors = observed_count

    floor_consistency = _floor_evidence_consistency(
        floor_observation, visible_floor_count
    )

    partial = _view_is_partial(contract)

    lower_bound = None

    if count_type == "TOTAL":
        # Explicitly established as a total; only a partial view can veto it.
        if partial:
            lower_bound = floors
            floors = None
        elif floor_consistency["status"] in ("CONTRADICTORY", "UNVERIFIED"):
            floors = None
    elif count_type in ("VISIBLE_LEVELS", "LOWER_BOUND", "AMBIGUOUS", "UNKNOWN"):
        lower_bound = floors
        floors = None
    elif partial:
        # Legacy contract, or a contract with no count_type: V1 behaviour.
        lower_bound = floors
        floors = None

    return {
        "floors": floors,
        "building_type": building_type,
        "building_type_family": _family(building_type),
        "evidence": evidence,
        "available": floors is not None or bool(building_type),
        "source": "facade_reference_vision_contract",
        "view_partial": bool(partial),
        "visible_floor_count_lower_bound": lower_bound,
        "floor_count_type": count_type,
        "floor_consistency": floor_consistency,
        "storey_divisions_legible": (
            floor_observation.get("storey_divisions_legible")
            if floor_observation else None
        ),
        # Time of day is carried as an OBSERVATION, never as a verdict.
        "lighting": contract.get("lighting") if isinstance(contract.get("lighting"), dict) else None,
    }


# ==========================================================
# 4. COMPARISON
# ==========================================================

def evaluate(architectural_intent, sampler_prompt, observed_contract,
             requested_text=None):
    """Compare the three properties and report each verdict separately."""
    requested = requested_constraints(architectural_intent)

    if requested["floors"] is None and requested_text:
        requested["floors"] = requested_floors_from_text(requested_text)
        requested["source"] = "architectural_intent+request_text"

    executed = executed_instruction(sampler_prompt)
    observed = observed_constraints(observed_contract)

    # ---- floors --------------------------------------------------------
    if requested["floors"] is None:
        floor_status = FLOOR_NOT_REQUESTED
        floor_reason = "no storey count was requested"
    elif observed["floors"] is None:
        floor_status = FLOOR_UNVERIFIED
        _count_type = observed.get("floor_count_type")
        _lower = observed.get("visible_floor_count_lower_bound")
        _consistency = observed.get("floor_consistency") or {}

        if _consistency.get("status") == "CONTRADICTORY":
            floor_reason = "the floor observation is contradictory: %s" % (
                _consistency.get("reason") or "its count and level evidence disagree",
            )
        elif _consistency.get("status") == "UNVERIFIED":
            floor_reason = "the floor observation remains unverified: %s" % (
                _consistency.get("reason") or "its per-level evidence is incomplete",
            )
        elif _count_type == "VISIBLE_LEVELS":
            if observed.get("storey_divisions_legible") is True:
                floor_reason = (
                    "the observer counted %s visible level(s) but did not "
                    "establish them as the building's complete storey count"
                    % (_lower,)
                )
            else:
                floor_reason = (
                    "the whole building is in frame but its storey divisions "
                    "are not legible, so the %s visible level(s) are not a "
                    "reliable floor count" % (_lower,)
                )
        elif _count_type in ("LOWER_BOUND", "AMBIGUOUS"):
            floor_reason = (
                "the observation could not establish a total: %s is only a "
                "lower bound" % (_lower,)
            ) if _count_type == "LOWER_BOUND" else (
                "the observer reported the storey count as ambiguous"
            )
        elif observed.get("view_partial"):
            floor_reason = (
                "the building is not fully in frame, so the %s visible "
                "storey(s) are a lower bound rather than a total"
                % (_lower,)
            )
        else:
            floor_reason = (
                "the observation path did not report a visible storey count; "
                "the instruction is not evidence of the result"
            )
    elif observed["floors"] == requested["floors"]:
        floor_status = FLOOR_VERIFIED
        floor_reason = "observed storey count matches the request"
    else:
        floor_status = FLOOR_MISMATCH
        floor_reason = "observed %d storeys, requested %d" % (
            observed["floors"], requested["floors"]
        )

    # ---- building type -------------------------------------------------
    if not requested["building_type"]:
        type_status = TYPE_NOT_REQUESTED
        type_reason = "no building type was requested"
    elif observed["building_type_family"] is None:
        type_status = TYPE_UNVERIFIED
        type_reason = "the observation path did not report a building type"
    elif observed["building_type_family"] == requested["building_type_family"]:
        type_status = TYPE_VERIFIED
        type_reason = "observed building type family matches the request"
    else:
        type_status = TYPE_MISMATCH
        type_reason = "observed %r, requested %r" % (
            observed["building_type"], requested["building_type"]
        )

    # The instruction is reported as its OWN fact. It is deliberately not
    # folded into either verdict above.
    instruction_carried = (
        requested["floors"] is not None
        and executed["floors_mentioned"] == requested["floors"]
    )

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "requested": requested,
        "executed": executed,
        "observed": observed,
        "instruction_carried_the_request": instruction_carried,
        "instruction_is_not_evidence_of_result": True,
        "floor_status": floor_status,
        "floor_reason": floor_reason,
        "building_type_status": type_status,
        "building_type_reason": type_reason,
        "design_accepted": (
            floor_status in (FLOOR_VERIFIED, FLOOR_NOT_REQUESTED)
            and type_status in (TYPE_VERIFIED, TYPE_NOT_REQUESTED)
        ),
    }


# ==========================================================
# 5. OBSERVING A PRODUCED IMAGE (EXISTING PROVIDER ONLY)
# ==========================================================

def observe_output(image_path, provider=None):
    """Run the EXISTING facade vision provider over a produced image.

    Returns the mapped contract (which already carries ``visible_floor_count``
    and ``building_type``). If the provider is unavailable or returns nothing
    usable, returns a dict with ``available: False`` so the caller reports
    UNVERIFIED rather than inventing a count.

    This function contains NO image analysis of its own.
    """
    result = {
        "available": False,
        "reason": None,
        "contract": None,
        "provider": None,
        "model": None,
    }

    try:
        from core.vision.facade_reference_vision_provider_v1 import (
            get_facade_provider,
            map_to_contract,
        )
    except Exception as exc:  # noqa: BLE001
        result["reason"] = "provider import failed: %r" % (exc,)
        return result

    try:
        active = provider or get_facade_provider("A")
    except Exception as exc:  # noqa: BLE001
        result["reason"] = "provider unavailable: %r" % (exc,)
        return result

    try:
        if hasattr(active, "is_available") and not active.is_available():
            result["reason"] = "provider reports itself unavailable"
            return result

        raw = active.analyze({"path": image_path, "filename": image_path})

        if not isinstance(raw, dict):
            result["reason"] = "provider returned no observation"
            return result

        parsed = raw.get("parsed") if isinstance(raw.get("parsed"), dict) else raw

        contract = map_to_contract(parsed)

        result.update({
            "available": True,
            "contract": contract,
            "provider": getattr(active, "name", None) or active.__class__.__name__,
            "model": getattr(active, "model", None),
        })
        return result

    except Exception as exc:  # noqa: BLE001
        result["reason"] = "provider call failed: %r" % (exc,)
        return result
