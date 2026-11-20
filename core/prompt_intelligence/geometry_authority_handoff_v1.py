# ==========================================================
# ARCHITECTOS — GEOMETRY AUTHORITY HANDOFF V1.1
#
# Resolves precedence between data the system already produces:
#   architectural_intent.preserve_geometry / preserve_constraints
#   architectural_intent.normalized_prompt          (the user's own words)
#   image_edit_delta_v1 edit_class                  (structured appearance signal)
#   resolved_facade_knowledge                       (style suggestions)
#
# PRECEDENCE
#   1. explicit user-approved geometric operation (structured: verb + target)
#   2. explicit user preservation statement
#   3. default preservation (preserve_geometry + preserve_constraints)
#   4. architectural knowledge as compatible guidance
#   5. optional model detail — no independent authority
#
# V1.1 corrections
#   * appearance edit classes (colour/material/lighting/time) never authorise
#     geometry, whatever nouns they contain
#   * negation and preservation are evaluated PER CLAUSE, so a preserve
#     statement about windows cannot cancel an authorisation about the roof
#   * an explicit preservation statement outranks an explicit operation on the
#     same domain -> conflict; default preservation does not
#   * "add" and "redesign" are treated identically: both are explicit
#     operations and both are evaluated against explicitly fixed domains
#   * Persian is parsed with its own lexicon; unparseable requests are
#     UNRESOLVED and never silently granted authority
#
# Pure functions. No I/O, no GPU, no model, no ontology.
# ==========================================================

import re
from copy import deepcopy

from core.architecture.knowledge.human_learning_ledger_v1 import (
    CHANGE_MARKERS as _RULE_CHANGE_MARKERS,
    DOMAIN_TOKENS as _RULE_DOMAIN_TOKENS,
)
from core.prompt_intelligence.architectural_preservation_intent_v1 import (
    build_architectural_preservation_intent_v1,
)

CONTRACT = "GeometryAuthorityHandoffV1"
VERSION = "1.1"

STATUS_OK = "ok"
STATUS_SUGGESTIONS_FILTERED = "style_suggestions_filtered"
STATUS_AUTHORIZED = "explicit_geometric_change_authorized"
STATUS_CONFLICT = "explicit_operation_conflicts_with_fixed_geometry"
STATUS_UNRESOLVED = "geometric_authorization_unresolved"

DISCLOSURE_STRICT_PRESERVATION = (
    "strict_preservation_guarantee_unsupported: the selected workflow conditions "
    "geometry probabilistically; it cannot guarantee pixel-level preservation"
)

#: Edit classes that describe appearance only. These NEVER authorise geometry.
#:
#: HAIKU_ARCHITECTURAL_KNOWLEDGE_FIDELITY_V2 — `style_change` was added when
#: the delta compiler gained the class (KNOWLEDGE_RUNTIME_CONNECTION_V2) but
#: this set was never updated, so a style request was analysed as a GEOMETRIC
#: operation. Measured consequence: "Redesign the facade … in a neoclassical
#: style" (the ordinary way to ask for a restyle) authorised an `opening`
#: change because "architectural" contains "arch", which replaced the whole
#: geometry-preservation block with "redesign any element outside the
#: authorised scope". A style change is an appearance edit of the existing
#: surfaces and never authorises geometry on its own.
APPEARANCE_EDIT_CLASSES = frozenset({
    "material_change", "color_change", "lighting_change", "time_of_day_change",
    "finish_change", "texture_change", "style_change",
})

DOMAIN_ROOF = "roof"
DOMAIN_OPENING = "opening"
DOMAIN_MASSING = "massing"
DOMAIN_CIRCULATION = "circulation"
DOMAIN_CAMERA = "camera"

# ----------------------------------------------------------
# English lexicon
# ----------------------------------------------------------

_EN_DOMAIN_MARKERS = (
    (DOMAIN_ROOF, ("pediment", "gable", "dormer", "parapet", "roofline", "roof",
                   "eave", "cornice", "dentil", "tympanum", "spire", "turret", "shape")),
    (DOMAIN_OPENING, ("opening", "window", "door", "arch", "frame", "glazing",
                      "portal", "skylight", "gateway")),
    (DOMAIN_MASSING, ("massing", "volume", "silhouette", "proportion", "storey", "storeys",
                      "floor", "bay", "setback", "overhang", "symmetry", "symmetr",
                      "colonnade", "portico", "pilaster", "column", "quoin",
                      "string course", "entablature", "frieze", "capital",
                      "classical order")),
    (DOMAIN_CIRCULATION, ("stair", "staircase", "terrace", "balcony", "balustrade",
                          "landing", "railing", "railings", "handrail", "guardrail",
                          "banister", "parapet rail")),
    (DOMAIN_CAMERA, ("camera", "perspective", "composition")),
)

_EN_VERBS = (
    "redesign", "rebuild", "replace", "reshape", "restructure", "reconfigure",
    "remove", "demolish", "extend", "raise", "lower", "change", "modify",
    "alter", "renovate", "add", "introduce", "install", "place", "create",
    "incorporate", "include", "append", "attach", "put",
)

_EN_APPEARANCE_OBJECTS = (
    "colour", "color", "paint", "material", "finish", "texture", "cladding",
    "tone", "palette", "lighting", "light", "veneer", "surface", "render",
    "plaster", "glaze", "tile", "stain",
)

_EN_PRESERVE_PATTERNS = (
    r"\b(?:keep|preserve|maintain|retain|leave)\b[^,.;]{0,40}?\b(?:unchanged|fixed|intact|as is|as-is|the same)\b",
    r"\bwithout\s+(?:changing|modifying|altering|touching|moving)\b",
    r"\b(?:remain|stay|remains|stays)\s+(?:unchanged|fixed|intact)\b",
    r"\bdo\s+not\s+(?:change|modify|alter|touch|move|redesign|replace|add|remove)\b",
    r"\bno\s+changes?\s+to\b",
    # bare "preserve its original shape" — a preserve verb attached to an
    # element is a preservation statement even without "unchanged"
    r"\b(?:keep|preserve|maintain|retain)\b",
)

# ----------------------------------------------------------
# Persian lexicon (script-detected, clause-scoped)
# ----------------------------------------------------------

_FA_DOMAIN_MARKERS = (
    (DOMAIN_ROOF, ("سقف", "بام", "شیروانی", "سنتوری", "پدیمان", "قرنیز", "فرم")),
    (DOMAIN_OPENING, ("پنجره", "در", "بازشو", "قوس", "چارچوب")),
    (DOMAIN_MASSING, ("حجم", "ارتفاع", "طبقه", "تناسب", "نما", "ستون", "پیلستر")),
    (DOMAIN_CIRCULATION, ("پله", "تراس", "بالکن", "نرده")),
    (DOMAIN_CAMERA, ("دوربین", "پرسپکتیو", "کادر")),
)

_FA_VERBS = ("بازطراحی", "طراحی مجدد", "اضافه", "تغییر", "حذف", "جایگزین", "بساز", "بده")

_FA_APPEARANCE_OBJECTS = ("رنگ", "مصالح", "بافت", "پوشش", "نور", "سطح", "متریال")

_FA_PRESERVE_PATTERNS = (
    r"ثابت\s*بمان(?:د|ند|ه)",
    r"بدون\s*تغییر",
    r"حفظ",
    r"دست\s*نزن",
    # R4_POSITIVE_INSTRUCTION_CONTRACT_V1 — the negative-imperative family.
    #
    # This table matched only the 3rd-person singular «تغییر نکند». The form a
    # user actually writes when listing several protected elements is the
    # plural «تغییر نکنند», which matched nothing, so the clause fell through
    # to `_has_verb` (which DOES contain «تغییر») and was recorded as an
    # OPERATION.
    #
    # Measured consequence on the accepted R4 request: «حجم ساختمان تغییر
    # نکنند» authorized a MASSING change, `massing` was lifted out of
    # `fixed_domains`, `authorized_domains` became ["massing"], and
    # `preserve_lists()` consequently returned an EMPTY preserve list with the
    # single prohibition "redesign any element outside the authorised scope".
    # The user's explicit "must not change" therefore reached the sampler as
    # permission to change it, and the geometry contract disappeared from the
    # prompt.
    #
    # A negative constraint is never an authorization. The patterns below cover
    # the whole imperative family (singular, plural, 2nd person, subjunctive
    # and the passive forms) without matching any positive operation.
    r"تغییر\s*ن(?:کن|کند|کنند|کنه|کنید|کنیم|کنن|خورد|خورند|خوره|"
    r"شود|شوند|بشود|بده|دهد|دهند)",
    r"تغییر\s*نده",
    r"عوض\s*ن(?:کن|کند|کنند|کنه|کنید|شود|شوند|بشود)",
    r"جابه\s*جا\s*ن(?:کن|شود|شوند|کند|کنند)",
)

_CLAUSE_SPLIT = re.compile(
    r"[.;!?،؛,]|\band\b|\bbut\b|\bthen\b|\bwhile\b|\bwhilst\b|\bwhereas\b|\bو\b",
    re.IGNORECASE,
)
_PERSIAN_SCRIPT = re.compile(r"[\u0600-\u06FF]")
_LATIN_SCRIPT = re.compile(r"[A-Za-z]")

#: Function words and architectural vocabulary used to decide whether a
#: Latin-script request is actually English. A German sentence contains none
#: of these, so it is reported as unresolved rather than silently treated as
#: an English request that happens to match nothing.
_EN_RECOGNITION = frozenset({
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "with", "without",
    "keep", "keeps", "change", "add", "preserve", "do", "not", "only", "its",
    "this", "that", "make", "apply", "use", "should", "must", "remain",
    "building", "facade", "wall", "walls", "roof", "window", "windows",
    "door", "doors", "stone", "material", "materials", "colour", "color",
    "light", "lighting", "surface", "texture", "finish", "cladding", "floor",
    "floors", "geometry", "style", "exact", "original", "travertine",
    "concrete", "brick", "glass", "metal", "wood", "paint", "site",
    "redesign", "replace", "remove", "renovate", "modify", "alter",
})


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if str(v).strip()]
    return [str(value)]


def detect_language(text):
    text = str(text or "")
    if _PERSIAN_SCRIPT.search(text):
        return "fa"
    if not _LATIN_SCRIPT.search(text):
        return "unknown"

    words = re.findall(r"[a-z]+", text.lower())

    # Short fragments ("hello", "same tower, night", "travertine cladding")
    # are not language evidence. Only a sentence-length Latin-script string
    # that shares nothing with the recognised vocabulary is treated as a
    # language we cannot parse — otherwise ordinary English edits would be
    # refused for the wrong reason.
    if len(words) >= 6 and not any(w in _EN_RECOGNITION for w in words):
        return "unknown"

    return "en"


#: I2I_CAPABILITY_GATE_REPAIR_V1 — a comma/"and" fragment that CONTINUES a
#: list already opened by a prohibition.
_NEGATED_LIST_CONTINUATION = re.compile(r"^(?:or|and|nor)\b", re.IGNORECASE)

_RESTRUCTURE_VERB_START = re.compile(
    r"^(?:add|adding|introduce|introducing|remove|removing|delete|deleting"
    r"|change|changing|modify|modifying)\b",
    re.IGNORECASE,
)


def _continues_negated_list(previous, part):
    """True when `part` continues a list opened by a prohibition."""

    low = " " + previous.lower() + " "

    if not any(marker in low for marker in _PROHIBITION_MARKERS):

        return False

    return bool(
        _NEGATED_LIST_CONTINUATION.match(part)
        or _RESTRUCTURE_VERB_START.match(part)
    )


def split_clauses(text):
    """Split into clauses, keeping a PROHIBITED LIST together.

    I2I_CAPABILITY_GATE_REPAIR_V1 — the splitter breaks on commas and on
    "and", so

        "Do not add floors, remove floors, or change the geometry"

    became three clauses and "remove floors" lost the prohibition in front of
    it. `_has_prohibition_marker` then saw no prohibition, `_has_verb` saw
    "remove", and the fragment was recorded as an explicit MASSING operation.
    That collided with the request's own "preserve … building massing" clause
    and blocked an otherwise supported facade edit with
    `explicit_operation_conflicts_with_fixed_geometry`.

    A fragment that continues a list opened by a prohibition is now re-attached
    to the clause that carries the prohibition, so the list stays one negative
    statement.
    """

    parts = [c.strip() for c in _CLAUSE_SPLIT.split(str(text or "")) if c.strip()]

    merged = []

    for part in parts:

        if merged and _continues_negated_list(merged[-1], part):

            merged[-1] = merged[-1] + ", " + part

            continue

        merged.append(part)

    return merged


_MARKER_RE_CACHE = {}


def _marker_re(marker):
    """Word-start match with an optional plural, cached per marker.

    `arch` must match `arch`/`arches` but never `architectural`/`ARCHITECTOS`.
    """

    pattern = _MARKER_RE_CACHE.get(marker)

    if pattern is None:

        pattern = re.compile(
            r"(?<![a-z0-9])" + re.escape(str(marker)) + r"(?:s|es)?(?![a-z0-9])"
        )

        _MARKER_RE_CACHE[marker] = pattern

    return pattern


def _domains_in(clause, lexicon):
    found = []
    low = clause.lower()
    for domain, markers in lexicon:
        # LIVE_HANDOFF_V1 — markers were matched with `in`, so the OPENING
        # marker "arch" matched inside "ARCHITECTOS" and "architectural".
        # Every facade request that named the product acquired an
        # `authorized_domains: ["opening"]` entry, which is what produced the
        # false "Explicitly authorised geometry change: opening." sentence.
        # Markers now match at a word start with an optional plural.
        if any(_marker_re(marker).search(low) for marker in markers):
            found.append(domain)
    return found


def _has_preserve_marker(clause, patterns):
    low = clause.lower()
    return any(re.search(p, low) for p in patterns)


def _has_appearance_object(clause, words):
    low = clause.lower()
    return any(w in low for w in words)


def _has_verb(clause, verbs):
    low = clause.lower()
    return any(v in low for v in verbs)


# FACADE_RENDER_INSTRUCTION_AUTHORITY_V2 — A PROHIBITION IS NOT AN OPERATION.
#
# MEASURED DEFECT: the accepted facade request says
#   "Preserve … original positions and dimensions of windows and doors"
#   "… surrounds around EXISTING openings; never by recutting or enlarging
#    openings"
# and `analyze_request` reported a geometric OPERATION on `opening`, because
# `_domains_in()` matched "openings" and `_has_verb()` matched "recutting" /
# "enlarging". `resolve_geometry_authority` then produced
#   authorized_domains = ["opening"]
# which `authority_note()` renders as
#   "Explicitly authorised geometry change: opening."
# i.e. a preservation sentence granted permission to change the openings.
#
# A clause that forbids something cannot authorise it. Such a clause is
# skipped here; genuine operations ("add a new window") are unaffected.
_PROHIBITION_MARKERS = (
    "do not", "don't", "never", "must not", "shall not", "without",
    "avoid", "instead of", "no ", "not ",
    "نکن", "نشه", "نباشد", "بدون", "نه ",
)


def _has_prohibition_marker(clause):
    low = " " + clause.lower() + " "
    return any(marker in low for marker in _PROHIBITION_MARKERS)


def analyze_request(user_text, edit_class=None):
    """Clause-scoped analysis of the user's own words.

    Returns explicit operations, explicit preservation, and whether the whole
    request is appearance-only. Nothing here grants authority by itself.
    """

    text = str(user_text or "")
    language = detect_language(text)
    appearance_class = str(edit_class or "") in APPEARANCE_EDIT_CLASSES

    if language == "fa":
        lexicon, verbs, appearance, preserve = (
            _FA_DOMAIN_MARKERS, _FA_VERBS, _FA_APPEARANCE_OBJECTS, _FA_PRESERVE_PATTERNS,
        )
    else:
        lexicon, verbs, appearance, preserve = (
            _EN_DOMAIN_MARKERS, _EN_VERBS, _EN_APPEARANCE_OBJECTS, _EN_PRESERVE_PATTERNS,
        )

    operations, preserved = [], []

    for clause in split_clauses(text):

        domains = _domains_in(clause, lexicon)

        if _has_preserve_marker(clause, preserve):
            for domain in domains:
                if domain not in preserved:
                    preserved.append(domain)
            continue

        # FACADE_RENDER_INSTRUCTION_AUTHORITY_V2 — a clause that FORBIDS a
        # change cannot grant it. Checked after preservation (a preserve
        # sentence may also read as a prohibition) and before the verb test.
        if _has_prohibition_marker(clause):
            continue

        if not _has_verb(clause, verbs):
            continue

        if not domains:
            continue

        appearance_only = appearance_class or _has_appearance_object(clause, appearance)

        for domain in domains:
            operations.append({
                "clause": clause,
                "domain": domain,
                "appearance_only": bool(appearance_only),
            })

    return {
        "language": language,
        "edit_class": edit_class,
        "appearance_class": appearance_class,
        "clauses": split_clauses(text),
        "operations": operations,
        "explicit_preserved_domains": preserved,
        "geometric_operations": [o for o in operations if not o["appearance_only"]],
        "appearance_operations": [o for o in operations if o["appearance_only"]],
    }


_CONSTRAINT_DOMAINS = {
    "roofline": DOMAIN_ROOF, "roof_shape": DOMAIN_ROOF,
    "building_silhouette": DOMAIN_MASSING, "overall_massing": DOMAIN_MASSING,
    "major_proportions": DOMAIN_MASSING, "number_of_floors": DOMAIN_MASSING,
    "main_window_positions": DOMAIN_OPENING, "main_door_positions": DOMAIN_OPENING,
    "major_recess_projection_geometry": DOMAIN_OPENING,
    "main_balconies": DOMAIN_CIRCULATION,
    "camera": DOMAIN_CAMERA, "perspective": DOMAIN_CAMERA,
}


def resolve_geometry_authority(
    terms,
    preserve_geometry=True,
    preserve_constraints=(),
    user_text="",
    edit_class=None,
    resolved_facade_knowledge=None,
):
    """Resolve precedence and return the admissible instruction terms."""

    constraints = _as_list(preserve_constraints)

    default_domains = []
    if preserve_geometry:
        for constraint in constraints:
            domain = _CONSTRAINT_DOMAINS.get(str(constraint))
            if domain and domain not in default_domains:
                default_domains.append(domain)

    analysis = analyze_request(user_text, edit_class=edit_class)

    explicit_preserved = list(analysis["explicit_preserved_domains"])
    geometric_ops = [o["domain"] for o in analysis["geometric_operations"]]

    # explicit preservation outranks default preservation
    fixed = list(dict.fromkeys(default_domains + explicit_preserved))

    # an explicit preservation statement outranks an explicit operation on the
    # same domain -> that is a contradiction, not an authorisation
    conflicts = [d for d in dict.fromkeys(geometric_ops) if d in explicit_preserved]

    authorized = [d for d in dict.fromkeys(geometric_ops) if d not in conflicts]

    # authorised domains are lifted; conflicting ones stay fixed
    fixed = [d for d in fixed if d not in authorized]

    unresolved_reason = None
    if analysis["language"] == "unknown" and str(user_text or "").strip():
        unresolved_reason = "language_not_supported"

    authority_active = bool(fixed)

    admitted, suppressed = [], []
    for term in _as_list(terms):
        domain = None
        low = str(term).lower()
        for d, markers in _EN_DOMAIN_MARKERS:
            if any(m in low for m in markers):
                domain = d
                break
        if authority_active and domain is not None and domain in fixed:
            suppressed.append({"term": term, "domain": domain})
            continue
        admitted.append(term)

    if conflicts:
        status = STATUS_CONFLICT
    elif unresolved_reason:
        status = STATUS_UNRESOLVED
    elif authorized:
        status = STATUS_AUTHORIZED
    elif suppressed:
        status = STATUS_SUGGESTIONS_FILTERED
    else:
        status = STATUS_OK

    disclosures = []
    if authority_active:
        disclosures.append(DISCLOSURE_STRICT_PRESERVATION)

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "status": status,
        "language": analysis["language"],
        "edit_class": edit_class,
        "appearance_only": bool(analysis["appearance_class"]) or not geometric_ops,
        "preserve_geometry": bool(preserve_geometry),
        "preserve_constraints": constraints,
        "default_fixed_domains": default_domains,
        "explicit_preserved_domains": explicit_preserved,
        "fixed_domains": fixed,
        "authorized_domains": authorized,
        "conflicts": [{"domain": d, "reason": "explicitly preserved by the user"} for d in conflicts],
        "operations": analysis["operations"],
        "unresolved_reason": unresolved_reason,
        "admitted_terms": admitted,
        "suppressed_terms": suppressed,
        "disclosures": disclosures,
    }


# ==========================================================
# ARCHITECTURAL REASONING INTEGRATION V8
# Evidence-aware projection of the EXISTING authority decision.
#
# This is deliberately not another planner. It keeps
# ``resolve_geometry_authority`` as the authority owner and adds the image,
# knowledge, editable-target and workflow fields that the live edit boundary
# needs in order to explain the same decision. The function is pure and never
# upgrades MODEL_REPORTED evidence to pixel verification.
# ==========================================================

_REMOVE_MARKERS = (
    "remove", "delete", "take off", "حذف", "بردار", "برداشته",
)
_PRESERVE_MARKERS = (
    "preserve", "keep", "retain", "unchanged", "fixed", "do not change",
    "without changing", "حفظ", "بدون تغییر", "ثابت", "دست نزن",
)
_ALL_OTHER_MARKERS = (
    "everything else", "all other", "the rest", "بقیه", "سایر",
)
_FURNITURE_MARKERS = ("furniture", "furnishings", "مبلمان", "اثاث")


#: I2I_NEGATED_REMOVE_FIX_V1 — a remove marker counts only as a STANDALONE
#: word inside a clause that is not itself a prohibition.
#:
#: MEASURED: "Do not add floors, remove floors, or change the geometry" made
#: the whole-text substring scan below report `operation = "remove"`, which
#: overrode the request's own `material_change` classification and pushed the
#: design decision to NEEDS_SPATIAL_TARGETING — a mask demand for a request
#: that asks to remove nothing.
#:
#: ASCII markers are word-bounded so ordinary words cannot match; Persian
#: markers stay substring because Persian attaches clitics and suffixes to the
#: verb stem ("حذفش", "حذفکن").
_REMOVE_MARKER_PATTERNS = tuple(
    re.compile(r"\b" + re.escape(marker) + r"\b", re.IGNORECASE)
    if marker.isascii()
    else re.compile(re.escape(marker))
    for marker in _REMOVE_MARKERS
)

#: Sentence boundary. `split_clauses` re-attaches a restructure verb to the
#: clause before it even when a full stop separates them, so
#: "Do not touch the roof. Remove the balcony railing." collapsed into ONE
#: prohibition clause and the affirmative removal disappeared. Splitting
#: sentences first keeps a prohibition scoped to its own sentence while the
#: comma-list merge inside that sentence still works.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟])\s+|\n+")


def _affirmative_remove_clause(text):
    """First clause that requests removal OUTSIDE a prohibition, else None."""

    for sentence in _SENTENCE_SPLIT.split(str(text or "")):

        for clause in split_clauses(sentence):

            if _has_prohibition_marker(clause):

                continue

            for pattern in _REMOVE_MARKER_PATTERNS:

                if pattern.search(clause):

                    return clause

    return None


def _decision_text(value):
    return " ".join(
        str(value or "").lower().replace("\u200c", " ").replace("_", " ").split()
    )


def _decision_aliases(record):
    values = [record.get("element")]
    values.extend(record.get("kind") or [])
    aliases = []
    for value in values:
        text = _decision_text(value)
        if not text:
            continue
        aliases.append(text)
        # Bounded English plural normalization; source labels remain intact.
        if text.endswith("ies") and len(text) > 3:
            aliases.append(text[:-3] + "y")
        elif text.endswith("s") and len(text) > 3:
            aliases.append(text[:-1])
    return list(dict.fromkeys(aliases))


def _mentions_record(text, record):
    normalized = _decision_text(text)
    return any(alias in normalized for alias in _decision_aliases(record))


def _element_records(understanding):
    evidence = (
        (understanding or {}).get("element_evidence")
        if isinstance(understanding, dict)
        else None
    ) or {}
    records = evidence.get("elements") or []
    return [deepcopy(item) for item in records if isinstance(item, dict)]


def _context_projection(understanding, records):
    projection = []
    for item in records:
        evidence_class = str(item.get("evidence_class") or "UNVERIFIED")
        basis = str(item.get("kind_basis") or "")
        epistemic = (
            "INTERPRETED"
            if "interpret" in basis or item.get("verification_status") == "UNVERIFIED"
            and basis == "appearance_supported_interpretation"
            else "OBSERVED"
        )
        projection.append({
            "element": item.get("element"),
            "kinds": list(item.get("kind") or []),
            "context_kinds": list(item.get("context_kinds") or []),
            "relations": deepcopy(item.get("relations") or []),
            "source_quote": item.get("source_quote"),
            "epistemic_status": epistemic,
            "evidence_class": evidence_class,
            "verification_status": item.get("verification_status") or (
                "VERIFIED" if evidence_class == "PIXEL_VERIFIED" else "UNVERIFIED"
            ),
            "position": deepcopy(item.get("position")),
        })

    local = (
        (understanding or {}).get("local_plan_reading")
        if isinstance(understanding, dict)
        else None
    ) or {}
    for item in local.get("furniture_evidence") or []:
        if not isinstance(item, dict):
            continue
        projection.append({
            "element": item.get("class"),
            "kinds": ["furniture"],
            "context_kinds": [],
            "relations": [],
            "source_quote": None,
            "epistemic_status": "OBSERVED",
            "evidence_class": "LOCAL_RASTER_GROUNDED",
            "verification_status": "VERIFIED_LOCAL_EVIDENCE",
            "position": deepcopy(item.get("bbox_pixels")),
        })
    return projection


def _preserved_element_names(user_text, records, editable_names):
    clauses = split_clauses(user_text)
    preserved = []
    for clause in clauses:
        low = _decision_text(clause)
        if not any(marker in low for marker in _PRESERVE_MARKERS):
            continue
        for item in records:
            name = item.get("element")
            if name and name not in editable_names and _mentions_record(clause, item):
                preserved.append(name)

    # Coordination may split "preserve columns, windows and entrance" into
    # fragments whose later items do not repeat the verb. Once an explicit
    # preservation marker appears, only the suffix governed by that marker is
    # considered; the earlier change clause is never borrowed.
    full = _decision_text(user_text)
    marker_positions = [
        full.find(marker) for marker in _PRESERVE_MARKERS if marker in full
    ]
    if marker_positions:
        preserve_suffix = full[min(marker_positions):]
        for item in records:
            name = item.get("element")
            if (
                name
                and name not in editable_names
                and _mentions_record(preserve_suffix, item)
            ):
                preserved.append(name)

    if any(marker in full for marker in _ALL_OTHER_MARKERS):
        preserved.extend(
            item.get("element") for item in records
            if item.get("element") and item.get("element") not in editable_names
        )
    return list(dict.fromkeys(preserved))


def _human_rule_words(text):
    return {
        token.lower()
        for token in re.findall(r"[^\W\d_]+", str(text or ""), re.UNICODE)
        if len(token) > 2
    }


def _rule_fixed_domain_conflict(rule, fixed_domains):
    """True when an accepted rule proposes a CHANGE inside a fixed domain.

    Advisory guidance about proportion or composition does not conflict. A rule
    that proposes to change a domain the current request fixes does, and the
    explicit current constraint wins.
    """

    text = str(rule.get("human_observation") or "").lower()

    if not any(marker in text for marker in _RULE_CHANGE_MARKERS):
        return None

    words = _human_rule_words(text)

    for domain in fixed_domains or ():

        tokens = _RULE_DOMAIN_TOKENS.get(domain) or ()

        if any(token in words for token in tokens):
            return domain

    return None


def _project_human_rules(rules, authority, user_text, design_context=None,
                         operation=None, fixed_elements=(), style=None):
    """(applied, conflicts, evaluations) for accepted human learning rules.

    Rules are accepted knowledge, never visual evidence. Applicability is
    decided by the ledger's structured evaluator: a rule the context cannot
    settle is NEEDS_REVIEW and is not applied. Exclusions are reported.
    """

    from core.architecture.knowledge.human_learning_ledger_v1 import (
        applicable_rules,
        rule_applicability_report,
    )

    context = {"text": str(user_text or "")}

    if isinstance(design_context, dict):
        context.update({
            key: value for key, value in design_context.items() if value
        })
        context.setdefault("text", str(user_text or ""))

    if style:
        context.setdefault("style", style)

    if operation:
        context.setdefault("operation", operation)

    if fixed_elements:
        context["fixed_elements"] = list(fixed_elements)

    evaluations = rule_applicability_report(rules, context)

    candidates = applicable_rules(rules, context)

    conflicts = []

    # 1. Contradiction between two accepted rules.
    contradictory = set()

    for index, first in enumerate(candidates):

        for second in candidates[index + 1:]:

            if first.get("polarity") == second.get("polarity"):
                continue

            shared = _human_rule_words(
                first.get("human_observation")
            ) & _human_rule_words(second.get("human_observation"))

            if len(shared) >= 2:
                contradictory.update((first.get("id"), second.get("id")))
                conflicts.append({
                    "reason": "contradictory_accepted_rules",
                    "rule_ids": [first.get("id"), second.get("id")],
                    "detail": (
                        "two accepted human rules disagree about the same "
                        "subject; neither is applied"
                    ),
                    "shared_terms": sorted(shared),
                })

    # 2. An explicit current constraint outranks a general rule.
    fixed_domains = list(authority.get("fixed_domains") or [])

    applied = []

    for rule in candidates:

        if rule.get("id") in contradictory:
            continue

        domain = _rule_fixed_domain_conflict(rule, fixed_domains)

        if domain:
            conflicts.append({
                "reason": "explicit_constraint_priority",
                "rule_ids": [rule.get("id")],
                "detail": (
                    "the rule proposes a change in %s, which the current "
                    "request requires to stay unchanged" % domain
                ),
                "domain": domain,
            })
            continue

        applied.append(rule)

    return applied, conflicts, evaluations


def _knowledge_projection(resolved):
    """Project ResolvedFacadeKnowledgeV1 into the decision's knowledge block.

    FACADE_KNOWLEDGE_HANDOFF_V1 — MEASURED DEFECT. This projection kept only
    the style name. The resolver had already resolved the composition, the
    element vocabulary and a surface-by-surface assembly, and every one of
    them was discarded one function before it would have been used. That is
    why the product behaved as "one stone across the image": the surface
    knowledge never arrived.

    What is carried now is exactly what the resolver produced, under its own
    names. Nothing is inferred here and nothing is promoted:

      * `surface_assignment` is a SEMANTIC category map. It says which KIND of
        surface receives which finish. It does NOT say where that surface is
        in the image, and it is explicitly marked `SEMANTIC_ONLY_NOT_SEGMENTED`
        so no consumer can mistake it for a region.
      * `architectural_elements` is STYLE-DERIVED vocabulary. It describes the
        language of the style, not elements the user asked for. The user's own
        requested elements are carried by the prompt compiler, which reads the
        user's words directly; this block must never be used to add ornament.
    """

    if not isinstance(resolved, dict) or resolved.get("contract") != "ResolvedFacadeKnowledgeV1":
        return None, []

    canonical = resolved.get("canonical_style")

    # Only non-empty element groups are carried: an empty group is an absence
    # of style vocabulary, not a finding about the building.
    _elements = resolved.get("architectural_elements")
    elements = {}
    if isinstance(_elements, dict):
        elements = {
            str(key): list(value)
            for key, value in _elements.items()
            if isinstance(value, (list, tuple)) and value
        }

    _assembly = (
        (resolved.get("surface_strategy") or {}).get("facade_assembly") or {}
    )
    _system = _assembly.get("facade_system")
    surface_assignment = {}
    if isinstance(_system, dict):
        surface_assignment = {
            str(key): value
            for key, value in _system.items()
            if isinstance(value, dict) and value
        }

    knowledge = {
        "contract": resolved.get("contract"),
        "canonical_style": canonical,
        "style_family": resolved.get("style_family"),
        "composition": list(resolved.get("composition") or []),
        "architectural_elements": elements,
        "entrance_hierarchy": list(resolved.get("entrance_hierarchy") or []),
        "opening_treatment": list(resolved.get("opening_treatment") or []),
        "parapet_treatment": list(resolved.get("parapet_treatment") or []),
        "balcony_treatment": list(resolved.get("balcony_treatment") or []),
        "surface_assignment": surface_assignment,
        "surface_semantics": "SEMANTIC_ONLY_NOT_SEGMENTED",
        "material_specificity": (
            (resolved.get("materials") or {}).get("selection_specificity")
            if isinstance(resolved.get("materials"), dict)
            else None
        ),
        "provenance": deepcopy(resolved.get("sources") or resolved.get("provenance") or {}),
        "epistemic_status": "INTERPRETED",
    }

    decisions = []

    if canonical and canonical != "UNKNOWN":
        decisions.append(
            "use %s as architectural-language guidance, not as proof of visible elements"
            % str(canonical).replace("_", " ")
        )

    if surface_assignment:
        decisions.append(
            "surface assignment is a semantic category map, not a segmented "
            "pixel region; no surface is verified to be at any location"
        )

    return knowledge, decisions


def _conceptual_global_admission(admission, edit_class):
    """Validate the existing R4 conceptual whole-facade admission.

    This is policy authority, not visual evidence.  It deliberately does not
    inspect or rewrite image observations and cannot turn MODEL_REPORTED or
    UNVERIFIED claims into OBSERVED facts.
    """

    if not isinstance(admission, dict):
        return False

    editable = admission.get("editable") or {}
    integrity = admission.get("source_integrity") or {}
    source = admission.get("source") or {}

    return bool(
        admission.get("contract") == "ArchitecturalEditAdmissionV1"
        and admission.get("admitted") is True
        and admission.get("reason") == "conceptual_appearance_edit_consented"
        and admission.get("selected_workflow") == "flux_img2img.json"
        and admission.get("preservation_status") == "conceptual_unverified"
        and admission.get("preservation_contract") is None
        and admission.get("edit_class") == edit_class
        and edit_class in ("material_change", "style_change")
        and editable.get("scope") == "global"
        and integrity.get("verified") is True
        and source.get("valid") is True
    )


def resolve_design_decision(
    *,
    user_text,
    edit_delta=None,
    image_understanding=None,
    resolved_facade_knowledge=None,
    preserve_geometry=True,
    preserve_constraints=(),
    human_learning_rules=None,
    design_context=None,
    conceptual_admission=None,
):
    """Project the existing authority result into an evidence-aware decision.

    The return value deliberately retains ``GeometryAuthorityHandoffV1`` as
    its contract. It is an additive reporting/execution projection, not a new
    reasoning schema. No masks, coordinates, counts, materials or elements are
    inferred here.
    """

    delta = edit_delta if isinstance(edit_delta, dict) else {}
    edit_class = delta.get("edit_class")
    authority = resolve_geometry_authority(
        (),
        preserve_geometry=preserve_geometry,
        preserve_constraints=preserve_constraints,
        user_text=user_text,
        edit_class=edit_class,
        resolved_facade_knowledge=resolved_facade_knowledge,
    )
    understanding = image_understanding if isinstance(image_understanding, dict) else {}
    image_type = understanding.get("image_type") or "unknown"
    records = _element_records(understanding)
    context = _context_projection(understanding, records)
    text = _decision_text(user_text)

    operation = "change"
    if _affirmative_remove_clause(user_text):
        operation = "remove"
    elif edit_class == "time_of_day_change":
        operation = "relight"
    elif edit_class == "material_change":
        # ==================================================
        # FACADE_KNOWLEDGE_HANDOFF_V1 — MATERIAL REPLACEMENT vs FACADE DESIGN
        #
        # `compile_edit_delta` gives the MATERIAL precedence when a request
        # names both a style and a material, so
        #
        #   "Design a restrained neoclassical facade … use cream travertine …"
        #
        # arrives as `material_change` even though the style IS captured on
        # `delta["style"]`. Treating it as a material swap would silently drop
        # the entire design contract — which is exactly the collapse the
        # product owner reported.
        #
        # This is a PRECEDENCE rule, not a second classifier: the existing
        # delta already carries the style, and a request that names a style is
        # a style operation whose material is its finish. A pure material
        # request carries no style at all and is untouched.
        # ==================================================
        operation = "restyle" if _named_style(delta) else "replace_finish"
    elif edit_class == "style_change":
        operation = "restyle"
    elif any(marker in text for marker in _FURNITURE_MARKERS):
        operation = "rearrange"

    # A valid R4 conceptual admission authorises the EXISTING whole-image
    # appearance workflow even when live observation cannot verify a facade
    # surface.  Unknown image classification is permitted; a known plan is
    # not.  This authority comes from the user's explicit request + consent +
    # verified source integrity, never from fabricated visual grounding.
    conceptual_global = bool(
        image_type != "floor_plan_or_sketch"
        and _conceptual_global_admission(conceptual_admission, edit_class)
    )

    requested = {
        "status": "REQUESTED",
        "operation": operation,
        "edit_class": edit_class,
        "style": delta.get("style"),
        "material": delta.get("material"),
        "material_tone": delta.get("material_tone"),
        "time_of_day": delta.get("time_of_day"),
        "source": "USER_TEXT",
        "source_text": str(user_text or ""),
    }

    editable = []
    target_records = []
    has_wall = any("wall" in (item.get("kind") or []) for item in records)
    has_furniture = any(
        item.get("kinds") == ["furniture"] for item in context
    )

    if operation == "remove":
        # Subject labels outrank contextual kind words. Thus "wall-mounted
        # lanterns" targets the lantern record, not the wall record whose kind
        # happens to occur in the same phrase.
        target_records = [
            item for item in records
            if _decision_text(item.get("element"))
            and _decision_text(item.get("element")) in text
        ]
        if not target_records:
            target_records = [
                item for item in records if _mentions_record(user_text, item)
            ]
        editable = [item.get("element") for item in target_records if item.get("element")]
    elif edit_class == "material_change":
        if image_type in ("facade_or_elevation", "architectural_render_or_photo") and has_wall:
            editable = [
                "facade_surface_expression"
                if operation == "restyle"
                else "facade_wall_surface"
            ]
        elif conceptual_global and operation == "restyle" and records:
            # ==================================================
            # NEOCLASSICAL_LIVE_EVIDENCE_HANDOFF_V1
            #
            # MEASURED GAP: a consented global conceptual restyle was
            # authorised for the workflow but granted NO editable target,
            # because the target required `image_type` to be a facade type.
            # The persisted analysis of the accepted source is a genuine,
            # 18-element architectural reading whose classification is
            # `unknown` — so `editable` stayed empty, the constraint block was
            # 0 characters, and the request degraded to a material sentence.
            #
            # The requirement being applied here is a VERIFIED-OBSERVATION
            # requirement. On the conceptual route there is no verified
            # observation by definition (`preservation_status:
            # conceptual_unverified`), and the admission already authorises a
            # GLOBAL whole-image appearance edit. The user's explicit request
            # establishes the desired intervention; it never establishes the
            # observed existence of anything.
            #
            # So the target is granted as the SEMANTIC facade-expression
            # target, not as a pixel region, and only when ALL of the
            # following already hold:
            #   * the R4 conceptual admission passed in full
            #     (`_conceptual_global_admission`: admitted, consented,
            #      flux_img2img, conceptual_unverified, no preservation
            #      contract, global scope, verified source integrity);
            #   * the image is not a plan (`conceptual_global` excludes it);
            #   * the operation is a design restyle, not a finish swap;
            #   * real persisted element evidence exists (`records`).
            #
            # `image_type` is NOT rewritten. It stays `unknown`.
            # ==================================================
            editable = ["facade_surface_expression"]
    elif edit_class == "style_change":
        if image_type in ("facade_or_elevation", "architectural_render_or_photo") and has_wall:
            editable = ["facade_surface_expression"]
        elif conceptual_global and records:
            editable = ["facade_surface_expression"]
    elif edit_class in ("time_of_day_change", "lighting_change"):
        if image_type != "floor_plan_or_sketch":
            editable = ["lighting", "atmosphere"]
    elif operation == "rearrange" and image_type == "floor_plan_or_sketch" and has_furniture:
        editable = ["furniture"]

    fixed_elements = _preserved_element_names(user_text, records, set(editable))
    knowledge, knowledge_decisions = _knowledge_projection(resolved_facade_knowledge)
    applied_human_rules, rule_conflicts, rule_evaluations = _project_human_rules(
        human_learning_rules, authority, user_text, design_context,
        operation=operation,
        fixed_elements=fixed_elements,
        style=(delta.get("style") if isinstance(delta, dict) else None),
    )
    conflicts = []
    uncertainty = []

    if authority.get("conflicts"):
        conflicts.append("requested change conflicts with an explicit fixed constraint")
    if operation == "remove" and not target_records:
        conflicts.append("requested element is not supported by image evidence")
    if (
        edit_class in ("material_change", "style_change")
        and not editable
        and not conceptual_global
    ):
        conflicts.append("editable facade surface is not supported by image evidence")
    if edit_class == "material_change":
        uncertainty.append("material appearance in the source image")
    if any(item.get("verification_status") == "UNVERIFIED" for item in context):
        uncertainty.append("source-anchored model observations remain unverified at pixel level")

    if conceptual_global:
        workflow = {
            "capability": "conceptual whole-image appearance edit",
            "route": "existing_image_edit",
            "conditions": "explicit conceptual consent and verified source integrity",
        }
    else:
        workflow = {
            "capability": "Kontext global appearance edit",
            "route": "existing_image_edit",
            "conditions": "source image and existing geometry-preservation gate",
        }
    status = "READY_FOR_EXISTING_WORKFLOW"

    if authority.get("conflicts"):
        status = "BLOCKED_CONFLICT"
        workflow = {"capability": "none", "route": None, "conditions": "resolve constraint conflict"}
    elif operation == "remove" and target_records:

        # SPATIAL_TARGETING_IS_NOT_POSITION_METADATA (V8.1)
        #
        # A recorded `position` is a model-reported observation, not a
        # validated mask. Previously any record carrying one made a localized
        # removal READY, and it was then recommended as a GLOBAL appearance
        # edit — i.e. position metadata substituted for the precise-edit
        # mechanism. Removal now always requires spatial targeting; only a
        # caller-supplied validated mask authorises execution, which
        # ImageHandler enforces.
        status = "NEEDS_SPATIAL_TARGETING"
        workflow = {
            "capability": "Kontext masked edit",
            "route": "existing_precise_image_edit",
            "conditions": "verified caller-supplied mask",
        }
    elif operation == "remove" and not target_records:
        status = "INSUFFICIENT_IMAGE_EVIDENCE"
        workflow = {"capability": "none", "route": None, "conditions": "grounded target evidence required"}
    elif image_type == "floor_plan_or_sketch":
        if editable:
            status = "INSUFFICIENT_SPATIAL_EVIDENCE"
            workflow = {
                "capability": "none",
                "route": None,
                "conditions": "authoritative plan geometry and approved spatial operation required",
            }
        elif edit_class in ("material_change", "style_change"):
            status = "INSUFFICIENT_IMAGE_EVIDENCE"
            workflow = {"capability": "none", "route": None, "conditions": "facade evidence required"}
    elif (
        edit_class in ("material_change", "style_change")
        and not editable
        and not conceptual_global
    ):
        status = "INSUFFICIENT_IMAGE_EVIDENCE"
        workflow = {"capability": "none", "route": None, "conditions": "grounded facade surface required"}

    intended = []
    if operation == "relight":
        intended.append("change lighting and atmosphere only")
    elif operation == "replace_finish" and delta.get("material"):
        if conceptual_global and not editable:
            intended.append(
                "apply user-authorized global facade finish transformation to %s; "
                "surface localization remains unverified" % delta["material"]
            )
        else:
            intended.append("replace supported facade finish with %s" % delta["material"])
    elif operation == "restyle" and delta.get("style"):
        intended.append("apply %s facade language to supported existing surfaces" % delta["style"])
    elif operation == "remove" and editable:
        intended.append("remove only: " + ", ".join(editable))
    elif operation == "rearrange" and editable:
        intended.append("rearrange image-supported furniture only")

    preservation = list(authority.get("fixed_domains") or [])
    preservation.extend(fixed_elements)

    # NEOCLASSICAL_FIRST_RENDER_FIX_V1 — resolved BEFORE the decision dict so
    # the prohibition can outrank an accidental positive match.
    _prohibitions = _user_prohibitions(user_text)
    _requested = _requested_ornament(user_text)
    _requested = {
        "elements": _prohibited_ornament(_requested.get("elements") or [], _prohibitions),
        "source": _requested.get("source", "USER_TEXT"),
    }

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "decision_layer": "ARCHITECTURAL_REASONING_INTEGRATION_V8",
        "image_type": image_type,
        "requested_operation": requested,
        # NEOCLASSICAL_DESIGN_CHAT_ROUTE_V1 — the decorative elements the USER
        # named, carried with an explicit source so they can never be read as
        # style-derived knowledge. Empty for every request that names none.
        "requested_ornament": _requested,
        # NEOCLASSICAL_FIRST_RENDER_FIX_V1 — the objects the user forbade, so an
        # accidental positive match can never outrank an explicit prohibition.
        "user_prohibitions": _prohibitions,
        "image_supported_context": context,
        "applicable_knowledge": knowledge,
        "knowledge_derived_decisions": knowledge_decisions,
        # HUMAN TEACHING T1 — accepted human rules that are applicable here.
        # Their provenance is HUMAN_ACCEPTED_RULE and is never merged into the
        # visually observed evidence above.
        "applied_human_rules": applied_human_rules,
        "rule_conflicts": rule_conflicts,
        # Why each supplied rule was or was not applied. A rule the context
        # cannot settle is NEEDS_REVIEW and is never applied.
        "rule_evaluations": rule_evaluations,
        "fixed_constraints": {
            "status": "FIXED",
            "domains": list(authority.get("fixed_domains") or []),
            "elements": fixed_elements,
            "source": "USER_TEXT_AND_EXISTING_GEOMETRY_AUTHORITY",
        },
        "editable_elements": list(dict.fromkeys(editable)),
        "intended_changes": intended,
        "preservation_requirements": list(dict.fromkeys(preservation)),
        "conflicts": conflicts,
        "remaining_uncertainty": list(dict.fromkeys(uncertainty)),
        "workflow_recommendation": workflow,
        "post_execution_verification": [
            "verify requested change against the actual output",
            "verify fixed geometry and explicitly preserved elements against the source",
        ],
        "execution_status": status,
        "geometry_authority": authority,
        "render_executed": False,
        "comfy_invoked": False,
    }

    if conceptual_global:
        result["conceptual_global_edit"] = {
            "authorized": True,
            "authority": "explicit_user_request_and_conceptual_consent",
            "workflow": "flux_img2img.json",
            "preservation_status": "conceptual_unverified",
            "surface_localization_verified": False,
            "visual_evidence_promoted": False,
        }

    # ARCHITECTURAL_PRESERVATION_INTELLIGENCE_V1 — additive projection of the
    # existing decision into design/protected-building/protected-context
    # scopes.  It does not change this decision's status, workflow selection or
    # R4 admission.  Capability claims are accepted only when the caller
    # supplies positive evidence for every required enforcement mechanism.
    _design_context = design_context if isinstance(design_context, dict) else {}
    result["architectural_preservation_intent"] = (
        build_architectural_preservation_intent_v1(
            user_text=str(user_text or ""),
            requested_operation=requested,
            editable_elements=result["editable_elements"],
            fixed_constraints=result["fixed_constraints"],
            explicit_preservation_clauses=(
                delta.get("explicit_preservation_clauses") or []
            ),
            image_supported_context=context,
            workflow_capabilities=(
                _design_context.get("preservation_workflow_capabilities") or {}
            ),
            experiment_evidence=(
                _design_context.get("preservation_experiment_evidence") or {}
            ),
            user_prohibitions=_prohibitions,
        )
    )

    return result


DECISION_INSTRUCTION_CONTRACT = "RenderConstraintBlockV1"

#: Only a decision that authorises execution may produce an executable
#: instruction. A blocked or insufficient decision contributes nothing.
_EXECUTABLE_DECISION_STATUSES = (
    "READY_FOR_EXISTING_WORKFLOW",
    "NEEDS_SPATIAL_TARGETING",
)

_OPERATION_INSTRUCTION = {
    "remove": "Remove only the image-supported subject: %s.",
    "relight": (
        "Change only the image lighting and atmosphere (%s); do not restyle, "
        "re-material or re-model the building."
    ),
    "replace_finish": "Apply the requested finish only to the image-supported targets: %s.",
    "restyle": (
        "Apply the requested architectural style only to the image-supported "
        "targets: %s."
    ),
    "rearrange": "Rearrange only the image-supported items: %s.",
    "change": "Apply the requested change only to the image-supported targets: %s.",
}

#: Only a style edit carries knowledge GUIDANCE into the instruction. A
#: material edit already names its material in the compiled delta, and a
#: lighting edit must not receive facade vocabulary at all.
_KNOWLEDGE_BEARING_OPERATIONS = ("restyle",)

#: Values that mean "no style change", not a style to apply.
_KNOWLEDGE_SENTINELS = ("UNKNOWN", "EXISTING_ARCHITECTURAL_STYLE", "NONE")

_MAX_BLOCK_CHARS = 1100

#: NEOCLASSICAL_LIVE_EVIDENCE_HANDOFF_V1 — the resolver's own instruction
#: budget (`render_prompt_resolver_v1.resolve_render_prompt(
#: max_instruction_chars=2400)`). The block is built to fit it, so the resolver
#: never has to truncate on a sentence boundary and never drops half a pair.
_INSTRUCTION_BUDGET = 2400


def _design_decision_sentence(decision):
    """The bounded bookkeeping sentence, emitted last and never dropped."""

    status = decision.get("execution_status")

    operation = (
        (decision.get("requested_operation") or {}).get("operation")
        if isinstance(decision.get("requested_operation"), dict)
        else None
    ) or "change"

    editable = decision.get("editable_elements") or []

    return "Design decision: %s | operation: %s | image-supported targets: %d." % (
        _display(status).lower(),
        operation,
        len(editable),
    )

#: NEOCLASSICAL_LIVE_EVIDENCE_HANDOFF_V1 — how many image-observed elements are
#: named in the bounded instruction, and how long each label may be. The full
#: list is never lost: it stays on the decision.
_MAX_PRESERVED_IN_BLOCK = 6
_MAX_PRESERVED_LABEL_CHARS = 48

#: NEOCLASSICAL_FIRST_RENDER_FIX_V1 — the user's explicit prohibitions.
#:
#: MEASURED DEFECT: "Do not add arches, domes, sculptural ornament" never
#: reached the effective instruction. The real Chat route compiles the prompt
#: from the edit delta, not from the instruction owner's `english_instruction`,
#: and the delta carries no prohibition. So a brief that forbade sculptural
#: ornament was rendered with a positive request for it and no prohibition at
#: all.
#:
#: The evidence comes from the EXISTING shared negation layer
#: (`negation_scope_v1.rejected_span`), applied per sentence. That layer returns
#: ONE span for the whole text — the LAST prohibition — so a multi-clause brief
#: lost every earlier one. Iterating sentences is not a second parser: it is the
#: same extractor on a narrower scope.
_MAX_PROHIBITIONS_IN_BLOCK = 4

#: A leading verb is stripped so the sentence reads as a list of rejected
#: objects ("Do NOT include: arches, domes …") rather than an instruction.
_PROHIBITION_LEAD_VERBS = (
    "add ", "apply ", "introduce ", "include ", "use ", "carry ",
    "automatically ",
)


def _user_prohibitions(user_text):
    """The objects the user explicitly forbade, in the user's own words."""

    text = str(user_text or "").strip()

    if not text:

        return []

    try:

        from core.chat.negation_scope_v1 import rejected_span

    except Exception:  # noqa: BLE001 — an enrichment, never fatal

        return []

    spans = []

    for sentence in re.split(r"(?<=[.!?])\s+", text):

        if " do not" not in (" " + sentence.lower()):

            continue

        span = " ".join(str(rejected_span(sentence, max_chars=80) or "").split())

        span = span.strip(" .,;:")

        if not span:

            continue

        lowered = span.lower()

        for verb in _PROHIBITION_LEAD_VERBS:

            if lowered.startswith(verb):

                span = span[len(verb):].strip()

                break

        if span and span.lower() not in [item.lower() for item in spans]:

            spans.append(span)

    return spans[:_MAX_PROHIBITIONS_IN_BLOCK]


def _preserved_label(value):
    """A short, comma-free label for one observed element.

    The analysis stores full sentences. A comma inside one of them fragments
    the constraint block when the resolver splits it into sentences, so commas
    are removed rather than carried into the instruction.
    """

    text = " ".join(str(value or "").replace(",", " ").split())

    text = text.strip().strip(".;:").strip()

    if len(text) <= _MAX_PRESERVED_LABEL_CHARS:

        return text

    clipped = text[:_MAX_PRESERVED_LABEL_CHARS]

    if " " in clipped:

        clipped = clipped.rsplit(" ", 1)[0]

    return clipped.strip().rstrip(".;:,")

#: A bounded number of accepted rules is stated in the instruction; the encoder
#: budget is finite and the decision keeps the rest in its own contract.
_MAX_RULES_IN_BLOCK = 2


def _display(value):
    return " ".join(str(value or "").replace("_", " ").split())


def _named_style(delta):
    """True when the compiled delta carries a REAL style token.

    FACADE_KNOWLEDGE_HANDOFF_V1 — the existing delta already distinguishes a
    style request from a pure material request; this only reads it. Sentinels
    that mean "no style" are refused so a placeholder can never promote a
    material edit into a design edit.
    """

    if not isinstance(delta, dict):
        return False

    style = delta.get("style")

    if isinstance(style, dict):
        style = style.get("target") or style.get("name") or ""

    token = "_".join(str(style or "").upper().split())

    return bool(token) and token not in _KNOWLEDGE_SENTINELS


def _prohibited_ornament(elements, prohibitions):
    """Drop a requested element the user explicitly forbade.

    NEOCLASSICAL_FIRST_RENDER_FIX_V1 — an explicit prohibition outranks an
    accidental positive keyword match. A single-word element is matched on its
    stem ("pilasters" -> "pilaster"); a multi-word element is matched on its
    FIRST word, which is its head noun ("sculptural relief" -> "sculptural").
    """

    joined = " ".join(str(item) for item in (prohibitions or [])).lower()

    if not joined:

        return list(elements)

    kept = []

    for element in elements:

        name = str(element).lower().strip()

        if not name:

            continue

        key = name.split()[0] if " " in name else name

        if key.endswith("s") and not key.endswith("ss"):

            key = key[:-1]

        if re.search(r"\b" + re.escape(key) + r"\b", joined):

            continue

        kept.append(element)

    return kept


def _requested_ornament(user_text):
    """The decorative elements the USER explicitly named, or [].

    NEOCLASSICAL_DESIGN_CHAT_ROUTE_V1 — MEASURED PRODUCTION GAP. On the real
    Chat route the compiled prompt is the EDIT DELTA prompt, not the prompt
    compiler's `english_instruction`. The delta prompt is a material sentence
    ("replace the facade finish with …"), so it carries the style and the
    material and NOTHING else: pilasters, capitals, stringcourses, cornices,
    window surrounds and balustrades were all absent from the payload that
    would have been rendered.

    The requested elements are USER TEXT, not style knowledge, so they cannot
    come from `applicable_knowledge`. They are read here through the EXISTING
    understanding owner and carried on the decision with an explicit source,
    and the block emits them through the EXISTING compiler vocabulary rather
    than a second word list.

    Returns a dict so a consumer cannot mistake a bare list for style-derived
    knowledge: ``{"elements": [...], "source": "USER_TEXT"}``.
    """

    text = str(user_text or "").strip()

    if not text:

        return {"elements": [], "source": "USER_TEXT"}

    try:

        from core.prompt_intelligence.persian_architectural_understanding import (
            understand,
        )

        understood = understand(text)

    except Exception:  # noqa: BLE001 — an enrichment, never fatal

        return {"elements": [], "source": "USER_TEXT"}

    elements = [
        str(item) for item in (understood.get("elements") or []) if str(item)
    ]

    return {"elements": list(dict.fromkeys(elements)), "source": "USER_TEXT"}


def _ornament_sentence(requested_ornament):
    """The compiler's own element phrasing for the user's requested elements.

    Reuses `ArchitecturalPromptCompiler._compile_elements`, so the wording is
    identical to the prompt-compiler path and there is no second vocabulary.

    Only the PHRASE LIST is kept from that call. Its own wrapper ("REQUIRED
    ARCHITECTURAL ELEMENTS — include …; each must be … surface relief WITHIN
    the existing wall planes …") restates the authorised-addition boundary
    that this block already states in its own sentence, and the duplication
    pushed the block past the resolver's 2400-character budget, where it would
    have been truncated on a sentence boundary.
    """

    if not isinstance(requested_ornament, dict):

        return ""

    elements = list(requested_ornament.get("elements") or [])

    if not elements:

        return ""

    try:

        from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
            ArchitecturalPromptCompiler,
        )

        lines = ArchitecturalPromptCompiler()._compile_elements(
            {
                "elements": elements,
                "preserve_constraints": {"geometry": True},
                "reference_image_policy": {},
                "entrance": {},
                "negative_constraints": [],
            }
        )

    except Exception:  # noqa: BLE001 — an enrichment, never fatal

        return ""

    text = " ".join(str(line).strip() for line in lines if str(line).strip())

    if not text:

        return ""

    listed = text

    if " — include " in listed:

        listed = listed.split(" — include ", 1)[1]

    if "; each must" in listed:

        listed = listed.split("; each must", 1)[0]

    listed = listed.strip().strip(";").strip()

    if not listed:

        return ""

    return (
        "Requested decorative additions, applied as relief only on the "
        "existing wall planes: %s." % listed
    )


def _surface_assignment_sentence(knowledge):
    """One bounded sentence stating which surface receives which finish.

    FACADE_KNOWLEDGE_HANDOFF_V1 — reads ONLY the resolved assembly that the
    resolver already produced. It names a KIND of surface, never a location,
    and says so, so no consumer can read it as segmentation.
    """

    assignment = knowledge.get("surface_assignment")

    if not isinstance(assignment, dict) or not assignment:
        return ""

    parts = []

    wall = assignment.get("wall_surface")

    if isinstance(wall, dict) and wall.get("material"):
        parts.append("the wall field in %s" % _display(wall["material"]))

    base = assignment.get("base")

    if isinstance(base, dict) and base.get("material"):
        parts.append("the base in %s" % _display(base["material"]))

    openings = assignment.get("openings")

    if isinstance(openings, dict) and openings.get("elements"):
        parts.append(
            "the existing openings framed in %s"
            % _display(", ".join(openings["elements"]))
        )

    vertical = assignment.get("vertical_elements")

    if isinstance(vertical, dict) and vertical.get("elements"):
        parts.append(
            "the vertical rhythm as %s"
            % _display(", ".join(vertical["elements"]))
        )

    upper = assignment.get("upper_elements")

    if isinstance(upper, dict) and upper.get("elements"):
        parts.append(
            "the upper elements as %s"
            % _display(", ".join(upper["elements"]))
        )

    # The three surfaces that the accepted evidence says were wrongly clad.
    soffit = assignment.get("soffit")

    if isinstance(soffit, dict) and soffit:
        material = _display(soffit.get("material")) or "a smooth painted finish"
        parts.append("the soffits in %s, not facade stone" % material)

    glazing = assignment.get("glazing")

    if isinstance(glazing, dict) and glazing:
        parts.append("the glazing and frames as glass and metal, not stone")

    site = assignment.get("site")

    if isinstance(site, dict) and site:
        parts.append(
            "the site paving, boundary walls and planting in a separate site scope"
        )

    if not parts:
        return ""

    return (
        "Surface assignment (semantic categories, not measured regions): %s."
        % "; ".join(parts)
    )


_COMPLETION_OPERATION_INSTRUCTIONS = {
    "complete_windows_within_existing_openings": (
        "Install requested windows, frames and glazing inside existing openings "
        "only; never create, relocate or enlarge openings."
    ),
    "install_door_within_existing_doorway": (
        "Install requested doors and frames inside existing doorways only; "
        "never create, relocate or enlarge doorways."
    ),
    "apply_decorative_column_treatment": (
        "Apply requested non-structural cladding and capitals to existing "
        "columns only; never relocate or resize columns or create unsupported "
        "structural members."
    ),
    "finish_balcony_within_existing_boundaries": (
        "Finish existing balconies and terraces only within their current "
        "boundaries; never add, relocate or extend balconies."
    ),
    # The material-transition sentence below carries the requested finish and
    # source/final distinction, so a second surface sentence would duplicate it.
    "replace_requested_facade_surface_material": "",
}


def _scope_claim_ids(preservation_intent, scope):
    """Return bounded semantic IDs already established by the V1 contract."""

    scopes = preservation_intent.get("scopes") or {}
    values = scopes.get(scope) if isinstance(scopes, dict) else []
    return list(dict.fromkeys(
        str(item.get("id"))
        for item in (values or [])
        if isinstance(item, dict) and item.get("id")
    ))


def _architectural_completion_instruction_handoff(decision):
    """Project the existing completion contract into executable constraints.

    This is a serialization step, not a second reasoning pass. It accepts only
    operation IDs already admitted by ArchitecturalPreservationIntentV1, keeps
    their provenance in structured metadata, and states semantic boundaries as
    text without creating masks, coordinates, segmentation or hard-preservation
    capability.
    """

    preservation = decision.get("architectural_preservation_intent") or {}
    if not isinstance(preservation, dict):
        return [], {}
    if preservation.get("contract") != "ArchitecturalPreservationIntentV1":
        return [], {}

    completion = preservation.get("architectural_completion") or {}
    if not isinstance(completion, dict) or completion.get("status") != "REQUESTED":
        return [], {}

    operations = [
        item for item in (completion.get("allowed_operations") or [])
        if isinstance(item, dict)
        and item.get("id") in _COMPLETION_OPERATION_INSTRUCTIONS
        and item.get("grounding_category") == "user_specified"
        and item.get("verification_status") == "REQUESTED_NOT_EXECUTED"
        and item.get("geometry_change_authorized") is False
    ]
    if not operations:
        return [], {}

    operation_ids = list(dict.fromkeys(str(item["id"]) for item in operations))
    sentences = [
        _COMPLETION_OPERATION_INSTRUCTIONS[operation_id]
        for operation_id in operation_ids
        if _COMPLETION_OPERATION_INSTRUCTIONS[operation_id]
    ]

    forbidden = list(dict.fromkeys(
        str(item) for item in (
            completion.get("forbidden_geometric_operations") or []
        ) if str(item).strip()
    ))
    requirements = preservation.get("material_style_requirements") or {}
    transition = completion.get("material_transition") or {}
    requested_finish = (
        transition.get("requested_finish_material")
        if isinstance(transition, dict)
        else None
    )
    requested_finish_id = (
        str(requested_finish.get("id"))
        if isinstance(requested_finish, dict) and requested_finish.get("id")
        else ""
    )
    qualifiers = [
        _display(item) for item in (
            requirements.get("appearance_qualifiers") or []
        ) if _display(item)
    ] if isinstance(requirements, dict) else []
    excluded = [
        _display(item) for item in (
            requirements.get("excluded_material_expressions") or []
        ) if _display(item)
    ] if isinstance(requirements, dict) else []
    source_materials = [
        item for item in (
            transition.get("existing_construction_materials") or []
        ) if isinstance(item, dict)
    ] if isinstance(transition, dict) else []

    if requested_finish_id:
        finish_phrase = " ".join(qualifiers + [_display(requested_finish_id)]).strip()
        sentences.append(
            "Final facade finish: %s; raw source brick, block or masonry is "
            "construction context, not a required final finish." % finish_phrase
        )
    if excluded:
        sentences.append(
            "Exclude these material interpretations: %s."
            % ", ".join(excluded)
        )

    protected_architecture = _scope_claim_ids(
        preservation, "protected_architecture"
    )
    protected_context = _scope_claim_ids(preservation, "protected_context")
    if protected_architecture:
        sentences.append(
            "Keep protected building geometry: %s."
            % ", ".join(_display(item) for item in protected_architecture[:10])
        )
    if protected_context:
        sentences.append(
            "Keep this context outside the design scope: %s."
            % ", ".join(_display(item) for item in protected_context[:10])
        )

    if any(
        str(item.get("verification_status") or "").upper() == "UNVERIFIED"
        for item in source_materials
    ):
        sentences.append(
            "Source-material observations remain UNVERIFIED and grant no "
            "spatial authority."
        )

    capability = preservation.get("preservation_capability") or {}
    capability_status = (
        str(capability.get("status"))
        if isinstance(capability, dict) and capability.get("status")
        else ""
    )
    if capability_status:
        sentences.append(
            "Capability: %s; semantic guidance only, with no hard-preservation "
            "guarantee." % capability_status
        )

    spatial = completion.get("spatial_authority") or {}
    handoff = {
        "source_contract": preservation.get("contract"),
        "status": completion.get("status"),
        "allowed_operations": deepcopy(operations),
        "allowed_operation_ids": operation_ids,
        "forbidden_geometric_operations": forbidden,
        "material_transition": deepcopy(transition),
        "material_style_requirements": deepcopy(requirements),
        "protected_architecture": deepcopy(
            (preservation.get("scopes") or {}).get("protected_architecture") or []
        ),
        "protected_context": deepcopy(
            (preservation.get("scopes") or {}).get("protected_context") or []
        ),
        "preservation_capability_status": capability_status,
        "spatial_authority": deepcopy(spatial),
        "hard_preservation_claimed": False,
        "render_executed": False,
    }
    return sentences, handoff


def decision_instruction_block(decision):
    """Bounded instruction block derived ONLY from an existing V8 decision.

    This is a projection, not a second reasoning pass: it reads the decision's
    own targets, fixed elements, uncertainty and knowledge and states them as
    constraints. It never re-interprets the user request, and it emits nothing
    for a decision that does not authorise execution.

    Returns a ``RenderConstraintBlockV1`` dict, or ``""`` when there is nothing
    to say. The empty string keeps every legacy payload byte-identical.
    """

    if not isinstance(decision, dict):
        return ""

    if decision.get("contract") != CONTRACT:
        return ""

    if not decision.get("decision_layer"):
        return ""

    status = decision.get("execution_status")

    if status not in _EXECUTABLE_DECISION_STATUSES:
        return ""

    operation = (
        (decision.get("requested_operation") or {}).get("operation")
        if isinstance(decision.get("requested_operation"), dict)
        else None
    ) or "change"

    editable = [
        _display(item) for item in (decision.get("editable_elements") or [])
        if _display(item)
    ]

    if not editable:
        return ""

    fixed = [
        _display(item)
        for item in (
            (decision.get("fixed_constraints") or {}).get("elements") or []
        )
        if _display(item)
    ]

    sentences = [
        _OPERATION_INSTRUCTION.get(operation, _OPERATION_INSTRUCTION["change"])
        % ", ".join(editable)
    ]

    # ARCHITECTURAL_COMPLETION_RENDER_HANDOFF_V1 — consume the already-built
    # completion/preservation contract at the existing instruction owner. The
    # textual constraints enter before optional knowledge and uncertainty, and
    # the full provenance-bearing projection remains machine-readable on the
    # RenderConstraintBlockV1 payload. No spatial authority is inferred here.
    completion_sentences, completion_handoff = (
        _architectural_completion_instruction_handoff(decision)
    )
    sentences.extend(completion_sentences)

    # Subject/context separation: the element a target is mounted on is context
    # to keep, never a second removal target.
    context_sentences = []

    for item in decision.get("image_supported_context") or []:

        if not isinstance(item, dict):
            continue

        element = _display(item.get("element"))

        if element not in editable:
            continue

        for context_kind in item.get("context_kinds") or []:

            context_sentences.append(
                "The %s carrying the %s is mounting context and must be "
                "preserved, not removed." % (_display(context_kind), element)
            )

    sentences.extend(list(dict.fromkeys(context_sentences)))

    if fixed:
        # NEOCLASSICAL_LIVE_EVIDENCE_HANDOFF_V1 — BOUNDED, LABELLED LIST.
        #
        # MEASURED DEFECT: `_preserved_element_names` returns the analysis's
        # raw `element` strings. For the accepted source those are full model
        # sentences ("Ground floor is an open, column-only level", "Left half
        # of the upper four floors is faced with orange/tan brick", …), and
        # embedding all 18 of them produced a 666-character sentence that
        # pushed the block past the resolver's 2400-character budget. The
        # resolver then truncated on a sentence boundary and DROPPED the
        # authorised-addition boundary — the very sentence that keeps
        # decoration from becoming geometry drift.
        #
        # The block is a bounded instruction, not an evidence record: the full
        # list stays on the decision (`fixed_constraints.elements`) and in
        # `image_supported_context`. Here each entry is reduced to a short
        # label and the list is capped, which is the same bounding this block
        # already applies to human rules.
        sentences.append(
            "Preserve these image-observed elements exactly: %s."
            % ", ".join(
                _preserved_label(item)
                for item in fixed[:_MAX_PRESERVED_IN_BLOCK]
            )
        )

    knowledge = decision.get("applicable_knowledge") or {}

    if (
        isinstance(knowledge, dict)
        and operation in _KNOWLEDGE_BEARING_OPERATIONS
    ):
        _raw_style = "_".join(
            str(knowledge.get("canonical_style") or "").upper().split()
        )
        if _raw_style and _raw_style not in _KNOWLEDGE_SENTINELS:
            style = _display(knowledge.get("canonical_style"))
            sentences.append(
                "Use %s architectural knowledge as design guidance only; it is "
                "not evidence that those elements exist in the source image." % style
            )

            # ==================================================
            # FACADE_KNOWLEDGE_HANDOFF_V1 — THE KNOWLEDGE MUST REACH THE
            # PROMPT, NOT ONLY THE DECISION DICT.
            #
            # Carrying the resolved fields on `applicable_knowledge` while
            # this block still emitted the style name alone would have been a
            # no-op: this function is the ONLY path from the decision into the
            # executable instruction. So the two things a facade design
            # actually needs are stated here, and nothing else:
            #
            #   1. the SURFACE ASSIGNMENT — which kind of surface receives
            #      which finish. This is what makes soffits plaster and walls
            #      stone instead of one material across every surface.
            #   2. the AUTHORISED-ADDITION BOUNDARY — decoration is applied
            #      relief; the frame, openings, floor count and massing do not
            #      move. This is what separates an authorised addition from
            #      geometry drift.
            #
            # No element is enumerated here. The user's requested ornament is
            # carried by the prompt compiler from the user's own words; this
            # block must never be the thing that adds a pilaster.
            # ==================================================

            _surface_sentence = _surface_assignment_sentence(knowledge)

            if _surface_sentence:
                sentences.append(_surface_sentence)

            # NEOCLASSICAL_DESIGN_CHAT_ROUTE_V1 — the USER's own requested
            # ornament, in the compiler's own vocabulary. Without this the
            # real Chat route lost every requested element, because the
            # compiled prompt on that route is the edit-delta material
            # sentence, not the prompt compiler's instruction.
            _ornament_line = _ornament_sentence(
                decision.get("requested_ornament")
            )

            if _ornament_line:
                sentences.append(_ornament_line)

            # NEOCLASSICAL_FIRST_RENDER_FIX_V1 — the user's prohibitions, in the
            # instruction owner's own sentence form ("Do NOT include: …"), so a
            # brief that forbade arches/domes/sculptural ornament carries that
            # prohibition into the prompt instead of losing it.
            for _prohibition in decision.get("user_prohibitions") or []:
                sentences.append("Do NOT include: %s." % _prohibition)

            sentences.append(
                "Decorative elements are applied relief within the existing "
                "wall planes: the existing structural frame, the existing "
                "openings, the floor count and the building massing stay "
                "unchanged, and no structural member or new volume is added."
            )

    # FACADE_KNOWLEDGE_HANDOFF_V1 — a pure MATERIAL replacement gets no style
    # knowledge (the resolver returns UNKNOWN for it), but it still must not
    # carry the facade material onto surfaces that are not the facade. This is
    # a restriction, not an ornament, so it is safe on a material edit and it
    # closes the "stone on the soffits" defect at the instruction level.
    if operation == "replace_finish":
        sentences.append(
            "Apply the finish to the facade wall surface only; the exposed "
            "slab soffits, the glazing, the site paving and the boundary walls "
            "are separate surfaces and do not receive the facade material."
        )

    # Accepted human teaching is GUIDANCE with a preserved origin. It is never
    # presented as something observed in the image, and never as an override of
    # the constraints already stated above.
    #
    # NEOCLASSICAL_LIVE_EVIDENCE_HANDOFF_V1 — BUDGET-AWARE APPEND.
    #
    # MEASURED DEFECT: on the real route this block reached 2508 characters and
    # the resolver cut it at its 2400-character cap. The cut fell INSIDE the
    # ledger guidance, keeping "Accepted human architectural guidance (HL-008…)«…»."
    # and dropping the sentence that says it is guidance and not evidence — a
    # half-pair, which is worse than no pair. The architectural constraints
    # themselves (surface assignment, ornament, boundary) all fitted; it was
    # optional ledger content that pushed the block over.
    #
    # The block already states the policy "optional context is dropped before an
    # executable constraint". This applies it against the resolver's ACTUAL cap,
    # and drops a rule as a WHOLE unit so no half-pair can survive.
    _reserved = len(_design_decision_sentence(decision)) + 1

    for rule in (decision.get("applied_human_rules") or [])[:_MAX_RULES_IN_BLOCK]:

        if not isinstance(rule, dict):
            continue

        observation = str(rule.get("human_observation") or "").strip()

        if not observation:
            continue

        candidate = (
            "Accepted human architectural guidance (%s, %s): \u00ab%s\u00bb. "
            "Treat it as design guidance from a human teacher, not evidence of "
            "anything visible in the source image, and never as an override of "
            "the explicit constraints above."
            % (rule.get("id"), str(rule.get("modality") or "").lower(), observation)
        )

        if len(" ".join(sentences + [candidate])) + _reserved > _INSTRUCTION_BUDGET:

            break

        sentences.append(candidate)

    uncertainty = [
        str(item).strip() for item in (decision.get("remaining_uncertainty") or [])
        if str(item).strip()
    ] 

    uncertainty_sentence = ""

    if uncertainty:
        uncertainty_sentence = (
            "Remaining uncertainty: %s. Do not invent detail that is not visible "
            "in the source image." % "; ".join(uncertainty)
        )
        # Budget-aware: the uncertainty note is optional context and is dropped
        # whole if it would push the block past the resolver's cap.
        if (
            len(" ".join(sentences + [uncertainty_sentence])) + _reserved
            <= _INSTRUCTION_BUDGET
        ):
            sentences.append(uncertainty_sentence)
        else:
            uncertainty_sentence = ""

    # NOTE (R3_NIGHT_MATERIAL_FIDELITY_CPU_V1): the internal decision summary
    # below is prompt bookkeeping, not render guidance, and costs ~35 tokens.
    # Removing it was considered and REJECTED: an accepted contract
    # (`test_design_instruction_handoff_v8_1.py`) pins its presence, and the
    # saving is cosmetic. The material-fidelity work does not depend on it.
    sentences.append(_design_decision_sentence(decision))

    # Bounded: optional context is dropped before an executable constraint is.
    if uncertainty_sentence and len(" ".join(sentences)) > _MAX_BLOCK_CHARS:
        sentences.remove(uncertainty_sentence)

    block = " ".join(sentences)

    return {
        "contract": DECISION_INSTRUCTION_CONTRACT,
        "constraint_block": block,
        "english_instruction": block,
        "architectural_completion_handoff": completion_handoff,
        "provenance": {
            "decision_layer": decision.get("decision_layer"),
            "execution_status": status,
            "operation": operation,
            "editable_elements": list(decision.get("editable_elements") or []),
            "fixed_elements": list(
                (decision.get("fixed_constraints") or {}).get("elements") or []
            ),
            "render_executed": decision.get("render_executed"),
            "comfy_invoked": decision.get("comfy_invoked"),
            "architectural_completion_consumed": bool(completion_handoff),
            "preservation_capability_status": (
                completion_handoff.get("preservation_capability_status")
                if completion_handoff else None
            ),
        },
    }


def authority_note(authority):
    """One sentence stating what the instruction is allowed to do."""

    if not isinstance(authority, dict):
        return ""

    status = authority.get("status")

    if status == STATUS_CONFLICT:
        domains = ", ".join(sorted({c["domain"] for c in authority.get("conflicts") or []}))
        return (
            "The request asks to change %s, which the same request requires to stay "
            "unchanged; it has not been applied and needs clarification." % (domains or "a fixed element")
        )
    if status == STATUS_UNRESOLVED:
        return (
            "The requested geometric change could not be established from the "
            "instruction; no geometric authority has been granted."
        )
    if authority.get("authorized_domains"):
        return (
            "Explicitly authorised geometry change: %s. Every other fixed element remains protected."
            % ", ".join(authority["authorized_domains"])
        )
    if authority.get("suppressed_terms"):
        return (
            # EXACT_EDIT_SCOPE_RETENTION_V2 — this disclosure is an atomic,
            # complete sentence. RenderPromptResolver filters the generic tail
            # by comma-delimited segments; the former comma list could survive
            # only in fragments (measured node-206 ending: "material, colour")
            # when a later lighting segment conflicted with a material edit.
            # The authoritative delta already states the exact allowed material
            # scope, so this note must disclose only what was omitted.
            "Style vocabulary that would change fixed geometry has been omitted."
        )
    return ""


# ----------------------------------------------------------
# Preservation wording derived from the ACTUAL fixed domains
# ----------------------------------------------------------

_PRESERVE_PHRASES = {
    DOMAIN_ROOF: ["roof shape"],
    DOMAIN_MASSING: ["original building silhouette", "original massing",
                     "floor count", "wall positions", "proportions"],
    DOMAIN_OPENING: ["openings", "windows", "doors"],
    DOMAIN_CIRCULATION: ["terraces", "balconies", "stairs", "railings"],
    DOMAIN_CAMERA: ["camera angle", "perspective", "composition"],
}

_PRESERVE_ORDER = (DOMAIN_MASSING, DOMAIN_ROOF, DOMAIN_OPENING, DOMAIN_CIRCULATION, DOMAIN_CAMERA)

_PROHIBIT_PHRASES = {
    DOMAIN_MASSING: ["create a new building", "change volume", "add floors",
                     "remove floors", "move walls", "modify structural layout"],
    DOMAIN_ROOF: ["change the roof shape"],
    DOMAIN_OPENING: ["relocate windows or doors"],
    DOMAIN_CIRCULATION: ["remove terraces, balconies, stairs or railings"],
    DOMAIN_CAMERA: ["move the camera or perspective"],
}


def preserve_lists(authority):
    """Return (preserve_lines, prohibit_lines) for the ACTUAL fixed domains.

    With nothing authorised this reproduces the historical block, plus one
    correction: circulation (terraces, balconies, stairs, railings) is in
    `fixed_domains` for a default edit but was absent from the emitted text,
    so a day->night request preserved "openings" and "roof shape" while
    saying nothing about the balcony. The drift the night acceptance recorded
    — an ornate balcony replaced by a thin railing — happened in exactly that
    silent gap. The line is added only where circulation is actually fixed.
    """

    fixed = list(authority.get("fixed_domains") or [])
    authorized = list(authority.get("authorized_domains") or [])

    if not authorized:
        return (
            ["original building silhouette", "original massing", "floor count",
             "wall positions", "roof shape", "openings", "windows", "doors",
             "existing terraces, balconies, stairs and railings",
             "proportions", "camera angle", "perspective", "composition"],
            ["redesign the building", "create a new building", "change volume",
             "add floors", "remove floors", "move walls", "modify structural layout"],
        )

    preserve = []
    for domain in _PRESERVE_ORDER:
        if domain in fixed:
            preserve.extend(_PRESERVE_PHRASES[domain])

    prohibit = ["redesign any element outside the authorised scope"]
    for domain in _PRESERVE_ORDER:
        if domain in fixed:
            prohibit.extend(_PROHIBIT_PHRASES[domain])

    return preserve, prohibit
