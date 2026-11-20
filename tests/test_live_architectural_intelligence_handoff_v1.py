"""LIVE_ARCHITECTURAL_INTELLIGENCE_INTEGRATION_V1 — real-route handoff regression.

Every assertion here is made against a graph captured from the REAL
`ChatArchitect._handle_internal()` route, replayed with the AUTHENTIC recorded
vision understanding (`runs/live_handoff_v1/recorded_understanding.json`).

No vision inference runs: `analyze_ab_references` and `LLMGateway.generate`
are replayed from the record. No ComfyUI submission is possible: the executor
edge is stubbed and the HTTP submit paths are hard-blocked.

The tests assert the CORRECT behaviour, so they are RED while the live handoff
is broken and GREEN once it is fixed.
"""

import json
import os

import pytest

import core.chat.chat_architect as chat_architect_module
import core.render.comfy_http_runtime as comfy_http_runtime
import core.render.workflow_executor as workflow_executor
import core.vision.facade_reference_vision_provider_v1 as fvp_module
import core.llm.llm_gateway as llm_module
import core.runtime.gpu_handoff_v1 as gpu_handoff

from core.chat.chat_architect import ChatArchitect
from core.chat.session_registry_v1 import session_registry
from core.project.project_registry_bridge_v1 import project_registry_bridge
from core.project.project_workspace_v1 import project_workspace
from core.render.render_strategy_controller_v1 import resolve_strategy
from core.vision.image_registry_v1 import image_registry

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, "tests", "manual_facade_i2i_v1", "ArchitectOS_Reference_Style_Test_V1")
TARGET = os.path.join(PACK, "TARGET_A_GPU_768x1024.png")
STYLE = os.path.join(PACK, "STYLE_B_PIXEL_EXACT_PAD_768x1024.png")
REQUEST_FILE = os.path.join(PACK, "REFERENCE_STYLE_REQUEST_EN.txt")

RECORD = os.path.join(ROOT, "runs", "live_handoff_v1", "recorded_understanding.json")

TARGET_SHA = "fd1088ea4bf01add359af7696fc91a3056b7e8719a98e0de1c58a35e6db86f71"
DUAL_WORKFLOW = "flux_img2img_dual_conditioned.json"
UNET = "flux1-krea-dev_fp8_scaled.safetensors"
SEED = 20261030


class _Stop(RuntimeError):
    pass


@pytest.fixture(scope="module")
def recorded():
    with open(RECORD, encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def live_run(tmp_path_factory, recorded):
    """ONE real-route execution, replayed from the recorded understanding."""

    base = tmp_path_factory.mktemp("live_handoff_v1")

    # ---- ephemeral single-source acceptance (never the production root) ----
    acc_root = base / "render_acceptance"
    os.makedirs(acc_root, exist_ok=True)
    record = {
        "contract": "ArchitecturalPreservationAcceptanceV1",
        "version": "1.0",
        "workflow": DUAL_WORKFLOW,
        "status": "accepted",
        "accepted_scope": "single_source",
        "preservation_capability": "architectural_facade_preservation",
        "evidence": {"report": "test_fixture_only", "human_approval": False, "ephemeral": True},
        "model": {"unet_name": UNET},
        "source_sha256": TARGET_SHA,
    }
    with open(os.path.join(acc_root, DUAL_WORKFLOW), "w", encoding="utf-8") as handle:
        json.dump(record, handle)

    old_acc = chat_architect_module._R4_ACCEPTANCE_ROOT
    chat_architect_module._R4_ACCEPTANCE_ROOT = str(acc_root)

    old_projects, old_trash = project_workspace.projects_root, project_workspace.trash_root
    project_workspace.projects_root = str(base / "projects")
    project_workspace.trash_root = str(base / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)

    manifest = project_workspace.create("live-handoff-v1")
    project_registry_bridge.bind(manifest["project_id"])
    session_registry.begin(manifest["session_id"])
    image_registry.reset(manifest["session_id"])

    # ---- replay the recorded vision evidence (no inference) ----
    real_analyze = fvp_module.analyze_ab_references
    real_generate = llm_module.LLMGateway.generate

    fvp_module.analyze_ab_references = lambda references, context=None: recorded["ab_analysis"]

    def _generate(self, user, use_context=False):
        calls = recorded.get("llm_calls") or []
        return calls[0]["result"] if calls else None

    llm_module.LLMGateway.generate = _generate

    # ---- block every hardware / submission edge ----
    # Every global patched below is saved first and restored in teardown, so a
    # later test in the same pytest process never inherits a stubbed hardware
    # edge or a hard-blocked submit path.
    _saved_globals = {
        (gpu_handoff, "require_render_vram"): gpu_handoff.require_render_vram,
        (gpu_handoff, "unload_ollama_models_for_render"): gpu_handoff.unload_ollama_models_for_render,
        (gpu_handoff, "gpu_render_lease"): gpu_handoff.gpu_render_lease,
        (workflow_executor.WorkflowExecutor, "execute"): workflow_executor.WorkflowExecutor.execute,
        (comfy_http_runtime.ComfyHTTPRuntime, "submit"): comfy_http_runtime.ComfyHTTPRuntime.submit,
        (comfy_http_runtime.ComfyHTTPRuntime, "_submit_locked"): comfy_http_runtime.ComfyHTTPRuntime._submit_locked,
    }

    gpu_handoff.require_render_vram = lambda *a, **k: {"ok": True, "reason": "cpu", "free_mib": 99999}
    gpu_handoff.unload_ollama_models_for_render = lambda *a, **k: {"status": "not_loaded"}

    class _Lease:
        def acquire(self):
            return True

        def release(self):
            return None

    gpu_handoff.gpu_render_lease = lambda *a, **k: _Lease()

    def _forbidden(*_a, **_k):
        raise AssertionError("a real submission path was reached")

    workflow_executor.WorkflowExecutor.execute = _forbidden
    comfy_http_runtime.ComfyHTTPRuntime.submit = _forbidden
    comfy_http_runtime.ComfyHTTPRuntime._submit_locked = _forbidden

    references = {
        "A": {"role": "facade_reference", "authority": "appearance_only", "present": True,
              "path": STYLE, "asset_id": "ref_style_b", "filename": os.path.basename(STYLE),
              "mime_type": "image/png"},
        "B": {"role": "target_building", "authority": "geometry", "present": True,
              "path": TARGET, "asset_id": "target_a", "filename": os.path.basename(TARGET),
              "mime_type": "image/png"},
    }
    for path in (STYLE, TARGET):
        image_registry.register(manifest["session_id"], path=path,
                                source_type="uploaded", make_active=False)

    text = recorded["request_text"]
    strategy = resolve_strategy(user_text=text, requested_mode=None)
    context = {
        "session_id": manifest["session_id"],
        "project_id": manifest["project_id"],
        "references": references,
        "mode": strategy.get("resolved_mode"),
        "conditioned_render": None,
        "seed": SEED,
        "image": {"path": TARGET},
    }

    chat = ChatArchitect(brain=None)
    captured = {"calls": 0, "graph": None}

    def _capture(workflow, engine=None, **kwargs):
        captured["calls"] += 1
        captured["graph"] = workflow
        raise _Stop("captured")

    chat.render_runtime.executor.execute = _capture

    try:
        result = chat._handle_internal({"text": text, "image": {"path": TARGET}}, context)
    except _Stop:
        result = {"type": "captured"}

    graph = captured["graph"] or {}
    prompt = ((graph.get("206") or {}).get("inputs") or {}).get("text") or ""

    payload = {
        "graph": graph,
        "prompt": prompt,
        "calls": captured["calls"],
        "admission": getattr(chat, "last_r4_admission", None) or {},
        "result": result,
    }

    # ---- restore IMMEDIATELY, not at teardown ----
    # Every global patched for the capture is put back the moment the run
    # finishes, so a later test in the same pytest process can never inherit a
    # stubbed hardware edge or a hard-blocked submit path.
    fvp_module.analyze_ab_references = real_analyze
    llm_module.LLMGateway.generate = real_generate
    for (owner, name), original in _saved_globals.items():
        setattr(owner, name, original)
    chat_architect_module._R4_ACCEPTANCE_ROOT = old_acc
    try:
        image_registry.reset(manifest["session_id"])
        session_registry.end()
        project_registry_bridge.unbind()
    except Exception:  # noqa: BLE001
        pass
    project_workspace.projects_root, project_workspace.trash_root = old_projects, old_trash

    yield payload


# ==========================================================
# the route itself
# ==========================================================


def test_the_route_reaches_the_conditioned_graph(live_run):
    assert live_run["calls"] == 1
    assert live_run["admission"].get("admitted") is True
    assert live_run["admission"].get("selected_workflow") == DUAL_WORKFLOW
    assert len(live_run["graph"]) == 21
    assert live_run["prompt"], "no prompt reached node 206"


# ==========================================================
# A — preservation must reach the compiler
# ==========================================================


def test_A_surface_only_sentence_is_used(live_run):
    """V4's surface-relief sentence must run for a facade-only transfer."""

    prompt = live_run["prompt"]

    assert "applied as surface relief WITHIN the existing wall planes" in prompt
    assert "structurally supported" not in prompt
    assert "rather than applied as surface decoration" not in prompt


# ==========================================================
# B — prohibitions must reach element compilation
# ==========================================================


def test_B_prohibited_reference_elements_are_not_required(live_run):
    """The reference's columns/arches must not become REQUIRED elements."""

    prompt = live_run["prompt"]

    assert "classical columns" not in prompt
    assert "meaningful arches with proper voussoirs" not in prompt


def test_B2_permitted_surface_details_survive(live_run):
    """Cornices and shallow relief were explicitly requested and must remain."""

    prompt = live_run["prompt"]

    assert "cornice" in prompt.lower()
    assert "relief" in prompt.lower()


# ==========================================================
# C — no false opening authorization
# ==========================================================


def test_C_no_false_opening_authorization(live_run):
    prompt = live_run["prompt"]

    assert "Explicitly authorised geometry change" not in prompt


# ==========================================================
# D — facade-only scope
# ==========================================================


def test_D_no_whole_building_composition_change(live_run):
    prompt = live_run["prompt"]

    assert "overall building composition" not in prompt
    assert "facade expression only" in prompt.lower() or "facade" in prompt.lower()


# ==========================================================
# E — semantic role labels
# ==========================================================


def test_E_semantic_roles_are_used(live_run):
    prompt = live_run["prompt"]

    assert "TARGET_BUILDING" in prompt
    assert "STYLE_REFERENCE" in prompt


# ==========================================================
# F — the facade surface-treatment boundary must reach the model
#
# §5F asked whether the V3 PERMITTED/FORBIDDEN block is SELECTED by the live
# route. It is not, and that is correct: the V3 block lives in the
# `not resolved` fallback branch, and this route resolves facade knowledge, so
# the resolved branch runs instead. That branch carries an EQUIVALENT boundary
# in prose ("Treat these as facade-language and surface instructions… Express
# the listed cues only through shallow applied detail… do not add, remove,
# resize or relocate any built element"). Duplicating the V3 block here purely
# to satisfy a literal string check is exactly what §5F forbids, so this test
# asserts the SEMANTIC boundary instead of the token.
# ==========================================================


def test_F_surface_treatment_boundary_is_present(live_run):
    low = live_run["prompt"].lower()

    # permits applied decoration within the existing wall planes
    assert "shallow applied" in low
    assert "within the existing wall planes" in low or "within existing wall planes" in low
    # the facade knowledge is explicitly bounded to appearance
    assert "facade-language and surface instructions" in low
    assert "not as permission to alter source geometry" in low
    # and the V4 element sentence forbids structural addition
    assert "without adding structural members" in low
    # the decoration the user asked for is actually named
    assert "cornice" in low


# ==========================================================
# FINAL_ROLE_LABEL_CONSISTENCY_V1 — the exact semantic conflict
#
# The user's own request labels IMAGE A as the TARGET building and IMAGE B as
# the STYLE reference (the test pack's lettering, which is the INVERSE of the
# product's A=style / B=target keys). The generated instruction used to say
# "Preserve the TARGET BUILDING from IMAGE B (geometry authority)" — assigning
# IMAGE B to the target in the same prompt that assigns it to the reference.
#
# The verbatim block is authoritative and must keep the user's letters. Every
# GENERATED sentence must use semantic role names only.
# ==========================================================

_VERBATIM_MARKER = "USER REQUEST (verbatim, authoritative):"
_GENERATED_MARKER = "ARCHITECTURAL PRESERVATION CONTRACT"


def _split_verbatim(prompt):
    """(verbatim_block, generated_rest) — or (prompt, '') if no marker."""

    if _VERBATIM_MARKER not in prompt:
        return "", prompt

    start = prompt.index(_VERBATIM_MARKER)
    tail = prompt[start:]

    if _GENERATED_MARKER not in tail:
        return tail, ""

    end = start + tail.index(_GENERATED_MARKER)
    return prompt[start:end], prompt[end:]


def test_G_generated_instructions_never_reuse_the_user_image_letters(live_run, recorded):
    prompt = live_run["prompt"]
    verbatim, generated = _split_verbatim(prompt)

    assert verbatim, "the authoritative user block is missing"
    assert generated, "no generated instruction follows the user block"

    # 1. the user's request is preserved verbatim inside its block
    import re as _re

    norm = lambda s: _re.sub(r"\s+", " ", s).strip()
    assert norm(recorded["request_text"]) in norm(verbatim), "user text was altered"

    # 2. the user's own letters may appear ONLY inside that block
    assert "IMAGE A" not in generated
    assert "IMAGE B" not in generated

    # 3. generated instructions use the semantic roles
    assert "TARGET_BUILDING" in generated
    assert "STYLE_REFERENCE" in generated

    # 4. and the target is never bound to the reference's letter
    assert "TARGET BUILDING from IMAGE" not in prompt
    assert "target building (IMAGE" not in prompt.lower()


def test_G2_hardware_and_submission_globals_are_restored():
    """§10 — no stubbed edge may leak into a later test in this process."""

    assert gpu_handoff.require_render_vram.__name__ != "<lambda>"
    assert gpu_handoff.gpu_render_lease.__name__ != "<lambda>"
    assert gpu_handoff.unload_ollama_models_for_render.__name__ != "<lambda>"
    assert workflow_executor.WorkflowExecutor.execute.__name__ == "execute"
    assert comfy_http_runtime.ComfyHTTPRuntime.submit.__name__ == "submit"
    assert comfy_http_runtime.ComfyHTTPRuntime._submit_locked.__name__ == "_submit_locked"


# ==========================================================
# FACADE_MATERIAL_TRANSFER_ENGINE_DIAGNOSIS_V1 — reference role
#
# The request asks for STYLE *and* MATERIAL from the reference
# ("Use IMAGE B only for style, material, surface rhythm, color and decorative
# inspiration"). The classifier checked `material_only` FIRST and fired on the
# single word "material" + "use", so the reference role collapsed to
# material/finish and could no longer inform style or detailing.
# ==========================================================


def test_H_reference_role_permits_style_and_material(recorded):
    from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
        REFERENCE_SENTENCE,
    )
    from core.prompt_intelligence.persian_architectural_understanding import (
        PersianArchitecturalUnderstandingEngine,
    )

    engine = PersianArchitecturalUnderstandingEngine()

    policy = engine._detect_reference(recorded["request_text"])

    assert policy["role"] != "material_only", (
        "a request that explicitly asks for style resolved to material_only"
    )
    assert policy["preserve_base_geometry"] is True
    assert policy["copy_reference_geometry"] is False

    sentence = REFERENCE_SENTENCE.get(policy["role"], "")

    # the role sentence must not forbid style, and must forbid geometry copying
    assert "material/finish" not in sentence
    assert "geometry template" in sentence or "style" in sentence


def test_H2_a_material_only_request_keeps_material_only():
    """The narrowing must not break a request that really is material-only."""

    from core.prompt_intelligence.persian_architectural_understanding import (
        PersianArchitecturalUnderstandingEngine,
    )

    engine = PersianArchitecturalUnderstandingEngine()

    policy = engine._detect_reference("Use the material of this reference image only.")

    assert policy["role"] == "material_only"


# ==========================================================
# the material request must survive every fix
# ==========================================================


def test_material_request_survives(live_run):
    low = live_run["prompt"].lower()

    assert "travertine" in low
    assert "ivory" in low or "cream" in low
