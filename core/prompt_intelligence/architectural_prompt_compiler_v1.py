# ==========================================================
# ArchitectOS Architectural Prompt Compiler v1.0
#
# PHASE 2D-3 — ARCHITECTURAL PROMPT COMPILER / ENGLISH PROJECTION
#
# Consumes canonical SEMANTICS (2D-2 PersianArchitecturalUnderstandingV1,
# optionally the deterministic ArchitecturalIntent) and compiles a
# professional, deterministic, structured English architectural prompt.
#
# This is NOT a translator.  No LLM is required.  No render execution.
# No image understanding.  Raw Persian is retained for audit only.
# ==========================================================


from __future__ import annotations

import hashlib
import json


CONTRACT = "ArchitecturalCompiledPromptV1"
VERSION = "1.0"


# ==========================================================
# CONTRACT
# ==========================================================

class ArchitecturalCompiledPromptV1(dict):
    """Versioned, dict-compatible compiled architectural prompt contract."""

    CONTRACT = CONTRACT
    VERSION = VERSION


# ==========================================================
# MODES
# ==========================================================

MODES = (
    "ARCHITECTURAL_GENERAL",
    "FACADE_REFINEMENT",
    "IMAGE_EDIT",
    "TEXT_TO_IMAGE",
    "DESIGN_REVISION",
)

# T2I_MODE_PROPAGATION_V1 — the render strategy controller speaks the
# PRODUCT's mode vocabulary (lowercase `text_to_image`, `image_to_image`,
# `chat`, `analyze_image`), while this compiler's sections are keyed by its
# own MODES. The two vocabularies never met, so `_infer_mode` fell through to
# `scope == "facade"` and compiled a fresh generation as FACADE_REFINEMENT —
# the prompt then told the model to "refine the existing facade" when no
# source facade existed.
#
# The mapping lives HERE, once, next to MODES, so no caller has to invent
# compiler vocabulary and no second routing table appears elsewhere.
PRODUCT_MODE_ALIASES = {
    "text_to_image": "TEXT_TO_IMAGE",
    "image_to_image": "IMAGE_EDIT",
    "image_edit": "IMAGE_EDIT",
    "edit": "IMAGE_EDIT",
    "chat": "ARCHITECTURAL_GENERAL",
    "analyze_image": "ARCHITECTURAL_GENERAL",
    # "auto" is deliberately absent: an unvalidated mode keeps inference.
}

RENDER_MODES = ("IMAGE_EDIT", "TEXT_TO_IMAGE", "FACADE_REFINEMENT")


# ==========================================================
# VOCABULARY
# ==========================================================

STYLE_WORD = {
    "modern": "contemporary",
    "minimal": "minimal, restrained",
    "classic": "classical",
    "neoclassical": "restrained neoclassical",
    "modern_classic": "contemporary-classic",
    "traditional": "contextually traditional",
    "industrial": "industrial",
    "luxury": "refined upscale",
    "roman": "Roman/classical",
    "roman_classic": "Roman/classical",
    "simple": "simple, restrained",
    "iranian_brick": "Iranian brick",
    "iranian_traditional": "traditional Iranian",
    # KNOWLEDGE_RUNTIME_CONNECTION_V2 — was "Islamic architectural", which the
    # style sentence template then followed with "architectural language",
    # producing "Islamic architectural architectural language". The phrase here
    # is the ADJECTIVE only; the template supplies the noun.
    "islamic_architecture": "Islamic",
    "french_classical": "French Classical",
    "beaux_arts": "Beaux-Arts",
    "second_empire": "Second Empire",
    "french_provincial": "French Provincial",
}

MATERIAL_WORD = {
    "stone": "natural stone",
    # ARCHITECTURAL_REQUEST_FIDELITY_REPAIR_V1 — a named material keeps its
    # own name. Without this entry the id would still have fallen back to
    # "limestone" via the snake_case rule, but the word is stated explicitly
    # so the material vocabulary is readable in one place.
    "limestone": "limestone",
    "travertine": "light travertine stone",
    "brick": "brick",
    "wood": "natural wood accents",
    "metal": "metal accents",
    "glass": "clear architectural glazing",
    "concrete": "exposed concrete",
    "white_cement": "white cement finish",
    "light_color": "light colour palette",
    "dark_color": "dark colour palette",
}

TONE_WORD = {
    "light": "light",
    "dark": "dark",
    "cream": "cream",
    "warm": "warm",
}

TONE_COMPARATIVE = {
    "light": "lighter",
    "dark": "darker",
    "cream": "cream",
    "warm": "warmer",
}

PRESERVE_SENTENCE = {
    "massing": "Preserve the existing building massing.",
    "geometry": "Preserve the existing building geometry.",
    "floor_count": "Preserve the existing floor count.",
    "windows": "Preserve the current window locations, dimensions, and overall opening layout.",
    "openings": "Preserve the existing opening layout.",
    "balconies": "Preserve the existing balconies.",
    "entrance_location": "Preserve the existing entrance location.",
    "structure": "Preserve the existing structural system.",
    "material": "Preserve the existing material expression.",
    "style": "Preserve the existing architectural style.",
    "facade": "Preserve the existing facade expression.",
    "arches": "Preserve the existing arches.",
    "reference_geometry": "Preserve the base building geometry as the authoritative reference.",
}

# target token -> preserve constraint field (mirrors 2D-2 authority)
TARGET_TO_PRESERVE_FIELD = {
    "massing": "massing",
    "geometry": "geometry",
    "windows": "windows",
    "window_frame": "openings",
    "openings": "openings",
    "balconies": "balconies",
    "entrance": "entrance_location",
    "floors": "floor_count",
    "structure": "structure",
    "materials": "material",
    "material": "material",
    "style": "style",
    "facade": "facade",
    "arches": "arches",
    "plan": "geometry",
}

NEGATIVE_SENTENCE = {
    "avoid_excessive_roman_style": "Avoid excessive Roman/classical styling.",
    "avoid_excessive_classical_style": "Avoid excessive classical styling.",
    "avoid_heavy_ornament": "Avoid heavy ornamentation.",
    "avoid_excessive_ornament": "Avoid excessive ornamentation.",
    "avoid_excessive_arches": "Avoid excessive use of arches.",
    "avoid_excessive_glass": "Avoid excessive glazing.",
    "avoid_dominant_metal": "Do not let metal dominate the facade composition.",
    "avoid_excessive_luxury": "Avoid excessive luxury or heavy decorative treatment.",
}

REFERENCE_SENTENCE = {
    "style_only": "Use the reference image for architectural style only.",
    "material_only": "Use the reference image only as a material/finish reference.",
    "composition_only": "Use the reference image only as a composition reference.",
    "inspiration_only": "Use the reference as design inspiration, not as a geometry template.",
}

MODE_TASK = {
    "IMAGE_EDIT": "Refine the existing architectural image.",
    "FACADE_REFINEMENT": "Refine the existing facade.",
    "TEXT_TO_IMAGE": "Generate an architectural visualization.",
    "DESIGN_REVISION": "Revise the current architectural design.",
    "ARCHITECTURAL_GENERAL": "Refine the architectural design.",
}

MODE_QUALITY = {
    "IMAGE_EDIT": "Photorealistic architectural visualization, realistic materials, balanced daylight, clean perspective.",
    "TEXT_TO_IMAGE": "Photorealistic architectural visualization, realistic materials, balanced exposure, clean perspective.",
    "FACADE_REFINEMENT": "Photorealistic architectural visualization, realistic materials, balanced daylight.",
}

# Mode policy (NOT user intent) — only emitted for IMAGE_EDIT.
IMAGE_EDIT_POLICY = (
    "The uploaded base building image is the authoritative geometry reference.",
    "Do not redesign the plan.",
    "Do not add or remove floors.",
    "Do not relocate preserved windows or openings.",
)

#: FACADE-COORDINATION-CONSISTENCY_V1 — how a removal target is spoken.
#: Phrased as an explicit element removal so the render prompt states what to
#: take away instead of silently relabelling it as a replacement.
REMOVAL_SENTENCE = {
    "windows": "Remove the existing windows; do not replace them with new ones.",
    "doors": "Remove the existing doors; do not replace them with new ones.",
    "railings": "Remove the existing railings; do not replace them with new ones.",
}

SCOPE_SENTENCE = {
    "facade": "Apply the changes to the facade expression only.",
    "whole_building": "Apply the changes to the overall building composition.",
    "entrance": "Apply the changes to the main entrance.",
    "windows": "Apply the changes to the window system.",
    "balcony": "Apply the changes to the balconies.",
    "material": "Apply the changes to the material palette.",
    "element": "Apply the changes to the specified architectural element.",
    "arches": "Apply the changes to the arches.",
    "materials": "Apply the changes to the material palette.",
    "window_frame": "Apply the changes to the window framing.",
}

# deterministic section order (never reordered)
#
# T2I_HIGH_RISE_SUBJECT_FIDELITY_V1 — `subject` is FIRST. The primary
# architectural subject must be the opening of the authoritative positive
# prompt; when it is absent (the default for every request that states no
# explicit affirmative floor count, or names no high-rise type) the section is
# empty and the compiled prompt is byte-identical to the previous behaviour.
SECTION_ORDER = (
    "subject",
    "task_scope",
    "preservation",
    "style",
    "materials",
    "modifications",
    "composition",
    "reference",
    "quality",
)


# ==========================================================
# COMPILER
# ==========================================================

class ArchitecturalPromptCompiler:

    VERSION = VERSION

    def __init__(self):
        print("🖋️ ARCHITECTURAL PROMPT COMPILER v1.0 ONLINE (deterministic)")

    # ------------------------------------------------------
    # helpers
    # ------------------------------------------------------

    @staticmethod
    def _has_signal(understanding):
        if not isinstance(understanding, dict) or not understanding:
            return False
        style = understanding.get("style") or {}
        materials = understanding.get("materials") or {}
        reference = understanding.get("reference_image_policy") or {}
        if style.get("target"):
            return True
        if materials.get("primary"):
            return True
        if understanding.get("negative_constraints"):
            return True
        if reference.get("referenced"):
            return True
        for op in understanding.get("change_operations", []) or []:
            if op.get("operation") != "preserve":
                return True
        preserve = understanding.get("preserve_constraints") or {}
        for key, value in preserve.items():
            if key not in ("explicit", "scope_unspecified") and value is True:
                return True
        return False

    def _normalize_mode(self, value):
        """Map either mode vocabulary onto this compiler's MODES.

        Accepts its own uppercase MODES, the product's lowercase render modes
        (T2I_MODE_PROPAGATION_V1), and returns None when nothing authoritative
        is present so `_infer_mode` can decide.
        """

        if not isinstance(value, str):

            return None

        text = value.strip()

        if text in MODES:

            return text

        return PRODUCT_MODE_ALIASES.get(text.lower())

    def _infer_mode(self, understanding, context):
        context = context or {}
        requested = self._normalize_mode(context.get("mode"))
        if requested:
            return requested
        reference = understanding.get("reference_image_policy") or {}
        preserve = understanding.get("preserve_constraints") or {}
        has_base = bool(
            context.get("base_image")
            or context.get("image_asset")
            or reference.get("preserve_base_geometry")
            or preserve.get("reference_geometry")
        )
        if has_base:
            return "IMAGE_EDIT"
        if understanding.get("scope") == "facade":
            return "FACADE_REFINEMENT"
        return "ARCHITECTURAL_GENERAL"

    # ------------------------------------------------------
    # conflicts
    # ------------------------------------------------------

    def _detect_conflicts(self, understanding):
        preserve = understanding.get("preserve_constraints") or {}
        conflicts = []
        dropped_indexes = set()
        for index, op in enumerate(understanding.get("change_operations", []) or []):
            if op.get("operation") not in ("increase", "decrease", "replace", "add", "remove", "refine"):
                continue
            target = op.get("target")
            field = TARGET_TO_PRESERVE_FIELD.get(target)
            if field and preserve.get(field) is True:
                conflicts.append({
                    "type": "preserve_vs_change",
                    "target": target,
                    "preserved_field": field,
                    "change_operation": op.get("operation"),
                    "resolution": "preservation_authoritative",
                })
                dropped_indexes.add(index)
        return conflicts, dropped_indexes

    # ------------------------------------------------------
    # sections
    # ------------------------------------------------------

    def _compile_task_scope(self, understanding, mode, has_change):
        lines = [MODE_TASK.get(mode, MODE_TASK["ARCHITECTURAL_GENERAL"])]
        scope = understanding.get("scope")
        scope_sentence = SCOPE_SENTENCE.get(scope)
        # only announce a scope of change when there is an actual change
        #
        # T2I_MODE_PROPAGATION_V1 — and never for a FRESH generation. Every
        # SCOPE_SENTENCE is phrased as a modification of something that
        # already exists ("Apply the changes to the facade expression
        # only."). A text-to-image turn has no source facade, so the sentence
        # asks the model to preserve something that is not there.
        # PRESERVE_COORDINATION_V1 — and never for a scope the user is
        # PRESERVING. "پنجره‌ها را حفظ کن و در چوبی اضافه کن" carries a
        # turn-wide change, but the window system is the element the user
        # protected, not the one they asked to alter. Announcing a change
        # scope there contradicted the preservation sentence emitted beside
        # it and directed the model at the preserved element.
        preserve = understanding.get("preserve_constraints") or {}
        scope_preserved = bool(
            preserve.get(TARGET_TO_PRESERVE_FIELD.get(scope))
        )
        if scope_sentence and has_change and mode != "TEXT_TO_IMAGE" \
                and not scope_preserved:
            lines.append(scope_sentence)
        return lines

    def _compile_preservation(self, understanding, mode, context, warnings):
        preserve = understanding.get("preserve_constraints") or {}
        reference = understanding.get("reference_image_policy") or {}
        has_base = bool(
            (context or {}).get("base_image")
            or (context or {}).get("image_asset")
            or reference.get("preserve_base_geometry")
        )

        lines = []

        # TEXT_TO_IMAGE has no source geometry — never claim to preserve one.
        if mode == "TEXT_TO_IMAGE" and not has_base:
            if any(v is True for k, v in preserve.items() if k not in ("explicit", "scope_unspecified")):
                warnings.append({
                    "code": "preservation_requested_without_source_geometry",
                    "detail": "preserve constraints ignored in TEXT_TO_IMAGE mode with no base image",
                })
            return lines

        if mode == "IMAGE_EDIT":
            lines.extend(IMAGE_EDIT_POLICY)

        for key, sentence in PRESERVE_SENTENCE.items():
            if preserve.get(key) is True:
                lines.append(sentence)

        if reference.get("referenced") and reference.get("copy_reference_geometry") is False:
            lines.append("Do not copy the reference image geometry.")

        return lines

    # ======================================================
    # T2I_HIGH_RISE_SUBJECT_FIDELITY_V1 — PRIMARY SUBJECT PHRASE
    #
    # MEASURED DEFECT (2026-11-03, ComfyUI prompt 924cd546-…):
    #   the authoritative positive prompt named the subject only as the bare
    #   tag "tower" ("…, photorealistic render, tower.") while the count
    #   survived as a separate trailing sentence ("The building has exactly 25
    #   floors."). The rendered building read as roughly 10–12 storeys with the
    #   roof cropped, although the intent layer had correctly resolved
    #   floors=25 and building_type="tower".
    #
    # This section states the subject ONCE as a count-bearing noun phrase, so
    # the number modifies the building noun instead of floating free.
    #
    # TWO HARD GATES — neither is inferred, neither has a fallback:
    #
    #   1. FLOOR COUNT must be an EXPLICIT AFFIRMATIVE REQUESTED count. It is
    #      read from `understanding["floors"]` / `FloorCountV1.value` with
    #      `source == "user_explicit"`, both of which are produced by the render
    #      instruction's `_floor_count()` — the single owner that already drops
    #      negated counts (`is_affirmed`), described counts
    #      (`_floor_count_is_description`) and prohibited spans. A count that is
    #      merely described ("این ساختمان سه طبقه است"), negated ("… نباشد"),
    #      or asked to be preserved ("تعداد طبقات را تغییر نده") never reaches
    #      this section. No count is ever derived from such a statement.
    #
    #   2. BUILDING TYPE must be GROUNDED as a high-rise. Only a type the user
    #      actually named qualifies, so an ordinary house or plain building
    #      never acquires a tower subject.
    #
    # Nothing is invented: no dimension, no structural element, no geometry.
    # The phrase carries only the stated count, the grounded type, the
    # residential/luxury qualifiers the request already carries, and a
    # proportion word.
    # ======================================================

    _HIGH_RISE_MARKERS = (
        "tower", "high-rise", "high rise", "highrise", "skyscraper",
        "بلندمرتبه", "بلند مرتبه",
    )

    #: The user's own words for a dwelling building. Used only to decide
    #: whether the subject phrase may carry the word "residential"; it never
    #: changes the subject type, the count, or any architectural property.
    _RESIDENTIAL_MARKERS = (
        "residential", "apartment", "housing", "مسکونی", "آپارتمان",
    )

    @staticmethod
    def _subject_floors(understanding, context):
        """Explicit affirmative requested count, else None.

        Returns ``(value, source_label)``. `value` is an int >= 2 only when the
        request stated one affirmatively; every other shape yields ``None``.
        """

        def _as_int(candidate):
            if isinstance(candidate, int) and not isinstance(candidate, bool):
                return candidate
            return None

        floor_count = understanding.get("floor_count")

        if isinstance(floor_count, dict):

            value = _as_int(floor_count.get("value"))

            # Only an explicitly stated count is a design target.
            if value is not None and str(
                floor_count.get("source") or ""
            ) == "user_explicit":

                return value, "understanding.floor_count[user_explicit]"

        value = _as_int(understanding.get("floors"))

        if value is not None:

            return value, "understanding.floors"

        if isinstance(context, dict):

            value = _as_int(context.get("requested_floors"))

            if value is not None:

                return value, "context.requested_floors"

        return None, None

    @staticmethod
    def _subject_building_type(understanding, context=None):
        """Grounded building type, lower-cased, or "".

        Three legitimate carriers, in decreasing authority:
          * the understanding's own `building_type` (when the producer sets it);
          * `context["subject_building_type"]`;
          * `context["subject_terms"]` — the canonical terminology terms the
            request actually matched (the same list `infer_preset` reads).
        """

        candidates = []

        raw = understanding.get("building_type")

        if isinstance(raw, dict):

            raw = raw.get("type") or raw.get("value")

        if raw:

            candidates.append(str(raw))

        if isinstance(context, dict):

            explicit = context.get("subject_building_type")

            if explicit:

                candidates.append(str(explicit))

            terms = context.get("subject_terms")

            if isinstance(terms, (list, tuple)):

                candidates.extend(str(term) for term in terms if term)

        return " ".join(" ".join(candidates).split()).lower()

    def _compile_subject(self, understanding, context):
        """(lines, provenance) — the count-bearing primary subject phrase."""

        floors, floors_source = self._subject_floors(understanding, context)

        # A single-storey building is not a storey-counted high-rise.
        if floors is None or floors < 2:

            return [], {"applied": False, "reason": "no_affirmative_floor_target"}

        building_type = self._subject_building_type(understanding, context)

        if not any(
            marker in building_type for marker in self._HIGH_RISE_MARKERS
        ):

            return [], {
                "applied": False,
                "reason": "building_type_not_high_rise",
                "building_type": building_type,
            }

        # -------- qualifiers the request already carries --------
        #
        # Nothing here is invented: every qualifier is read back from what the
        # user actually wrote. `luxury` comes from the resolved style signals
        # (target / mix / mentions); `residential` comes from the grounded
        # building type, the intent's program functions, or the user's own
        # words for a dwelling tower.
        qualifiers = []

        style_signals = []

        style_value = understanding.get("style")

        if isinstance(style_value, dict):

            style_signals.append(style_value.get("target"))

            style_signals.extend(style_value.get("mix") or [])

            style_signals.extend(style_value.get("mentions") or [])

        elif style_value:

            style_signals.append(style_value)

        style_text = " ".join(
            str(item) for item in style_signals if item
        ).lower()

        if "luxury" in style_text or "luxury" in building_type:

            qualifiers.append("luxury")

        functions = understanding.get("functions") or []

        raw_words = " ".join(
            str(understanding.get(key) or "")
            for key in ("raw_text", "normalized_text")
        ).lower()

        residential = (
            "residential" in building_type
            or any(
                "residential" in str(item).lower()
                for item in functions
            )
            or any(
                marker in raw_words
                for marker in self._RESIDENTIAL_MARKERS
            )
        )

        if residential:

            qualifiers.append("residential")

        # -------- assemble the phrase --------
        #
        # T2I_FULL_TOWER_CAMERA_FRAMING_V1 — this sentence is the SUBJECT and
        # nothing else. The previous wording carried
        #     "…, with tall vertical proportions, shown from a distance so the
        #      complete building fits inside the frame."
        # which states two opposing things in one breath: "tall vertical
        # proportions" pushes the mass to fill the frame, while "from a
        # distance" asks it to shrink. Measured on the accepted run
        # (architectos_v11_00272_), the building filled the frame and the roof
        # left the image. Composition is owned by the render instruction's
        # framing sentence, which can state it once, coherently and with
        # explicit margins; the subject must not compete with it.
        head = "A slender " + str(floors) + "-storey "

        if qualifiers:

            head += " ".join(qualifiers) + " "

        head += "high-rise tower"

        sentence = head + "."

        provenance = {
            "contract": "HighRiseSubjectPhraseV1",
            "applied": True,
            "floors": floors,
            "floors_source": floors_source,
            "building_type": building_type,
            "qualifiers": qualifiers,
            "phrase": sentence,
            "grounding": (
                "explicit_affirmative_floor_count"
                "+grounded_high_rise_building_type"
            ),
        }

        return [sentence], provenance

    def _compile_style(self, understanding):
        style = understanding.get("style") or {}
        target = style.get("target")
        if not target:
            return []
        word = STYLE_WORD.get(target, target)
        direction = style.get("direction")
        level = (understanding.get("intensity") or {}).get("level", "MEDIUM")

        # KNOWLEDGE_RUNTIME_CONNECTION_V2 — article agreement. The template
        # says "Adopt a {word} architectural language", which reads "a Islamic"
        # / "a Iranian brick" for vowel-initial style words. Consonant-initial
        # styles are unaffected, so existing compiled prompts do not move.
        article = "an" if str(word)[:1].lower() in "aeiou" else "a"

        if direction == "increase":
            if level == "LOW":
                return [f"Make the architectural expression slightly more {word}."]
            if level == "HIGH":
                return [f"Clearly strengthen the {word} architectural expression."]
            return [f"Make the architectural expression more {word}."]
        if direction == "decrease":
            return [f"Reduce the {word} influence."]
        return [f"Adopt {article} {word} architectural language."]

    @staticmethod
    def _qualify_material(tone_word, word):
        """Prepend a tone modifier without repeating it.

        T2I_MODE_PROPAGATION_V1 — a material name can already carry its own
        tone ("light travertine stone" comes from `light_travertine_stone`),
        so prefixing the tone again produced "Use light light travertine
        stone". The check is on the material's own words, not on a list of
        known phrases, so it holds for any material whose name encodes a tone.
        """

        tokens = [
            token.strip(".,").lower()
            for token in str(word).replace("_", " ").split()
        ]

        if str(tone_word).strip().lower() in tokens:

            return word

        return str(tone_word) + " " + str(word)

    def _compile_materials(self, understanding):
        materials = understanding.get("materials") or {}
        primary = materials.get("primary")
        if not primary:
            return []
        # An ontology id that has no display word here is still snake_case
        # ("light_travertine_stone"); rendering it verbatim put underscores
        # into the CLIP prompt. Ontology ids are snake_case by convention, so
        # this is a formatting rule, not a per-phrase special case.
        word = MATERIAL_WORD.get(
            primary,
            str(primary).replace("_", " "),
        )
        tone = materials.get("tone")
        direction = materials.get("tone_direction")

        # T2I_PROMPT_FIDELITY_REPAIR_V1 — a source-bound frame tone is more
        # specific than an unscoped colour word elsewhere in the brief.  The
        # 25-storey request already resolves ``windows.frame_tone=dark`` for
        # «فریم‌های فلزی تیره», while warm-white lighting made the generic
        # material tone ``light``.  Project the existing specific field instead
        # of turning dark metal frames into contradictory light metal accents.
        frame_tone = (understanding.get("windows") or {}).get("frame_tone")
        if primary == "metal" and frame_tone:
            tone = frame_tone

        if direction == "increase" and tone:
            tone_word = TONE_COMPARATIVE.get(tone, tone)
            return [f"Use a {self._qualify_material(tone_word, word)} tone."]
        if direction == "decrease" and tone:
            tone_word = TONE_WORD.get(tone, tone)
            return [f"Reduce the {tone_word} tone of the {word}."]
        if tone:
            tone_word = TONE_WORD.get(tone, tone)
            line = f"Use {self._qualify_material(tone_word, word)}."
        else:
            line = f"Use {word}."

        # CLASSICAL_DETAIL_RETENTION_V1 — when the user asks for visible stone
        # courses and joints, the material sentence must carry that scale.
        # Without it the model falls back to whatever coursing the source or
        # its prior supplies, which is how "stone" became whitewashed brick.
        if understanding.get("stone_detail"):
            line += (
                " Render realistic large-scale ashlar stone courses with "
                "recessed joints, visible per-block tonal variation and "
                "believable thickness."
            )

        return [line]

    _ELEMENT_SENTENCE = {
        "columns": "correctly proportioned classical columns",
        # FACADE_KNOWLEDGE_HANDOFF_V1 — a pilaster is applied relief on the
        # wall plane, not a free-standing column. The wording is deliberately
        # different from "columns" and ties the rhythm to the EXISTING
        # structure, so the element cannot be read as authorisation to invent
        # new structural verticals.
        "pilasters": (
            "correctly proportioned pilasters applied as relief on the "
            "existing wall plane, aligned with the existing structural rhythm"
        ),
        "capitals": "accurately carved Corinthian or Composite capitals",
        "cornices": "richly articulated projecting cornices with dentils or modillions",
        # FACADE_KNOWLEDGE_HANDOFF_V1 — stringcourses follow the existing floor
        # levels; they are not a licence to add levels.
        "stringcourses": (
            "horizontal stone stringcourses at the existing floor levels"
        ),
        # FACADE_KNOWLEDGE_HANDOFF_V1 — surrounds frame the EXISTING openings
        # and never resize or add one.
        "window surrounds": (
            "carved stone window surrounds framing the existing openings "
            "without resizing or adding any opening"
        ),
        "arches": "meaningful arches with proper voussoirs",
        "pediments": "window pediments above the openings",
        # FACADE_KNOWLEDGE_HANDOFF_V1 — "stone balustraded BALCONIES" invented a
        # balcony whenever a balustrade was requested. A balustrade is a
        # protection element that can sit on an existing terrace or bay edge;
        # it is not authorisation to add a balcony. The wording now names the
        # element and constrains it to edges that already exist.
        "balustrades": (
            "stone balustrades with visible balusters, on existing terrace or "
            "bay edges only, without adding a balcony or a new projection"
        ),
        "sculptural relief": "sculptural architectural relief carving",
        "quoins": "corner quoins articulating the building edges",
    }

    # ARCHITECTURAL_REQUEST_FIDELITY_REPAIR_V1 — "central arched entrance"
    # names an ENTRANCE, positioned centrally, with an arch. The arches element
    # covered only the arch, so the entrance and its hierarchy disappeared.
    # Emitted only when the request actually placed the entrance centrally:
    # a bare mention of an entrance does not authorize a composition change.
    _CENTRAL_ENTRANCE_SENTENCE = (
        "a single dominant main entrance on the central axis of the facade"
    )

    # FACADE_RENDER_INSTRUCTION_AUTHORITY_V2 — a PROHIBITED element is not a
    # required one.
    #
    # MEASURED DEFECT: the accepted facade request says
    #   "Do not copy IMAGE B's … arches, protruding columns, gables or
    #    triangular pediment as new volumes"
    # and the understanding layer recorded `arches` and `columns` as ELEMENTS.
    # `_compile_elements` then emitted
    #   "REQUIRED ARCHITECTURAL ELEMENTS — include … classical columns …
    #    meaningful arches with proper voussoirs …"
    # — a prohibition turned into an executable design requirement, in direct
    # contradiction with the same prompt's preservation contract.
    #
    # The filter reads only the structured prohibitive channels that already
    # exist on the understanding (`negative_constraints`,
    # `reference_image_policy.do_not_copy`). No new parser, no vocabulary
    # change, and an element is kept whenever the request also names it as an
    # affirmative change target.
    _PROHIBITION_TARGETS = (
        "preserve",
        "remove",
    )

    def _prohibited_elements(self, understanding):
        """Element names that appear ONLY in a prohibitive channel."""

        parts = []

        for item in understanding.get("negative_constraints") or []:

            # Items are `{"constraint": <token>}` dicts in the structured
            # contract, but a plain string is also accepted so a prohibition
            # stated in the user's own words is still read.
            if isinstance(item, dict):

                for value in item.values():

                    if isinstance(value, str):

                        parts.append(value)

            else:

                parts.append(str(item))

        reference = understanding.get("reference_image_policy") or {}

        for item in reference.get("do_not_copy") or []:

            parts.append(str(item))

        text = " ".join(parts).lower()

        if not text:

            return set()

        names = set()

        for element in self._ELEMENT_SENTENCE:

            if element in text or element.rstrip("s") in text:

                names.add(element)

        return names

    def _affirmative_element_targets(self, understanding):
        """Element names the request affirmatively asks to change."""

        targets = set()

        for op in understanding.get("change_operations") or []:

            operation = str(op.get("operation") or "").lower()

            target = str(op.get("target") or "").lower()

            if operation in self._PROHIBITION_TARGETS or not target:

                continue

            targets.add(target)

            targets.add(target + "s")

        return targets

    #: NEOCLASSICAL_DESIGN_CHAT_ROUTE_V1 — markers that the request treats the
    #: building as ALREADY EXISTING. Kept local to this module: the compiler
    #: has no core imports by design, and a cycle with the understanding owner
    #: would be a worse defect than this small duplication.
    _EXISTING_BUILDING_MARKERS = (
        "existing", "this building", "the building", "unfinished building",
        "current building", "renovat", "retrofit", "reclad", "re-clad",
    )

    @classmethod
    def _existing_facade_redesign(cls, understanding):
        """A facade design on a building the request treats as existing.

        Gated on three independent facts so a new-build request is never
        captured: facade scope, a real style, and an explicit reference to the
        existing building.
        """

        if not isinstance(understanding, dict):
            return False

        if understanding.get("scope") != "facade":
            return False

        style = understanding.get("style")

        target = (style or {}).get("target") if isinstance(style, dict) else None

        token = str(target or "").strip().lower()

        if not token or token in ("unknown", "none", "existing"):
            return False

        hay = " " + " ".join(str(understanding.get("raw_text") or "").lower().split()) + " "

        return any(marker in hay for marker in cls._EXISTING_BUILDING_MARKERS)

    def _compile_elements(self, understanding):
        """Emit ONLY the elements the user explicitly named.

        The understanding contract previously had no element channel, so a
        request naming columns, capitals, cornices, relief and balustrades
        compiled to a style line and a material line. This restores the
        user's own words as executable design instructions, in the existing
        canonical vocabulary. It never adds an element the request did not
        name, and it is not an ontology enumeration.
        """
        elements = understanding.get("elements") or []

        prohibited = self._prohibited_elements(understanding)

        affirmative = self._affirmative_element_targets(understanding)

        phrases = [
            self._ELEMENT_SENTENCE[item]
            for item in elements
            if item in self._ELEMENT_SENTENCE
            and not (item in prohibited and item not in affirmative)
        ]

        # The entrance is a requested element in its own right when the
        # request places it. Centrality is the part the arches element could
        # never express, so only a centrally-placed entrance is added here.
        entrance = understanding.get("entrance") or {}
        if entrance.get("position") == "central":
            phrases.append(self._CENTRAL_ENTRANCE_SENTENCE)

        if not phrases:
            return []
        if len(phrases) == 1:
            listed = phrases[0]
        else:
            listed = ", ".join(phrases[:-1]) + " and " + phrases[-1]

        # FACADE_STYLE_TRANSFER_READINESS_V4 — the sentence used to end
        # "… structurally supported and integrated into the facade rather than
        # applied as surface decoration", which instructs the model to BUILD
        # structure. The same prompt also says "Apply classical detailing as a
        # SURFACE treatment only". A model cannot satisfy both, and the
        # accepted facade request asks for applied cornices and shallow relief
        # WITHOUT touching the building geometry.
        #
        # The tail is now chosen from the contract that is already on the
        # understanding: when the base geometry is preserved the elements are
        # applied decoration within the existing wall planes; when the request
        # genuinely changes the building the structural wording is unchanged.
        _reference_policy = understanding.get("reference_image_policy") or {}
        _preserve = understanding.get("preserve_constraints") or {}

        _surface_only = bool(
            _reference_policy.get("preserve_base_geometry")
            or _preserve.get("reference_geometry")
            # FACADE_KNOWLEDGE_HANDOFF_V1 — the SAME contradiction returns by
            # another route. A facade-DESIGN request on a real photograph has
            # no reference image, so neither key above is set; it states its
            # preservation as structured constraints instead ("preserve the
            # original structural frame, floor count and massing"). Without
            # this, that request was told the ornament must be "structurally
            # supported", i.e. built — while the same instruction preserved the
            # geometry. Base-geometry preservation is the governing condition,
            # whatever channel states it.
            or _preserve.get("geometry")
            or _preserve.get("massing")
            # NEOCLASSICAL_DESIGN_CHAT_ROUTE_V1 — and a third route: the
            # preservation clause is written in ENGLISH ("Preserve the
            # existing structural frame, opening positions, massing and camera
            # perspective"), which the understanding owner's preserve detector
            # does not read, so `_preserve` is empty even though the user said
            # it. The facade scope + a real style + an explicit reference to
            # the existing building is the same fact stated another way, and
            # the wording must not contradict it.
            or self._existing_facade_redesign(understanding)
        )

        if _surface_only:

            return [
                f"REQUIRED ARCHITECTURAL ELEMENTS — include {listed}; each must "
                "be correctly proportioned and applied as surface relief WITHIN "
                "the existing wall planes, without adding structural members, "
                "new volumes or any change to the building geometry."
            ]

        return [
            f"REQUIRED ARCHITECTURAL ELEMENTS — include {listed}; each must be "
            "correctly proportioned, structurally supported and integrated into "
            "the facade rather than applied as surface decoration."
        ]

    def _compile_modifications(self, understanding, dropped_indexes):
        lines = []
        for index, op in enumerate(understanding.get("change_operations", []) or []):
            if index in dropped_indexes:
                continue
            operation = op.get("operation")
            target = op.get("target")

            if operation == "increase" and target == "entrance":
                lines.append("Increase the architectural emphasis of the main entrance.")
            elif operation == "decrease" and target == "entrance":
                lines.append("Reduce the visual emphasis of the main entrance.")
            elif operation == "decrease" and target == "arches":
                lines.append("Reduce the use and visual dominance of arches.")
            elif operation == "increase" and target == "arches":
                lines.append("Introduce a moderate, controlled use of arches.")
            elif target == "window_frame":
                frame_tone = (
                    (understanding.get("windows") or {}).get("frame_tone")
                )
                materials = understanding.get("materials") or {}
                mentions = materials.get("mentions") or []
                material = "metal " if "metal" in mentions else ""
                qualifier = (
                    f"{frame_tone} {material}" if frame_tone else material
                )
                lines.append(
                    "Use slimmer, more refined %swindow framing."
                    % qualifier
                )
            elif operation == "decrease" and target == "complexity":
                lines.append("Reduce overall visual complexity and ornamentation.")
            elif operation == "replace" and target == "facade":
                lines.append("Redesign the facade expression while keeping the building form unchanged.")
            elif operation == "replace":
                lines.append(f"Replace the {target} expression.")
            elif operation == "remove":
                # FACADE-COORDINATION-CONSISTENCY_V1 — a removal is its own
                # ask. The element table below exists because the raw target
                # token can be pluralised or unsafe to read aloud ("Remove the
                # doors." reads as DEMOLISH every door); the sentence names the
                # element the user named, in the singular or the plural they
                # used.
                lines.append(REMOVAL_SENTENCE.get(
                    target, f"Remove the {target}."
                ))
            elif operation == "add":
                lines.append(f"Introduce a {target} element.")
            elif operation == "refine" and target == "facade":
                lines.append("Refine the facade expression with restrained detailing.")
        return lines

    def _compile_composition(self, understanding):
        facade = understanding.get("facade") or {}
        lines = []
        if facade.get("depth") == "increase":
            lines.append("Introduce greater facade depth through controlled recessed and projecting elements.")
        if facade.get("rhythm") == "regular":
            lines.append("Establish a more regular, balanced facade rhythm.")

        # CLASSICAL_COMPOSITION_V1 — a complete-building request must survive
        # compilation as an explicit framing instruction. "clean perspective"
        # does not ask for the whole building; this does.
        framing = understanding.get("framing") or {}
        if framing.get("full_building"):
            lines.append(
                "Show the COMPLETE building in a single frame: the entire facade, "
                "the roofline and the ground-level base must all be visible, with "
                "the full width of the building inside the image boundary. "
                "Do not crop the roof, the building edges or the base."
            )
        elif framing.get("detail_only"):
            lines.append(
                "Frame this as a close architectural detail study rather than a "
                "complete building view."
            )
        camera = framing.get("camera")
        if camera == "front_three_quarter":
            lines.append(
                "Use a front three-quarter architectural camera, far enough back "
                "to include the whole building with its landscaped surroundings."
            )
        elif camera == "front_elevation":
            lines.append(
                "Use a straight-on front elevation architectural camera, far "
                "enough back to include the whole building."
            )
        return lines

    def _compile_reference(self, understanding, context, required_context):
        reference = understanding.get("reference_image_policy") or {}
        if not reference.get("referenced"):
            return []
        lines = []
        role = reference.get("role")
        sentence = REFERENCE_SENTENCE.get(role)
        if sentence:
            lines.append(sentence)
        if reference.get("preserve_base_geometry") is True:
            lines.append("Keep the base building geometry as the authoritative reference.")
        if reference.get("requires_image") and not (context or {}).get("base_image"):
            required_context.append("reference_image")
        return lines

    def _compile_negative(self, understanding):
        lines = []
        for item in understanding.get("negative_constraints", []) or []:
            token = item.get("constraint")
            sentence = NEGATIVE_SENTENCE.get(token)
            if sentence:
                lines.append(sentence)
        return lines

    def _compile_quality(self, mode):
        quality = MODE_QUALITY.get(mode)
        if not quality:
            return []
        return [quality]

    # ------------------------------------------------------
    # MAIN
    # ------------------------------------------------------

    def compile(self, understanding, mode=None, context=None):
        understanding = understanding if isinstance(understanding, dict) else {}
        context = context or {}

        resolved_mode = self._normalize_mode(mode) or self._infer_mode(understanding, context)

        warnings = []
        required_context = []

        # -------- ambiguity gate --------
        ambiguities = understanding.get("ambiguities") or []
        has_signal = self._has_signal(understanding)
        if understanding.get("intent_type") == "clarify" or (ambiguities and not has_signal):
            return self._finalize(
                understanding=understanding,
                mode=resolved_mode,
                status="NEEDS_CLARIFICATION",
                sections={},
                positive="",
                negative="",
                preservation=[],
                changes=[],
                materials=[],
                style=[],
                composition=[],
                reference=[],
                hard_constraints=[],
                soft_preferences=[],
                required_context=[],
                unresolved=[dict(a) for a in ambiguities],
                warnings=[],
                conflicts=[],
                provenance={"resolution": "ambiguity_blocked"},
            )

        if not has_signal:
            return self._finalize(
                understanding=understanding,
                mode=resolved_mode,
                status="NO_ARCHITECTURAL_INTENT",
                sections={},
                positive="",
                negative="",
                preservation=[],
                changes=[],
                materials=[],
                style=[],
                composition=[],
                reference=[],
                hard_constraints=[],
                soft_preferences=[],
                required_context=[],
                unresolved=[],
                warnings=[],
                conflicts=[],
                provenance={"resolution": "no_architectural_signal"},
            )

        # -------- conflicts (preservation wins) --------
        conflicts, dropped_indexes = self._detect_conflicts(understanding)
        if conflicts:
            warnings.append({
                "code": "preservation_overrides_change",
                "detail": "one or more change operations were dropped in favour of hard preservation constraints",
            })

        # -------- compile sections in fixed order --------
        sections = {}
        has_change = any(
            op.get("operation") != "preserve"
            for op in understanding.get("change_operations", []) or []
        )
        preservation = self._compile_preservation(understanding, resolved_mode, context, warnings)

        # T2I_HIGH_RISE_SUBJECT_FIDELITY_V1 — the count-bearing primary
        # subject. Empty for every request without an explicit affirmative
        # floor target on a grounded high-rise type.
        subject, subject_provenance = self._compile_subject(understanding, context)

        style = self._compile_style(understanding)
        materials = self._compile_materials(understanding)
        modifications = self._compile_modifications(understanding, dropped_indexes)

        # CLASSICAL_DETAIL_RETENTION_V1 — the user's explicitly named
        # architectural elements are emitted alongside the change operations.
        # Only named elements appear; nothing is enumerated from the ontology.
        modifications = list(modifications) + self._compile_elements(understanding)
        composition = self._compile_composition(understanding)
        reference = self._compile_reference(understanding, context, required_context)
        quality = self._compile_quality(resolved_mode)
        negatives = self._compile_negative(understanding)

        # complementary positive restraint for ornament/style-limiting negatives
        if any(
            item.get("constraint") in (
                "avoid_heavy_ornament",
                "avoid_excessive_ornament",
                "avoid_excessive_arches",
                "avoid_excessive_luxury",
                "avoid_excessive_roman_style",
                "avoid_excessive_classical_style",
            )
            for item in understanding.get("negative_constraints", []) or []
        ):
            modifications.append("Use restrained detailing and controlled ornamentation.")

        task_scope = self._compile_task_scope(understanding, resolved_mode, has_change)

        sections["subject"] = " ".join(subject)
        sections["task_scope"] = " ".join(task_scope)
        sections["preservation"] = " ".join(preservation)
        sections["style"] = " ".join(style)
        sections["materials"] = " ".join(materials)
        sections["modifications"] = " ".join(modifications)
        sections["composition"] = " ".join(composition)
        sections["reference"] = " ".join(reference)
        sections["quality"] = " ".join(quality)

        positive = "\n".join(
            sections[key] for key in SECTION_ORDER if sections.get(key)
        )
        negative = "\n".join(negatives)

        hard_constraints = list(preservation) + list(negatives)
        soft_preferences = list(subject) + list(style) + list(materials) + list(modifications) + list(composition) + list(reference)

        status = "COMPILED_WITH_CONFLICTS" if conflicts else "COMPILED"

        provenance = {
            "compiler": "ArchitecturalPromptCompiler",
            "compiler_version": VERSION,
            "mode": resolved_mode,
            "mode_policy_sections": ["preservation", "quality"] if resolved_mode == "IMAGE_EDIT" else (["quality"] if resolved_mode in RENDER_MODES else []),
            "user_intent_sections": [k for k in SECTION_ORDER if k not in ("quality",)],
            "source_semantic_contract": understanding.get("contract"),
            "source_semantic_version": understanding.get("version"),
            # T2I_HIGH_RISE_SUBJECT_FIDELITY_V1 — structured provenance for
            # the primary subject: whether it applied, why, which count and
            # which grounded type produced it.
            "subject": subject_provenance,
        }

        return self._finalize(
            understanding=understanding,
            mode=resolved_mode,
            status=status,
            sections=sections,
            positive=positive,
            negative=negative,
            preservation=preservation,
            changes=modifications,
            materials=materials,
            style=style,
            composition=composition,
            reference=reference,
            hard_constraints=hard_constraints,
            soft_preferences=soft_preferences,
            required_context=required_context,
            unresolved=[],
            warnings=warnings,
            conflicts=conflicts,
            provenance=provenance,
        )

    # ------------------------------------------------------
    # finalize (builds contract + deterministic hash)
    # ------------------------------------------------------

    def _finalize(
        self, understanding, mode, status, sections, positive, negative,
        preservation, changes, materials, style, composition, reference,
        hard_constraints, soft_preferences, required_context, unresolved,
        warnings, conflicts, provenance,
    ):
        result = ArchitecturalCompiledPromptV1({
            "contract": CONTRACT,
            "version": VERSION,
            "compiler_version": VERSION,

            "source_semantic_contract": understanding.get("contract"),
            "source_semantic_version": understanding.get("version"),

            "raw_text": understanding.get("raw_text", ""),
            "normalized_text": understanding.get("normalized_text", ""),

            "mode": mode,
            "scope": understanding.get("scope", "unknown"),
            "status": status,

            "positive_prompt": positive,
            "negative_prompt": negative,

            "preservation_instructions": list(preservation),
            "change_instructions": list(changes),
            "material_instructions": list(materials),
            "style_instructions": list(style),
            "composition_instructions": list(composition),
            "reference_instructions": list(reference),

            "hard_constraints": list(hard_constraints),
            "soft_preferences": list(soft_preferences),

            "required_context": sorted(set(required_context)),
            "unresolved_items": list(unresolved),
            "warnings": list(warnings),
            "conflicts": list(conflicts),

            "prompt_sections": dict(sections),
            "provenance": dict(provenance),
        })

        result["deterministic_hash"] = self._hash(result)
        return result

    @staticmethod
    def _hash(result):
        payload = {k: v for k, v in result.items() if k != "deterministic_hash"}
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ==========================================================
# SINGLETON + CONVENIENCE
# ==========================================================

architectural_prompt_compiler = ArchitecturalPromptCompiler()


def compile_prompt(understanding, mode=None, context=None):
    """Module-level convenience wrapper over the canonical 2D-3 compiler."""
    return architectural_prompt_compiler.compile(understanding, mode=mode, context=context)
