"""Conservative corroboration against independently produced local evidence.

No detector runs here and no thresholds are retuned. Absence from a detector is
not evidence of absence. Unsupported properties stay unverified; confidence is
never a verification input. Local contracts retain their independent semantics.
"""

import copy
import math
import re

from core.vision.observation_normalizer_v1 import iter_claims, parse_normalization
from core.vision.local_plan_elements_v1 import grounded_plan_elements
from core.vision.local_plan_symbols_v1 import grounded_plan_items


STATES = ("PROVIDER_CANDIDATE", "CONFIRMED", "CONTRADICTED", "UNVERIFIED", "AMBIGUOUS")
POLARITIES = ("PRESENT", "ABSENT", "UNKNOWN")
VERIFIER_VERSION = "local-candidate-verification-v1"
_KINDS = {
    "openings.doors": {"door"}, "openings.windows": {"window"},
    "openings.other_openings": {"opening"}, "vertical_circulation": {"stair"},
    "furniture": {"bed", "sofa", "seating", "chair", "dining_surface", "storage_cabinet"},
    "fixtures": {"kitchen_counter", "kitchen_sink_arrangement", "sanitary_fixture"},
    "structural_elements": {"column"},
}
_KINDS["observed_elements"] = set().union(*_KINDS.values())
_UNCERTAIN = re.compile(r"\b(maybe|perhaps|possible|possibly|probable|probably|unclear|ambiguous)\b|شاید|احتمال|نامشخص", re.I)
_NEGATIVE = re.compile(r"\b(no|not|without|absent|cannot|can't)\b|نیست|بدون|ندارد", re.I)
_UNKNOWN = re.compile(r"\b(unknown|undetermined|unreadable|uncertain)\b|نامعلوم|ناخوانا", re.I)

# ----------------------------------------------------------
# MIXED_POLARITY_ARCHITECTURAL_CLAIM_SAFETY_V1
#
# MEASURED DEFECT (facade B):
#
#   "one central rectangular doorway, open (no door leaf visible),
#    with a stone surround"
#
# The doorway is PRESENT; its door LEAF is not visible. The old rule tested the
# whole string for a negation marker, so one parenthetical about a component
# made the entire doorway ABSENT and the chat reply listed it as an absence.
#
# A negation that qualifies a SUBORDINATE COMPONENT does not negate the
# claim's own architectural subject. Two bounded modifier constructions are
# recognised here — both attach to the head noun, neither introduces a new
# subject:
#
#   * a parenthetical qualifier : "doorway, open (no door leaf visible)"
#   * a with/without phrase     : "doorway without a fitted door leaf"
#
# A COORDINATE clause can introduce a second subject ("A window is visible, but
# no door is visible"), so it ends the primary clause. "and" is deliberately
# absent from that set: it joins nouns inside one subject far more often than
# it joins clauses, and widening without evidence is not permitted here.
# ----------------------------------------------------------

_PARENTHETICAL = re.compile(r"\([^)]*\)")

_SUBORDINATE_MODIFIER = re.compile(r"\b(?:with|without)\b[^,.;]*", re.I)

_CLAUSE_BREAK = re.compile(r";|\b(?:but|while|whereas)\b", re.I)


def _strip_subordinate_modifiers(value):
    """Drop modifier spans that qualify a component rather than the subject."""

    return _SUBORDINATE_MODIFIER.sub(" ", _PARENTHETICAL.sub(" ", value))


def _negates_the_subject(value, kind):
    """Does a negation marker in `value` attach to the claim's own subject?

    `kind` is the candidate's own structured kind (e.g. "doorway"). When the
    leading clause names that kind, its polarity governs the claim. When it
    does not, the subject sits in a later clause and the claim stays
    conservatively ABSENT — a single-polarity field must never be talked into
    asserting presence it cannot prove.
    """

    if not _NEGATIVE.search(value):

        return False

    if not kind:

        return True

    clause = _CLAUSE_BREAK.split(value, maxsplit=1)[0]

    if not re.search(r"\b" + re.escape(kind), clause, re.I):

        return True

    return bool(_NEGATIVE.search(clause))


def claim_polarity(claim):
    """PRESENT / ABSENT / UNKNOWN for one provider claim.

    VISION_END_TO_END_RETENTION_FIX_V1 — a structured polarity so an ABSENCE
    can participate in verification. It is derived from the claim's OWN
    structured fields and its own quoted text:

      * `count == 0` is an explicit, machine-readable absence;
      * a generic negation marker over the claim's own text or quote is an
        absence (the module already used this marker for the negative path);
      * otherwise a claim that names something is a PRESENT claim;
      * an UNKNOWN-certainty claim, or the `unknowns` category, stays UNKNOWN.

    There is no per-room or per-phrase list anywhere in this rule.
    """

    if not isinstance(claim, dict):
        return "UNKNOWN"
    if claim.get("category") == "unknowns" or claim.get("certainty") == "UNKNOWN":
        return "UNKNOWN"
    if claim.get("count") == 0:
        return "ABSENT"
    text = str(claim.get("text") or "")
    # The ENCLOSING line matters: a claim quoted as "bed" inside the sentence
    # "no bed is present" is an absence. This is the same enclosing-context
    # rule the verifier already used for its negative path.
    context = str(claim.get("source_context") or claim.get("source_quote") or "")
    kind = str(claim.get("kind") or "").strip()

    # MIXED_POLARITY_ARCHITECTURAL_CLAIM_SAFETY_V1 — the negation must attach
    # to THIS claim's subject, not merely appear somewhere in the sentence.
    for value in (
        _strip_subordinate_modifiers(text),
        _strip_subordinate_modifiers(context),
    ):

        if _negates_the_subject(value, kind):

            return "ABSENT"

    return "PRESENT" if text.strip() else "UNKNOWN"


def local_ocr_evidence(local):
    """Carry local OCR without reclassifying lexicon corrections as exact text."""
    if (not isinstance(local, dict) or local.get("provider_independent") is not True
            or local.get("source") != "local_offline_raster"):
        return []
    size = local.get("image_size") or {}
    width, height = size.get("width", 0), size.get("height", 0)
    result = []
    for label in local.get("labels") or []:
        if not isinstance(label, dict):
            continue
        box = label.get("bbox_pixels")
        if (label.get("status") != "grounded_ocr" or label.get("evidence_type") != "local_ocr"
                or not isinstance(label.get("text"), str)
                or not isinstance(box, (tuple, list)) or len(box) != 4
                or not all(type(x) in (int, float) and math.isfinite(x) for x in box)
                or not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height)):
            continue
        result.append({**copy.deepcopy(label), "source": "local_ocr",
                       "exact_transcription": label.get("correction") is None
                       and label.get("raw_ocr") == label["text"]})
    return result


def provider_candidates(normalization, raw_text):
    """Revalidate at the trust boundary, ignoring all provider grounding flags."""
    if normalization.get("status") != "NORMALIZED":
        return []
    import json
    diagnostics = {}
    structured = parse_normalization(json.dumps(normalization["structured"]), raw_text,
                                     diagnostics=diagnostics)
    # Preserve upstream losses, and expose any new loss at this trust boundary.
    normalization["candidate_source_validation"] = diagnostics
    return [{**copy.deepcopy(claim), "candidate_id": "provider_claim_%d" % (i + 1),
             "source_context": _source_context(raw_text, claim["source_quote"]),
             "category": category, "origin": "PROVIDER", "state": "PROVIDER_CANDIDATE",
             "polarity": claim_polarity({**claim, "category": category}),
             "grounded": False, "verification": {"verifier_version": VERIFIER_VERSION}}
            for i, (category, claim) in enumerate(iter_claims(structured))]


def _source_context(raw_text, quote):
    # Do not allow a normalizer to hide a negation/qualifier by quoting only a
    # noun. Include complete enclosing lines for every occurrence of its quote.
    contexts, start = [], 0
    while True:
        index = raw_text.find(quote, start)
        if index < 0:
            break
        left = raw_text.rfind("\n", 0, index) + 1
        right = raw_text.find("\n", index + len(quote))
        contexts.append(raw_text[left:right if right >= 0 else len(raw_text)])
        start = index + len(quote)
    return "\n".join(dict.fromkeys(contexts))


def _numeric_category(text):
    if re.fullmatch(r"\d+\s*:\s*\d+", text):
        return "scale"
    if re.fullmatch(r"[+−-]\d+(?:[.,]\d+)?(?:\s*(?:m|cm|mm|متر))?", text):
        return "level_codes"
    if re.fullmatch(r"\d+(?:[.,]\d+)?(?:\s*(?:m|cm|mm|ft|in|متر|سانتی‌متر))?", text):
        return "dimensions"
    return None


def _decision(claim, elements, symbols, labels):
    category, kind, text = claim["category"], claim["kind"], claim["text"]
    quote, count = claim.get("source_context", claim["source_quote"]), claim["count"]
    if claim["certainty"] == "UNKNOWN" or category == "unknowns" or _UNKNOWN.search(quote):
        return "UNVERIFIED", "unknown_preserved", []
    if claim["certainty"] == "AMBIGUOUS" or _UNCERTAIN.search(quote):
        return "AMBIGUOUS", "observer_ambiguity_preserved", []
    if category == "interpretations":
        return "UNVERIFIED", "interpretation_is_not_observation", []

    eligible = [e for e in elements if e.get("type") == kind and e.get("status") == "visible"]
    eligible += [e for e in symbols if e.get("class") == kind]
    if kind in _KINDS.get(category, set()):
        # VISION_END_TO_END_RETENTION_FIX_V1 — the machine-readable CONTRADICTED
        # form is preserved exactly as before. A prose ABSENCE that is NOT in
        # that form stays UNVERIFIED here; it is surfaced as a CONFLICTING
        # provider/local disagreement by the grounding layer instead, so the
        # disagreement exists without changing a verification verdict.
        absence_text = text.casefold() in {
            "no " + kind.replace("_", " "), "no " + kind.replace("_", " ") + "s",
            "0 " + kind.replace("_", " "), "0 " + kind.replace("_", " ") + "s",
        }
        if count == 0 and absence_text and eligible:
            return "CONTRADICTED", "claimed_absence_conflicts_with_local_presence", eligible
        if _NEGATIVE.search(quote):
            return "UNVERIFIED", "negative_claim_requires_explicit_local_absence", []
        # Local detection does not establish completeness of total counts.
        if count is not None:
            return "UNVERIFIED", "total_count_not_independently_established", []
        # Only atomic type presence is verified, not unseen material/size/role
        # modifiers or a whole phrase just because it mentions a detected type.
        if text.casefold() not in (kind.casefold(), kind.replace("_", " ").casefold()):
            return "UNVERIFIED", "claim_properties_not_verified", []
        if eligible:
            return "CONFIRMED", "independent_local_type_presence", eligible

    if category in ("provider_ocr_candidate", "ocr_exact", "scale", "dimensions", "level_codes"):
        if category in ("scale", "dimensions", "level_codes") and _numeric_category(text) != category:
            return "UNVERIFIED", "numeric_category_mismatch", []
        matches = [label for label in labels if label["exact_transcription"] and label["text"] == text]
        if matches and not _NEGATIVE.search(quote):
            return "CONFIRMED", "verbatim_independent_local_ocr", matches
        if category == "level_codes" and _numeric_category(text) == category:
            matches = [e for e in elements if e.get("type") == "level"
                       and e.get("status") == "visible"
                       and e["attributes"].get("annotation_status") == "grounded_ocr"
                       and e["attributes"].get("annotation", {}).get("raw_text") == text]
            if matches:
                return "CONFIRMED", "verbatim_local_level_annotation", matches
    # Axes require a locally read label tied to the axis, not just grid geometry.
    # Orientation requires a verified indicator, not horizontal/vertical lines.
    return "UNVERIFIED", "no_applicable_independent_corroboration", []


def verify_candidates(candidates, local):
    elements, symbols = grounded_plan_elements(local), grounded_plan_items(local)
    labels = local_ocr_evidence(local)
    verified = []
    for original in candidates:
        claim = copy.deepcopy(original)
        state, reason, evidence = _decision(claim, elements, symbols, labels)
        claim["polarity"] = claim.get("polarity") or claim_polarity(claim)
        claim.update(state=state, grounded=state == "CONFIRMED")
        claim["verification"] = {
            "verifier_version": VERIFIER_VERSION, "initial_state": "PROVIDER_CANDIDATE",
            "reason": reason, "local_evidence": copy.deepcopy(evidence),
        }
        verified.append(claim)
    return verified
