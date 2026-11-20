# ==========================================================
# ArchitectOS Knowledge Reflection v1
#
# TEACHING SESSION STATE FIX — READ-ONLY KNOWLEDGE REFLECTION
#
# The user asks: "برداشت فعلی تو از این فضا چیست؟ / چه چیزهایی
# درباره آن می دانی؟"  ("what is your current understanding of this
# space / what do you know about it?")
#
# That is NOT teaching and NOT a teach-back request. The user wants the
# assistant to STATE WHAT IT ALREADY KNOWS from the EXISTING
# architectural corpus, as a baseline before teaching anything.
#
# This module is STRICTLY READ-ONLY.
#
#   - it never creates a teaching candidate
#   - it never stores teaching
#   - it never promotes knowledge
#   - it never starts a lesson
#   - it never touches the curriculum
#   - it never renders and never calls ComfyUI
#
# It reads the EXISTING corpus through the read-only bridges
# (`space_curriculum_v1` -> `space_types_v1` -> `knowledge_read_bridge_v1`)
# and reports it back verbatim. Nothing is invented: if the corpus has no
# record for the requested topic, the module says so and reports what the
# corpus DOES cover.
# ==========================================================


from __future__ import annotations


CONTRACT = "KnowledgeReflectionV1"
VERSION = "1.0"

MODE = "READ_ONLY_KNOWLEDGE_REFLECTION"


# ----------------------------------------------------------
# PHRASES
# ----------------------------------------------------------

PHRASES = {

    "fa": {

        "header": "برداشت فعلی من از %s:",

        "header_generic": "برداشت فعلی من از دانش معماری موجود:",

        "no_space_named": (
            "شما فضای مشخصی را نام نبردید، پس برداشت کلی خود را "
            "می‌گویم:"
        ),

        "unknown_topic": (
            "در پیکرهٔ دانش معماری موجود، موردی که با «%s» مطابقت کند "
            "پیدا نشد."
        ),

        "identified_as": "فضای شناسایی‌شده: %s",

        "category": "دسته: %s — منطقه: %s",

        "functional_role": "نقش کارکردی: %s",

        "functional_definition": "تعریف کارکردی: %s",

        "privacy": "سطح حریم: %s",

        "acoustic": "حساسیت حریم صوتی: %s",

        "daylight": "نیاز به نور روز: %s",

        "wet_zone": "فضای مرطوب: %s",

        "area": "حداقل مساحت (ضابطهٔ تأییدشده): %s مترمربع — %s بند %s",

        "adjacent": "هم‌جواری‌های متداول: %s",

        "discouraged": "هم‌جواری‌های نامطلوب: %s",

        "access": "الزامات دسترسی: %s",

        "inventory": (
            "آنچه در پیکرهٔ موجود هست: %s گونهٔ فضا در %s دسته (%s)."
        ),

        "inventory_hint": (
            "اگر نام یک فضا را بگویید (مثلاً «اتاق خواب»)، برداشت فعلی "
            "خودم را از همان فضا می‌گویم."
        ),

        "source": "منبع: پیکرهٔ دانش معماری موجود (فقط خواندنی).",

        "not_learned": (
            "این «دانستهٔ فعلی» من است؛ چیز جدیدی یاد نگرفتم و هیچ چیزی "
            "به دانش دائمی اضافه نشد."
        ),

        "yes": "بله",
        "no": "خیر",
    },

    "en": {

        "header": "My current understanding of %s:",

        "header_generic": (
            "My current understanding of the existing architectural "
            "knowledge:"
        ),

        "no_space_named": (
            "You did not name a specific space, so here is my general "
            "understanding:"
        ),

        "unknown_topic": (
            "The existing architectural corpus has no record matching "
            "\u201c%s\u201d."
        ),

        "identified_as": "Resolved space: %s",

        "category": "Category: %s \u2014 Zone: %s",

        "functional_role": "Functional role: %s",

        "functional_definition": "Functional definition: %s",

        "privacy": "Privacy level: %s",

        "acoustic": "Acoustic privacy sensitivity: %s",

        "daylight": "Daylight requirement: %s",

        "wet_zone": "Wet zone: %s",

        "area": "Minimum area (verified regulation): %s sqm \u2014 %s clause %s",

        "adjacent": "Typical adjacency: %s",

        "discouraged": "Discouraged adjacency: %s",

        "access": "Access requirements: %s",

        "inventory": (
            "What the corpus covers: %s space types across %s "
            "categories (%s)."
        ),

        "inventory_hint": (
            "Name a space (for example \u201cbedroom\u201d) and I will "
            "state my current understanding of that one."
        ),

        "source": "Source: the existing architectural corpus (read-only).",

        "not_learned": (
            "This is my CURRENT understanding; I learned nothing new and "
            "nothing was added to permanent knowledge."
        ),

        "yes": "yes",
        "no": "no",
    },
}


def _phrases(language):

    return PHRASES[
        "fa" if str(language or "").startswith("fa") else "en"
    ]


class KnowledgeReflectionV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    def __init__(self):

        print(
            "\U0001f9e0 KNOWLEDGE REFLECTION v1.0 ONLINE "
            "(read-only, states what is already known)"
        )

    # ======================================================
    # TOPIC RESOLUTION (read-only)
    # ======================================================

    def resolve_topic(self, text, language="fa"):

        """Resolve the space the user is asking about, from the corpus."""

        try:

            from core.curriculum.space_curriculum_v1 import (
                space_curriculum,
            )

            return space_curriculum.resolve_space_topic(text, language)

        except Exception as error:

            print(
                "KNOWLEDGE REFLECTION TOPIC ERROR:",
                type(error).__name__,
                error,
            )

            return None

    def _space_record(self, space_id, alias=None, language="fa"):

        try:

            from core.curriculum.space_types_v1 import space_types

            if space_id:

                record = space_types.space(space_id)

                if record:

                    return record

            if alias:

                return space_types.resolve(alias, language)

        except Exception as error:

            print(
                "KNOWLEDGE REFLECTION RECORD ERROR:",
                type(error).__name__,
                error,
            )

        return None

    def _inventory(self):

        try:

            from core.curriculum.space_types_v1 import space_types

            return {
                "count": space_types.count(),
                "categories": list(space_types.categories()),
            }

        except Exception:

            return {"count": 0, "categories": []}

    # ======================================================
    # RENDERING
    # ======================================================

    @staticmethod
    def _name(value, language="fa"):

        if isinstance(value, dict):

            return (
                value.get("fa")
                or value.get("en")
                or ""
            )

        return value or ""

    @staticmethod
    def _label(value):

        """Humanise an enum-ish token: PRIVATE_HALL_CORRIDOR -> the token."""

        return str(value or "").replace("_", " ")

    def _category_label(self, category, language="fa"):

        try:

            from core.curriculum.space_types_v1 import category_display

            return category_display(category, language)

        except Exception:

            return self._label(category)

    def _zone_label(self, zone, category=None, language="fa"):

        """Reuse the ZONE MODEL's own display — never a second copy.

        The space record carries a lowercase zone token (`private`) whose
        provenance is `DERIVED_FROM_CATEGORY`, while `zone_display` keys
        on `PRIVATE_ZONE`. Resolve through the canonical
        `ZONE_BY_CATEGORY` map first, then fall back to the raw token.
        """

        try:

            from core.curriculum.zone_model_v1 import (
                zone_display,
                ZONE_BY_CATEGORY,
            )

            key = ZONE_BY_CATEGORY.get(category) or zone

            return zone_display(key, language)

        except Exception:

            return self._label(zone)

    # Presentation labels for the few raw enum tokens this module
    # renders. These are display-only and deliberately local: the
    # DOMAIN vocabularies stay in their own modules.
    _ENUM_LABELS = {

        "fa": {
            "HIGH": "بالا",
            "MEDIUM": "متوسط",
            "LOW": "کم",
            "REQUIRED": "الزامی",
            "OPTIONAL": "اختیاری",
            "NOT_REQUIRED": "لازم نیست",
            "RECOMMENDED": "توصیه‌شده",
            "True": "بله",
            "False": "خیر",
        },

        "en": {},
    }

    def _enum_label(self, value, language="fa"):

        token = str(value)

        return (
            self._ENUM_LABELS.get(
                "fa" if str(language or "").startswith("fa") else "en", {}
            ).get(token)
            or self._label(token)
        )

    def _adjacent_names(self, ids, language="fa"):

        """Resolve adjacency ids to their corpus display names."""

        names = []

        for space_id in ids or []:

            record = self._space_record(space_id, language=language)

            name = self._name(
                (record or {}).get("name"), language
            )

            names.append(name or self._label(space_id))

        return names

    def _access_notes(self, access, text):
        if not isinstance(access, dict):

            return []

        notes = []

        for key in (
            "requires_enclosure",
            "requires_door",
            "open_connection_allowed",
            "may_be_open_plan",
            "can_be_transit_node",
        ):

            if key in access:

                notes.append(
                    "%s: %s"
                    % (
                        key,
                        self._enum_label(access.get(key)),
                    )
                )

        return notes

    def _render_space(self, record, topic, language="fa"):

        text = _phrases(language)

        lines = []

        display = (
            self._name(record.get("name"), language)
            or topic
            or record.get("space_id")
        )

        lines.append(text["header"] % display)

        if record.get("space_id") and display != record.get("space_id"):

            lines.append(
                "\u2022 " + text["identified_as"] % record.get("space_id")
            )

        lines.append(
            "\u2022 "
            + text["category"]
            % (
                self._category_label(record.get("category"), language),
                self._zone_label(
                    record.get("zone"),
                    record.get("category"),
                    language,
                )
                if record.get("zone")
                else "-",
            )
        )

        if record.get("functional_role"):

            lines.append(
                "\u2022 " + text["functional_role"] % record["functional_role"]
            )

        if record.get("functional_definition"):

            lines.append(
                "\u2022 "
                + text["functional_definition"]
                % record["functional_definition"]
            )

        if record.get("privacy_level"):

            lines.append(
                "\u2022 "
                + text["privacy"]
                % self._category_label(
                    record["privacy_level"], language
                )
            )

        if record.get("acoustic_privacy_sensitivity"):

            lines.append(
                "\u2022 "
                + text["acoustic"]
                % self._enum_label(
                    record["acoustic_privacy_sensitivity"], language
                )
            )

        if record.get("daylight_requirement"):

            lines.append(
                "\u2022 "
                + text["daylight"]
                % self._enum_label(
                    record["daylight_requirement"], language
                )
            )

        if "wet_zone" in record:

            lines.append(
                "\u2022 "
                + text["wet_zone"]
                % (text["yes"] if record.get("wet_zone") else text["no"])
            )

        area = (record.get("area_requirements") or {}).get(
            "verified_regulation"
        ) or {}

        if area.get("value") is not None:

            source = area.get("source") or {}

            lines.append(
                "\u2022 "
                + text["area"]
                % (
                    area.get("value"),
                    source.get("title_fa")
                    or source.get("title")
                    or area.get("provenance")
                    or "",
                    source.get("clause") or "",
                )
            )

        adjacent = self._adjacent_names(
            record.get("typical_adjacent"), language
        )

        if adjacent:

            lines.append(
                "\u2022 " + text["adjacent"] % "، ".join(adjacent)
            )

        discouraged = self._adjacent_names(
            record.get("discouraged_adjacent"), language
        )

        if discouraged:

            lines.append(
                "\u2022 " + text["discouraged"] % "، ".join(discouraged)
            )

        notes = self._access_notes(
            record.get("access_requirements"), text
        )

        if notes:

            lines.append("\u2022 " + text["access"] % "، ".join(notes))

        return lines

    def _render_generic(self, topic, language="fa"):

        text = _phrases(language)

        lines = [
            text["header_generic"]
            if not topic
            else text["header"] % topic
        ]

        if not topic:

            lines.append(text["no_space_named"])

        else:

            lines.append(text["unknown_topic"] % topic)

        inventory = self._inventory()

        if inventory["count"]:

            lines.append(
                "\u2022 "
                + text["inventory"]
                % (
                    inventory["count"],
                    len(inventory["categories"]),
                    "، ".join(inventory["categories"]),
                )
            )

        lines.append(text["inventory_hint"])

        return lines

    # ======================================================
    # PUBLIC ENTRY POINT
    # ======================================================

    def reflect(self, text, language="fa", topic=None):

        """State what is ALREADY known. Writes nothing, learns nothing."""

        lang = "fa" if str(language or "").startswith("fa") else "en"

        phrases = _phrases(lang)

        resolved = None

        record = None

        try:

            resolved = self.resolve_topic(text, lang)

        except Exception:

            resolved = None

        display_topic = topic or (resolved or {}).get("alias")

        if resolved and resolved.get("space_id"):

            record = self._space_record(
                resolved.get("space_id"),
                alias=resolved.get("alias"),
                language=lang,
            )

        if record:

            display_topic = (
                self._name(record.get("name"), lang)
                or display_topic
            )

            lines = self._render_space(record, display_topic, lang)

            has_knowledge = True

        else:

            lines = self._render_generic(display_topic, lang)

            has_knowledge = False

        lines.append(phrases["source"])

        lines.append(phrases["not_learned"])

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "status": "success",

            "mode": MODE,

            "language": lang,

            "topic": display_topic,

            "space_id": (record or {}).get("space_id"),

            # The corpus record, read-only, for audit. Never stored.
            "space": record,

            "source": "EXISTING_ARCHITECTURAL_CORPUS",

            "read_only": True,

            "has_existing_knowledge": has_knowledge,

            "result": "\n".join(lines),

            # ---- SAFETY FLAGS ------------------------------------
            # A reflection is NOT knowledge, NOT a candidate and NOT
            # an action. These are asserted by the contract tests.
            "is_knowledge": False,
            "is_action": False,
            "candidate_created": False,
            "learned_anything": False,
            "stored_teaching": False,
            "permanent_learning_implemented": False,
            "lesson_started": False,
            "curriculum_touched": False,
            "knowledge_promoted": False,
            "routed_to_execute": False,
            "writes_performed": False,
            "llm_used": False,
            "network_used": False,
            "render_requested": False,
            "comfy_invoked": False,
        }

    # ======================================================
    # READ-ONLY SURFACE
    # ======================================================

    def report(self):

        inventory = self._inventory()

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "mode": MODE,

            "read_only": True,
            "writes_performed": False,

            "corpus_space_count": inventory["count"],
            "corpus_categories": inventory["categories"],

            "creates_candidate": False,
            "stores_teaching": False,
            "promotes_knowledge": False,
            "starts_lesson": False,
            "touches_curriculum": False,
            "renders": False,
        }


knowledge_reflection = KnowledgeReflectionV1()
