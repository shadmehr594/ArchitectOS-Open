"""FACADE_REFERENCE_STYLE_AUTO_SELECTION_V1 — the NORMAL product route.

The previous milestone (`tests/test_facade_reference_style_product_integration_v1.py`)
drove `ChatArchitect._handle_internal()` with

    context["mode"]              = "image_to_image"
    context["conditioned_render"] = True

which proves the explicitly-selected conditioned pathway works. It does NOT
prove that a normal user request selects that pathway by itself.

This module removes BOTH overrides. The context is built the way `app.py`
really builds it:

    context["mode"]              = resolve_strategy(user_text=..., requested_mode=None)["resolved_mode"]
    context["conditioned_render"] = None          # the UI checkbox is OFF
    context["references"]         = {"A": <style>, "B": <target>}

`app.py` never puts `image_references` in the chat context, so role bindings
must come from the dual-image gate — exactly as in production.

Role mapping (product letters are the INVERSE of the test pack's):

    context["references"]["A"] = style_reference  -> node 302 (appearance)
    context["references"]["B"] = target_building  -> node 300 (geometry)

Nothing is submitted to ComfyUI. The executor edge is stubbed.
"""

import hashlib
import json
import os
from types import SimpleNamespace

import pytest

import core.chat.chat_architect as chat_architect_module
from core.chat.chat_architect import ChatArchitect
from core.chat.session_registry_v1 import session_registry
from core.project.project_registry_bridge_v1 import project_registry_bridge
from core.project.project_workspace_v1 import project_workspace
from core.render.render_strategy_controller_v1 import resolve_strategy
from core.vision.image_registry_v1 import image_registry

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PACK = os.path.join(
    ROOT, "tests", "manual_facade_i2i_v1", "ArchitectOS_Reference_Style_Test_V1"
)

TARGET = os.path.join(PACK, "TARGET_A_GPU_768x1024.png")
STYLE = os.path.join(PACK, "STYLE_B_PIXEL_EXACT_PAD_768x1024.png")
REQUEST_FILE = os.path.join(PACK, "REFERENCE_STYLE_REQUEST_EN.txt")

TARGET_SHA = "fd1088ea4bf01add359af7696fc91a3056b7e8719a98e0de1c58a35e6db86f71"
STYLE_SHA = "a9e3cfecd69a17ce37986c2aff9478ede527354297b3af539d6ba11b4d953604"

DUAL_WORKFLOW = "flux_img2img_dual_conditioned.json"
DEAD_WORKFLOW = "flux_img2img_dual.json"
KONTEXT_WORKFLOW = "flux_kontext_edit.json"

UNET = "flux1-krea-dev_fp8_scaled.safetensors"

SEED = 20261030

# The natural-language request of Test A. No role letters, no UI vocabulary.
NATURAL_TEXT = (
    "Redesign my building using the architectural style and cream stone "
    "materials of this reference facade. Preserve my building's original "
    "geometry."
)

COMPARISON_TEXT = "Compare these two buildings."


class _ExecutorStop(RuntimeError):
    """Raised by the stubbed executor to end the route without a GPU job."""


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _request():
    with open(REQUEST_FILE, encoding="utf-8") as handle:
        return handle.read().strip()


# ----------------------------------------------------------
# fixtures
# ----------------------------------------------------------


@pytest.fixture
def isolated_project(tmp_path):
    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(tmp_path / "projects")
    project_workspace.trash_root = str(tmp_path / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)
    manifest = project_workspace.create("ref-style-auto-selection")
    project_registry_bridge.bind(manifest["project_id"])
    session_registry.begin(manifest["session_id"])
    image_registry.reset(manifest["session_id"])
    try:
        yield manifest
    finally:
        session_registry.end()
        project_registry_bridge.unbind()
        image_registry.reset(manifest["session_id"])
        project_workspace.projects_root = old_projects
        project_workspace.trash_root = old_trash


@pytest.fixture
def acceptance_root(tmp_path, monkeypatch):
    """Ephemeral, test-scoped acceptance directory. Never the production one."""

    root = tmp_path / "render_acceptance"
    os.makedirs(root, exist_ok=True)
    monkeypatch.setattr(chat_architect_module, "_R4_ACCEPTANCE_ROOT", str(root))
    return root


def _write_acceptance(root, workflow, unet, sha=None):
    record = {
        "contract": "ArchitecturalPreservationAcceptanceV1",
        "version": "1.0",
        "workflow": workflow,
        "status": "accepted",
        "accepted_scope": "single_source" if sha else "capability",
        "preservation_capability": "architectural_facade_preservation",
        "evidence": {
            "report": "cpu_test_fixture_only",
            "human_approval": False,
            "ephemeral": True,
        },
        "model": {"unet_name": unet},
    }
    if sha:
        record["source_sha256"] = sha
    path = os.path.join(root, workflow)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle)
    return path


def _references(style_path=STYLE, target_path=TARGET):
    return {
        "A": {
            "role": "facade_reference",
            "authority": "appearance_only",
            "present": True,
            "path": style_path,
            "asset_id": "ref_style_b",
            "filename": os.path.basename(style_path),
            "mime_type": "image/png",
        },
        "B": {
            "role": "target_building",
            "authority": "geometry",
            "present": True,
            "path": target_path,
            "asset_id": "target_a",
            "filename": os.path.basename(target_path),
            "mime_type": "image/png",
        },
    }


def _natural_context(manifest, text, references):
    """Build the chat context exactly as `app.py` builds it.

    `app.py` line ~3166:  "mode": strategy.get("resolved_mode")
    `app.py` line ~3118:  "conditioned_render": conditioned_render  (None when
                          the UI checkbox is untouched)
    `app.py` line ~3099:  "references": image_references

    No test override is applied: `requested_mode=None` and the conditioning
    flag is left at its natural OFF/None state.
    """

    strategy = resolve_strategy(user_text=text, requested_mode=None)

    assert strategy.get("blocked") is False, strategy

    return {
        "session_id": manifest["session_id"],
        "project_id": manifest["project_id"],
        "references": references,
        "mode": strategy.get("resolved_mode"),
        "conditioned_render": None,
        "seed": SEED,
    }


def _drive(
    monkeypatch,
    manifest,
    *,
    text=NATURAL_TEXT,
    references=None,
    context_mutator=None,
    message_image=True,
):
    """Run the REAL chat route with the hardware edge stubbed."""

    references = references if references is not None else _references()

    for path in {
        (references.get("A") or {}).get("path"),
        (references.get("B") or {}).get("path"),
    }:
        if path:
            image_registry.register(
                manifest["session_id"],
                path=path,
                source_type="uploaded",
                make_active=False,
            )

    context = _natural_context(manifest, text, references)

    if context_mutator is not None:
        context_mutator(context)

    chat = ChatArchitect(brain=None)

    captured = {"calls": 0, "workflow": None, "kwargs": None}

    def _stub(workflow, engine=None, **kwargs):
        captured["calls"] += 1
        captured["workflow"] = workflow
        captured["kwargs"] = kwargs
        raise _ExecutorStop("cpu capture")

    chat.render_runtime.executor.execute = _stub

    import core.runtime.gpu_handoff_v1 as gpu_handoff

    monkeypatch.setattr(
        gpu_handoff,
        "require_render_vram",
        lambda *a, **k: {"ok": True, "reason": "cpu_stub", "free_mib": 99999},
    )
    monkeypatch.setattr(
        gpu_handoff,
        "unload_ollama_models_for_render",
        lambda *a, **k: {"status": "not_loaded", "reason": "cpu_stub"},
    )
    monkeypatch.setattr(
        gpu_handoff,
        "gpu_render_lease",
        lambda *a, **k: SimpleNamespace(acquire=lambda: True, release=lambda: None),
    )

    import core.render.workflow_executor as workflow_executor

    def _forbidden(*_a, **_k):
        raise AssertionError("real WorkflowExecutor.execute() reached")

    monkeypatch.setattr(workflow_executor.WorkflowExecutor, "execute", _forbidden)

    message = {"text": text}
    if message_image:
        target = (references.get("B") or {}).get("path")
        if target:
            message["image"] = {"path": target}

    try:
        result = chat._handle_internal(message, context)
    except _ExecutorStop:
        result = {"type": "cpu_capture", "status": "captured"}

    return {
        "result": result if isinstance(result, dict) else {},
        "chat": chat,
        "calls": captured["calls"],
        "workflow": captured["workflow"],
        "context": context,
        "strategy": resolve_strategy(user_text=text, requested_mode=None),
    }


def _graph(run):
    return run.get("workflow") or {}


def _node(graph, node_id, key):
    return ((graph.get(node_id) or {}).get("inputs") or {}).get(key)


def _admission(run):
    return (
        run["result"].get("admission")
        or getattr(run["chat"], "last_r4_admission", None)
        or {}
    )


# ==========================================================
# A — natural language, no manual conditioning
# ==========================================================


def test_A_natural_request_derives_transfer_policy_and_conditioning(
    isolated_project, acceptance_root, monkeypatch
):
    """The turn itself must be enough: no mode, no conditioning flag."""

    run = _drive(monkeypatch, isolated_project)

    # The boundary must NOT have been given an image-edit mode by the test.
    assert run["context"]["mode"] == "auto"
    assert run["context"]["conditioned_render"] is None

    from core.chat.chat_architect import _reference_transfer_policy

    policy = _reference_transfer_policy(
        NATURAL_TEXT, {"A": "facade_reference", "B": "target_building"}
    )

    assert isinstance(policy, dict), "no reference-transfer policy derived"
    assert policy.get("role") in ("style_only", "material_only")

    admission = _admission(run)

    assert admission.get("evaluated_workflow") == DUAL_WORKFLOW, (
        "the natural request did not reach the conditioned workflow: "
        f"{admission}"
    )


def test_A2_natural_request_selects_the_conditioned_workflow(
    isolated_project, acceptance_root, monkeypatch
):
    run = _drive(monkeypatch, isolated_project)

    admission = _admission(run)

    assert admission.get("evaluated_workflow") == DUAL_WORKFLOW

    conditioning = admission.get("conditioning") or {}
    assert conditioning.get("conditioned") is True, admission
    assert conditioning.get("source") == "reference_transfer_intent"


# ==========================================================
# B — the existing real request file
# ==========================================================


def test_B_real_request_file_selects_the_conditioned_workflow(
    isolated_project, acceptance_root, monkeypatch
):
    run = _drive(monkeypatch, isolated_project, text=_request())

    assert run["context"]["mode"] == "auto"
    assert run["context"]["conditioned_render"] is None

    admission = _admission(run)

    assert admission.get("evaluated_workflow") == DUAL_WORKFLOW, admission


# ==========================================================
# C — two images without transfer intent
# ==========================================================


def test_C_comparison_request_does_not_start_a_facade_redesign(
    isolated_project, acceptance_root, monkeypatch
):
    run = _drive(monkeypatch, isolated_project, text=COMPARISON_TEXT)

    assert run["calls"] == 0, "a comparison request started a render"

    admission = _admission(run)

    assert admission.get("evaluated_workflow") != DUAL_WORKFLOW
    assert (run["result"].get("reason") or "") != (
        "conditioning_unavailable_for_requested_transfer"
    )


def test_C2_comparison_never_derives_a_reference_policy():
    from core.chat.chat_architect import _reference_transfer_policy

    roles = {"A": "facade_reference", "B": "target_building"}

    assert _reference_transfer_policy(COMPARISON_TEXT, roles) is None

    assert (
        _reference_transfer_policy(
            "Compare the style of these two buildings.", roles
        )
        is None
    )


# ==========================================================
# D — ambiguous image roles
# ==========================================================


def test_D_missing_role_pair_does_not_guess_a_geometry_authority(
    isolated_project, acceptance_root, monkeypatch
):
    refs = _references()
    refs.pop("B")  # no declared target building

    run = _drive(monkeypatch, isolated_project, references=refs)

    assert run["calls"] == 0, "a render ran without a declared target building"

    admission = _admission(run)

    assert admission.get("evaluated_workflow") != DUAL_WORKFLOW


def test_D2_only_the_style_reference_cannot_become_the_target(
    isolated_project, acceptance_root, monkeypatch
):
    refs = {"A": _references()["A"]}

    run = _drive(monkeypatch, isolated_project, references=refs)

    assert run["calls"] == 0


# ==========================================================
# E — missing conditioned capability
# ==========================================================


def test_E_missing_conditioning_capability_blocks_the_transfer(
    isolated_project, acceptance_root, monkeypatch
):
    import core.render.dual_image_conditioning_v1 as conditioning

    monkeypatch.setattr(
        conditioning,
        "verify_conditioning_models",
        lambda **kwargs: {
            "status": "blocked",
            "missing": [{"role": "uso_style_patch"}],
            "invalid": [],
        },
    )

    run = _drive(monkeypatch, isolated_project)

    assert run["calls"] == 0, "the transfer executed without its conditioning assets"

    result = run["result"]

    assert result.get("type") == "render_blocked", result
    assert result.get("reason") == "conditioning_unavailable_for_requested_transfer"


def test_E2_capability_failure_never_falls_back_to_the_dead_graph(
    isolated_project, acceptance_root, monkeypatch
):
    import core.render.dual_image_conditioning_v1 as conditioning

    monkeypatch.setattr(
        conditioning,
        "verify_conditioning_models",
        lambda **kwargs: {"status": "blocked", "missing": [], "invalid": []},
    )

    run = _drive(monkeypatch, isolated_project)

    result = run["result"]

    assert run["calls"] == 0

    # The refusal must name the transfer, not pretend the dead graph was used.
    assert result.get("type") == "render_blocked", result
    assert result.get("reason") == "conditioning_unavailable_for_requested_transfer"
    assert (result.get("conditioning_decision") or {}).get("conditioned") is False

    admission = _admission(run)

    assert admission.get("evaluated_workflow") != DEAD_WORKFLOW
    assert admission.get("selected_workflow") != DEAD_WORKFLOW


# ==========================================================
# F — R4 remains CLOSED by default
# ==========================================================


def test_F_r4_refuses_execution_without_an_acceptance_record(
    isolated_project, acceptance_root, monkeypatch
):
    run = _drive(monkeypatch, isolated_project)

    result = run["result"]

    assert result.get("type") == "render_blocked", result
    assert result.get("reason") == "preservation_capability_unverified"
    assert result["admission"]["admitted"] is False
    assert run["calls"] == 0, "R4 closed but the executor still ran"

    assert not os.path.exists(
        os.path.join(ROOT, "data", "render_acceptance", DUAL_WORKFLOW)
    )


def test_F2_a_kontext_acceptance_does_not_authorise_the_dual_workflow(
    isolated_project, acceptance_root, monkeypatch
):
    _write_acceptance(
        acceptance_root, KONTEXT_WORKFLOW,
        "flux1-dev-kontext_fp8_scaled.safetensors", TARGET_SHA,
    )

    run = _drive(monkeypatch, isolated_project)

    assert run["result"].get("type") == "render_blocked"
    assert run["calls"] == 0


# ==========================================================
# G — isolated temporary test admission
# ==========================================================


def test_G_temporary_single_source_admission_permits_the_stubbed_executor(
    isolated_project, acceptance_root, monkeypatch
):
    _write_acceptance(acceptance_root, DUAL_WORKFLOW, UNET, TARGET_SHA)

    run = _drive(monkeypatch, isolated_project)

    assert run["calls"] == 1, run["result"]

    admission = run["chat"].last_r4_admission or {}

    assert admission.get("admitted") is True, admission
    assert admission.get("selected_workflow") == DUAL_WORKFLOW, admission

    # The executor receives the GRAPH, not the filename. The graph must be the
    # CONDITIONED one: the sampler's model input comes from the USO style node.
    graph = _graph(run)

    assert len(graph) == 21, sorted(graph)
    assert (graph.get("322") or {}).get("class_type") == "USOStyleReference"
    assert _node(graph, "210", "model") == ["322", 0]


def test_G2_an_admission_for_another_source_does_not_authorise(
    isolated_project, acceptance_root, monkeypatch
):
    _write_acceptance(acceptance_root, DUAL_WORKFLOW, UNET, "0" * 64)

    run = _drive(monkeypatch, isolated_project)

    assert run["result"].get("type") == "render_blocked"
    assert run["calls"] == 0


def test_G3_an_admission_for_another_model_does_not_authorise(
    isolated_project, acceptance_root, monkeypatch
):
    _write_acceptance(
        acceptance_root, DUAL_WORKFLOW,
        "flux1-dev-kontext_fp8_scaled.safetensors", TARGET_SHA,
    )

    run = _drive(monkeypatch, isolated_project)

    assert run["result"].get("type") == "render_blocked"
    assert run["calls"] == 0


# ==========================================================
# H — real graph wiring under the isolated admission
# ==========================================================


def test_H_graph_wiring_under_isolated_admission(
    isolated_project, acceptance_root, monkeypatch
):
    """The REAL request file, admitted in isolation, reaches the sampler."""

    _write_acceptance(acceptance_root, DUAL_WORKFLOW, UNET, TARGET_SHA)

    run = _drive(monkeypatch, isolated_project, text=_request())

    assert run["calls"] == 1, run["result"]

    graph = _graph(run)

    target_file = _node(graph, "300", "image")
    style_file = _node(graph, "302", "image")

    assert target_file and style_file
    assert target_file != style_file

    # geometry authority -> latent and depth
    assert _node(graph, "301", "pixels") == ["300", 0]
    assert _node(graph, "210", "latent_image") == ["301", 0]
    assert _node(graph, "306", "image") == ["300", 0]

    # appearance authority -> clip vision -> USO -> sampler model
    assert _node(graph, "303", "image") == ["302", 0]
    assert _node(graph, "322", "clip_vision_output") == ["303", 0]
    assert _node(graph, "210", "model") == ["322", 0]

    # the reference never becomes the geometry source
    assert _node(graph, "301", "pixels") != ["302", 0]

    # the prompt reaches node 206 and is the architectural instruction
    prompt = str(_node(graph, "206", "text") or "")
    lowered = prompt.lower()

    assert prompt
    assert "stone" in lowered or "travertine" in lowered
    assert "neoclassical" in lowered or "classical" in lowered
    assert "preserv" in lowered

    # staged bytes are the versioned pack, unmodified
    staging = run["chat"].image_handler.image_bridge.asset_bridge.comfy_input
    assert _sha256(os.path.join(staging, target_file)) == TARGET_SHA
    assert _sha256(os.path.join(staging, style_file)) == STYLE_SHA


def test_H2_natural_request_produces_the_same_conditioned_graph(
    isolated_project, acceptance_root, monkeypatch
):
    """Test A's turn — no mode, no flag — must reach the identical wiring."""

    _write_acceptance(acceptance_root, DUAL_WORKFLOW, UNET, TARGET_SHA)

    run = _drive(monkeypatch, isolated_project)  # NATURAL_TEXT, no overrides

    assert run["calls"] == 1, run["result"]

    graph = _graph(run)

    assert len(graph) == 21, sorted(graph)
    assert _node(graph, "301", "pixels") == ["300", 0]
    assert _node(graph, "306", "image") == ["300", 0]
    assert _node(graph, "303", "image") == ["302", 0]
    assert _node(graph, "322", "clip_vision_output") == ["303", 0]
    assert _node(graph, "210", "model") == ["322", 0]

    prompt = str(_node(graph, "206", "text") or "").lower()

    assert "stone" in prompt
    assert "preserv" in prompt


# ==========================================================
# I — regression controls
# ==========================================================


def test_I1_text_to_image_route_unchanged():
    from core.render.workflow_selector import WorkflowSelector

    selector = WorkflowSelector()

    assert selector.select({"engine": "flux"}) == "flux.json"
    assert selector.select({"engine": "flux", "mode": "edit"}) == "flux_img2img.json"
    assert (
        selector.select({"engine": "flux", "dual_image": True, "conditioned": True})
        == DUAL_WORKFLOW
    )


def test_I2_single_image_kontext_stays_closed(
    isolated_project, acceptance_root, monkeypatch
):
    chat = ChatArchitect.__new__(ChatArchitect)
    chat._default_state = session_registry.current_state()

    record = image_registry.register(
        isolated_project["session_id"], path=TARGET,
        source_type="uploaded", make_active=True,
    )

    chat.image_handler = SimpleNamespace(
        resolve_source_bound_intent=lambda r: {"status": "unknown"},
        sanitize_architectural_intent=lambda v: {},
        handle_image_edit=lambda **k: {"status": "success"},
    )
    chat.render_runtime = SimpleNamespace(last_render_metadata={})

    result = chat._route_image_edit(
        "Redesign this facade in a modern style.", record,
        {"image_id": record["image_id"]}, None, None, SEED, {},
        image_understanding=None,
    )

    assert result["type"] == "render_blocked"
    assert result["reason"] == "preservation_capability_unverified"


def test_I3_explicit_opt_out_is_honoured(
    isolated_project, acceptance_root, monkeypatch
):
    """A UI opt-out must win over the derived transfer policy."""

    def _opt_out(context):
        context["conditioned_render"] = False

    run = _drive(monkeypatch, isolated_project, context_mutator=_opt_out)

    result = run["result"]

    assert run["calls"] == 0
    assert result.get("type") == "render_blocked", result

    # The explicit OFF must be what decided it, not the capability gate.
    assert (result.get("conditioning_decision") or {}).get("explicit") is False
    assert (result.get("conditioning_decision") or {}).get("conditioned") is False

    admission = _admission(run)

    assert admission.get("evaluated_workflow") != DUAL_WORKFLOW


def test_I4_code_request_routing_unchanged(isolated_project, monkeypatch):
    """A code turn with no images must not reach the render dispatch."""

    chat = ChatArchitect(brain=None)

    try:
        result = chat._handle_internal(
            {"text": "write me a python function that sums a list"},
            {
                "session_id": isolated_project["session_id"],
                "project_id": isolated_project["project_id"],
            },
        )
    except Exception:  # noqa: BLE001 - the turn may need a live brain
        pytest.skip("code turn requires a live brain in this environment")

    assert isinstance(result, dict)
    assert result.get("type") not in ("render_blocked", "cpu_capture")
