# ==========================================================
# ArchitectOS Persian Architectural Language Understanding v1.0
#
# PHASE 2D-2 — PERSIAN ARCHITECTURAL LANGUAGE UNDERSTANDING
#
# raw_text -> 2D-1 PersianNormalizer -> normalized_text
#          -> 2D-2 understanding -> Canonical Architectural
#             Change / Facade Semantic Intent  (STOPS HERE)
#
# Deterministic phrase/ontology layer first.  Optional, injected LLM
# enrichment may fill EMPTY fields only; it can never overwrite a
# deterministic value.  No prompt generation.  No translation.  No image
# understanding.  No memory behaviour change.
# ==========================================================


from __future__ import annotations

import re

from core.cognition.persian_normalizer import persian_normalizer


CONTRACT = "PersianArchitecturalUnderstandingV1"
VERSION = "1.0"


# ==========================================================
# CONTRACT
# ==========================================================

class PersianArchitecturalUnderstandingV1(dict):
    """Versioned, dict-compatible canonical semantic intent (2D-2).

    Pure JSON-serialisable structure (str / bool / int / float / list / dict).
    """

    CONTRACT = CONTRACT
    VERSION = VERSION


# ==========================================================
# INTENSITY MAPPING (deterministic, fixed — no arbitrary numbers)
# ==========================================================

INTENSITY_SCALE = {
    "LOW": 0.25,
    "MEDIUM": 0.5,
    "HIGH": 1.0,
}


# ==========================================================
# LEXICONS  (order matters: more specific first)
# ==========================================================

STYLE_TERMS = (
    # VISUAL_KNOWLEDGE_INTEGRATION_COMPLETION_V1 — these are existing
    # canonical ontology ids.  Specific regional/family names precede their
    # generic substrings so an explicit request is not reduced to
    # ``traditional`` / ``classic`` / no style at all.
    ("iranian_brick", (
        "آجر قزاقی", "آجرقزاقی", "نمای آجری ایرانی", "آجرکاری ایرانی",
        "qazaghi brick", "qazaqi brick", "iranian brick", "persian brick",
    )),
    ("iranian_traditional", (
        "سنتی ایرانی", "معماری ایرانی", "iranian traditional",
        # BENCHMARK_V1 — the natural English word order is "traditional
        # Iranian", which the table did not carry, so an explicit Iranian
        # request fell through to the bare "traditional" token and then to the
        # compiler's classical default.
        "traditional iranian", "iranian traditional architecture",
        "persian architecture", "iranian architecture",
    )),
    ("islamic_architecture", ("معماری اسلامی", "islamic architecture")),
    ("beaux_arts", ("بوزار", "beaux arts", "beaux-arts")),
    ("second_empire", ("امپراتوری دوم", "هوسمان", "second empire", "haussmann")),
    ("french_provincial", ("پروانس", "روستایی فرانسه", "french provincial", "provencal")),
    ("french_classical", ("کلاسیک فرانسوی", "نمای فرانسوی", "french classical")),
    # KNOWLEDGE_RUNTIME_CONNECTION_V2 — the ontology keys this family as
    # "roman_classic", but the table only had a bare "roman" entry AFTER the
    # generic "classic" one, so "Roman classic style" matched "classic" first
    # and the canonical roman_classic record was never reached. Specific
    # family evidence precedes the generic classic term.
    ("roman_classic", (
        "roman classic", "Roman classic", "roman classical", "Roman classical",
        "roman-classic", "Roman-classic",
        "کلاسیک رومی", "رومی کلاسیک", "رومي کلاسيک",
    )),
    ("neoclassical", ("نئوکلاسیک", "نوکلاسیک", "neoclassic", "neo classic", "neo-classic")),
    ("modern_classic", ("مدرن کلاسیک", "مدرن‌کلاسیک", "modern classic")),
    ("minimal", ("مینیمال", "مینیمالیستی", "minimal")),
    ("modern", ("مدرن", "معاصر", "modern", "contemporary")),
    ("classic", ("کلاسیک", "classic")),
    ("roman", ("رومی", "roman")),
    ("traditional", ("سنتی", "traditional")),
    ("industrial", ("صنعتی", "industrial")),
    ("luxury", ("لاکچری", "لوکس", "luxury", "luxurious")),
    ("simple", ("ساده", "simple", "plain")),
)

# Styles whose comparative form means "reduce complexity" rather than
# "more of this style".
_COMPLEXITY_REDUCING_STYLES = ("simple", "minimal")

MATERIAL_TERMS = (
    ("travertine", ("تراورتن", "travertine")),
    ("white_cement", ("سیمان سفید", "white cement")),
    ("light_color", ("رنگ روشن", "light color")),
    ("dark_color", ("رنگ تیره", "dark color")),
    # KNOWLEDGE_RECOVERY_01 — SPECIFIC MATERIAL NAMES MUST BE TESTED BEFORE
    # THE GENERIC HEAD NOUNS they are built on. `_match_lexicon` consumes
    # matched spans in table order, so "آجر نسوز" has to reach fire_brick
    # before the generic "آجر" can claim it. Canonical names are the
    # existing material-ontology identifiers.
    ("marble", ("سنگ مرمر", "مرمر", "marble")),
    ("natural_stone", ("سنگ طبیعی", "natural stone")),
    # ARCHITECTURAL_REQUEST_FIDELITY_REPAIR_V1 — `limestone` was not in the
    # lexicon at all, so the generic head noun "stone" claimed it and the
    # request "limestone facade" compiled to "Use natural stone." A named
    # material the user actually selected must not be silently generalized,
    # so the specific name is tested BEFORE the generic head noun it is built
    # on (same ordering rule as the brick entries below).
    ("limestone", ("سنگ آهک", "سنگ اهک", "limestone")),
    ("traditional_brick", (
        "آجر قزاقی", "آجرقزاقی", "qazaghi brick", "qazaqi brick",
    )),
    ("glazed_tile", (
        "کاشی‌کاری", "کاشی کاری", "کاشیکاری", "glazed tilework",
        "architectural tilework",
    )),
    ("fire_brick", ("آجر نسوز", "نسوز", "fire brick", "firebrick",
                    "refractory brick")),
    ("red_brick", ("آجر قرمز", "red brick")),
    ("stone", ("سنگ", "stone")),
    ("brick", ("آجر", "brick")),
    ("wood", ("ترمووود", "چوب", "wood", "timber")),
    ("metal", ("فلز", "metal", "steel")),
    ("glass", ("شیشه", "glass")),
    ("concrete", ("بتن", "concrete")),
)

TONE_TERMS = (
    ("light", ("روشن", "روشن‌تر", "روشنتر", "light", "lighter", "سفید")),
    ("dark", ("تیره", "تیره‌تر", "تیرهتر", "dark", "darker", "سیاه")),
    ("cream", ("کرم", "cream")),
    ("warm", ("گرم", "warm")),
)

# element term -> canonical target token
TARGET_TERMS = (
    ("window_frame", ("قاب پنجره", "قاب‌ها", "قاب", "window frame", "frame", "فریم")),
    ("facade", ("نما", "نمای", "facade", "façade")),
    ("massing", ("حجم", "massing")),
    ("windows", ("پنجره", "window", "windows")),
    ("balconies", ("بالکن", "بالکن‌ها", "balcony", "balconies")),
    ("entrance", ("ورودی", "ورودی‌ش", "ورودیش", "entrance", "entry")),
    ("arches", ("قوس", "قوس‌ها", "قوسها", "arch", "arches")),
    ("ornament", ("تزئینات", "تزیینات", "ornament", "decoration")),
    ("rhythm", ("ریتم", "rhythm")),
    ("depth", ("عمق", "depth")),
    ("floors", ("طبقات", "طبقه", "floor", "floors", "story")),
    ("structure", ("سازه", "structure")),
    ("geometry", ("هندسه", "geometry")),
    ("plan", ("پلان", "plan")),
    ("materials", ("متریال", "متریالش", "material", "materials")),
)

# preserve field mapping (target token -> preserve constraint field)
_PRESERVE_FIELD = {
    "facade": "facade",
    "massing": "massing",
    "windows": "windows",
    "balconies": "balconies",
    "entrance": "entrance_location",
    "arches": "arches",
    "floors": "floor_count",
    "structure": "structure",
    "geometry": "geometry",
    "plan": "geometry",
    "materials": "material",
    "style": "style",
    "window_frame": "openings",
}

# Terms meaning "the building itself" -> preserve massing + geometry.
_WHOLE_BUILDING_TERMS = ("خود ساختمون", "خود ساختمان", "خود بنا", "خود پلان", "ساختمون", "ساختمان", "بنا")

# --- preserve patterns (negative imperative / keep) ---
#
# FACADE-04D.3C-9P-A — the ORIGINAL list only matched a VERB-INTERNAL negation
# ("تغییر ... نکن", "دست نزن"). A user who writes the prepositional construction
# "بدون تغییر" ("without changing") — extremely common — was therefore never
# understood as requesting preservation, so no preserve slot was produced and
# the fidelity gate silently had nothing to check. The two patterns below close
# that gap. They are additive: every original pattern is retained unchanged.
#
# These patterns only OPEN the preserve branch. WHICH field is preserved is
# still decided by the clause-scoped target scan in `_detect_preserve()`, so a
# bare "بدون تغییر" with no named target stays scope-unspecified and never
# fabricates a window/opening/floor constraint.
_PRESERVE_PATTERNS = (
    r"دست\s*نزن",
    r"دست\s*نزنید",
    r"(تغییر|عوض|جابه\s*جا|جابجا|کپی|حرکت)\s*ن(کن|کنه|کنید|کنن|دن|ده|دین|شه|شن|شود|شوند)",
    r"(بمونه|بمونن|بماند|بمانند|بمون)",
    r"(همین|همون)\s*(باشه|بمونه|بمونن)",
    r"(نگه\s*دار|نگهدار|حفظ\s*(کن|کنه|بشه|بشود)|ثابت\s*بمونه)",
    # "بدون تغییر" / "بدون تغییر در ..." / "without changing ..."
    r"بدون\s*تغییر",
    # "بدون جابه‌جایی" / "بدون جابجایی ..." (no relocation)
    r"بدون\s*جابه[\s\u200c]*جایی",
    r"بدون\s*جابجایی",
    r"without\s+(changing|change|altering|alteration|modifying|modification|moving|relocation)",
)

# FACADE-04D.3C-9P-A — the "without change" family in Persian and English. A
# preservation clause opened by one of these is parsed for its NAMED target
# only (window/opening/floor); the noun must sit in the SAME clause.
_NO_CHANGE_PREFIXES = (
    "بدون تغییر", "بدون تغییر در", "بدون هیچ تغییری", "بدون هیچ تغییر",
    "بدون جابه جایی", "بدون جابجایی", "بدون جابه‌جایی",
    "without changing", "without change", "without altering", "without modifying",
)

# Clause boundaries for Persian and English: sentence punctuation, the Persian
# comma, and the contrastive conjunctions that start a NEW instruction.
_CLAUSE_BOUNDARY = re.compile(
    r"[.،,؛;!؟?\n]|(?:\bولی\b)|(?:\bاما\b)|(?:\bhowever\b)|(?:\bbut\b)",
    re.IGNORECASE,
)

# Target nouns that may follow a "without change" prefix. Aliasing to the
# canonical preserve FIELD keeps position/shape distinguishable: only the
# POSITION noun maps to a position-preserving field.
_NO_CHANGE_TARGETS = (
    ("طبقات", "floor_count"), ("طبقه", "floor_count"),
    ("تعداد طبقات", "floor_count"),
    ("مکان پنجره‌ها", "windows"), ("مکان پنجره ها", "windows"), ("مکان پنجره", "windows"),
    ("جای پنجره‌ها", "windows"), ("جای پنجره ها", "windows"), ("جای پنجره", "windows"),
    ("موقعیت پنجره‌ها", "windows"), ("موقعیت پنجره ها", "windows"), ("موقعیت پنجره", "windows"),
    ("پنجره‌ها", "windows"), ("پنجره ها", "windows"), ("پنجره", "windows"),
    ("بازشوها", "openings"), ("بازشو", "openings"),
    ("نورگیر", "openings"),
    ("windows", "windows"), ("window", "windows"),
    ("openings", "openings"), ("opening", "openings"),
    ("doors", "openings"), ("door", "openings"),
    ("شناسه بازشو", "openings"),
    ("floors", "floor_count"), ("floor", "floor_count"),
    ("storeys", "floor_count"), ("storey", "floor_count"),
    ("number of floors", "floor_count"),
)

# Colour / finish / appearance nouns that must NOT be read as window/openings
# preservation even if they sit inside a "without change" clause
# ("بدون تغییر در رنگ نما" must not become preserve_windows=True).
_NO_CHANGE_NON_GEOMETRY = (
    "رنگ", "رنگ نما", "رنگ‌بندی", "رنگ بندی", "متریال", "متریال نما",
    "بافت", "تم", "نورپردازی", "تزئینات", "تزیینات",
    "colour", "color", "material", "texture", "finish", "lighting",
)

# FACADE-04D.3C-9P-A — a CHANGE verb that turns a noun into a modification
# target, so "پنجره جدید اضافه کن" is NOT a preservation request.
_CHANGE_ARG_PREFIXES = (
    "جدید", "اضافه", "حذف", "جایگزین", "کپی",
    "new", "add", "remove", "delete", "replace", "copy",
)

# --- modification (replace) patterns ---
#
# FACADE-COORDINATION-CONSISTENCY_V1 — the removal branch used to live here,
# so "در را حذف کن و پنجره اضافه کن" became `replace(windows)`: the removal
# was relabelled as a replacement, and attributed to the OTHER element in the
# sentence. Removal is now resolved on its own, clause-scoped, as `remove`.
_REPLACE_PATTERNS = (
    r"(تغییر|عوض|جابه\s*جا|جابجا)\s*(بده|بدید|کن|کنید|کنه|شه|شود)",
    r"جایگزین",
)

# --- removal patterns and the element they can name ---
#
# FACADE-COORDINATION-CONSISTENCY_V1 — a removal is an instruction about the
# element in ITS OWN clause. The table is deliberately local and small: it is
# not the global target lexicon (whose Persian "در" would match inside
# ordinary words), and it never promotes an element to a change scope.
_REMOVAL_VERB = re.compile(
    r"(?:بردار|حذف)\s*(?:کن|کنه|کنید|کنن)|"
    r"\b(?:remove|delete)\b",
    re.IGNORECASE,
)

#: Each entry is a regex, not a substring. Persian "در" also occurs inside
#: ordinary words ("مدیر", "دریچه"), so the door form requires a boundary — the
#: noun must stand alone ("در را", "در چوبی", "در،").
_REMOVAL_TARGETS = (
    ("windows", r"پنجره|(?<![A-Za-z])windows?(?![A-Za-z])"),
    ("doors", r"(?<![\w؀-ۿ])در(?![؀-ۿ])"
              r"|(?<![A-Za-z])doors?(?![A-Za-z])"),
    ("railings", r"نرده|جان‌پناه|جانپناه"
                 r"|(?<![A-Za-z])(?:railings?|parapets?)(?![A-Za-z])"),
)

#: Clause boundaries for the removal scan. A removal names one element; the
#: coordinated element that follows a different verb is not that element.
_REMOVAL_CLAUSE_BOUNDARY = re.compile(r"[.،,؛;!؟?\n]|\bو\b|\band\b", re.IGNORECASE)

# --- negative quality terms -> constraint token ---
_QUALITY_NEGATION = (
    ("رومی", "avoid_excessive_roman_style", "roman"),
    ("roman", "avoid_excessive_roman_style", "roman"),
    ("کلاسیک", "avoid_excessive_classical_style", "classic"),
    ("classic", "avoid_excessive_classical_style", "classic"),
    ("شلوغ", "avoid_heavy_ornament", "ornament"),
    ("تزئینات", "avoid_excessive_ornament", "ornament"),
    ("تزیینات", "avoid_excessive_ornament", "ornament"),
    ("قوس", "avoid_excessive_arches", "arches"),
    ("arch", "avoid_excessive_arches", "arches"),
    ("شیشه", "avoid_excessive_glass", "glass"),
    ("glass", "avoid_excessive_glass", "glass"),
    ("فلز", "avoid_dominant_metal", "metal"),
    ("metal", "avoid_dominant_metal", "metal"),
    ("لوکس", "avoid_excessive_luxury", "luxury"),
    ("luxury", "avoid_excessive_luxury", "luxury"),
)

_NEG_MARKERS = (
    "نشه", "نباشه", "نباشن", "نداشته باشه", "نداشته باشن",
    "نکن", "نکنه", "نکنید", "نشود", "نباشد", "نمیخوام", "نمی خوام",
)

# --- intensity ---
_LOW_MARKERS = ("یه کم", "یه‌کم", "یه ذره", "یه‌ذره", "یه خرده", "کمی", "ملایم", "آروم", "آرام", "خیلی کم")
_HIGH_MARKERS = ("خیلی", "بسیار", "زیاد", "شدید", "کلی", "حسابی", "کاملاً", "کاملا")
_DECREASE_MARKERS = ("کمتر", "کم کن", "کمش کن", "کاهش", "بیشتر نکن")
_INCREASE_MARKERS = ("بیشتر", "افزایش", "ترش کن", "تر کن", "تر باشه", "تر شه")

# --- vague modifiers that require an architectural target ---
_VAGUE_MODIFIERS = ("بهتر", "خوب‌تر", "خوبتر", "شیک‌تر", "شیکتر", "قشنگ‌تر", "قشنگتر", "جذاب‌تر", "جذابتر", "باحال‌تر", "باحالتر")
_TARGETED_EMPHASIS = ("قوی‌تر", "قویتر", "شاخص‌تر", "شاخصتر", "برجسته‌تر", "برجستهتر")

# --- reference image words ---
_IMAGE_WORDS = ("عکس", "تصویر", "رفرنس", "reference", "image", "photo")


# ==========================================================
# LIVE_HANDOFF_V1 — element needles are matched at a WORD boundary.
#
# The element table used plain substring matching, so the needle "arch"
# matched "ARCHITECTOS" and "architectural". Every facade request therefore
# carried a REQUIRED "arches" element that the user never asked for, and the
# geometry analyzer independently read the same substring as an authorized
# OPENING change. Matching at a word start with an optional plural keeps
# "arch"/"arches"/"column"/"columns" and refuses "architectural".
# ==========================================================

_ELEMENT_NEEDLE_CACHE = {}


# "IMAGE A", "IMAGE B", "image b." — an explicit role label on an attachment.
_REFERENCE_ROLE_LABEL_RE = re.compile(r"(?<![a-z0-9])image\s+[ab](?![a-z0-9])", re.I)

# "Do not copy ... as new volumes" — the user's own prohibition on taking the
# reference's GEOMETRY. Only the words the user wrote are mapped onto the
# existing canonical element vocabulary.
_DO_NOT_COPY_RE = re.compile(r"do\s+not\s+copy\b([^.]*)", re.I)


def _element_needle_re(needle):
    pattern = _ELEMENT_NEEDLE_CACHE.get(needle)
    if pattern is None:
        pattern = re.compile(
            r"(?<![a-z0-9])" + re.escape(str(needle)) + r"(?:s|es)?(?![a-z0-9])"
        )
        _ELEMENT_NEEDLE_CACHE[needle] = pattern
    return pattern


# ==========================================================
# ENGINE
# ==========================================================

class PersianArchitecturalUnderstandingEngine:

    VERSION = VERSION

    def __init__(self):
        print("🧩 PERSIAN ARCHITECTURAL UNDERSTANDING v1.0 ONLINE (deterministic)")

    # ------------------------------------------------------
    # low-level helpers
    # ------------------------------------------------------

    @staticmethod
    def _has(text, phrase):
        return phrase in text

    @staticmethod
    def _match_lexicon(text, lexicon):
        """Return [(canonical, phrase), ...] matching in order, consuming spans."""
        remaining = text
        matches = []
        for canonical, phrases in lexicon:
            for phrase in phrases:
                if phrase in remaining:
                    matches.append((canonical, phrase))
                    remaining = remaining.replace(phrase, " ")
                    break
        return matches

    @staticmethod
    def _is_comparative_increase(text, phrase):
        pattern = re.escape(phrase) + r"[\u200c\s]*تر"
        return re.search(pattern, text) is not None

    @staticmethod
    def _is_comparative_decrease(text, phrase):
        escaped = re.escape(phrase)
        if re.search(r"کمتر[\s\u200c]*" + escaped, text):
            return True
        if re.search(escaped + r"[\s\u200c]*(کمتر|کم)", text):
            return True
        return False

    # ------------------------------------------------------
    # NEGATIVE CONSTRAINTS
    # ------------------------------------------------------

    def _detect_negatives(self, text):
        """Return (constraints, negated_terms)."""
        constraints = []
        negated = set()

        for marker in _NEG_MARKERS:
            start = 0
            while True:
                idx = text.find(marker, start)
                if idx == -1:
                    break
                window = text[max(0, idx - 25):idx]
                for term, token, target in _QUALITY_NEGATION:
                    if term in window:
                        strong = any(q in window for q in _HIGH_MARKERS)
                        constraints.append({
                            "constraint": token,
                            "target": target,
                            "term": term,
                            "intensity": "HIGH" if strong else "MEDIUM",
                        })
                        negated.add(term)
                start = idx + len(marker)

        # de-duplicate constraints
        unique = []
        seen = set()
        for item in constraints:
            key = (item["constraint"], item["target"])
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique, negated

    # ------------------------------------------------------
    # PRESERVE
    # ------------------------------------------------------

    def _no_change_clause_fields(self, text):
        """FACADE-04D.3C-9P-A — clause-scoped parse of the "without change" family.

        Returns the set of preserve FIELDS named directly by a `بدون تغییر`
        ("without changing") clause. Only nouns sitting in the SAME clause as
        the prefix count, so the parse is not confused by a window mentioned
        elsewhere in the request. Position nouns map to the position field;
        a change-verb construction ("پنجره جدید اضافه کن") is never read as
        preservation; and colour/finish nouns ("بدون تغییر در رنگ نما") map to
        nothing geometric.
        """

        fields = set()

        clauses = _CLAUSE_BOUNDARY.split(text)

        for clause in clauses:

            lowered = clause.lower()

            prefix_hit = None

            for prefix in _NO_CHANGE_PREFIXES:

                if prefix in clause or prefix in lowered:

                    prefix_hit = prefix

                    break

            if not prefix_hit:

                continue

            # a clause that also carries a change-verb construction is NOT a
            # preservation instruction ("بدون تغییر ... پنجره جدید اضافه کن"
            # is contradictory; the change verb wins and nothing is preserved)
            if any(v in clause or v in lowered for v in _CHANGE_ARG_PREFIXES):

                continue

            named = set()

            for noun, field in _NO_CHANGE_TARGETS:

                if noun in clause or noun in lowered:

                    named.add(field)

            if not named:

                continue

            # A colour / finish / material noun is appearance, not geometry:
            # "بدون تغییر در رنگ نما" must not preserve windows or openings.
            # Geometry nouns (window/opening/floor) in the SAME clause do count.
            geometry_named = set()

            for noun, field in _NO_CHANGE_TARGETS:

                if field not in ("windows", "openings", "floor_count"):

                    continue

                if noun in clause or noun in lowered:

                    for non_geom in _NO_CHANGE_NON_GEOMETRY:

                        # skip a window/opening noun that is really the object
                        # of an appearance phrase ("رنگ پنجره" = window colour)
                        if non_geom + " " + noun in clause:

                            break

                    else:

                        geometry_named.add(field)

            for field in geometry_named:

                fields.add(field)

        return fields

    @staticmethod
    def _detect_removals(text):
        """The elements the user asked to REMOVE, resolved clause by clause.

        A removal verb governs only the element in its own clause. In
        "در را حذف کن و پنجره اضافه کن" the door is removed and the window is
        added; the two never share a target.
        """

        removed = []

        for clause in _REMOVAL_CLAUSE_BOUNDARY.split(text):

            if not clause or not _REMOVAL_VERB.search(clause):
                continue

            for canonical, pattern in _REMOVAL_TARGETS:

                if re.search(pattern, clause):
                    if canonical not in removed:
                        removed.append(canonical)
                    break

        return removed

    def _detect_preserve(self, text, targets, changed_targets=()):
        matched = any(re.search(p, text) for p in _PRESERVE_PATTERNS)
        if not matched:
            return {"explicit": False}, False

        changed_targets = set(changed_targets or ())

        preserve = {
            "massing": False,
            "floor_count": False,
            "windows": False,
            "openings": False,
            "balconies": False,
            "entrance_location": False,
            "structure": False,
            "geometry": False,
            "material": False,
            "style": False,
            "facade": False,
            "arches": False,
            "reference_geometry": False,
            "explicit": True,
        }

        any_target = False

        # FACADE-04D.3C-9P-A — every preserve field is resolved CLAUSE-SCOPED.
        # A target noun (or a whole-building term) only preserves when it sits
        # in a clause that itself carries a preserve signal. Otherwise the
        # request "نمای این ساختمان ... بازطراحی کن" would wrongly preserve the
        # facade/massing merely because it names the building.
        preserve_clauses = self._preserve_clauses(text)

        scoped = " ".join(preserve_clauses)

        for target in targets:
            if target in changed_targets:
                # a target being modified cannot simultaneously be preserved
                continue
            field = _PRESERVE_FIELD.get(target)
            if field and self._target_in_preserve_clause(target, preserve_clauses):
                preserve[field] = True
                any_target = True

        # FACADE-04D.3C-9P-A — the clause-scoped "without change" parse. A
        # named target wins even when the modifier/verb scan above did not
        # recognise the request (e.g. "بدون تغییر در مکان پنجره‌ها").
        #
        # NOTE: this direct, user-scoped statement is NOT filtered by
        # `changed_targets`. "بدون تغییر در مکان پنجره‌ها، شکل پنجره‌ها را عوض کن"
        # preserves POSITION while the user separately changes STYLE — the two
        # are different attributes and must be able to coexist.
        for field in self._no_change_clause_fields(text):

            preserve[field] = True

            any_target = True

        if any(term in scoped for term in _WHOLE_BUILDING_TERMS):
            preserve["massing"] = True
            preserve["geometry"] = True
            any_target = True

        preserve["scope_unspecified"] = not any_target
        return preserve, True

    def _preserve_clauses(self, text):
        """The clauses that actually carry a preserve signal.

        A clause qualifies when it matches a `_PRESERVE_PATTERNS` entry OR
        contains a "without change" prefix. Everything else is ignored, so a
        noun mentioned in an ordinary instruction never becomes a preserve
        constraint.
        """

        out = []

        for clause in _CLAUSE_BOUNDARY.split(text):

            if any(re.search(p, clause) for p in _PRESERVE_PATTERNS):

                out.append(clause)

                continue

            lowered = clause.lower()

            if any(prefix in clause or prefix in lowered for prefix in _NO_CHANGE_PREFIXES):

                out.append(clause)

        return out

    def _scope_is_only_preserved(self, text, scope):
        """True when every clause naming `scope` is a pure preservation statement.

        A scope promoted from the target scan is not automatically a changed
        target. "پنجره‌ها را حفظ کن و در چوبی اضافه کن" mentions the window
        only to protect it; the change in that turn is the material. Treating
        the window as changed there silently dropped the user's preserve.

        A clause that names the scope AND carries a change verb still counts as
        a change — "پنجره‌ها را تغییر بده" and "فقط نما مدرن‌تر شه" are
        modifications, so the promotion stands and they are scoped normally.
        """

        naming = self._clauses_naming(scope, text)
        if not naming:
            return False

        for clause in naming:
            lowered = clause.lower()
            if any(re.search(p, clause) for p in _REPLACE_PATTERNS):
                return False
            if any(prefix in clause or prefix in lowered for prefix in _CHANGE_ARG_PREFIXES):
                return False
            if any(marker in clause for marker in _INCREASE_MARKERS):
                return False
            if any(marker in clause for marker in _DECREASE_MARKERS):
                return False
            if any(marker in clause for marker in _TARGETED_EMPHASIS):
                return False

        return True

    @staticmethod
    def _clauses_naming(target, text):
        """The clauses of `text` that name `target` by one of its own phrases.

        Split on `و` as well: coordination joins two independent instructions
        ("پنجره‌ها را حفظ کن و در چوبی اضافه کن"), and the add verb of the
        second must not be read as a change to the element of the first.
        """

        phrases = next((p for c, p in TARGET_TERMS if c == target), ())
        return [
            clause for clause in _REMOVAL_CLAUSE_BOUNDARY.split(text)
            if any(phrase in clause for phrase in phrases)
        ]

    @staticmethod
    def _target_in_preserve_clause(target, preserve_clauses):
        """True when a target TOKEN's phrases appear inside a preserve clause."""

        for canonical, phrases in TARGET_TERMS:

            if canonical != target:

                continue

            for phrase in phrases:

                for clause in preserve_clauses:

                    if phrase in clause:

                        return True

        return False

    # ------------------------------------------------------
    # REFERENCE IMAGE POLICY (text only — no image understanding)
    # ------------------------------------------------------

    def _detect_reference(self, text):
        has_image_word = any(w in text for w in _IMAGE_WORDS)
        # REFERENCE_TRANSFER_POLICY_V1 — `_IMAGE_WORDS` already carries English
        # nouns ("reference", "image", "photo"), but the demonstrative test was
        # Persian-only, so an English request such as "apply the style of the
        # reference facade to this building" produced `referenced: False` and
        # the reference was never recognised at all. The English markers are
        # the direct equivalents of این / مثل and still require an image noun,
        # so "make this building red" is unaffected.
        referenced = has_image_word and (
            "این" in text
            or "مثل" in text
            or "این عکس" in text
            or "this image" in text
            or "these images" in text
            or "these photos" in text
            or "this photo" in text
            or "this reference" in text
            or "the reference" in text
            or "reference image" in text
            # LIVE_HANDOFF_V1 — a request that ROLE-LABELS its attachments
            # ("IMAGE A — TARGET BUILDING", "IMAGE B — STYLE & MATERIAL
            # REFERENCE") is unambiguously reference-guided, yet none of the
            # demonstrative phrases above matched it, so `referenced` stayed
            # False and the whole reference contract was dropped. The label is
            # a stronger signal than a demonstrative, not a weaker one.
            or _REFERENCE_ROLE_LABEL_RE.search(text) is not None
        )

        policy = {
            "referenced": bool(referenced),
            "role": "none",
            "copy_reference_geometry": False,
            "preserve_base_geometry": False,
            "requires_image": bool(referenced),
        }

        if not referenced:
            return policy

        # role resolution (most specific first)
        #
        # REFERENCE_TRANSFER_POLICY_V1 — the English branches mirror the
        # Persian ones one-for-one; each still requires its explicit
        # qualifier ("only"/"take"/"use"), so a bare mention of materials is
        # not promoted to a transfer role.
        #
        # FACADE_MATERIAL_TRANSFER_ENGINE_DIAGNOSIS_V1 — the `material_only`
        # test ran FIRST and fires on `"material" in text and "use" in text`.
        # The real request says "Use IMAGE B only for style, material, surface
        # rhythm, color and decorative inspiration", so the single word
        # "material" captured the role and the explicit STYLE instruction was
        # discarded. The prompt then carried "Use the reference image only as a
        # material/finish reference" — the reference could no longer inform
        # style, rhythm or detailing, which is precisely what the render failed
        # to deliver.
        #
        # `material_only` is now reserved for a request that asks for material
        # and NOT for style. A request naming both resolves to `style_only`,
        # which is a TRANSFER role (dual_image_conditioning_v1
        # TRANSFER_REFERENCE_ROLES) — `inspiration_only` is not, and selecting
        # it would block the conditioned route entirely. Material is not lost:
        # it is stated in the user's own request and carried by the resolved
        # facade knowledge, independently of the reference role.
        _material_requested = (
            ("متریال" in text and ("فقط" in text or "بگیر" in text or "بردار" in text))
            or ("material" in text and ("only" in text or "take" in text or "use" in text))
        )
        _style_requested = ("سبک" in text or "style" in text)
        _inspiration_requested = ("الهام" in text or "inspiration" in text)
        _composition_requested = ("ترکیب" in text or "composition" in text)

        if _material_requested and not _style_requested:
            policy["role"] = "material_only"
        elif _composition_requested:
            policy["role"] = "composition_only"
        elif _style_requested:
            policy["role"] = "style_only"
        elif _inspiration_requested:
            policy["role"] = "inspiration_only"
        else:
            policy["role"] = "inspiration_only"

        # geometry copy / preservation
        if "کپی" in text and not re.search(r"کپی\s*ن", text):
            policy["copy_reference_geometry"] = True

        if "هندسه" in text and ("حفظ" in text or "خودم" in text or "خودمون" in text or "خود ساختمون" in text):
            policy["preserve_base_geometry"] = True

        # LIVE_HANDOFF_V1 — an APPEARANCE-ONLY transfer takes appearance FROM
        # the reference and never its geometry. The base building is therefore
        # preserved by construction, and the compiler's surface-only contract
        # must know that. Previously `preserve_base_geometry` was set ONLY by
        # the Persian "هندسه ... حفظ" branch, so every English facade transfer
        # compiled with the old "structurally supported" element sentence.
        if policy["role"] in ("style_only", "material_only", "inspiration_only"):
            if not policy["copy_reference_geometry"]:
                policy["preserve_base_geometry"] = True

        # The reference's own geometric vocabulary must never become a
        # REQUIRED element of the target building.
        policy["do_not_copy"] = self._detect_do_not_copy(text)

        return policy

    def _detect_do_not_copy(self, text):
        """Canonical element names the user forbade copying from the reference."""

        found = []

        for match in _DO_NOT_COPY_RE.finditer(str(text or "")):

            clause = " " + match.group(1).lower() + " "

            for canonical, needles in self._ELEMENT_TERMS:

                if canonical in found:

                    continue

                if any(_element_needle_re(needle).search(clause) for needle in needles):

                    found.append(canonical)

        return found

    # ------------------------------------------------------
    # INTENSITY
    # ------------------------------------------------------

    def _detect_intensity(self, text):
        evidence = []
        level = "MEDIUM"

        if any(m in text for m in _LOW_MARKERS):
            level = "LOW"
            evidence.append("low_marker")
        elif any(m in text for m in _HIGH_MARKERS):
            level = "HIGH"
            evidence.append("high_marker")

        return {"level": level, "value": INTENSITY_SCALE[level], "evidence": evidence}

    # ------------------------------------------------------
    # SCOPE
    # ------------------------------------------------------

    def _detect_scope(self, text, targets):
        if "فقط" in text:
            for token, phrases in TARGET_TERMS:
                for phrase in phrases:
                    if phrase in text and "فقط" in text[max(0, text.find(phrase) - 12):text.find(phrase)]:
                        return token
            # "فقط" present but no explicit target after it
        if "نما" in text and "فقط" in text:
            return "facade"
        if "پلان" in text or "خود ساختمون" in text or "خود ساختمان" in text:
            return "whole_building"
        if len(targets) == 1:
            return targets[0]
        if targets:
            return "whole_building"
        return "unknown"

    # ------------------------------------------------------
    # NEOCLASSICAL_DESIGN_CHAT_ROUTE_V1
    #
    # A request that designs the FACADE of an EXISTING building states its
    # preservation clause in the same sentence:
    #
    #   "…Preserve the existing structural frame, original floor count,
    #    opening positions, ground-floor openness, massing and camera
    #    perspective."
    #
    # Every noun in that clause was counted as a CHANGE TARGET, so `targets`
    # became [facade, floors, massing, window_frame] and `_detect_scope` fell
    # back to "whole_building". The compiler then opened the prompt with
    # "Apply the changes to the overall building composition." — for a request
    # that only asks to re-treat the facade.
    #
    # A PRESERVATION clause is not a set of change targets. These two
    # predicates keep the correction narrow: a real style must be requested,
    # the facade must be a target, and the request must refer to the building
    # as already existing.
    # ------------------------------------------------------

    _EXISTING_BUILDING_MARKERS = (
        "existing", "this building", "the building", "unfinished building",
        "current building", "renovat", "retrofit", "reclad", "re-clad",
        "ساختمان موجود", "این ساختمان", "بنای موجود", "بازسازی",
    )

    @classmethod
    def _refers_to_existing_building(cls, text):
        """True when the request treats the building as ALREADY EXISTING."""

        hay = " " + " ".join(str(text or "").lower().split()) + " "

        return any(marker in hay for marker in cls._EXISTING_BUILDING_MARKERS)

    @staticmethod
    def _named_style_target(style):
        """True when a real style is requested (not a sentinel)."""

        target = (style or {}).get("target") if isinstance(style, dict) else None

        token = str(target or "").strip().lower()

        return bool(token) and token not in ("unknown", "none", "existing")

    # ------------------------------------------------------
    # CLASSICAL_DETAIL_RETENTION_V1
    #
    # The understanding contract had no place to put element-level
    # architectural vocabulary, so "columns and capitals, carved cornices,
    # sculptural detailing, balustrades" survived only as a style and a
    # material. The compiler cannot emit what the contract cannot carry, so
    # the executable prompt lost them.
    #
    # These three detectors are deliberately narrow: they read ONLY words the
    # user actually wrote, map them onto existing canonical element names, and
    # never add an element the request did not name.
    # ------------------------------------------------------

    _ELEMENT_TERMS = (
        # FACADE_KNOWLEDGE_HANDOFF_V1 — pilasters were folded into "columns",
        # so "stone pilasters" compiled to "correctly proportioned classical
        # COLUMNS". A pilaster is a flat, wall-attached vertical member and a
        # column is a free-standing one; they are different architectural
        # elements with different construction implications, so the user's own
        # word is now carried as its own element.
        ("columns", ("column", "columns", "colonnade", "ستون")),
        ("pilasters", ("pilaster", "pilasters", "pilastered",
                       "نیم‌ستون", "نیم ستون")),
        ("capitals", ("capital", "capitals", "corinthian", "composite order", "سرستون")),
        # FACADE_KNOWLEDGE_HANDOFF_V1 — two neoclassical elements had no
        # channel at all, so a design brief naming them compiled to a style
        # line and lost them. Deliberately narrow needles: "surrounds" alone
        # would match "surrounding".
        ("stringcourses", ("stringcourse", "stringcourses",
                           "string course", "string courses")),
        ("window surrounds", ("window surround", "window surrounds",
                              "stone surround", "stone surrounds")),
        ("cornices", ("cornice", "cornices", "modillion", "dentil", "dentils", "قرنیز")),
        ("arches", ("arch", "arches", "arched", "arcade", "طاق", "قوس")),
        ("pediments", ("pediment", "pediments", "سنتوری")),
        ("balustrades", ("balustrade", "balustrades", "baluster", "balusters", "جان‌پناه")),
        # NEOCLASSICAL_DESIGN_CHAT_ROUTE_V1 — bare "carved"/"carving" removed.
        # "carved stone surrounds" is a WINDOW SURROUND request; the adjective
        # was being read as a separate request for sculptural relief, so a
        # design brief that asked for carved surrounds silently gained
        # "sculptural architectural relief carving".
        #
        # NEOCLASSICAL_FIRST_RENDER_FIX_V1 — bare "relief" removed for the same
        # reason. "Apply neoclassical architectural design elements as SURFACE
        # RELIEF within the existing wall planes only" is a statement about
        # applied decoration, but it matched the bare needle and produced a
        # positive request for sculptural carving — in a brief that explicitly
        # said "Do not add … sculptural ornament". The element is now
        # identified by its OWN noun ("sculptural relief", "relief carving",
        # "ornamental carving", "sculpture"), never by the bare word that
        # qualifies another element or describes a technique.
        ("sculptural relief", ("sculptural relief", "relief carving",
                               "ornamental carving", "sculpture", "sculptural",
                               "حجاری", "نقش‌برجسته")),
        ("quoins", ("quoin", "quoins", "rustication", "rusticated")),
    )

    # A clause that FORBIDS an element must never be read as a request for it.
    # The Iranian brief says "do not introduce classical Roman columns,
    # European balustrades" — without this, those exact words were emitted as
    # REQUIRED elements, which is the opposite of the instruction.
    # Markers carry a leading space and are matched against " " + clause, so a
    # marker can only match at a WORD START. Without that, the Persian "نه "
    # matched the tail of "بمونه" ("bemune" = "should stay") and a preservation
    # clause was discarded as a negation.
    _NEGATION_MARKERS = (
        " do not", " don't", " does not", " must not", " should not", " no ",
        " without", " avoid", " never", " instead of",
        " بدون", " نه ", " نکن", " نداشته",
    )

    def _positive_clauses(self, text):
        """The request with every negated clause removed.

        BENCHMARK_V1 — a forbidding clause names the very things it forbids.
        "do not introduce classical Roman columns, European balustrades" was
        being read as a REQUEST for classical columns and balustrades, which
        turned an Iranian brief into a classical one.
        """
        raw = " ".join(str(text or "").lower().split())
        kept = []
        for chunk in raw.replace(";", ".").split("."):
            clause = chunk.strip()
            if not clause:
                continue
            hay = " " + clause + " "
            if any(marker in hay for marker in self._NEGATION_MARKERS):
                continue
            kept.append(clause)
        return " " + " ".join(kept) + " "

    def _detect_elements(self, text):
        scanned = self._positive_clauses(text)
        found = []
        for canonical, needles in self._ELEMENT_TERMS:
            # LIVE_HANDOFF_V1 — the needles used to be matched with `in`, so
            # "arch" matched inside "ARCHITECTOS"/"architectural" and every
            # facade request silently acquired a REQUIRED "arches" element.
            # A word-start boundary plus an optional plural keeps "arches"
            # and "columns" while refusing "architectural".
            if any(_element_needle_re(needle).search(scanned) for needle in needles):
                found.append(canonical)
        return found

    _FULL_BUILDING_TERMS = (
        "complete", "entire", "whole building", "full-building", "full building",
        "uncropped", "no cropped", "roofline", "roof line", "within the frame",
        "in frame", "both floors", "entire facade", "whole facade",
        "ground level", "building edges", "entire building",
    )

    _DETAIL_ONLY_TERMS = (
        "close-up", "close up", "closeup", "detail shot", "detail study",
        "cropped detail",
    )

    def _detect_framing(self, text):
        lowered = " " + " ".join(str(text or "").lower().split()) + " "
        full = any(term in lowered for term in self._FULL_BUILDING_TERMS)
        # "facade detailing" is a REQUEST for detail, not a request for a
        # detail-only framing, so the detail markers are deliberately narrow.
        detail = any(term in lowered for term in self._DETAIL_ONLY_TERMS)
        camera = None
        if "three-quarter" in lowered or "three quarter" in lowered:
            camera = "front_three_quarter"
        elif "front elevation" in lowered or "front view" in lowered:
            camera = "front_elevation"
        return {
            "full_building": bool(full and not detail),
            "detail_only": bool(detail and not full),
            "camera": camera,
        }

    # ARCHITECTURAL_REQUEST_FIDELITY_REPAIR_V1 — "a central arched entrance"
    # is a COMPOSITION instruction, not just an arch. The entrance target and
    # the arches element were both detected, but the centrality was never
    # captured, so the prompt asked for arches somewhere on the building
    # instead of a central entrance. Proximity is required so that an
    # unrelated "central courtyard" elsewhere in the request cannot make an
    # ordinary entrance central.
    _ENTRANCE_NEEDLES = ("entrance", "entry", "ورودی")
    _CENTRAL_MARKERS = ("central", "centre", "center", "محوری", "مرکزی", "در مرکز")
    _ENTRANCE_PROXIMITY_CHARS = 40

    def _detect_entrance_position(self, text):
        """Return "central" when the request places the entrance centrally."""
        scanned = " " + " ".join(
            str(self._positive_clauses(text) or "").lower().split()
        ) + " "

        # EVERY mention of an entrance is considered, not just the first: a
        # brief can say "entrance steps ... must be visible" early and
        # "central entrance" much later.
        entrances = []
        for needle in self._ENTRANCE_NEEDLES:
            start = scanned.find(needle)
            while start != -1:
                entrances.append(start)
                start = scanned.find(needle, start + 1)
        if not entrances:
            return None

        for marker in self._CENTRAL_MARKERS:
            start = scanned.find(marker)
            while start != -1:
                for index in entrances:
                    if abs(start - index) <= self._ENTRANCE_PROXIMITY_CHARS:
                        return "central"
                start = scanned.find(marker, start + 1)
        return None

    _STONE_DETAIL_TERMS = (
        "course", "courses", "joint", "joints", "ashlar",
        "per-block", "per block", "recessed joint", "stone block", "stone blocks",
    )

    def _detect_stone_detail(self, text):
        lowered = " " + " ".join(str(text or "").lower().split()) + " "
        return any(term in lowered for term in self._STONE_DETAIL_TERMS)

    # ------------------------------------------------------
    # MAIN
    # ------------------------------------------------------

    def interpret(self, request, context=None):
        # --- accept NormalizedRequest (2D-1) or a raw string ---
        if isinstance(request, dict) and "normalized_text" in request:
            raw_text = request.get("raw_text", "")
            normalized_text = request.get("normalized_text", "")
            language = request.get("detected_language", "unknown")
        else:
            nr = persian_normalizer.normalize(request)
            raw_text = nr["raw_text"]
            normalized_text = nr["normalized_text"]
            language = nr["detected_language"]

        text = normalized_text or ""

        evidence = []
        change_operations = []
        ambiguities = []

        # ---------------- negatives (first; they consume spans) ----------------
        negative_constraints, negated_terms = self._detect_negatives(text)
        if negative_constraints:
            evidence.append("negative_constraint_detected")

        # A negated clause names what it forbids, so style and material are
        # matched against the positive remainder only.
        positive_text = self._positive_clauses(text)

        # ---------------- style ----------------
        style_matches = self._match_lexicon(positive_text, STYLE_TERMS)
        style_matches = [
            (c, p) for (c, p) in style_matches if p not in negated_terms
        ]
        style = {"target": None, "direction": None, "intensity": None, "mix": [], "mentions": []}
        if style_matches:
            style["mentions"] = [c for c, _ in style_matches]
            for canonical, phrase in style_matches:
                if self._is_comparative_increase(text, phrase):
                    if canonical in _COMPLEXITY_REDUCING_STYLES:
                        # "ساده‌تر" / "مینیمال‌تر" = reduce complexity, not a style target
                        change_operations.append({"operation": "decrease", "target": "complexity", "style": canonical})
                        continue
                    style["direction"] = "increase"
                    change_operations.append({"operation": "increase", "target": "style", "style": canonical})
                elif self._is_comparative_decrease(text, phrase):
                    style["direction"] = "decrease"
                    change_operations.append({"operation": "decrease", "target": "style", "style": canonical})
            for canonical, phrase in style_matches:
                if self._is_comparative_increase(text, phrase) and canonical in _COMPLEXITY_REDUCING_STYLES:
                    continue
                style["target"] = canonical
                break
            if len(style_matches) > 1:
                style["mix"] = style["mentions"]
            evidence.append("style_detected")

        # ---------------- materials ----------------
        material_matches = self._match_lexicon(positive_text, MATERIAL_TERMS)
        material_matches = [
            (c, p) for (c, p) in material_matches if p not in negated_terms
        ]
        materials = {"primary": None, "mentions": [], "tone": None, "tone_direction": None, "direction": None}
        if material_matches:
            materials["primary"] = material_matches[0][0]
            materials["mentions"] = [c for c, _ in material_matches]
            evidence.append("material_detected")

        # tones (skip when an explicit light/dark colour material was matched)
        tones = []
        if materials["primary"] not in ("light_color", "dark_color"):
            for canonical, phrases in TONE_TERMS:
                for phrase in phrases:
                    if phrase in text:
                        tones.append((canonical, phrase))
                        break
        if tones:
            materials["tone"] = tones[0][0]
            if self._is_comparative_increase(text, tones[0][1]):
                materials["tone_direction"] = "increase"
            elif self._is_comparative_decrease(text, tones[0][1]):
                materials["tone_direction"] = "decrease"

        if materials["primary"] and materials["tone_direction"] == "increase":
            change_operations.append({
                "operation": "increase",
                "target": "material",
                "material": materials["primary"],
                "attribute": "tone",
                "value": materials["tone"],
            })

        # ---------------- targets / elements ----------------
        target_matches = self._match_lexicon(text, TARGET_TERMS)
        targets = [c for c, _ in target_matches]

        entrance = {"emphasis": None, "direction": None, "position": None}
        windows = {"change": None, "frame_tone": None}
        balconies = {"complexity": None}
        arches = {"intensity": None, "direction": None}
        facade = {"depth": None, "rhythm": None}

        # secondary tone applied to the window frame (mixed-language case)
        if "window_frame" in targets and len(tones) > 1:
            windows["frame_tone"] = tones[1][0]

        # entrance emphasis (needs a target: entrance)
        if "entrance" in targets:
            if any(m in text for m in _TARGETED_EMPHASIS):
                entrance["emphasis"] = "increase"
                entrance["direction"] = "increase"
                change_operations.append({"operation": "increase", "target": "entrance", "attribute": "emphasis"})
            elif "کمتر" in text:
                entrance["emphasis"] = "decrease"
                change_operations.append({"operation": "decrease", "target": "entrance", "attribute": "emphasis"})

        # ARCHITECTURAL_REQUEST_FIDELITY_REPAIR_V1 — the entrance's POSITION
        # in the composition, independent of any change operation. A fresh
        # "design a villa with a central arched entrance" turn has no change
        # operation at all, so the centrality used to be dropped entirely.
        entrance["position"] = self._detect_entrance_position(text)

        # arches decrease/increase
        if "arches" in targets:
            if "کمتر" in text or "کم" in text:
                arches["direction"] = "decrease"
                change_operations.append({"operation": "decrease", "target": "arches"})
            elif "بیشتر" in text or self._is_comparative_increase(text, "قوس"):
                arches["direction"] = "increase"
                change_operations.append({"operation": "increase", "target": "arches"})

        # window frame refinement ("قاب پنجره‌ها ظریف‌تر شه")
        if "window_frame" in targets and "ظریف" in text:
            change_operations.append({"operation": "decrease", "target": "window_frame", "attribute": "emphasis"})

        # facade depth / rhythm
        if "facade" in targets:
            if "عمق" in text and ("بیشتر" in text or "داشته باشه" in text or "داشته" in text):
                facade["depth"] = "increase"
                change_operations.append({"operation": "increase", "target": "facade", "attribute": "depth"})
            if "ریتم" in text and ("منظم" in text):
                facade["rhythm"] = "regular"
                change_operations.append({"operation": "refine", "target": "facade", "attribute": "rhythm", "value": "regular"})

        # ---------------- replace / add / remove ----------------
        if any(re.search(p, text) for p in _REPLACE_PATTERNS):
            replace_target = "facade" if "facade" in targets else (targets[0] if targets else "unknown")
            change_operations.append({"operation": "replace", "target": replace_target})
            evidence.append("replace_detected")

        # FACADE-COORDINATION-CONSISTENCY_V1 — a removal is recorded as a
        # removal of the element named in ITS OWN clause. It used to be
        # recorded as `replace` against a single global target, so
        # "در را حذف کن و پنجره اضافه کن" claimed to REPLACE the windows and
        # the door disappeared from the prompt entirely.
        for removal_target in self._detect_removals(text):
            if not any(
                op["operation"] == "remove" and op["target"] == removal_target
                for op in change_operations
            ):
                change_operations.append({
                    "operation": "remove",
                    "target": removal_target,
                })
                evidence.append("remove_detected")

        # ---------------- material request (no explicit operation yet) ----------------
        if materials["primary"] and not any(op["target"] == "material" for op in change_operations):
            change_operations.append({
                "operation": "refine",
                "target": "material",
                "material": materials["primary"],
                "tone": materials["tone"],
            })

        # ---------------- changed targets (preserve filtering) ----------------
        changed_targets = {
            op["target"] for op in change_operations
            if op["operation"] in ("increase", "decrease", "replace", "add", "remove", "refine")
        }
        scope = self._detect_scope(text, targets)
        # PRESERVE_COORDINATION_V1 — the scope pivot is a DERIVED target. When
        # the clause that names it is a pure preservation statement, promoting
        # it to a changed target suppressed the preserve clause the user
        # actually wrote, leaving the element silently unprotected.
        #
        # The promotion stays whenever the scope's own clause asks for a
        # change: "پنجره‌ها را تغییر بده" and "همین حجم و پنجره‌ها بمونه فقط نما
        # مدرن‌تر شه" keep it, because in the second the facade is genuinely
        # being modernised even though the turn also preserves other elements.
        if changed_targets and scope not in ("unknown", "whole_building"):
            if not self._scope_is_only_preserved(text, scope):
                changed_targets.add(scope)

        # ---------------- preserve ----------------
        preserve, preserve_detected = self._detect_preserve(text, targets, changed_targets)
        if preserve_detected:
            evidence.append("preserve_detected")
            if preserve.get("scope_unspecified"):
                ambiguities.append({
                    "type": "ambiguous_target",
                    "reason": "preserve_without_target",
                    "text": text,
                })
            for field, value in preserve.items():
                if value is True and field not in ("explicit",):
                    change_operations.append({"operation": "preserve", "target": field})

        # ---------------- reference ----------------
        reference_policy = self._detect_reference(text)
        if reference_policy["referenced"]:
            evidence.append("reference_text_detected")

        # LIVE_HANDOFF_V1 — an appearance-only reference transfer changes the
        # FACADE, not the building. `_detect_scope` falls back to
        # "whole_building" whenever more than one target is named, which made
        # the compiler emit "Apply the changes to the overall building
        # composition" for what is a facade restyle.
        if (
            reference_policy.get("referenced")
            and reference_policy.get("preserve_base_geometry")
            and not reference_policy.get("copy_reference_geometry")
        ):
            scope = "facade"
            evidence.append("facade_scope_from_reference_transfer")

        # NEOCLASSICAL_DESIGN_CHAT_ROUTE_V1 — the SAME fallback, reached
        # WITHOUT a reference image. See the predicate block above: a facade
        # design for an existing building lists its preserved elements in the
        # same breath, and those nouns were inflating the scope to
        # "whole_building".
        if (
            scope == "whole_building"
            and "facade" in targets
            and self._named_style_target(style)
            and self._refers_to_existing_building(text)
        ):
            scope = "facade"
            evidence.append("facade_scope_from_existing_building_design")

        # ---------------- ambiguity (vague modifier without target) ----------------
        vague_found = [m for m in _VAGUE_MODIFIERS if m in text]
        vague_found += [m for m in _TARGETED_EMPHASIS if m in text and not targets]
        if vague_found and not targets:
            ambiguities.append({
                "type": "ambiguous_target",
                "modifier": vague_found[0],
                "reason": "vague_modifier_without_target",
                "text": text,
            })
            evidence.append("ambiguity_detected")

        # ---------------- intent type ----------------
        has_change = any(op["operation"] in ("increase", "decrease", "replace", "add", "remove", "refine") for op in change_operations)
        has_preserve = any(op["operation"] == "preserve" for op in change_operations)
        if has_change and has_preserve:
            intent_type = "mixed"
        elif has_change:
            intent_type = "change"
        elif has_preserve:
            intent_type = "preserve"
        elif negative_constraints:
            intent_type = "constraint"
        elif reference_policy["referenced"]:
            intent_type = "reference"
        elif ambiguities:
            intent_type = "clarify"
        else:
            intent_type = "none"

        confidence = {
            "deterministic": 1.0 if (change_operations or negative_constraints or reference_policy["referenced"]) else 0.0,
            "ambiguous": bool(ambiguities),
        }

        result = PersianArchitecturalUnderstandingV1({
            "contract": CONTRACT,
            "version": VERSION,

            "raw_text": raw_text,
            "normalized_text": normalized_text,
            "language": language,

            "scope": scope,
            "intent_type": intent_type,
            "targets": sorted(set(targets)),

            "style": style,
            "materials": materials,
            "facade": facade,
            "entrance": entrance,
            "windows": windows,
            "balconies": balconies,
            "arches": arches,

            "preserve_constraints": preserve,
            "negative_constraints": negative_constraints,

            # CLASSICAL_DETAIL_RETENTION_V1 — the user's explicitly named
            # architectural elements, and how the building must be framed.
            # Deterministic, additive, and limited to words the user wrote:
            # this is not an ontology dump and it never invents a feature.
            "elements": self._detect_elements(text),
            "framing": self._detect_framing(text),
            "stone_detail": self._detect_stone_detail(text),

            "change_operations": change_operations,

            "intensity": self._detect_intensity(text),

            "reference_image_policy": reference_policy,

            "ambiguities": ambiguities,

            "confidence": confidence,
            "deterministic_evidence": evidence,
            "llm_enrichment": {},
            "conflicts": [],
            "provenance": {
                "engine": "PersianArchitecturalUnderstandingEngine",
                "version": VERSION,
                "normalizer_version": persian_normalizer.VERSION,
                "deterministic": True,
            },
        })

        return result

    # ======================================================
    # OPTIONAL LLM ENRICHMENT (never overwrites deterministic fields)
    # ======================================================

    def enrich_with_llm(self, result, llm_callable=None, schema_validator=None):
        """Fill EMPTY fields from an optional LLM enrichment.

        - disabled by default (llm_callable=None) -> deterministic-only
        - validated output only
        - never overwrites a non-empty deterministic field
        - conflicts are recorded, never silently reconciled
        - any failure returns the deterministic result unchanged
        """
        if llm_callable is None:
            return result

        try:
            candidate = llm_callable(result.get("normalized_text", ""))
        except Exception as exc:  # provider failure must not break parsing
            result["llm_enrichment"] = {"attempted": True, "status": "failed", "error": str(exc)}
            return result

        if not isinstance(candidate, dict):
            result["llm_enrichment"] = {"attempted": True, "status": "rejected_non_dict"}
            return result

        if schema_validator is not None:
            try:
                if not schema_validator(candidate):
                    result["llm_enrichment"] = {"attempted": True, "status": "rejected_schema"}
                    return result
            except Exception as exc:
                result["llm_enrichment"] = {"attempted": True, "status": "validator_error", "error": str(exc)}
                return result

        applied = []
        conflicts = []
        for key in ("style", "materials", "facade", "entrance", "windows", "balconies", "arches"):
            incoming = candidate.get(key)
            if not isinstance(incoming, dict):
                continue
            current = result.get(key, {})
            for field, value in incoming.items():
                if value in (None, "", [], {}):
                    continue
                if current.get(field) in (None, "", [], {}):
                    current[field] = value
                    applied.append(f"{key}.{field}")
                elif current.get(field) != value:
                    conflicts.append({
                        "field": f"{key}.{field}",
                        "deterministic": current.get(field),
                        "llm": value,
                        "resolution": "deterministic_authoritative",
                    })
            result[key] = current

        result["llm_enrichment"] = {"attempted": True, "status": "applied", "applied": applied}
        if conflicts:
            result["conflicts"] = list(result.get("conflicts", [])) + conflicts
        return result


# ==========================================================
# SINGLETON + CONVENIENCE
# ==========================================================

persian_architectural_understanding = PersianArchitecturalUnderstandingEngine()


def understand(request, context=None):
    """Module-level convenience wrapper over the canonical 2D-2 engine."""
    return persian_architectural_understanding.interpret(request, context)
