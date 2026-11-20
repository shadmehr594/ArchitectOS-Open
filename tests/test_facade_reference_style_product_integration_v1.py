"""FACADE_REFERENCE_STYLE_PRODUCT_INTEGRATION_V1 — real dual-image route.

Every test drives the REAL production entry point:

    ChatArchitect._handle_internal(message, context)

with a verified A/B reference pair, a stubbed GPU/executor edge and (where the
scenario needs it) an EPHEMERAL single-source acceptance record confined to a
temporary directory. Nothing is submitted to ComfyUI.

The route performs live LLM intent inference and two live vision analyses; the
analysis is cached in-process by content hash, so only the first test pays for
it.

Role mapping (the product's letters are the INVERSE of the test pack's):

    context["references"]["A"] = style_reference  -> node 302 (appearance)
    context["references"]["B"] = target_building  -> node 300 (geometry)
"""

import hashlib
import json
import os
import shutil
import tempfile
from types import SimpleNamespace

import pytest
from PIL import Image

import core.chat.chat_architect as chat_architect_module
from core.chat.chat_architect import ChatArchitect
from core.chat.session_registry_v1 import session_registry
from core.project.project_registry_bridge_v1 import project_registry_bridge
from core.project.project_workspace_v1 import project_workspace
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

SEED = 20261030


class _ExecutorStop(RuntimeError):
    pass


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
    manifest = project_workspace.create("ref-style-integration")
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
    monkeypatch.setattr(
        chat_architect_module, "_R4_ACCEPTANCE_ROOT", str(root)
    )
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


def _drive(
    monkeypatch,
    tmp_path,
    manifest,
    *,
    text=None,
    references=None,
    image=True,
    context_extra=None,
):
    """Run the REAL chat route with the hardware edge stubbed."""

    text = text if text is not None else _request()
    references = references if references is not None else _references()

    for path in {references.get("A", {}).get("path"),
                 references.get("B", {}).get("path")}:
        if path:
            image_registry.register(
                manifest["session_id"], path=path,
                source_type="uploaded", make_active=False,
            )

    context = {
        "session_id": manifest["session_id"],
        "project_id": manifest["project_id"],
        "references": references,
        "mode": "generate",
    }
    context.update(context_extra or {})

    chat = ChatArchitect(brain=None)

    captured = {"calls": 0, "workflow": None}

    def _stub(workflow, engine=None, **kwargs):
        captured["calls"] += 1
        captured["workflow"] = workflow
        raise _ExecutorStop("cpu capture")

    chat.render_runtime.executor.execute = _stub

    import core.runtime.gpu_handoff_v1 as gpu_handoff

    monkeypatch.setattr(
        gpu_handoff, "require_render_vram",
        lambda *a, **k: {"ok": True, "reason": "cpu_stub", "free_mib": 99999},
    )
    monkeypatch.setattr(
        gpu_handoff, "unload_ollama_models_for_render",
        lambda *a, **k: {"status": "not_loaded", "reason": "cpu_stub"},
    )
    monkeypatch.setattr(
        gpu_handoff, "gpu_render_lease",
        lambda *a, **k: SimpleNamespace(acquire=lambda: True, release=lambda: None),
    )

    import core.render.workflow_executor as workflow_executor

    def _forbidden(*_a, **_k):
        raise AssertionError("real WorkflowExecutor.execute() reached")

    monkeypatch.setattr(
        workflow_executor.WorkflowExecutor, "execute", _forbidden
    )

    message = {"text": text}
    if image:
        message["image"] = {"path": references["B"]["path"]}

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
    }


def _graph(run):
    return (run.get("workflow") or {})


def _node(graph, node_id, key):
    return ((graph.get(node_id) or {}).get("inputs") or {}).get(key)


# ==========================================================
# A — R4 coverage on the dual route
# ==========================================================


def test_A_dual_reference_edit_is_blocked_without_acceptance(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    run = _drive(
        monkeypatch, tmp_path, isolated_project,
        context_extra={"mode": "image_to_image", "conditioned_render": True},
    )

    result = run["result"]

    assert result.get("type") == "render_blocked", result.get("type")
    assert result.get("reason") == "preservation_capability_unverified"
    assert result["admission"]["admitted"] is False
    assert run["calls"] == 0


def test_A2_the_refusal_names_the_workflow_it_would_have_used(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    run = _drive(
        monkeypatch, tmp_path, isolated_project,
        context_extra={"mode": "image_to_image", "conditioned_render": True},
    )

    admission = run["result"].get("admission") or {}

    assert admission.get("selected_workflow") in (None, DUAL_WORKFLOW)
    assert DUAL_WORKFLOW in (admission.get("rejected_workflows") or {})
    assert run["calls"] == 0


# ==========================================================
# B — workflow identity
# ==========================================================


def test_B_a_kontext_acceptance_does_not_authorise_the_dual_workflow(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    _write_acceptance(
        acceptance_root, KONTEXT_WORKFLOW,
        "flux1-dev-kontext_fp8_scaled.safetensors", TARGET_SHA,
    )

    run = _drive(
        monkeypatch, tmp_path, isolated_project,
        context_extra={"mode": "image_to_image", "conditioned_render": True},
    )

    assert run["result"].get("type") == "render_blocked"
    assert run["result"].get("reason") == "preservation_capability_unverified"
    assert run["calls"] == 0


def test_B2_a_dual_record_for_another_model_does_not_authorise(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    _write_acceptance(
        acceptance_root, DUAL_WORKFLOW,
        "flux1-dev-kontext_fp8_scaled.safetensors", TARGET_SHA,
    )

    run = _drive(
        monkeypatch, tmp_path, isolated_project,
        context_extra={"mode": "image_to_image", "conditioned_render": True},
    )

    assert run["result"].get("type") == "render_blocked"
    assert run["calls"] == 0


def test_B3_a_dual_record_for_another_source_does_not_authorise(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    _write_acceptance(
        acceptance_root, DUAL_WORKFLOW,
        "flux1-krea-dev_fp8_scaled.safetensors",
        "0" * 64,
    )

    run = _drive(
        monkeypatch, tmp_path, isolated_project,
        context_extra={"mode": "image_to_image", "conditioned_render": True},
    )

    assert run["result"].get("type") == "render_blocked"
    assert run["calls"] == 0


# ==========================================================
# C — explicit style transfer selects the conditioned graph
# ==========================================================


def test_C_explicit_style_transfer_selects_the_conditioned_workflow(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    run = _drive(
        monkeypatch, tmp_path, isolated_project,
        context_extra={"mode": "image_to_image", "conditioned_render": True},
    )

    admission = run["result"].get("admission") or {}

    # The route must have resolved the request to the graph that really
    # consumes the reference — even though it then refuses to render it.
    assert admission.get("evaluated_workflow") == DUAL_WORKFLOW, admission
    assert run["workflow"] != DEAD_WORKFLOW


def test_C2_the_dead_reference_graph_is_never_chosen(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    run = _drive(
        monkeypatch, tmp_path, isolated_project,
        context_extra={"mode": "image_to_image", "conditioned_render": True},
    )

    assert run["workflow"] != DEAD_WORKFLOW
    admission = run["result"].get("admission") or {}
    assert admission.get("selected_workflow") != DEAD_WORKFLOW


# ==========================================================
# D — ambiguity must not activate conditioning
# ==========================================================


def test_D_no_transfer_language_does_not_activate_conditioning():
    from core.chat.chat_architect import _reference_transfer_policy
    from core.render.dual_image_conditioning_v1 import resolve_conditioning

    roles = {"A": "facade_reference", "B": "target_building"}

    policy = _reference_transfer_policy("Here are two images.", roles)

    assert policy is None

    decision = resolve_conditioning(
        role_bindings=roles,
        reference_policy=policy,
        mode="generate",
        text="Here are two images.",
        explicit=None,
    )

    assert decision["conditioned"] is False


def test_D2_explicit_transfer_language_derives_a_style_policy():
    from core.chat.chat_architect import _reference_transfer_policy

    roles = {"A": "facade_reference", "B": "target_building"}

    policy = _reference_transfer_policy(
        "Redesign my building using the architectural style and materials of "
        "this reference facade",
        roles,
    )

    assert isinstance(policy, dict)
    assert policy.get("role") in ("style_only", "material_only")


def test_D3_policy_requires_a_verified_pair():
    from core.chat.chat_architect import _reference_transfer_policy

    assert _reference_transfer_policy(
        "Redesign my building using the architectural style of this reference",
        {"A": "facade_reference"},
    ) is None


# ==========================================================
# E — role binding and graph wiring (admitted, ephemeral record)
# ==========================================================


@pytest.fixture
def admitted(isolated_project, acceptance_root):
    _write_acceptance(
        acceptance_root, DUAL_WORKFLOW,
        "flux1-krea-dev_fp8_scaled.safetensors", TARGET_SHA,
    )
    return isolated_project


def test_E_target_and_reference_reach_the_correct_nodes(
    admitted, tmp_path, monkeypatch
):
    run = _drive(
        monkeypatch, tmp_path, admitted,
        context_extra={"mode": "image_to_image", "conditioned_render": True},
    )

    assert run["calls"] == 1, run["result"]

    graph = _graph(run)

    target_file = _node(graph, "300", "image")
    style_file = _node(graph, "302", "image")

    assert target_file and style_file
    assert target_file != style_file

    # target -> latent
    assert _node(graph, "301", "pixels") == ["300", 0]
    assert _node(graph, "210", "latent_image") == ["301", 0]

    # target -> depth -> ControlNet
    assert _node(graph, "306", "image") == ["300", 0]

    # reference -> clip vision -> USO -> sampler model
    assert _node(graph, "303", "image") == ["302", 0]
    assert _node(graph, "322", "clip_vision_output") == ["303", 0]
    assert _node(graph, "210", "model") == ["322", 0]

    # the reference must NOT become the geometry source
    assert _node(graph, "301", "pixels") != ["302", 0]


def test_E2_staged_bytes_match_the_pack(admitted, tmp_path, monkeypatch):
    run = _drive(
        monkeypatch, tmp_path, admitted,
        context_extra={"mode": "image_to_image", "conditioned_render": True},
    )

    graph = _graph(run)

    staging = run["chat"].image_handler.image_bridge.asset_bridge.comfy_input

    target_staged = os.path.join(staging, _node(graph, "300", "image"))
    style_staged = os.path.join(staging, _node(graph, "302", "image"))

    assert os.path.isfile(target_staged) and os.path.isfile(style_staged)
    assert _sha256(target_staged) == TARGET_SHA
    assert _sha256(style_staged) == STYLE_SHA


# ==========================================================
# F — preservation admission contents
# ==========================================================


def test_F_admitted_route_carries_a_preservation_contract(
    admitted, tmp_path, monkeypatch
):
    run = _drive(
        monkeypatch, tmp_path, admitted,
        context_extra={"mode": "image_to_image", "conditioned_render": True},
    )

    admission = run["chat"].last_r4_admission or {}

    assert admission.get("admitted") is True
    assert admission.get("selected_workflow") == DUAL_WORKFLOW

    contract = admission.get("preservation_contract") or {}

    assert contract.get("contract") == "ArchitecturalPreservationContractV1"
    assert len(contract.get("preserve") or []) >= 8
    assert len(contract.get("prohibit") or []) >= 5
    assert (contract.get("source") or {}).get("sha256") == TARGET_SHA


def test_F2_style_reference_cannot_become_the_target(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    """The reference must never be edited as if it were the building."""

    _write_acceptance(
        acceptance_root, DUAL_WORKFLOW,
        "flux1-krea-dev_fp8_scaled.safetensors", STYLE_SHA,
    )

    refs = _references()
    # swap: the STYLE file is declared as the target building
    refs["B"] = dict(refs["B"], path=STYLE, filename=os.path.basename(STYLE))

    run = _drive(monkeypatch, tmp_path, isolated_project, references=refs)

    # Either the admission refuses (sha/scope) or the run is blocked; it must
    # never silently render the reference as the building.
    assert run["calls"] == 0 or run["result"].get("type") == "render_blocked"


# ==========================================================
# G — prompt integrity
# ==========================================================


def test_G_prompt_is_cream_stone_neoclassical_with_preservation(
    admitted, tmp_path, monkeypatch
):
    run = _drive(
        monkeypatch, tmp_path, admitted,
        context_extra={"mode": "image_to_image", "conditioned_render": True},
    )

    graph = _graph(run)
    prompt = str(_node(graph, "206", "text") or "")

    assert prompt
    lowered = prompt.lower()

    assert "stone" in lowered or "travertine" in lowered
    assert "neoclassical" in lowered or "classical" in lowered
    assert "preserv" in lowered

    assert "metal panel cladding" not in lowered
    assert "terracotta brick" not in lowered


# ==========================================================
# H — existing routes unchanged
# ==========================================================


def test_H_single_image_kontext_route_stays_closed(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    from core.chat.chat_architect import ChatArchitect as _CA

    chat = _CA.__new__(_CA)
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


def test_H2_text_to_image_selection_unchanged():
    from core.render.workflow_selector import WorkflowSelector

    selector = WorkflowSelector()

    assert selector.select({"engine": "flux"}) == "flux.json"
    assert selector.select({"engine": "flux", "mode": "edit"}) == "flux_img2img.json"
    assert selector.select(
        {"engine": "flux", "dual_image": True, "conditioned": True}
    ) == DUAL_WORKFLOW
