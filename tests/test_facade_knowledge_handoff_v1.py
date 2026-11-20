"""FACADE_KNOWLEDGE_HANDOFF_V1 — CPU end-to-end acceptance.

Drives the REAL production chain:

    SharedFacadeKnowledgeResolverV1.resolve()
      -> resolve_design_decision(resolved_facade_knowledge=...)
      -> _knowledge_projection()
      -> decision_instruction_block()          (RenderConstraintBlockV1)
      -> resolve_render_prompt()               (the real composer)
      -> final prompt
      -> ImageWorkflowInjector.inject()        (nonexecuting graph capture)

No GPU, no ComfyUI request, no model, no vision provider, no live Chat turn.

ACCEPTANCE CASE
    The previously accepted user building photograph
    `uploads/chat_media/c4b77de5d388_Gemini_Generated_Image_2cc3us2cc3us2cc3.jpg`
    (1792x2400, sha256 8052c743...64c872) is the EXISTING ARCHITECTURAL
    REFERENCE for this milestone: four upper levels over an open ground level,
    brick infill on the upper left facade, concrete-block infill on the lowest
    infill level, eight unglazed openings on the left, four deep open bays on
    the right with ribbed slab soffits, a stepped roof/parapet, and an
    unfinished foreground with boundary walls.

    `IMAGE_EVIDENCE` below is a FIXTURE that stands in for what the production
    vision layer reports for such a photograph. It is NOT an analysis of that
    image, it asserts nothing about its pixels, and no coordinate, polygon or
    measurement appears anywhere in this file.
"""

import copy
import json
import os

import pytest

from core.architecture.knowledge.resolved_facade_knowledge import (
    SharedFacadeKnowledgeResolverV1,
)
from core.cognition.architectural_render_instruction_v1 import (
    build_render_instruction,
    understand,
)
from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    decision_instruction_block,
    resolve_design_decision,
)
from core.prompt_intelligence.image_edit_delta_v1 import (
    compile_edit_delta,
    conflict_terms as edit_delta_conflict_terms,
)
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)
from core.render.image_workflow_injector import ImageWorkflowInjector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SOURCE_IMAGE = os.path.join(
    ROOT, "uploads", "chat_media",
    "c4b77de5d388_Gemini_Generated_Image_2cc3us2cc3us2cc3.jpg",
)

SOURCE_SHA256 = (
    "8052c743189202425e37e41bf82b3681d2aebcb155ee2c7d73f585c1cb64c872"
)

PRESERVE = (
    "number_of_floors",
    "overall_massing",
    "building_silhouette",
    "main_window_positions",
    "main_door_positions",
    "roofline",
)

# ---- OPERATION 1: pure material replacement -------------------------------

MATERIAL_TEXT = "Change the unfinished facade material to cream travertine."

# ---- OPERATION 2: explicit architectural design ---------------------------

DESIGN_TEXT = (
    "Design a restrained neoclassical facade for this unfinished building. "
    "Use cream travertine, correctly proportioned pilasters and capitals, "
    "stone window surrounds, horizontal stringcourses, a formal cornice and "
    "stone balustrades on suitable existing terraces. Preserve the original "
    "structural frame, openings, floor count and building massing."
)

CLASSIC_TEXT = (
    "Change the facade to a classic style with arches and balustrades while "
    "keeping the mass, openings and floors unchanged."
)

MODERN_TEXT = (
    "Change the facade to a modern style while keeping the mass, openings "
    "and floors unchanged."
)


def _element(name, kinds):
    return {
        "element": name,
        "kind": list(kinds),
        "context_kinds": [],
        "kind_basis": "subject_explicit",
        "source_quote": name,
        "evidence_class": "MODEL_REPORTED",
        "verification_status": "UNVERIFIED",
        "confidence": None,
        "position": None,
        "relations": [],
    }


#: FIXTURE — stands in for the production vision report. Not an image analysis.
IMAGE_EVIDENCE = {
    "contract": "ImageUnderstandingV1",
    "analysis_status": "ANALYZED_WITH_UNCERTAINTY",
    "image_type": "facade_or_elevation",
    "element_evidence": {
        "contract": "ArchitecturalElementEvidenceV1",
        "source_image": {"image_id": "accepted-building", "sha256": SOURCE_SHA256},
        "elements": [
            _element("facade wall", ("wall",)),
            _element("windows", ("window", "opening")),
            _element("structural frame", ("column", "beam")),
        ],
    },
}


def _resolve(text, materials=None):
    delta = compile_edit_delta(text, image_edit=True)
    resolved = SharedFacadeKnowledgeResolverV1().resolve(
        {
            "style": delta.get("style"),
            "materials": materials or (
                [delta["material"]] if delta.get("material") else []
            ),
        }
    )
    return delta, resolved


def _decision(text):
    delta, resolved = _resolve(text)
    decision = resolve_design_decision(
        user_text=text,
        edit_delta=delta,
        image_understanding=IMAGE_EVIDENCE,
        resolved_facade_knowledge=resolved,
        preserve_geometry=True,
        preserve_constraints=PRESERVE,
    )
    return delta, resolved, decision


def _effective_prompt(text, *, structured_preserve=True):
    """The exact prompt the render path resolves, through the real owners."""

    delta, resolved, decision = _decision(text)

    understanding = understand(text)

    if structured_preserve:
        merged = dict(understanding)
        merged["preserve_constraints"] = {
            "geometry": True,
            "massing": True,
            "floor_count": True,
            "openings": True,
        }
    else:
        merged = understanding

    instruction = build_render_instruction(
        text,
        understanding=merged,
        mode="img2img",
        context={"mode": "img2img"},
    )

    block = decision_instruction_block(decision)

    resolution = resolve_render_prompt(
        compiled_prompt=instruction.get("english_instruction"),
        builder_prompt="",
        user_text=text,
        conflict_terms=tuple(edit_delta_conflict_terms(delta)),
        architectural_instruction=block,
    )

    return {
        "delta": delta,
        "resolved": resolved,
        "decision": decision,
        "block": block,
        "instruction": instruction,
        "prompt": resolution["final_prompt"],
        "prompt_lower": resolution["final_prompt"].lower(),
    }


@pytest.fixture(scope="module")
def design():
    return _effective_prompt(DESIGN_TEXT)


@pytest.fixture(scope="module")
def material():
    return _effective_prompt(MATERIAL_TEXT)


# ==========================================================
# A — material-only requests stay material-only
# ==========================================================

def test_A_material_request_is_a_finish_replacement(material):

    operation = material["decision"]["requested_operation"]["operation"]

    assert operation == "replace_finish"
    assert material["decision"]["editable_elements"] == ["facade_wall_surface"]


def test_A_material_request_gains_no_decorative_geometry(material):

    lowered = material["block"]["constraint_block"].lower()

    for ornament in ("pilaster", "capital", "cornice", "balustrade",
                     "stringcourse", "arch", "dome"):
        assert ornament not in lowered, ornament


def test_A_material_request_still_forbids_cladding_other_surfaces(material):

    lowered = material["block"]["constraint_block"].lower()

    assert "soffit" in lowered
    assert "boundary walls" in lowered
    assert "do not receive the facade material" in lowered


# ==========================================================
# B — neoclassical stays distinct from classic
# ==========================================================

def test_B_neoclassical_is_distinct_from_classic():

    neo = SharedFacadeKnowledgeResolverV1().resolve({"style": "neoclassical"})
    classic = SharedFacadeKnowledgeResolverV1().resolve({"style": "classic"})

    assert neo["canonical_style"] == "neoclassical"
    assert classic["canonical_style"] == "classic"
    assert neo["composition"] != classic["composition"]

    # The ontology's own distinction: arches are classic/Roman, not
    # neoclassical.
    assert neo["architectural_elements"]["arches"] == []
    assert classic["architectural_elements"]["arches"]


def test_B_neoclassical_balustrades_are_not_an_ontology_fact():

    neo = SharedFacadeKnowledgeResolverV1().resolve({"style": "neoclassical"})

    # A balustrade is a CROSS-STYLE element. The neoclassical record must not
    # claim it, so the instruction's balustrade can only come from the user.
    assert neo["architectural_elements"]["balustrades"] == []


# ==========================================================
# C / D — the assembly is populated and the surfaces differ
# ==========================================================

def test_C_neoclassical_assembly_is_populated(design):

    system = design["resolved"]["surface_strategy"]["facade_assembly"][
        "facade_system"
    ]

    for surface in ("base", "wall_surface", "openings",
                    "vertical_elements", "upper_elements",
                    "soffit", "glazing", "site"):
        assert system.get(surface), surface


def test_D_soffit_finish_differs_from_wall_cladding(design):

    system = design["resolved"]["surface_strategy"]["facade_assembly"][
        "facade_system"
    ]

    wall = system["wall_surface"]["material"]
    soffit = system["soffit"]["material"]

    assert wall == "travertine"
    assert soffit == "painted_plaster"
    assert wall != soffit
    assert system["soffit"]["is_facade_stone"] is False
    assert system["glazing"]["material"] == "glass"
    assert system["site"]["is_facade_stone"] is False


def test_C_existing_styles_keep_their_five_key_assembly():

    for style in ("classic", "roman_classic", "modern"):

        system = SharedFacadeKnowledgeResolverV1().resolve(
            {"style": style}
        )["surface_strategy"]["facade_assembly"]["facade_system"]

        assert set(system) == {
            "base", "wall_surface", "openings",
            "vertical_elements", "upper_elements",
        }, style


# ==========================================================
# E — the knowledge reaches the real consumer
# ==========================================================

def test_E_resolved_knowledge_reaches_the_decision(design):

    knowledge = design["decision"]["applicable_knowledge"]

    assert knowledge["canonical_style"] == "neoclassical"
    assert knowledge["surface_assignment"]
    assert knowledge["composition"]
    assert knowledge["surface_semantics"] == "SEMANTIC_ONLY_NOT_SEGMENTED"


def test_E_knowledge_reaches_the_effective_prompt(design):

    lowered = design["prompt_lower"]

    assert "surface assignment" in lowered
    assert "the wall field in travertine" in lowered
    assert "the soffits in painted plaster" in lowered
    assert "not facade stone" in lowered
    assert "separate site scope" in lowered


def test_E_projection_is_not_inert(design):

    """Adding fields to the decision dict is not enough on its own."""

    assert design["block"], "the constraint block must not be empty"
    assert len(design["block"]["constraint_block"]) > 400


# ==========================================================
# F — the requested elements appear individually
# ==========================================================

def test_F_requested_elements_appear(design):

    lowered = design["prompt_lower"]

    for element in ("pilaster", "capital", "stringcourse",
                    "cornice", "window surround", "balustrade"):
        assert element in lowered, element


def test_F_pilasters_are_not_rendered_as_columns(design):

    """The user asked for pilasters; a column is a different element."""

    assert "pilasters" in design["instruction"]["english_instruction"].lower()

    understanding = understand("Neoclassical facade with stone pilasters.")

    assert understanding["elements"] == ["pilasters"]


# ==========================================================
# G — an explicit balustrade is authorised, with honest provenance
# ==========================================================

def test_G_requested_balustrade_is_authorised_and_constrained(design):

    lowered = design["prompt_lower"]

    assert "balustrade" in lowered
    # Authorised only on edges that already exist.
    assert "existing terrace or bay edges only" in lowered


# ==========================================================
# H — nothing unrequested is injected
# ==========================================================

def test_H_no_unrequested_arches_domes_or_balconies(design):

    lowered = design["prompt_lower"]

    # "architectural"/"architecture" are not arches; "arched"/"arches" are.
    scrubbed = lowered.replace("architectural", "").replace("architecture", "")

    assert "arch" not in scrubbed
    assert "dome" not in lowered

    # A balcony may appear ONLY inside the prohibition that stops one being
    # added — never as something to produce.
    for sentence in lowered.split("."):

        if "balcon" in sentence:
            assert "without adding" in sentence, sentence


def test_H_ornament_is_not_turned_into_structure(design):

    elements = design["instruction"]["english_instruction"].lower()

    # A fixed-geometry design request must not ask for built structure.
    assert "structurally supported" not in elements
    assert "surface relief within the existing wall planes" in elements


# ==========================================================
# I — protected quantities stay protected at instruction level
# ==========================================================

def test_I_preservation_binds_at_the_instruction_level(design):

    constraints = design["instruction"]["constraints"]

    assert constraints["geometry"]["preserve_geometry"] is True
    assert constraints["geometry"]["preserve_massing"] is True
    assert constraints["geometry"]["preserve_floor_count"] is True
    assert constraints["openings"]["preserve_openings"] is True


def test_I_authorised_addition_boundary_is_stated(design):

    lowered = design["block"]["constraint_block"].lower()

    assert "applied relief within the existing wall planes" in lowered
    assert "floor count" in lowered
    assert "massing" in lowered
    assert "no structural member or new volume" in lowered


# ==========================================================
# J — the site stays a separate scope
# ==========================================================

def test_J_site_is_a_separate_scope(design):

    system = design["resolved"]["surface_strategy"]["facade_assembly"][
        "facade_system"
    ]

    assert system["site"]["element"] == "separate_site_scope"
    assert system["site"]["material"] is None
    assert "separate site scope" in design["prompt_lower"]


# ==========================================================
# K — no invented geometry, no segmentation claim
# ==========================================================

def test_K_no_coordinates_or_polygons_anywhere(design):

    block = design["block"]["constraint_block"].lower()

    assert "not measured regions" in block
    assert "semantic categories" in block

    for token in ("polygon", "bounding box", "coordinates", "pixel",
                  "x0", "y0", "px"):
        assert token not in block, token


def test_K_decision_never_claims_a_verified_region(design):

    knowledge = design["decision"]["applicable_knowledge"]

    assert knowledge["surface_semantics"] == "SEMANTIC_ONLY_NOT_SEGMENTED"

    decisions = " ".join(design["decision"]["knowledge_derived_decisions"]).lower()

    assert "not a segmented pixel region" in decisions


# ==========================================================
# L — classic and modern contracts remain valid
# ==========================================================

def test_L_classic_keeps_arches_and_balustrades():

    classic = _effective_prompt(CLASSIC_TEXT)

    lowered = classic["prompt_lower"]

    assert classic["resolved"]["canonical_style"] == "classic"
    assert "arch" in lowered
    assert "balustrade" in lowered


def test_L_modern_still_resolves():

    modern = _effective_prompt(MODERN_TEXT)

    assert modern["resolved"]["canonical_style"] == "modern"
    assert modern["resolved"]["style_family"] == "modern"


def test_L_material_only_contract_is_unchanged_in_shape(material):

    # The block still opens with the same operation sentence and still closes
    # with the same bookkeeping sentence.
    block = material["block"]["constraint_block"]

    assert block.startswith(
        "Apply the requested finish only to the image-supported targets"
    )
    assert "Design decision:" in block


# ==========================================================
# M — nonexecuting graph capture
# ==========================================================

def test_M_effective_prompt_reaches_the_graph_without_executing(design):

    path = os.path.join(
        ROOT, "core", "render", "workflows", "flux_img2img.json"
    )

    with open(path, encoding="utf-8") as handle:
        canonical = json.load(handle)

    injected = ImageWorkflowInjector().inject(
        copy.deepcopy(canonical),
        prompt=design["prompt"],
        image_asset={"filename": "source.png", "working_dimensions": [336, 448]},
        context={"denoise": 0.25, "seed": 1793774657, "steps": 8},
        mask_asset=None,
    )

    node_206 = injected["workflow"]["206"]["inputs"]["text"]

    assert "pilaster" in node_206.lower()
    assert "surface assignment" in node_206.lower()
    assert "soffits in painted plaster" in node_206.lower()

    # The capture is a deep copy: the canonical graph is untouched.
    assert canonical["206"]["inputs"]["text"] != node_206


def test_M_canonical_workflow_is_not_modified():

    import hashlib

    path = os.path.join(
        ROOT, "core", "render", "workflows", "flux_img2img.json"
    )

    with open(path, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()

    assert digest == (
        "3e6656efe1d9eacac7d903502d4adf389eb49d18a05a9d6f1055e9265d6948ca"
    )


# ==========================================================
# N — nothing executed
# ==========================================================

def test_N_no_execution_flags(design):

    assert design["decision"]["render_executed"] is False
    assert design["decision"]["comfy_invoked"] is False


def test_N_acceptance_case_source_is_the_accepted_photograph():

    import hashlib

    with open(SOURCE_IMAGE, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()

    assert digest == SOURCE_SHA256
