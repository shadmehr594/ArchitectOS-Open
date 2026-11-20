# ==========================================================
# ArchitectOS Image Edit Prompt Builder v1.3
# Geometry Preserving + Architectural Style Transformation
# Img2Img Facade Intelligence
# ==========================================================

import re

from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    resolve_geometry_authority,
    authority_note,
    preserve_lists,
    STATUS_CONFLICT,
    STATUS_UNRESOLVED,
)


# ==========================================================
# R4_POSITIVE_INSTRUCTION_CONTRACT_V1 — REQUESTED CHANGE
#
# The lighting suppression at the end of `build()` removes the FACADE
# TRANSFORMATION and ARCHITECTURAL VISUALIZATION QUALITY sections
# structurally. That is correct — a lighting request must not ask for a facade
# redesign — but on its own it left this builder with a preservation contract
# and NO statement of what to change.
#
# When the authoritative delta already carries a compiled prompt, the normal
# production path supplies it as `compiled_render_prompt`
# (`_route_image_edit()` calls `edit_delta_prompt()`), so the change is already
# in the effective instruction. Restating it here would duplicate the delta and
# spend T5 budget that the DO-NOT block needs — R3 measured that block being
# displaced to token 612 of a 512 window. The section is therefore emitted
# ONLY when the delta has no compiled prompt of its own, i.e. exactly when this
# builder IS the whole instruction.
#
# Every sentence is BUILDING-AGNOSTIC: no brick, no villa, no storey count.
# ==========================================================

# ==========================================================
# FINAL_CORRECTED_FACADE_GPU_PREFLIGHT_V1 — TRUSTED PROVENANCE
#
# The suppression below keys on the STRUCTURED contract object carried at
# `design["r4_preservation_contract"]`, never on a rendered textual marker.
#
# Text cannot be provenance here: the composed instruction reproduces the
# user's request verbatim, so a request containing the literal header would
# otherwise be indistinguishable from a product-issued contract and could
# suppress the only geometry constraint in the instruction.
# ==========================================================

_CONTRACT_NAME = "ArchitecturalPreservationContractV1"


_LIGHTING_QUALITY_CHANGE = {

    "warmer": (
        "REQUESTED CHANGE: adjust only the illumination of this existing "
        "building, slightly warmer and more natural daylight on the same "
        "surfaces, same time of day, same sun position, same sky"
    ),

    "cooler": (
        "REQUESTED CHANGE: adjust only the illumination of this existing "
        "building, slightly cooler and cleaner daylight on the same "
        "surfaces, same time of day, same sun position, same sky"
    ),

    "more_natural": (
        "REQUESTED CHANGE: adjust only the illumination of this existing "
        "building, more natural and better balanced daylight on the same "
        "surfaces without changing their material colour, same time of day, "
        "same sun position, same sky"
    ),
}


def _requested_change_section(edit_delta):

    """Bounded CHANGE statement for a lighting-quality edit, or "".

    Returns "" for every other class, so a material/style restyle keeps the
    FACADE TRANSFORMATION contract unchanged, and "" when the delta is already
    authoritative (see the anti-duplication note above).
    """

    if not isinstance(edit_delta, dict):

        return ""

    if str(edit_delta.get("edit_class") or "") != "lighting_change":

        return ""

    if str(edit_delta.get("prompt") or "").strip():

        return ""

    return _LIGHTING_QUALITY_CHANGE.get(
        str(edit_delta.get("lighting_quality") or ""),
        "",
    )


class ImageEditPromptBuilder:


    VERSION = "1.3"

    # Architectural knowledge contains both construction vocabulary and
    # non-structural visual language.  Only the latter can safely enrich a
    # fixed-geometry image edit.  These markers classify the *role* of terms
    # already supplied by the existing resolver; they are not another style
    # vocabulary or ontology.
    _SURFACE_LANGUAGE_MARKERS = (
        "detail",
        "ornament",
        "pattern",
        "motif",
        "calligraphy",
        "relief",
        "texture",
        "finish",
        "appearance",
        "identity",
        "expression",
    )

    _SURFACE_LANGUAGE_EXCLUSIONS = (
        # Despite the word "expression", this cue can induce a scale/massing
        # change and is therefore not safe under exact-geometry preservation.
        "monumental",
    )


    def semantic_strings(self, value):

        result = []

        if isinstance(value, str):

            cleaned = value.replace("_", " ").strip()

            if cleaned and cleaned != "UNKNOWN":

                result.append(cleaned)

        elif isinstance(value, dict):

            for key, item in value.items():

                if key in (
                    "contract",
                    "version",
                    "provenance",
                    "unresolved",
                    "geometry_preservation_method",
                    "selection_specificity",
                    "source",
                    "styles",
                    "compatible_options",
                ):

                    continue

                result.extend(self.semantic_strings(item))

        elif isinstance(value, (list, tuple)):

            for item in value:

                result.extend(self.semantic_strings(item))

        unique = []
        seen = set()

        for item in result:

            marker = item.lower()

            if marker not in seen:

                seen.add(marker)
                unique.append(item)

        return unique


    def surface_language_terms(self, resolved, admitted_terms):
        """Project existing knowledge into non-structural surface cues.

        Geometry-changing suggestions have already been rejected by
        ``resolve_geometry_authority``.  This second, narrower projection uses
        only facade-language terms from the existing resolver and keeps cues
        whose semantic role is finish/detail/pattern/expression.  Explicit
        caller facade details are retained when the authority layer admitted
        them.  Materials, compatible style families and implementation
        metadata are never read here.
        """

        if not isinstance(resolved, dict):

            return []

        facade_language = resolved.get("facade_language") or {}

        if not isinstance(facade_language, dict):

            facade_language = {}

        explicit_details = self.semantic_strings(
            resolved.get("user_facade_details")
        )

        candidates = self.semantic_strings({
            "composition": facade_language.get("composition"),
            "elements": facade_language.get("elements"),
            "user_facade_details": explicit_details,
        })

        admitted = {
            str(term).replace("_", " ").strip().lower()
            for term in (admitted_terms or ())
        }
        explicit = {
            str(term).replace("_", " ").strip().lower()
            for term in explicit_details
        }

        result = []

        for term in candidates:

            display = str(term).replace("_", " ").strip()
            lowered = display.lower()

            if not display or lowered not in admitted:

                continue

            if any(blocked in lowered for blocked in self._SURFACE_LANGUAGE_EXCLUSIONS):

                continue

            if (
                lowered not in explicit
                and not any(
                    marker in lowered
                    for marker in self._SURFACE_LANGUAGE_MARKERS
                )
            ):

                continue

            if lowered not in {item.lower() for item in result}:

                result.append(display)

        return result



    def build(
        self,
        intent
    ):


        print(
            "🔥 IMAGE EDIT BUILDER INPUT:",
            intent
        )


        # ==================================================
        # V4.3D — EDIT CLASS (must be read BEFORE the unwrap)
        #
        # `PromptRouter` flattens the payload to `{**architectural_intent,
        # "_user_prompt": …}` and `handle_image_edit()` places the compiled
        # edit delta inside `architectural_intent`, so the classification is at
        # the top level here. Reading it first means the later unwrap below
        # cannot lose it.
        #
        # A lighting-only edit must not be handed generic facade-restyle
        # instructions; a material/style edit still must be.
        # ==================================================

        _edit_delta = (
            intent.get("edit_delta")
            if isinstance(intent, dict)
            else None
        )

        _edit_class = (
            _edit_delta.get("edit_class")
            if isinstance(_edit_delta, dict)
            else None
        )

        _facade_restyle_suppressed = _edit_class in (
            "time_of_day_change",
            "lighting_change",
        )

        # AUTHORITY_HANDOFF_V1 — the router's raw user turn lives at the top
        # level; capture it before the architectural_intent unwrap below.
        _router_user_prompt = (
            intent.get("_user_prompt")
            if isinstance(intent, dict)
            else None
        )

        # ==================================================
        # FACADE_FULL_PROMPT_SEMANTIC_CONSISTENCY_V1
        #
        # The admitted facade-redesign route states a STRUCTURED preservation
        # contract (ArchitecturalPreservationContractV1) upstream, and that
        # contract is carried into this same instruction. This builder then
        # emits a SECOND, element-level preservation block:
        #
        #   PRESERVE EXACTLY: ... openings - windows - doors -
        #   existing terraces, balconies, stairs and railings ...
        #
        # Two preservation statements in one instruction — one
        # property-specific, one element-level — is a contradiction, and a
        # model resolves it in favour of the freeze. Measured: the captured
        # 9,506-char instruction permitted "railing appearance ... design,
        # material, colour and pattern" at offset ~3.5k and required
        # "existing terraces, stairs and railings" preserved at offset ~6.1k.
        #
        # The structured contract is the authority for this route, so this
        # block is suppressed HERE and only here: the FACADE TRANSFORMATION
        # and QUALITY sections are kept, because they carry resolved facade
        # knowledge and rendering quality the contract does not.
        #
        # Detection is structural, not textual guesswork: the design already
        # carries the composed instruction, and its contract marker is the
        # same explicit marker the render runtime uses for
        # RenderConstraintBlockV1. With no structured contract present the
        # historical block is emitted unchanged, so generic image edits,
        # material-only edits and lighting edits are untouched.
        # ==================================================

        _design_context = (
            intent.get("design_context")
            if isinstance(intent, dict)
            else None
        )

        _design = (
            _design_context.get("design")
            if isinstance(_design_context, dict)
            else None
        )

        _carried_instruction = (
            _design.get("compiled_render_prompt")
            if isinstance(_design, dict)
            else None
        )

        if isinstance(_carried_instruction, dict):

            _carried_instruction = " ".join(
                str(value) for value in _carried_instruction.values()
            )

        # ----------------------------------------------
        # FINAL_CORRECTED_FACADE_GPU_PREFLIGHT_V1 — TRUSTED PROVENANCE
        #
        # A textual header is NOT provenance. The composed instruction
        # reproduces the user's request verbatim, so a request that contains
        # the literal header
        #   "ARCHITECTURAL PRESERVATION CONTRACT (ArchitecturalPreservationContractV1):"
        # would otherwise suppress the preservation block and remove the only
        # geometry constraint from the instruction.
        #
        # The authoritative signal is the structured contract OBJECT that
        # chat_architect hands to the payload from
        # `context["r4_preservation_contract"]` (set only from the bounded
        # admission verdict at chat_architect.py:2332 — "Nothing is persisted
        # and no client input can set this"). The builder reads it as data and
        # never trusts the rendered text.
        # ----------------------------------------------

        _carried_contract = (
            _design.get("r4_preservation_contract")
            if isinstance(_design, dict)
            else None
        )

        _structured_contract_present = bool(
            isinstance(_carried_contract, dict)
            and str(_carried_contract.get("contract") or "")
            == _CONTRACT_NAME
            and _carried_contract.get("preserve")
        )


        # ==================================================
        # NORMALIZE PROMPT ROUTER CONTEXT
        # ==================================================

        if "architectural_intent" in intent:

            intent = intent.get(
                "architectural_intent",
                {}
            )


        # ==================================================
        # AUTHORITY_HANDOFF_V1 — geometry authority inputs
        #
        # The fixed-geometry contract ALREADY exists on the intent
        # (`preserve_geometry`, `preserve_constraints`, `geometry_authority`),
        # but it used to reach the prompt only as English prose while the
        # resolved style vocabulary was injected unconditionally. These values
        # are captured here so the vocabulary can be checked against them at
        # the point of injection. No new authority model is introduced.
        # ==================================================

        _authority_preserve_geometry = bool(
            intent.get("preserve_geometry", True)
        )

        _authority_constraints = (
            intent.get("preserve_constraints")
            or ()
        )

        _authority_user_text = (
            intent.get("normalized_prompt")
            or _router_user_prompt
            or ""
        )

        self.last_geometry_authority = None


        materials = intent.get(
            "materials",
            []
        )


        style = intent.get(
            "style",
            ""
        )



        request_type = intent.get(
            "request_type",
            ""
        )

        # FACADE_PROMPT_BUILDER_FINAL_CORRECTION_V3 — the TARGET supplies the
        # building category. The reference supplies appearance only, so it must
        # never lend its type to the target. Read the grounded classification
        # when the understanding provides one; otherwise stay neutral.
        _target_building_type = str(
            intent.get("building_type") or ""
        ).strip().lower()

        # Only a grounded classification may name a type. An unknown type stays
        # neutral ("building") rather than inheriting the reference's.
        if "villa" in _target_building_type:

            _type_phrase = "villa"

        elif (
            "apartment" in _target_building_type
            or "flat" in _target_building_type
            or "block" in _target_building_type
        ):

            _type_phrase = "apartment building"

        elif "residential" in _target_building_type:

            _type_phrase = "residential building"

        else:

            _type_phrase = "building"



        if isinstance(
            materials,
            list
        ):

            materials_text = ", ".join(
                materials
            )

        else:

            materials_text = str(
                materials
            )



        material_lower = materials_text.lower()

        style_lower = str(
            style
        ).lower()



        edits = []


        resolved = intent.get(
            "resolved_facade_knowledge",
            {}
        )


        if isinstance(resolved, dict) and resolved.get("contract") == "ResolvedFacadeKnowledgeV1":

            facade_terms = self.semantic_strings({
                "canonical_style": resolved.get("canonical_style"),
                "facade_language": resolved.get("facade_language"),
                "composition": resolved.get("composition"),
                "symmetry": resolved.get("symmetry"),
                "vertical_horizontal_emphasis": resolved.get("vertical_horizontal_emphasis"),
                "solid_void_strategy": resolved.get("solid_void_strategy"),
                "entrance_hierarchy": resolved.get("entrance_hierarchy"),
                "opening_treatment": resolved.get("opening_treatment"),
                "balcony_treatment": resolved.get("balcony_treatment"),
                "parapet_treatment": resolved.get("parapet_treatment"),
                "architectural_elements": resolved.get("architectural_elements"),
                "materials": resolved.get("materials"),
                "surface_strategy": resolved.get("surface_strategy"),
                "user_facade_details": resolved.get("user_facade_details"),
            })

            # V4.3D — a lighting-only edit must not receive facade-language /
            # surface instructions. The V4.3C audit measured this sentence
            # reaching morning, sunset AND night prompts. Conflict-term removal
            # is not usable here: the block is comma-joined, so filtering it
            # would delete only "…: modern" and orphan the rest of the facade
            # vocabulary. The guard is the narrow fix; explicit material and
            # style edits keep the knowledge unchanged.
            # AUTHORITY_HANDOFF_V1 — the resolved ontology is DESIGN GUIDANCE.
            # Vocabulary that would change a fixed-geometry domain is withheld
            # BEFORE it can become an instruction; material, finish, colour,
            # lighting and surface terms always pass. The decision is recorded
            # on the builder so the caller can report a conflict truthfully
            # instead of presenting an unsupported edit as a success.
            _authority = resolve_geometry_authority(
                facade_terms,
                preserve_geometry=_authority_preserve_geometry,
                preserve_constraints=_authority_constraints,
                user_text=_authority_user_text,
                edit_class=_edit_class,
                resolved_facade_knowledge=resolved,
            )

            self.last_geometry_authority = _authority

            facade_terms = _authority["admitted_terms"]

            # FACADE_MATERIAL_VISUAL_ACCEPTANCE_V1 — the resolved ontology
            # carries cross-domain suggestions (compatible styles inside
            # materials, recommended materials inside surface_strategy) and
            # implementation labels.  For a single-domain edit we reduce the
            # projection to the single requested concept so the FACADE
            # TRANSFORMATION sentence cannot introduce unrequested styles,
            # materials or structural elements.  Combined edits keep the full
            # vocabulary (labels already filtered by semantic_strings).
            _has_style = (
                isinstance(_edit_delta, dict)
                and bool(_edit_delta.get("style"))
            )
            _has_material = (
                isinstance(_edit_delta, dict)
                and bool(_edit_delta.get("material"))
            )

            # HAIKU_ARCHITECTURAL_KNOWLEDGE_FIDELITY_V2 — project ONLY the
            # domains the user actually asked for.
            #
            # The previous version reduced single-domain edits but handed a
            # COMBINED style+material edit the whole admitted ontology. Because
            # the geometry authority is inert unless the request states
            # preservation clause by clause, that dump carried construction
            # vocabulary ("columns", "pilasters", "cornices", "stone frames")
            # and another style family's label ("modern luxury") into an edit
            # whose geometry is fixed. Measured on the production path.
            #
            # Single-domain and combined edits follow ONE authority rule: the
            # executable sentence names the requested style/material, then may
            # add only NON-STRUCTURAL surface-language cues projected from the
            # existing resolver. This retains useful architectural intelligence
            # without restoring the former ontology dump.
            _surface_terms = []

            if (
                _edit_class in ("style_change", "material_change")
                and not _facade_restyle_suppressed
            ):

                _labels = []

                if _edit_class == "style_change" or _has_style:

                    _style_name = resolved.get("canonical_style") or style

                    if _style_name and str(_style_name) != "UNKNOWN":

                        _labels.append(str(_style_name).replace("_", " "))

                    _surface_terms = self.surface_language_terms(
                        resolved,
                        facade_terms,
                    )

                if _edit_class == "material_change" or _has_material:

                    # The material the USER asked for outranks the resolved
                    # style's recommended materials. `primary` falls back to
                    # the style record when the intent carries no material, so
                    # reading it first turned a generic "stone" request into
                    # the style default ("travertine") for any caller that
                    # carries the request in the delta, as the delta contract
                    # defines.
                    _mat = (
                        _edit_delta.get("material")
                        if isinstance(_edit_delta, dict)
                        else None
                    )

                    if not _mat:

                        _resolved_materials = resolved.get("materials")

                        if isinstance(_resolved_materials, dict):

                            _mat = _resolved_materials.get("primary")

                        elif isinstance(_resolved_materials, list):

                            _mat = _resolved_materials

                        if isinstance(_mat, list) and _mat:

                            _mat = _mat[0]

                    if not _mat or _mat == "UNKNOWN":

                        _mat = materials_text

                    if _mat and str(_mat) != "preserve existing facade materials":

                        # Display form, never the internal identifier
                        # ("natural_stone" is an ontology id, not a material
                        # name the image model should read).
                        _labels.append(str(_mat).replace("_", " "))

                for _surface_term in _surface_terms:

                    if _surface_term.lower() not in {
                        item.lower() for item in _labels
                    }:

                        _labels.append(_surface_term)

                facade_terms = _labels

            if not _facade_restyle_suppressed and facade_terms:

                _facade_sentence = (
                    "Apply the resolved ArchitectOS facade knowledge: "
                    + ", ".join(facade_terms[:60])
                    + ". Treat these as facade-language and surface instructions, not as permission to alter source geometry."
                )

                if _surface_terms:

                    _facade_sentence = (
                        _facade_sentence
                        + " Express the listed cues only through shallow applied "
                        "detail, relief, pattern or colour articulation on the "
                        "existing wall planes; do not add, remove, resize or "
                        "relocate any built element, and do not change a material "
                        "unless the user explicitly requested it."
                    )

                _authority_qualifier = authority_note(_authority)

                if _authority_qualifier:

                    _facade_sentence = (
                        _facade_sentence
                        + " "
                        + _authority_qualifier
                    )

                edits.append(_facade_sentence)



        if self.last_geometry_authority is None:

            # No resolved facade knowledge was present, so the style ontology
            # contributes nothing here — but an explicit geometric operation
            # can still conflict with the fixed contract and must still be
            # reported rather than silently absorbed by the generic builder.
            self.last_geometry_authority = resolve_geometry_authority(
                (),
                preserve_geometry=_authority_preserve_geometry,
                preserve_constraints=_authority_constraints,
                user_text=_authority_user_text,
                edit_class=_edit_class,
            )

        # ==================================================
        # TRAVERTINE CLASSICAL
        # ==================================================

        if (
            not resolved
            and
            "travertine" in material_lower
            or
            not resolved
            and
            "تراورتن" in material_lower
        ):

            # AUTHORITY_HANDOFF_V1 — this legacy fallback used to inject
            # cornices, pilasters and columns unconditionally, bypassing the
            # authority decision entirely. Under a fixed-geometry contract
            # those are construction operations with no authority, so they are
            # withheld like any other structural suggestion.
            _fallback_authority = self.last_geometry_authority or {}

            _fallback_fixed = list(
                _fallback_authority.get("fixed_domains") or []
            )

            _classical_lines = """
                Create classical architectural facade language:
                symmetrical facade composition,
                elegant stone window surrounds,
                decorative stone frames,
                classical cornices,
                pilasters,
                refined columns where compatible,
                balanced vertical rhythm,
                premium residential classical architecture.
                """

            if "massing" in _fallback_fixed or "roof" in _fallback_fixed:

                # FACADE_PROMPT_BUILDER_FINAL_CORRECTION_V3 — the previous
                # sentence ("Do not add cornices, pilasters, columns or any
                # other new built element") forbade exactly the treatment the
                # user asked for ("applied cornice detailing", "restrained
                # classical pilaster-like flat relief", "surrounds around
                # EXISTING openings"). It also stopped forbidding the things
                # that really are dangerous, because it lumped decoration and
                # structure into one word list.
                #
                # Decoration applied WITHIN the preserved envelope is not a
                # geometric change; a new structural element is. The sentence
                # now states that boundary explicitly instead of banning both.
                _classical_lines = """
                Apply classical detailing as a SURFACE treatment only:
                within the existing facade envelope and wall planes.
                PERMITTED: applied cornice expression that follows the existing
                roofline without altering it; shallow pilaster-like flat relief;
                stone window and door surrounds that frame the existing openings
                without resizing them; material contrast and surface articulation.
                FORBIDDEN: new structural columns, load-bearing projections,
                added building volume, new balconies, any change to the floor
                count, recut or enlarged windows or doors, a changed roofline,
                and any geometry copied from the reference building.
                """

            edits.append(

                """
                Transform the facade appearance into a luxury classical travertine stone residence.

                Use natural beige travertine stone cladding.
                """

                + _classical_lines

                + "\n                The facade must read as a classical travertine "
                "renovation of this existing "
                + _type_phrase
                + ", not as a different building type.\n                "

            )



        # ==================================================
        # STYLE INTELLIGENCE
        # ==================================================

        if not resolved and style and not any(
            x in style_lower
            for x in [
                "existing",
                "unknown",
                "original"
            ]
        ):

            # AUTHORITY_HANDOFF_V1 — "proportions" is a geometric instruction,
            # not a style word. It is dropped when massing is fixed, exactly
            # like the resolved-vocabulary path.
            _style_authority = self.last_geometry_authority or {}

            _style_vocab = "facade rhythm, ornamentation, material expression, architectural details"

            if "massing" not in (_style_authority.get("fixed_domains") or []):

                _style_vocab = "facade rhythm, proportions, " + _style_vocab


            edits.append(

                f"""

                Transform the facade architectural style into {style}.

                Apply the correct architectural vocabulary:
                {_style_vocab}.

                """

            )



        # ==================================================
        # GENERIC MATERIAL
        # ==================================================

        if (
            not resolved
            and
            materials_text
            and
            "travertine" not in material_lower
            and
            "تراورتن" not in material_lower
        ):


            edits.append(

                f"""

                Replace only the facade surface material with {materials_text}.

                Keep the architectural form unchanged.

                """

            )



        # ==================================================
        # FACADE_RENDERING_FIRST_I2I_ADMISSION_V1 — THE USER'S OWN REQUEST
        #
        # Everything above is a template: a generic facade-restyle document
        # that says "transform the facade" without saying WHAT THIS USER
        # asked for. A request for modern Iranian brick with dark metal
        # window frames used to reach the sampler as style/material
        # vocabulary only, and a generic classical sentence could replace it.
        #
        # The verbatim request is therefore emitted as the authoritative
        # CHANGE statement whenever this builder IS the whole instruction
        # (no compiled delta prompt) and the edit is a restyle. It is never
        # emitted for a lighting-only edit, which must carry no facade
        # language, and it is never emitted when the delta is already
        # authoritative — that would duplicate the instruction and spend T5
        # budget the DO-NOT block needs.
        #
        # It is ALSO never emitted when the geometry authority reported a
        # CONFLICT or an UNRESOLVED operation. In that state the authority
        # layer has deliberately WITHHELD part of the request ("add a
        # triangular pediment" against "the roofline must stay unchanged").
        # Re-pasting the raw sentence would re-authorise exactly the
        # structural change the authority refused, turning a withheld
        # instruction into an emitted one. The existing clarification note
        # remains the only statement in that case.
        # ==================================================

        _verbatim_request = " ".join(str(_router_user_prompt or "").split())

        _delta_is_authoritative = bool(
            isinstance(_edit_delta, dict)
            and str(_edit_delta.get("prompt") or "").strip()
        )

        _authority_state = self.last_geometry_authority or {}

        _authority_withheld = bool(
            str(_authority_state.get("status") or "")
            in (STATUS_CONFLICT, STATUS_UNRESOLVED)
            or _authority_state.get("conflicts")
        )

        if (
            _verbatim_request
            and not _facade_restyle_suppressed
            and not _delta_is_authoritative
            and not _authority_withheld
        ):

            # FACADE_PROMPT_BUILDER_FINAL_CORRECTION_V3 — this block used to
            # assert "verbatim user instruction, authoritative" no matter what
            # it was handed. On the failed GPU job (prompt_id ff38a9d2…) the
            # text under that label was a COMPILER TAG LIST, and the real user
            # request was already stated authoritatively by the preservation
            # contract — so the model read two competing "authoritative" blocks.
            #
            # The builder is a DERIVED channel. It now labels its own text for
            # what it is: the user's request when the text really is the user's
            # request, and a compiled instruction when it is not. The single
            # verbatim-authority claim stays with the preservation contract.
            _authoritative_user_text = " ".join(
                str(_authority_user_text or "").split()
            )

            _is_user_words = bool(
                _authoritative_user_text
                and _verbatim_request == _authoritative_user_text
            )

            if _is_user_words:

                _label = "REQUESTED CHANGE (user request, restated): "

            else:

                _label = (
                    "REQUESTED CHANGE (compiled instruction, derived from the "
                    "user request): "
                )

            edits.append(_label + _verbatim_request)

        if not edits:


            edits.append(

                """
                Improve facade appearance with realistic architectural materials
                while keeping the existing architectural identity.
                """

            )



        edit_text = " ".join(
            edits
        )

        # AUTHORITY_HANDOFF_V1 — the preservation block is derived from the
        # domains that are ACTUALLY fixed after explicit authorisations have
        # been applied. Previously it was a static list, so an authorised roof
        # redesign still emitted "PRESERVE EXACTLY: roof shape" and
        # "DO NOT: redesign the building" — the instruction contradicted the
        # authority decision it was supposed to express.
        _authority_final = self.last_geometry_authority or {}

        _preserve_lines, _prohibit_lines = preserve_lists(_authority_final)

        _preserve_block = "\n".join("- " + line for line in _preserve_lines)

        _prohibit_block = "\n".join("- " + line for line in _prohibit_lines)



        prompt = f"""

STRICT ARCHITECTURAL IMG2IMG EDIT.

THIS IS AN EXISTING BUILDING IMAGE.

The original building is the exact geometric reference.


==================================================
GEOMETRY PRESERVATION
==================================================

PRESERVE EXACTLY:

{_preserve_block}


DO NOT:

{_prohibit_block}



==================================================
FACADE TRANSFORMATION
==================================================


{edit_text}



==================================================
ARCHITECTURAL VISUALIZATION QUALITY
==================================================

Create a professional architectural renovation visualization.

The output should look like a real architect-designed facade transformation.

Maintain exact geometry but strongly express the requested architectural style.

Photorealistic architectural visualization.

High detail realistic materials.

Professional archviz render.

Natural lighting.

"""


        # ==================================================
        # V4.3D — LIGHTING-ONLY EDITS CARRY NO FACADE INSTRUCTION
        #
        # The template above is a FACADE-TRANSFORMATION document: it ends with
        # a quality section that asks for "a real architect-designed facade
        # transformation" and to "strongly express the requested architectural
        # style". A morning/sunset/night request must not carry either.
        #
        # Conflict-term filtering CANNOT do this safely here. The template is
        # comma-free once the facade-knowledge sentence is suppressed, so the
        # whole builder tail becomes ONE segment and any matching term deletes
        # the GEOMETRY PRESERVATION block with it (measured: the prompt dropped
        # from 1 310 to 582 chars and lost the geometry contract entirely).
        # The sections are therefore removed structurally, and only for the
        # two lighting classes.
        # ==================================================

        # ==================================================
        # FACADE_FULL_PROMPT_SEMANTIC_CONSISTENCY_V1 — see the detection
        # above. The GEOMETRY PRESERVATION section is removed STRUCTURALLY,
        # by its own headings, in the same way this builder already removes
        # the facade sections for a lighting-only edit. The structured
        # contract has already stated these constraints in property-specific
        # form; this block's element nouns ("windows", "doors", "railings")
        # are what froze appearance.
        # ==================================================

        if _structured_contract_present:

            prompt = re.sub(
                r"=+\s*GEOMETRY PRESERVATION\s*=+.*?(?==+\s*FACADE TRANSFORMATION)",
                "",
                prompt,
                flags=re.S,
            )

        if _facade_restyle_suppressed:

            prompt = re.sub(
                r"=+\s*ARCHITECTURAL VISUALIZATION QUALITY\s*=+.*\Z",
                "",
                prompt,
                flags=re.S,
            )

            prompt = re.sub(
                r"=+\s*FACADE TRANSFORMATION\s*=+.*\Z",
                "",
                prompt,
                flags=re.S,
            )

            # R4_POSITIVE_INSTRUCTION_CONTRACT_V1 — after the facade sections
            # are removed the builder must still say WHAT to change, otherwise
            # a lighting-only edit reaches the sampler as preservation prose
            # with no requested modification.
            _change_section = _requested_change_section(_edit_delta)

            if _change_section:

                prompt = prompt.rstrip() + "\n\n" + _change_section + "\n"


        final_prompt = " ".join(
            prompt.split()
        )


        print(
            "🔥 IMAGE EDIT FINAL PROMPT:",
            final_prompt
        )


        return final_prompt
