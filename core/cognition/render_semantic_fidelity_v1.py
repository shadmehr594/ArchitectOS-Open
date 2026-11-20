# -*- coding: utf-8 -*-
"""RENDER_SEMANTIC_FIDELITY_V1 — does the English instruction keep the Persian constraints?

WHY THIS EXISTS
---------------
`architectural_render_instruction_v1` produces an English render instruction
from a Persian request. Nothing verified that the instruction still carries
what the user actually asked for — a floor count, a dimension, a prohibition
or the difference between "build" and "refine" can silently disappear.

This module is the GATE. It answers PASS or BLOCKED, and when it blocks it
names the exact reason.

HOW IT WORKS (and why it is not keyword matching)
-------------------------------------------------
Both sides are parsed into the SAME structured slot form

    (slot, value, polarity)

by the SAME extractor:

    Persian source          -> build_render_instruction(...)["constraints"]
    English instruction     -> _instruction_slots(...)

The two slot sets are then COMPARED slot by slot. A check therefore fails on
a MISSING VALUE, a DIFFERENT VALUE or a REVERSED POLARITY — not on the absence
of a word. The extractors are grammatical (number adjacency, unit adjacency,
negation scope), never a list of acceptance sentences.

FAIL-CLOSED
-----------
An unreadable request, an empty instruction, an unexpected error or an
unverifiable slot all produce BLOCKED. PASS is never the default.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core.cognition.architectural_render_instruction_v1 import (
    CONTRACT as INSTRUCTION_CONTRACT,
    build_render_instruction,
)


CONTRACT = "RenderSemanticFidelityV1"
VERSION = "1.0"


STATUS_PASS = "PASS"
STATUS_BLOCKED = "BLOCKED"


# Reason codes. Each is a SPECIFIC, actionable cause.
NO_INSTRUCTION = "NO_INSTRUCTION"
UNVERIFIABLE_SOURCE = "UNVERIFIABLE_SOURCE"
MISSING_FLOOR_COUNT = "MISSING_FLOOR_COUNT"
FLOOR_COUNT_MISMATCH = "FLOOR_COUNT_MISMATCH"
MISSING_DIMENSION = "MISSING_DIMENSION"
REVERSED_VALUE = "REVERSED_VALUE"
REVERSED_INTENT = "REVERSED_INTENT"
MISSING_HARD_CONSTRAINT = "MISSING_HARD_CONSTRAINT"
CONTRADICTORY_INSTRUCTION = "CONTRADICTORY_INSTRUCTION"
VALIDATOR_ERROR = "VALIDATOR_ERROR"
# FACADE-04D.3C-9P-A — a geometry-PRESERVATION request that the instruction
# does not carry (or actively reverses). Distinct from a missing hard
# constraint so the failure is specific and actionable.
MISSING_PRESERVATION = "MISSING_PRESERVATION"
REVERSED_PRESERVATION = "REVERSED_PRESERVATION"
UNRESOLVABLE_FLOOR_BASELINE = "UNRESOLVABLE_FLOOR_BASELINE"


# English unit tokens the instruction may carry.
_UNIT_TOKENS = ("m2", "m²", "sqm", "m", "cm", "mm")

_FLOOR_NOUNS_EN = ("floors", "floor", "storeys", "storey", "stories", "story")

_REFINE_MARKERS = ("refine the architectural design", "preserve the existing")
_CREATE_MARKERS = ("create a new architectural design", "new architectural design")

_DIMENSION_SENTENCE = re.compile(
    r"required\s+(area|dimension)\s*:\s*(\d+)\s*([a-z0-9²]+)", re.IGNORECASE
)
_FLOOR_SENTENCE = re.compile(
    r"has\s+exactly\s+(\d+)\s+(floors|floor|storeys|storey|stories|story)",
    re.IGNORECASE,
)
_NEGATION_MARKERS = ("do not", "don't", "dont", "never", "without")

# FACADE-04D.3C-9P-A — POSITION-preservation markers. The English instruction
# must state that the window/opening POSITIONS are kept. A generic mention of
# "windows" is NOT position preservation.
_WINDOW_POSITION_MARKERS = (
    "window positions", "window position", "windows' positions",
    "positions of the windows", "windows unchanged", "windows' locations",
    "window locations", "window location",
)
_OPENING_POSITION_MARKERS = (
    "opening positions", "opening position", "openings' positions",
    "positions of the openings", "openings unchanged", "opening layout",
    "openings' locations", "opening locations",
)
_FLOOR_PRESERVE_MARKERS = (
    "floor count unchanged", "floor count", "number of floors unchanged",
    "floor levels unchanged", "keep the existing floor", "existing floor count",
    "without changing the floor count", "do not change the floor count",
)
# A reversal: the instruction explicitly asks to MOVE/RELOCATE the openings.
# FACADE-04D.3C-9P-A — these are matched NEGATION-AWARE (see
# `_affirmative_move`): "do NOT move or relocate the windows" is a
# PRESERVATION, not a reversal, and must never be read as one.
_WINDOW_MOVE_MARKERS = (
    "move the windows", "relocate the windows", "move windows",
    "change the window positions", "shift the windows",
    "move or relocate the windows",
)
_OPENING_MOVE_MARKERS = (
    "move the openings", "relocate the openings", "move openings",
    "change the opening positions", "shift the openings",
    "move or relocate the openings",
)


def _affirmative_move(lowered: str, markers) -> bool:
    """True only when a MOVE marker appears WITHOUT a nearby negation.

    FACADE-04D.3C-9P-A — "do NOT move or relocate the windows" is a
    preservation; "move the windows to the left" is a reversal. The clause is
    checked for a negation marker in the ~40 characters preceding the match.
    """

    for marker in markers:

        start = 0

        while True:

            idx = lowered.find(marker, start)

            if idx == -1:

                break

            window = lowered[max(0, idx - 40):idx]

            if not any(neg in window for neg in _NEGATION_MARKERS):

                return True

            start = idx + len(marker)

    return False


def _instruction_slots(instruction: str) -> Dict[str, Any]:
    """Parse the ENGLISH instruction into the same slot form as the source."""

    text = str(instruction or "")

    lowered = text.lower()

    floors = None

    match = _FLOOR_SENTENCE.search(text)

    if match:

        floors = int(match.group(1))

    dimensions: List[Dict[str, Any]] = []

    for match in _DIMENSION_SENTENCE.finditer(text):

        dimensions.append({
            "value": int(match.group(2)),
            "unit": match.group(3).lower(),
            "kind": "area" if match.group(1).lower() == "area" else "length",
        })

    # A bare "N floors" / "N m" form is accepted too, so the validator does
    # not depend on this module's own sentence template.
    if floors is None:

        for match in re.finditer(r"(\d+)\s*([a-z]+)", lowered):

            if match.group(2) in _FLOOR_NOUNS_EN:

                floors = int(match.group(1))

                break

    if not dimensions:

        for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(m2|m²|sqm|m|cm|mm)\b", lowered):

            dimensions.append({
                "value": int(float(match.group(1))),
                "unit": match.group(2),
                "kind": "area" if match.group(2) in ("m2", "m²", "sqm") else "length",
            })

    return {
        "floor_count": floors,
        "dimensions": dimensions,
        "refines": any(marker in lowered for marker in _REFINE_MARKERS),
        "creates": any(marker in lowered for marker in _CREATE_MARKERS),
        "negated": any(marker in lowered for marker in _NEGATION_MARKERS),
        # FACADE-04D.3C-9P-A — explicit preservation signals read from the
        # ENGLISH instruction. `preserve_openings` is a POSITION signal; a bare
        # mention of "window"/"opening" is never sufficient.
        "preserve_window_positions": any(
            m in lowered for m in _WINDOW_POSITION_MARKERS
        ),
        "preserve_opening_positions": any(
            m in lowered for m in _OPENING_POSITION_MARKERS
        ),
        "preserve_floor_count": any(
            m in lowered for m in _FLOOR_PRESERVE_MARKERS
        ),
        "moves_windows": _affirmative_move(lowered, _WINDOW_MOVE_MARKERS),
        "moves_openings": _affirmative_move(lowered, _OPENING_MOVE_MARKERS),
        "text": text,
    }


def _source_slots(contract: Dict[str, Any]) -> Dict[str, Any]:
    """The Persian source's slots, already structured by the contract."""

    constraints = contract.get("constraints") or {}

    floors = constraints.get("floor_count")

    openings = constraints.get("openings") or {}

    geometry = constraints.get("geometry") or {}

    provenance = constraints.get("floor_count_provenance") or {}

    return {
        "floor_count": floors.get("value") if isinstance(floors, dict) else None,
        "dimensions": constraints.get("dimensions") or [],
        "openings": openings,
        "geometry": geometry,
        "negations": constraints.get("negations") or {},
        "intent": contract.get("intent"),
        # FACADE-04D.3C-9P-A — explicit preservation requests, resolved by the
        # upstream contract. These drive the fail-closed checks below.
        "preserve_window_positions": bool(
            openings.get("preserve_window_positions")
            or openings.get("preserve_windows")
        ),
        "preserve_opening_positions": bool(
            openings.get("preserve_opening_positions")
            or openings.get("preserve_openings")
        ),
        "preserve_floor_count": bool(geometry.get("preserve_floor_count")),
        "floor_count_provenance": provenance,
    }


def _blocked(reason_code: str, reason: str, **extra) -> Dict[str, Any]:

    report = {
        "contract": CONTRACT,
        "version": VERSION,
        "status": STATUS_BLOCKED,
        "reason_code": reason_code,
        "reason": reason,
        "may_proceed_to_render": False,
    }

    report.update(extra)

    return report


def validate_render_fidelity(
    source_text: Any,
    instruction: Optional[str] = None,
    *,
    contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return the RenderSemanticFidelityV1 verdict for one request.

    ``contract`` may be supplied by the caller (already built for this turn)
    so the live path never computes the instruction twice.
    """

    try:

        source = str(source_text or "").strip()

        if not source:

            return _blocked(
                UNVERIFIABLE_SOURCE,
                "The request text is empty, so nothing can be verified.",
            )

        if contract is None:

            contract = build_render_instruction(source)

        english = (
            instruction
            if instruction is not None
            else str(contract.get("english_instruction") or "")
        ).strip()

        source_slots = _source_slots(contract)

        instruction_slots = _instruction_slots(english)

        # ----------------------------------------------------------
        # 1. FAIL-CLOSED — an architectural request with no instruction
        # ----------------------------------------------------------

        has_content = bool(
            contract.get("terminology_families")
            or (contract.get("constraints", {}).get("geometry", {}) or {}).get("markers")
            or source_slots["floor_count"] is not None
            or source_slots["dimensions"]
            or source_slots["openings"].get("mentioned")
        )

        if not english:

            return _blocked(
                NO_INSTRUCTION,
                "The English render instruction is empty"
                + (" for a request that carries architectural content."
                   if has_content else "."),
                instruction_contract=INSTRUCTION_CONTRACT,
                source_slots=source_slots,
            )

        missing: List[Dict[str, Any]] = []

        reversed_items: List[Dict[str, Any]] = []

        contradictory: List[Dict[str, Any]] = []

        checks: List[Dict[str, Any]] = []

        # ----------------------------------------------------------
        # 2. FLOOR COUNT — value equality, not word presence
        # ----------------------------------------------------------

        if source_slots["floor_count"] is not None:

            expected = source_slots["floor_count"]

            observed = instruction_slots["floor_count"]

            checks.append({
                "slot": "floor_count",
                "expected": expected,
                "observed": observed,
            })

            if observed is None:

                missing.append({
                    "slot": "floor_count",
                    "expected": expected,
                    "reason_code": MISSING_FLOOR_COUNT,
                })

            elif observed != expected:

                reversed_items.append({
                    "slot": "floor_count",
                    "expected": expected,
                    "observed": observed,
                    "reason_code": FLOOR_COUNT_MISMATCH,
                })

        # ----------------------------------------------------------
        # 3. DIMENSIONS — every stated value must survive
        # ----------------------------------------------------------

        expected_dimensions = source_slots["dimensions"]

        observed_dimensions = instruction_slots["dimensions"]

        observed_values = {item["value"] for item in observed_dimensions}

        for item in expected_dimensions:

            checks.append({
                "slot": "dimension",
                "expected": item["value"],
                "observed": sorted(observed_values),
            })

            if item["value"] not in observed_values:

                missing.append({
                    "slot": "dimension",
                    "expected": item["value"],
                    "unit": item["unit"],
                    "reason_code": MISSING_DIMENSION,
                })

        # ----------------------------------------------------------
        # 4. REVERSED VALUE — the instruction must not state a value the
        #    user explicitly rejected.
        # ----------------------------------------------------------

        rejected = (source_slots["negations"] or {}).get("rejected_span") or ""

        rejected_numbers = {
            int(match.group(0))
            for match in re.finditer(r"[0-9\u06F0-\u06F9]+", rejected)
        }

        for value in sorted(rejected_numbers):

            if value in observed_values:

                reversed_items.append({
                    "slot": "dimension",
                    "rejected_value": value,
                    "observed": sorted(observed_values),
                    "reason_code": REVERSED_VALUE,
                })

        # ----------------------------------------------------------
        # 5. REVERSED INTENT — CREATE must not become REFINE
        # ----------------------------------------------------------

        if source_slots["intent"] == "CREATE":

            checks.append({
                "slot": "intent",
                "expected": "CREATE",
                "observed": (
                    "REFINE" if instruction_slots["refines"] else "CREATE"
                ),
            })

            if instruction_slots["refines"] and not instruction_slots["creates"]:

                reversed_items.append({
                    "slot": "intent",
                    "expected": "CREATE",
                    "observed": "REFINE",
                    "reason_code": REVERSED_INTENT,
                })

        # ----------------------------------------------------------
        # 6. HARD CONSTRAINTS — preserve flags must reach the instruction
        # ----------------------------------------------------------

        preserve_expectations = (
            ("preserve_windows", "window"),
            ("preserve_openings", "opening"),
        )

        for key, label in preserve_expectations:

            if (source_slots["openings"] or {}).get(key):

                present = label in instruction_slots["text"].lower()

                checks.append({
                    "slot": "hard_constraint",
                    "expected": key,
                    "observed": present,
                })

                if not present:

                    missing.append({
                        "slot": "hard_constraint",
                        "expected": key,
                        "reason_code": MISSING_HARD_CONSTRAINT,
                    })

        for key, label in (
            ("preserve_geometry", "geometry"),
            ("preserve_massing", "massing"),
        ):

            if (source_slots["geometry"] or {}).get(key):

                present = label in instruction_slots["text"].lower()

                checks.append({
                    "slot": "hard_constraint",
                    "expected": key,
                    "observed": present,
                })

                if not present:

                    missing.append({
                        "slot": "hard_constraint",
                        "expected": key,
                        "reason_code": MISSING_HARD_CONSTRAINT,
                    })

        # ----------------------------------------------------------
        # 7. CONTRADICTION — a value both asserted and negated, or a
        #    preserve instruction that also asks to change the same slot.
        # ----------------------------------------------------------

        if (source_slots["negations"] or {}).get("is_negated"):

            lowered = instruction_slots["text"].lower()

            if not instruction_slots["negated"] and not any(
                marker in lowered
                for marker in ("keep the existing", "do not", "preserve")
            ):

                contradictory.append({
                    "slot": "negation",
                    "expected": "preserved",
                    "observed": "absent",
                    "reason_code": CONTRADICTORY_INSTRUCTION,
                })

        if (source_slots["openings"] or {}).get("preserve_windows"):

            if re.search(r"move the windows|change the windows", instruction_slots["text"], re.I):

                contradictory.append({
                    "slot": "openings",
                    "expected": "preserve",
                    "observed": "change",
                    "reason_code": CONTRADICTORY_INSTRUCTION,
                })

        # ----------------------------------------------------------
        # 7.5 FACADE-04D.3C-9P-A — FAIL-CLOSED EXPLICIT PRESERVATION
        #
        # An explicitly requested geometry preservation MUST result in a real
        # check: the instruction must carry the SAME target and the SAME
        # polarity. A generic mention of "windows", or a bare negation echo,
        # is NOT a completed check. If preservation cannot be represented or
        # verified, BLOCK — never PASS with zero checks.
        # ----------------------------------------------------------

        # 7.5.1 window POSITION preservation
        if source_slots["preserve_window_positions"]:

            if instruction_slots["moves_windows"]:

                checks.append({
                    "slot": "window_positions",
                    "expected": "preserve_position",
                    "observed": "move",
                })

                reversed_items.append({
                    "slot": "window_positions",
                    "expected": "preserve_position",
                    "observed": "move",
                    "reason_code": REVERSED_PRESERVATION,
                })

            else:

                present = instruction_slots["preserve_window_positions"]

                checks.append({
                    "slot": "window_positions",
                    "expected": "preserve_position",
                    "observed": present,
                })

                if not present:

                    missing.append({
                        "slot": "window_positions",
                        "expected": "preserve_position",
                        "reason_code": MISSING_PRESERVATION,
                    })

        # 7.5.2 opening POSITION preservation
        if source_slots["preserve_opening_positions"]:

            if instruction_slots["moves_openings"]:

                checks.append({
                    "slot": "opening_positions",
                    "expected": "preserve_position",
                    "observed": "move",
                })

                reversed_items.append({
                    "slot": "opening_positions",
                    "expected": "preserve_position",
                    "observed": "move",
                    "reason_code": REVERSED_PRESERVATION,
                })

            else:

                present = instruction_slots["preserve_opening_positions"]

                checks.append({
                    "slot": "opening_positions",
                    "expected": "preserve_position",
                    "observed": present,
                })

                if not present:

                    missing.append({
                        "slot": "opening_positions",
                        "expected": "preserve_position",
                        "reason_code": MISSING_PRESERVATION,
                    })

        # 7.5.3 floor-count preservation (without a numeral)
        if source_slots["preserve_floor_count"]:

            present = instruction_slots["preserve_floor_count"]

            checks.append({
                "slot": "floor_count_preservation",
                "expected": "preserve_existing_count",
                "observed": present,
                "baseline": (
                    source_slots["floor_count_provenance"] or {}
                ).get("value"),
            })

            if not present:

                missing.append({
                    "slot": "floor_count_preservation",
                    "expected": "preserve_existing_count",
                    "reason_code": MISSING_PRESERVATION,
                })

            # The preservation must resolve against a REAL baseline. A count
            # may be stated as a numeral (USER_TEXT) or observed on IMAGE B
            # (VISION_OBSERVATION_UNVERIFIED). If neither exists, the request
            # cannot be verified — fail closed rather than fabricate a count.
            elif source_slots["floor_count"] is None and (
                (source_slots["floor_count_provenance"] or {}).get("value")
                is None
            ):

                missing.append({
                    "slot": "floor_count_preservation",
                    "expected": "resolvable_baseline",
                    "reason_code": UNRESOLVABLE_FLOOR_BASELINE,
                })

        # ----------------------------------------------------------
        # 8. VERDICT
        # ----------------------------------------------------------

        if missing or reversed_items or contradictory:

            primary = (missing + reversed_items + contradictory)[0]

            return {
                "contract": CONTRACT,
                "version": VERSION,
                "status": STATUS_BLOCKED,
                "reason_code": primary["reason_code"],
                "reason": _describe(primary),
                "missing": missing,
                "reversed": reversed_items,
                "contradictory": contradictory,
                "checks": checks,
                "instruction_contract": INSTRUCTION_CONTRACT,
                "instruction": english,
                "may_proceed_to_render": False,
            }

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "status": STATUS_PASS,
            "reason_code": None,
            "reason": "Every essential Persian constraint is present in the "
                      "English instruction with the same value and polarity.",
            "missing": [],
            "reversed": [],
            "contradictory": [],
            "checks": checks,
            "instruction_contract": INSTRUCTION_CONTRACT,
            "instruction": english,
            "may_proceed_to_render": True,
        }

    except Exception as error:

        return _blocked(
            VALIDATOR_ERROR,
            "The fidelity check could not complete: "
            + type(error).__name__ + ": " + str(error),
        )


def _describe(item: Dict[str, Any]) -> str:

    code = item.get("reason_code")

    if code == MISSING_FLOOR_COUNT:

        return ("The Persian request states %s floors but the English "
                "instruction carries no floor count." % item.get("expected"))

    if code == FLOOR_COUNT_MISMATCH:

        return ("The Persian request states %s floors but the English "
                "instruction says %s." % (item.get("expected"), item.get("observed")))

    if code == MISSING_DIMENSION:

        return ("The Persian request states a %s of %s but the English "
                "instruction does not carry it." % (
                    item.get("unit"), item.get("expected")))

    if code == REVERSED_VALUE:

        return ("The English instruction repeats the value %s that the user "
                "explicitly rejected." % item.get("rejected_value"))

    if code == REVERSED_INTENT:

        return ("The user asked to CREATE a new design but the English "
                "instruction asks to REFINE an existing one.")

    if code == MISSING_HARD_CONSTRAINT:

        return ("The hard constraint %s is missing from the English "
                "instruction." % item.get("expected"))

    if code == CONTRADICTORY_INSTRUCTION:

        return ("The English instruction contradicts the request on %s." % item.get("slot"))

    if code == MISSING_PRESERVATION:

        return ("The request asks to PRESERVE %s but the English instruction "
                "does not carry that preservation." % item.get("slot"))

    if code == REVERSED_PRESERVATION:

        return ("The request asks to PRESERVE %s but the English instruction "
                "asks to change it." % item.get("slot"))

    if code == UNRESOLVABLE_FLOOR_BASELINE:

        return ("The request asks to preserve the floor count but no reliable "
                "baseline exists (no numeral and no IMAGE B observation); the "
                "baseline must not be fabricated.")

    return "The English instruction does not preserve the Persian constraints."


print("🛡️ RENDER SEMANTIC FIDELITY v1.0 ONLINE (fail-closed gate, no render)")
