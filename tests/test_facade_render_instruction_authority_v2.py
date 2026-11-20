"""FACADE_RENDER_INSTRUCTION_AUTHORITY_V2 — RED/GREEN tests.

Drives the REAL production objects, no LLM / GPU / ComfyUI:

  * `ArchitecturalPromptCompiler._compile_elements()`      (file 1)
  * `resolve_geometry_authority()` / `authorize_request()` (file 2)
  * `ImageEditPromptBuilder.build()`                       (final assembler)
  * `architectural_render_instruction_v1` role block       (file 3)

The replay reconstructs the architectural understanding from the RECORDED job
(`runs/dual_gpu_acceptance_v1/run_result.json`) and pushes it through the real
compiler and the real final assembler. It is a code-corrected replay of the
recorded inputs, not a live route capture — stated so the evidence is not
overclaimed.
"""

import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PACK = os.path.join(
    ROOT, "tests", "manual_facade_i2i_v1", "ArchitectOS_Reference_Style_Test_V1"
)
REQUEST = os.path.join(PACK, "REFERENCE_STYLE_REQUEST_EN.txt")
RECORD = os.path.join(ROOT, "runs", "dual_gpu_acceptance_v1", "run_result.json")

# The prohibition sentence that produced the false REQUIREMENT.
PROHIBITION = (
    "Do not copy IMAGE B's building mass, floor layout, fenestration, arches, "
    "protruding columns, gables or triangular pediment as new volumes."
)

# Preservation / decorative-surround sentence that produced the false
# "authorised geometry change: opening".
PRESERVATION = (
    "Preserve its exact silhouette, floor arrangement, roofline, balcony slabs "
    "and projections, original positions and dimensions of windows and doors, "
    "entrance location, building proportions, camera, perspective and framing."
)
DECORATIVE = (
    "Applied cornice detailing and elegant classical surrounds around EXISTING "
    "openings; never by recutting or enlarging openings."
)


def _request():
    with open(REQUEST, encoding="utf-8") as fh:
        return fh.read().strip()


def _recorded():
    with open(RECORD, encoding="utf-8") as fh:
        return json.load(fh)["result"]["render_handoff"]


# ----------------------------------------------------------
# understanding reconstruction (from the recorded job)
# ----------------------------------------------------------


def _understanding():
    """Reconstructed from the recorded compiled prompt + architectural_intent.

    The live understanding dict was not persisted. The fields below are exactly
    the ones the recorded prompt proves were present: the four emitted elements,
    the two materials, the style, and the reference prohibition.
    """

    return {
        "scope": "facade",
        "style": {"target": "neoclassical", "intensity": {"level": "MEDIUM"}},
        "materials": {
            "primary": [
                "light ivory natural stone",
                "cream travertine-like facade cladding",
            ]
        },
        "elements": ["columns", "cornices", "arches", "sculptural relief"],
        "negative_constraints": [
            PROHIBITION,
            "No red/orange brick redesign, no black-metal wall cladding.",
            "The result must look like a new stone neoclassical facade, not a "
            "brick facade recolored beige.",
        ],
        "preserve_constraints": {
            "reference_geometry": True,
            "explicit": [PRESERVATION],
        },
        "reference_image_policy": {
            "referenced": True,
            "preserve_base_geometry": True,
            "do_not_copy": ["massing", "arches", "columns", "pediment"],
        },
        "change_operations": [
            {"operation": "replace", "target": "facade"},
        ],
        "entrance": {"position": None},
    }


# ==========================================================
# A / B — element compilation
# ==========================================================


def test_A_prohibited_arches_and_columns_do_not_become_required():
    from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
        ArchitecturalPromptCompiler,
    )

    compiler = ArchitecturalPromptCompiler()
    lines = compiler._compile_elements(_understanding())
    text = " ".join(lines).lower()

    assert "arches" not in text, f"prohibited element promoted to requirement: {text}"
    assert "columns" not in text, f"prohibited element promoted to requirement: {text}"


def test_A2_genuine_positive_elements_are_preserved():
    from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
        ArchitecturalPromptCompiler,
    )

    compiler = ArchitecturalPromptCompiler()
    lines = compiler._compile_elements(_understanding())
    text = " ".join(lines).lower()

    # cornices are affirmatively requested ("applied cornice detailing") and are
    # NOT named in any prohibition, so they must survive.
    assert "cornice" in text


def test_B_affirmative_columns_remain_available():
    from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
        ArchitecturalPromptCompiler,
    )

    compiler = ArchitecturalPromptCompiler()
    understanding = _understanding()
    understanding["negative_constraints"] = []          # no prohibition at all
    understanding["reference_image_policy"] = {
        "referenced": True,
        "preserve_base_geometry": True,
    }
    understanding["elements"] = ["columns"]

    text = " ".join(compiler._compile_elements(understanding)).lower()

    assert "columns" in text


# ==========================================================
# C / D — geometry authority
# ==========================================================


def test_C_preservation_does_not_authorize_opening_changes():
    from core.prompt_intelligence.geometry_authority_handoff_v1 import (
        resolve_geometry_authority,
    )

    authority = resolve_geometry_authority(
        terms=[],
        user_text=PRESERVATION + " " + DECORATIVE,
        edit_class="style_change",
    )

    assert "opening" not in (authority.get("authorized_domains") or []), (
        "a preservation/decorative clause authorised changing openings: "
        f"{authority.get('authorized_domains')}"
    )


def test_C2_the_authority_note_does_not_claim_opening_is_authorised():
    from core.prompt_intelligence.geometry_authority_handoff_v1 import (
        authority_note,
        resolve_geometry_authority,
    )

    authority = resolve_geometry_authority(
        terms=[],
        user_text=PRESERVATION + " " + DECORATIVE,
        edit_class="style_change",
    )
    note = authority_note(authority).lower()

    assert "authorised geometry change" not in note


def test_D_an_explicit_geometry_edit_is_still_authorized():
    from core.prompt_intelligence.geometry_authority_handoff_v1 import (
        resolve_geometry_authority,
    )

    authority = resolve_geometry_authority(
        terms=[],
        user_text="Add a new window on the ground floor of the front facade.",
        edit_class="geometry_edit",
    )

    assert "opening" in (authority.get("authorized_domains") or []), authority


def test_D2_a_prohibition_is_not_an_operation():
    from core.prompt_intelligence.geometry_authority_handoff_v1 import (
        analyze_request,
    )

    analysis = analyze_request(
        "Do not change the roofline or move any window.", edit_class="geometry_edit"
    )

    domains = [o["domain"] for o in analysis["geometric_operations"]]

    assert "roof" not in domains
    assert "opening" not in domains


# ==========================================================
# E / F / G / H / I — the assembled prompt
# ==========================================================


@pytest.fixture(scope="module")
def assembled():
    from _v2_replay import assemble_final_prompt

    return assemble_final_prompt()


def test_E_one_unambiguous_role_mapping(assembled):
    text = assembled["prompt"]

    # the product block must not redefine IMAGE A as the style reference
    assert "style reference's (IMAGE A)" not in text
    assert "target building's (IMAGE B)" not in text
    # explicit semantic roles must be present
    assert "TARGET_BUILDING" in text
    assert "STYLE_REFERENCE" in text


def test_F_image_bindings_unchanged(assembled):
    roles = assembled["bindings"]

    assert roles["target_building"]["node_id"] == "300"
    assert roles["style_reference"]["node_id"] == "302"
    assert (
        roles["target_building"]["sha256"]
        == "fd1088ea4bf01add359af7696fc91a3056b7e8719a98e0de1c58a35e6db86f71"
    )
    assert (
        roles["style_reference"]["sha256"]
        == "a9e3cfecd69a17ce37986c2aff9478ede527354297b3af539d6ba11b4d953604"
    )


def test_G_material_instruction_is_cream_stone_not_brick(assembled):
    low = assembled["prompt"].lower()

    assert "cream" in low or "ivory" in low
    assert "travertine" in low
    # brick may only appear as a prohibition, never in the requested tag tail
    tail = assembled["tag_tail"].lower()
    assert "brick" not in tail


def test_H_no_generic_block_overrides_preservation(assembled):
    low = assembled["prompt"].lower()

    # The REQUIRED ELEMENTS sentence must not name a PROHIBITED element. The
    # words "arches"/"columns" may still appear inside the user's own
    # prohibition ("Do not copy … arches, protruding columns"), which is
    # correct — so the check is scoped to that sentence.
    block = re.search(r"required architectural elements[^.]*\.", low)

    if block:
        assert "arches" not in block.group(0), block.group(0)
        assert "columns" not in block.group(0), block.group(0)

    assert "preserve exactly" in low
    assert "explicitly authorised geometry change: opening" not in low


def test_I_no_second_block_claims_to_be_verbatim(assembled):
    text = assembled["prompt"]

    claims = len(re.findall(r"\(verbatim[^)]*authoritative\)", text, re.I))

    assert claims <= 1, (
        "more than one block claims to be the user's verbatim text: "
        f"{claims}"
    )


# ==========================================================
# J — unrelated behaviour
# ==========================================================


def test_J_workflow_selection_unchanged():
    from core.render.workflow_selector import WorkflowSelector

    selector = WorkflowSelector()

    assert selector.select({"engine": "flux"}) == "flux.json"
    assert selector.select({"engine": "flux", "mode": "edit"}) == "flux_img2img.json"
    assert (
        selector.select({"engine": "flux", "dual_image": True, "conditioned": True})
        == "flux_img2img_dual_conditioned.json"
    )
