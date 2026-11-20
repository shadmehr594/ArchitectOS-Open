"""FACADE_RENDERING_FIRST_I2I_ADMISSION_V1 — CPU admission contract.

Scope
-----
The first real product scenario:

    existing building photograph -> facade redesign from a text instruction
    -> existing Kontext instruction-edit workflow

This module drives the REAL production call chain:

    ChatArchitect._route_image_edit()
        -> _r4_architectural_edit_admission()   (the production gate)
        -> ImageHandler.handle_image_edit()
        -> RenderRuntime.render() / PromptRouter / ImageEditPromptBuilder
        -> resolve_render_prompt()
        -> WorkflowSelector / WorkflowLoader
        -> ImageWorkflowInjector.inject()
        -> WorkflowExecutor.execute()           (STUBBED — the hardware edge)

Only the hardware boundary is replaced: VRAM measurement, the Ollama unload
and the ComfyUI submission. `RenderRuntime.last_render_request` therefore
carries the exact prompt and the exact graph the sampler would receive.

No GPU job is submitted by this module. `WorkflowExecutor.execute` is replaced
by a sentinel and the real class method is additionally monkeypatched to raise,
so a forgotten stub cannot reach the network.

Evidence rules
--------------
A successful CPU run proves the pathway is PREPARED and BOUNDED. It does not
prove architectural preservation. `test_F` therefore keeps the default
production admission CLOSED, and no test in this module claims visual
fidelity.
"""

import hashlib
import json
import os
import re
from types import SimpleNamespace

import pytest
from PIL import Image

from core.chat.chat_architect import ChatArchitect
from core.chat.chat_image_bridge import ChatImageBridge
from core.chat.handlers.image_handler import ImageHandler
from core.chat.image_response_adapter import ImageResponseAdapter
from core.chat.session_registry_v1 import session_registry
from core.intelligence.semantic_intent import SemanticIntentEngine
from core.project.project_registry_bridge_v1 import project_registry_bridge
from core.project.project_workspace_v1 import project_workspace
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.prompt_intelligence.image_edit_delta_v1 import compile_edit_delta
from core.render.render_result_bridge import RenderResultBridge
from core.render.render_runtime import RenderRuntime
from core.render.workflow_selector import WorkflowSelector
from core.vision.image_registry_v1 import image_registry

import core.chat.chat_architect as chat_architect_module


# ----------------------------------------------------------
# The bounded acceptance subject
# ----------------------------------------------------------

WORKFLOW = "flux_kontext_edit.json"

REQUEST_EN = (
    "Redesign this building in modern Iranian brick architecture with dark "
    "metal window frames."
)

# The same request, phrased so the delta compiler classifies it as a style
# edit rather than a material replacement.
REQUEST_STYLE_EN = (
    "Redesign this building in a contemporary Iranian brick style, keep the "
    "existing floor arrangement, window positions, balcony locations, "
    "roofline and camera perspective unchanged."
)

SEED = 20261030

# Distinct, textured source content. A flat placeholder is NOT a valid
# architectural source and the integrity check must reject it.
SOURCE_SIZE = (96, 80)


class _State:
    """Minimal session state object (get / update / add_message)."""

    def __init__(self):
        self.data = {}

    def get(self):
        return self.data

    def update(self, values):
        self.data.update(values or {})

    def add_message(self, *args, **kwargs):
        return None


class _ExecutorStop(RuntimeError):
    """Sentinel raised at the ComfyUI submission boundary."""


# ----------------------------------------------------------
# Fixtures
# ----------------------------------------------------------


@pytest.fixture
def isolated_project(tmp_path):
    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(tmp_path / "projects")
    project_workspace.trash_root = str(tmp_path / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)
    manifest = project_workspace.create("facade-i2i-admission-v1")
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
    """Server-side acceptance directory, isolated per test.

    The production default lives inside the project; tests redirect it so a
    test can never install a capability the product does not have.
    """

    root = tmp_path / "render_acceptance"
    os.makedirs(root, exist_ok=True)
    monkeypatch.setattr(
        chat_architect_module, "_R4_ACCEPTANCE_ROOT", str(root)
    )
    return root


def _write_acceptance(root, **overrides):
    record = {
        "contract": "ArchitecturalPreservationAcceptanceV1",
        "version": "1.0",
        "workflow": WORKFLOW,
        "status": "accepted",
        "accepted_scope": "capability",
        "preservation_capability": "architectural_facade_preservation",
        "evidence": {
            "report": "ARCHITECTOS_FACADE_RENDERING_FIRST_I2I_ACCEPTANCE_V1.md",
            "human_approval": True,
        },
        "model": {"unet_name": "flux1-dev-kontext_fp8_scaled.safetensors"},
    }
    record.update(overrides)
    path = root / (WORKFLOW.replace(".json", "") + ".json")
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def _textured_source(tmp_path, manifest, name="facade.png"):
    """A registered original with real content (never a flat placeholder)."""

    path = tmp_path / name
    image = Image.new("RGB", SOURCE_SIZE)
    pixels = image.load()
    for y in range(SOURCE_SIZE[1]):
        for x in range(SOURCE_SIZE[0]):
            # Deterministic texture: brick-ish banding plus a gradient.
            band = 40 if (y // 8) % 2 else 0
            pixels[x, y] = (
                min(255, 120 + band + x // 2),
                min(255, 100 + band + y // 3),
                min(255, 90 + band),
            )
    image.save(path)
    return image_registry.register(
        manifest["session_id"],
        path=str(path),
        source_type="uploaded",
        make_active=True,
    )


def _flat_source(tmp_path, manifest, name="placeholder.png"):
    path = tmp_path / name
    Image.new("RGB", SOURCE_SIZE, (12, 12, 12)).save(path)
    return image_registry.register(
        manifest["session_id"],
        path=str(path),
        source_type="uploaded",
        make_active=True,
    )


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _chain(monkeypatch, tmp_path):
    """Real production chain; only the hardware boundary is replaced."""

    runtime = RenderRuntime()

    captured = {"executor_calls": 0, "workflow": None, "engine": None}

    def _stub_execute(workflow, engine=None, **kwargs):
        captured["executor_calls"] += 1
        captured["workflow"] = workflow
        captured["engine"] = engine
        raise _ExecutorStop("cpu capture")

    runtime.executor.execute = _stub_execute

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

    def _forbidden_real_execute(*_args, **_kwargs):
        raise AssertionError("real WorkflowExecutor.execute() reached")

    monkeypatch.setattr(
        workflow_executor.WorkflowExecutor, "execute", _forbidden_real_execute
    )

    image_bridge = ChatImageBridge()
    staging = tmp_path / "comfy_input"
    os.makedirs(staging, exist_ok=True)
    image_bridge.asset_bridge.comfy_input = str(staging)

    handler = ImageHandler(
        render_runtime=runtime,
        result_bridge=RenderResultBridge(),
        semantic_intent=SemanticIntentEngine(fallback=ArchitecturalIntent()),
        image_bridge=image_bridge,
        image_response=ImageResponseAdapter(),
        writeback=None,
        state=_State(),
        prompt_builder=None,
    )

    chat = ChatArchitect.__new__(ChatArchitect)
    chat._default_state = session_registry.current_state()
    chat.image_handler = handler
    chat.render_runtime = runtime

    return chat, runtime, captured, staging


def _route(chat, record, text, context=None, image_understanding=None):
    return chat._route_image_edit(
        text,
        record,
        {"image_id": record.get("image_id")},
        None,
        None,
        SEED,
        context if context is not None else {},
        image_understanding=image_understanding,
    )


def _run(monkeypatch, tmp_path, record, text, context=None):
    chat, runtime, captured, staging = _chain(monkeypatch, tmp_path)
    result = _route(chat, record, text, context)
    return {
        "result": result,
        "chat": chat,
        "runtime": runtime,
        "captured": captured,
        "staging": staging,
        "prompt": (runtime.last_render_request or {}).get("resolved_prompt") or "",
        "request": runtime.last_render_request or {},
    }


def _admitted(run):
    result = run["result"]
    assert not (
        isinstance(result, dict) and result.get("type") == "render_blocked"
    ), result
    assert run["captured"]["executor_calls"] == 1
    return run["captured"]["workflow"]


# ==========================================================
# F — the DEFAULT production admission stays closed
# ==========================================================


def test_F_default_admission_remains_closed(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    """No acceptance record => the pre-existing refusal, unchanged."""

    assert list(acceptance_root.iterdir()) == []

    source = _textured_source(tmp_path, isolated_project)
    run = _run(monkeypatch, tmp_path, source, REQUEST_EN)

    result = run["result"]

    assert result["type"] == "render_blocked"
    assert result["status"] == "blocked"
    assert result["reason"] == "preservation_capability_unverified"
    assert result["admission"]["admitted"] is False
    assert result["admission"]["selected_workflow"] is None
    assert result["admission"]["rejected_workflows"] == {
        "flux_kontext_edit.json": "preservation_capability_unverified",
        "flux_img2img.json": "preservation_capability_unverified",
    }
    assert result["admission"]["human_learning_authority"] == (
        "not_used_for_visual_capability"
    )
    assert run["captured"]["executor_calls"] == 0
    assert run["prompt"] == ""


def test_F2_an_acceptance_for_another_workflow_does_not_admit(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    """A record names ONE workflow; it cannot authorise a different graph."""

    _write_acceptance(acceptance_root, workflow="flux_img2img.json")

    source = _textured_source(tmp_path, isolated_project)
    run = _run(monkeypatch, tmp_path, source, REQUEST_EN)

    assert run["result"]["type"] == "render_blocked"
    assert run["captured"]["executor_calls"] == 0


def test_F3_a_pending_or_rejected_record_does_not_admit(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    _write_acceptance(acceptance_root, status="pending")

    source = _textured_source(tmp_path, isolated_project)
    run = _run(monkeypatch, tmp_path, source, REQUEST_EN)

    assert run["result"]["type"] == "render_blocked"
    assert run["captured"]["executor_calls"] == 0


def test_F4_an_acceptance_for_another_checkpoint_does_not_admit(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    """Preservation capability is bound to the accepted model identity."""

    _write_acceptance(
        acceptance_root,
        model={"unet_name": "flux1-krea-dev_fp8_scaled.safetensors"},
    )

    source = _textured_source(tmp_path, isolated_project)
    run = _run(monkeypatch, tmp_path, source, REQUEST_EN)

    assert run["result"]["type"] == "render_blocked"
    assert run["captured"]["executor_calls"] == 0


# ==========================================================
# A — the authorized architectural edit candidate
# ==========================================================


def test_A_authorized_facade_redesign_reaches_the_kontext_workflow(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    _write_acceptance(acceptance_root)

    source = _textured_source(tmp_path, isolated_project)
    run = _run(monkeypatch, tmp_path, source, REQUEST_EN)

    graph = _admitted(run)

    # The graph IS the existing Kontext instruction-edit graph.
    classes = {node.get("class_type") for node in graph.values()}
    assert "ReferenceLatent" in classes
    assert graph["202"]["inputs"]["unet_name"] == (
        "flux1-dev-kontext_fp8_scaled.safetensors"
    )

    # The selector agrees with the graph that was actually prepared.
    selector = WorkflowSelector()
    assert selector.select({"engine": "flux", "kontext_edit": True}) == WORKFLOW

    # Admission is reported truthfully on the request.
    admission = run["request"].get("admission") or run["request"].get(
        "r4_admission"
    )
    assert admission is None or admission.get("admitted") is not False


def test_A2_admission_is_recorded_on_the_request_context(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    """The contract must be visible to the caller, not implied."""

    _write_acceptance(acceptance_root)

    source = _textured_source(tmp_path, isolated_project)
    run = _run(monkeypatch, tmp_path, source, REQUEST_EN)

    admission = run["chat"].last_r4_admission

    assert isinstance(admission, dict), admission
    assert admission["admitted"] is True
    assert admission["selected_workflow"] == WORKFLOW

    contract = admission["preservation_contract"]

    assert contract["contract"] == "ArchitecturalPreservationContractV1"
    assert contract["workflow"] == WORKFLOW
    assert contract["source"]["sha256"] == _sha256(source["path"])
    assert contract["source"]["verified"] is True
    assert contract["requested_change"] == REQUEST_EN

    # The contract is carried into the instruction, not merely recorded.
    assert "ArchitecturalPreservationContractV1" in run["prompt"]


# ==========================================================
# B — invalid / unregistered source stays blocked
# ==========================================================


def test_B_cross_session_source_is_blocked_even_with_an_acceptance(
    tmp_path, isolated_project, acceptance_root, monkeypatch
):
    _write_acceptance(acceptance_root)

    foreign_path = tmp_path / "foreign.png"
    Image.new("RGB", SOURCE_SIZE, (140, 120, 100)).save(foreign_path)
    foreign = image_registry.register(
        "foreign-session",
        path=str(foreign_path),
        source_type="uploaded",
        make_active=True,
    )

    run = _run(monkeypatch, tmp_path, foreign, REQUEST_EN)

    assert run["result"]["type"] == "render_blocked"
    assert run["result"]["reason"] == "source_image_authority_mismatch"
    assert run["captured"]["executor_calls"] == 0


def test_B2_a_missing_file_is_not_an_authoritative_source(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    _write_acceptance(acceptance_root)

    source = _textured_source(tmp_path, isolated_project)
    os.unlink(source["path"])

    run = _run(monkeypatch, tmp_path, source, REQUEST_EN)

    assert run["result"]["type"] == "render_blocked"
    assert run["captured"]["executor_calls"] == 0


def test_B3_a_flat_placeholder_source_fails_integrity(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    """File identity is not visual quality — a black frame is refused."""

    _write_acceptance(acceptance_root)

    source = _flat_source(tmp_path, isolated_project)
    run = _run(monkeypatch, tmp_path, source, REQUEST_EN)

    assert run["result"]["type"] == "render_blocked"
    assert run["result"]["reason"] == "source_image_integrity_failed"
    assert run["captured"]["executor_calls"] == 0


# ==========================================================
# C — source / reference role isolation
# ==========================================================


def test_C_style_reference_cannot_become_the_target_building(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    """IMAGE A is appearance-only and must never be the geometry authority."""

    _write_acceptance(acceptance_root)

    reference = _textured_source(tmp_path, isolated_project, "style_ref.png")
    target = _textured_source(tmp_path, isolated_project, "target.png")

    context = {
        "references": {
            "A": {"path": reference["path"], "role": "style_reference"},
            "B": {"path": target["path"], "role": "target_building"},
        }
    }

    run = _run(monkeypatch, tmp_path, reference, REQUEST_EN, context)

    assert run["result"]["type"] == "render_blocked"
    assert run["result"]["reason"] == "source_image_role_conflict"
    assert run["captured"]["executor_calls"] == 0


def test_C2_the_target_building_is_still_admitted_alongside_a_reference(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    _write_acceptance(acceptance_root)

    reference = _textured_source(tmp_path, isolated_project, "style_ref.png")
    target = _textured_source(tmp_path, isolated_project, "target.png")

    context = {
        "references": {
            "A": {"path": reference["path"], "role": "style_reference"},
            "B": {"path": target["path"], "role": "target_building"},
        }
    }

    run = _run(monkeypatch, tmp_path, target, REQUEST_EN, context)

    _admitted(run)


# ==========================================================
# D — the user's own instruction survives
# ==========================================================


def test_D_user_instruction_reaches_the_model_instruction(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    _write_acceptance(acceptance_root)

    source = _textured_source(tmp_path, isolated_project)
    run = _run(monkeypatch, tmp_path, source, REQUEST_EN)

    _admitted(run)

    prompt = run["prompt"]
    lowered = prompt.lower()

    # The user's actual design request, verbatim.
    assert REQUEST_EN in prompt

    # …including the details the delta compiler drops.
    assert "dark metal window frames" in lowered
    assert "brick" in lowered
    assert "iranian" in lowered


def test_D2_the_user_request_is_not_replaced_by_a_classical_template(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    _write_acceptance(acceptance_root)

    source = _textured_source(tmp_path, isolated_project)
    run = _run(monkeypatch, tmp_path, source, REQUEST_EN)

    _admitted(run)

    lowered = run["prompt"].lower()

    # A brick + metal request must never become a stone/classical one.
    assert "limestone" not in lowered
    assert "travertine" not in lowered
    assert "bronze" not in lowered


# ==========================================================
# E — architectural invariants, no invented geometry
# ==========================================================


def test_E_prompt_preserves_observable_geometry_without_inventing_it(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    _write_acceptance(acceptance_root)

    source = _textured_source(tmp_path, isolated_project)
    run = _run(monkeypatch, tmp_path, source, REQUEST_EN)

    _admitted(run)

    prompt = run["prompt"]
    lowered = prompt.lower()

    for invariant in (
        "massing",
        "silhouette",
        "roofline",
        "windows",
        "doors",
        "balcon",
        "camera",
        "perspective",
        "floor",
    ):
        assert invariant in lowered, invariant

    # Unknown geometry is preserved as-is, never measured.
    assert re.search(r"\b\d+\s*(?:storey|storeys|story|stories|floors?)\b", lowered) is None
    assert re.search(r"\b\d+\s*(?:mm|cm|metres|meters|m)\b", lowered) is None

    # The contract states the policy explicitly.
    assert "not established" in lowered or "no measured" in lowered or (
        "unknown" in lowered
    )


# ==========================================================
# G — nothing unrelated changed
# ==========================================================


def test_G_text_to_image_route_is_unchanged():
    selector = WorkflowSelector()
    assert selector.select({"engine": "flux"}) == "flux.json"
    assert selector.select({"engine": "flux", "mode": "edit"}) == "flux_img2img.json"
    assert selector.select({"engine": "flux", "image": "x.png"}) == "flux_img2img.json"


def test_G2_non_architectural_edit_keeps_its_existing_route(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    """The guard's existing non-architectural pass-through is untouched."""

    source = _textured_source(tmp_path, isolated_project)
    run = _run(monkeypatch, tmp_path, source, "change the image colour to blue")

    _admitted(run)
    assert run["captured"]["workflow"] is not None


def test_G3_an_admitted_request_never_carries_a_mask(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    """The first controlled I2I acceptance is maskless by construction."""

    _write_acceptance(acceptance_root)

    source = _textured_source(tmp_path, isolated_project)
    run = _run(monkeypatch, tmp_path, source, REQUEST_EN)

    graph = _admitted(run)

    # No mask asset was supplied, so the compositing branch must be pruned:
    # the save node reads VAEDecode, never ImageCompositeMasked.
    save = [n for n in graph.values() if n.get("class_type") == "SaveImage"]
    assert len(save) == 1
    source_node = graph[str(save[0]["inputs"]["images"][0])]
    assert source_node["class_type"] == "VAEDecode"


# ==========================================================
# H — CPU end-to-end prepared payload
# ==========================================================


def test_H_prepared_payload_binds_the_exact_registered_source(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    _write_acceptance(acceptance_root)

    source = _textured_source(tmp_path, isolated_project)
    source_sha = _sha256(source["path"])

    run = _run(monkeypatch, tmp_path, source, REQUEST_EN)
    graph = _admitted(run)

    # LoadImage (300) carries a staged copy that is byte-identical.
    staged_name = graph["300"]["inputs"]["image"]
    staged_path = os.path.join(run["staging"], staged_name)

    assert os.path.isfile(staged_path)
    assert _sha256(staged_path) == source_sha

    # The reference latent is encoded FROM that source, not from an empty one.
    assert graph["301"]["class_type"] == "VAEEncode"
    assert graph["301"]["inputs"]["pixels"] == ["300", 0]
    assert graph["320"]["class_type"] == "ReferenceLatent"
    assert graph["320"]["inputs"]["latent"] == ["301", 0]

    # The empty latent is sized from the source, never the 384x512 template.
    assert graph["302"]["inputs"]["width"] == SOURCE_SIZE[0]
    assert graph["302"]["inputs"]["height"] == SOURCE_SIZE[1]

    # The sampler prompt is the prepared instruction, not the template.
    positive = graph["206"]["inputs"]["text"]
    assert REQUEST_EN in positive
    assert "massing" in positive.lower()

    # No GPU job: exactly one submission attempt, stopped at the boundary.
    assert run["captured"]["executor_calls"] == 1


def test_H2_the_source_asset_is_never_used_as_a_mask(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    """The near-black failure mode: one asset in LoadImage AND LoadImageMask."""

    _write_acceptance(acceptance_root)

    source = _textured_source(tmp_path, isolated_project)
    run = _run(monkeypatch, tmp_path, source, REQUEST_EN)

    graph = _admitted(run)

    load_images = {
        str((node.get("inputs") or {}).get("image") or "")
        for node in graph.values()
        if node.get("class_type") == "LoadImage"
    }

    load_masks = {
        str((node.get("inputs") or {}).get("image") or "")
        for node in graph.values()
        if node.get("class_type") == "LoadImageMask"
    }

    assert not (load_images & load_masks) - {""}


# ==========================================================
# I — the builder's own CHANGE statement (Part B, second owner)
# ==========================================================


def _builder_prompt(user_text, architectural_intent):
    from core.prompt_intelligence.prompt_router import PromptRouter

    return PromptRouter().build(
        {
            "prompt": user_text,
            "architectural_intent": architectural_intent,
        },
        mode="img2img",
    )["description"]


def test_I_builder_alone_carries_the_verbatim_user_request():
    """When the builder IS the instruction it must state the real request."""

    delta = {"edit_class": "style_change", "style": "modern", "prompt": ""}

    built = _builder_prompt(
        "Redesign this facade in modern Iranian brick with dark metal window "
        "frames.",
        {"building_type": "villa", "edit_delta": delta},
    )

    assert "REQUESTED CHANGE (verbatim user instruction, authoritative):" in built
    assert "dark metal window frames" in built


def test_I2_a_withheld_geometry_change_is_never_re_authorised():
    """A verbatim paste must not restore what the authority withheld."""

    resolved = {
        "contract": "ResolvedFacadeKnowledgeV1",
        "version": "1.0",
        "canonical_style": "neoclassical",
        "facade_language": {"composition": ["classical order"]},
        "composition": ["classical grid"],
        "symmetry": ["symmetrical composition"],
        "vertical_horizontal_emphasis": ["vertical emphasis"],
        "solid_void_strategy": ["solid void contrast"],
        "entrance_hierarchy": ["formal entry"],
        "opening_treatment": ["stone frames around openings"],
        "balcony_treatment": [],
        "parapet_treatment": ["strong horizontal cornice"],
        "architectural_elements": {"cornices": ["dentilled cornice"]},
        "materials": {"primary": ["light travertine stone"]},
        "surface_strategy": {"cladding": ["travertine"]},
        "user_facade_details": [],
        "unresolved": [],
    }

    built = _builder_prompt(
        "Add a triangular pediment; the roofline must stay unchanged",
        {
            "building_type": "villa",
            "normalized_prompt": (
                "Add a triangular pediment; the roofline must stay unchanged"
            ),
            "preserve_geometry": True,
            "preserve_constraints": ["roofline", "overall_massing"],
            "resolved_facade_knowledge": resolved,
        },
    )

    lowered = built.lower()

    # The authority withheld the pediment, so the raw sentence must not be
    # re-pasted as a REQUESTED CHANGE — that would authorise it again.
    assert "triangular pediment" not in lowered
    assert "needs clarification" in lowered
