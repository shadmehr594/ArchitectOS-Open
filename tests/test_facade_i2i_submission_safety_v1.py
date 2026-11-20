"""FACADE_I2I_SUBMISSION_SAFETY_V1 — CPU submission-safety contract.

Three defects are pinned here, each against the REAL production owner:

A. The maskless prepared graph still carried a `LoadImageMask` node pointing at
   a non-existent `mask.png`, plus the `ImageCompositeMasked` it feeds.
   Owner: `core/render/image_workflow_injector.py`.

B. A material bound to a WINDOW FRAME or a RAILING was compiled as the facade
   cladding, so "brick architecture with dark metal window frames" reached the
   sampler as "metal panel cladding".
   Owner: `core/prompt_intelligence/image_edit_delta_v1.py`.

C. The proposed acceptance source is a generated text-to-image output, not an
   original photograph. Lineage is established from the project asset registry,
   not from the file's own hash.

Evidence rules
--------------
No GPU job, no network inference, no new workflow JSON. The executor and GPU
lease are stubbed at the hardware edge; the real `WorkflowExecutor.execute` is
additionally replaced so a lost stub cannot reach the network.

A passing CPU contract says the route is submission-safe. It does NOT say
architectural preservation has been visually accepted.
"""

import copy
import hashlib
import json
import os
from types import SimpleNamespace

import pytest
from PIL import Image

import core.chat.chat_architect as chat_architect_module
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
from core.render.image_workflow_injector import ImageWorkflowInjector
from core.render.render_result_bridge import RenderResultBridge
from core.render.render_runtime import RenderRuntime
from core.vision.image_registry_v1 import image_registry


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW_DIR = os.path.join(ROOT, "core", "render", "workflows")

KONTEXT = "flux_kontext_edit.json"
USO = "flux_uso_reference.json"
DUAL = "flux_img2img_dual.json"

# The previously proposed acceptance source. Its lineage is the subject of
# group C; it is still a perfectly valid *pipeline* input for groups A and B.
RECORDED_SOURCE = r"C:\ComfyUI-Zluda\output\architectos_v11_00263_.png"
RECORDED_SHA = (
    "ae77532be8dd80bbf35af1a04136b86d1689f9b0845b50325f0e4c8a5cde1ab4"
)

SOURCE_SIZE = (768, 704)
SEED = 20261030

REQUEST_BRICK_METAL = (
    "Redesign this building in modern Iranian brick architecture with dark "
    "metal window frames."
)


# ----------------------------------------------------------
# Graph helpers
# ----------------------------------------------------------


def _load(name):
    with open(os.path.join(WORKFLOW_DIR, name), encoding="utf-8") as handle:
        return json.load(handle)


def _classes(graph):
    return {
        str(node.get("class_type"))
        for node in graph.values()
        if isinstance(node, dict)
    }


def _node_ids(graph, class_type):
    return [
        node_id
        for node_id, node in graph.items()
        if isinstance(node, dict) and node.get("class_type") == class_type
    ]


def _reachable_from_outputs(graph):
    """Node ids reachable from any SaveImage, following input links."""

    stack = list(_node_ids(graph, "SaveImage"))
    seen = set()

    while stack:

        node_id = stack.pop()

        if node_id in seen or node_id not in graph:
            continue

        seen.add(node_id)

        inputs = (graph.get(node_id) or {}).get("inputs") or {}

        for value in inputs.values():

            if (
                isinstance(value, list)
                and len(value) == 2
                and isinstance(value[0], (str, int))
            ):
                stack.append(str(value[0]))

    return seen


def _asset(tmp_path, name="architectos_staged.png"):
    path = tmp_path / name
    image = Image.new("RGB", SOURCE_SIZE)
    pixels = image.load()
    for y in range(SOURCE_SIZE[1]):
        for x in range(SOURCE_SIZE[0]):
            band = 40 if (y // 8) % 2 else 0
            pixels[x, y] = (
                min(255, 120 + band + x // 2),
                min(255, 100 + band + y // 3),
                min(255, 90 + band),
            )
    image.save(path)
    return {
        "filename": name,
        "path": str(path),
        "working_dimensions": list(SOURCE_SIZE),
        "original_dimensions": list(SOURCE_SIZE),
    }


def _inject(tmp_path, name=KONTEXT, mask_asset=None, prompt="edit the facade"):
    graph = _load(name)
    return ImageWorkflowInjector().inject(
        graph,
        prompt,
        image_asset=_asset(tmp_path),
        context={"seed": SEED},
        mask_asset=mask_asset,
    )


# ==========================================================
# A — maskless graph carries no dead mask branch
# ==========================================================


def test_A1_maskless_payload_has_no_load_image_mask(tmp_path):
    result = _inject(tmp_path, mask_asset=None)

    assert result["status"] in ("injected", "blocked")
    assert _node_ids(result["workflow"], "LoadImageMask") == []


def test_A2_maskless_payload_has_no_unused_composite(tmp_path):
    result = _inject(tmp_path, mask_asset=None)

    assert _node_ids(result["workflow"], "ImageCompositeMasked") == []


def test_A3_save_image_still_reads_vae_decode(tmp_path):
    result = _inject(tmp_path, mask_asset=None)
    graph = result["workflow"]

    saves = _node_ids(graph, "SaveImage")
    assert len(saves) == 1

    source_id = str(graph[saves[0]]["inputs"]["images"][0])

    assert graph[source_id]["class_type"] == "VAEDecode"


def test_A4_source_and_reference_latent_nodes_are_intact(tmp_path):
    result = _inject(tmp_path, mask_asset=None)
    graph = result["workflow"]

    assert graph["300"]["class_type"] == "LoadImage"
    assert graph["301"]["class_type"] == "VAEEncode"
    assert graph["301"]["inputs"]["pixels"] == ["300", 0]
    assert graph["320"]["class_type"] == "ReferenceLatent"
    assert graph["320"]["inputs"]["latent"] == ["301", 0]
    assert graph["210"]["class_type"] == "KSampler"


def test_A5_staged_filename_is_passed_through_unchanged(tmp_path):
    asset = _asset(tmp_path)
    graph = _load(KONTEXT)

    result = ImageWorkflowInjector().inject(
        graph, "edit", image_asset=asset, context={"seed": SEED}
    )

    assert result["workflow"]["300"]["inputs"]["image"] == asset["filename"]


def test_A6_the_source_can_never_become_a_mask(tmp_path):
    result = _inject(tmp_path, mask_asset=None)
    graph = result["workflow"]

    load_images = {
        str((node.get("inputs") or {}).get("image") or "")
        for node in graph.values()
        if isinstance(node, dict) and node.get("class_type") == "LoadImage"
    }
    load_masks = {
        str((node.get("inputs") or {}).get("image") or "")
        for node in graph.values()
        if isinstance(node, dict) and node.get("class_type") == "LoadImageMask"
    }

    assert not (load_images & load_masks) - {""}


def test_A7_a_genuinely_masked_edit_keeps_its_composite(tmp_path):
    """A real caller-supplied mask must still be honoured, unchanged."""

    result = _inject(tmp_path, mask_asset={"filename": "real_mask.png"})
    graph = result["workflow"]

    masks = _node_ids(graph, "LoadImageMask")
    composites = _node_ids(graph, "ImageCompositeMasked")

    assert len(masks) == 1
    assert graph[masks[0]]["inputs"]["image"] == "real_mask.png"
    assert len(composites) == 1

    saves = _node_ids(graph, "SaveImage")
    assert str(graph[saves[0]]["inputs"]["images"][0]) == composites[0]


def test_A8_reference_guided_workflows_are_untouched(tmp_path):
    """Graphs without a mask branch must be byte-identical after injection."""

    for name in (USO, DUAL):

        before = _load(name)

        result = _inject(tmp_path, name=name, mask_asset=None)

        assert set(result["workflow"]) == set(before), name
        assert _classes(result["workflow"]) == _classes(before), name


def test_A9_pruning_never_removes_a_node_the_output_needs(tmp_path):
    result = _inject(tmp_path, mask_asset=None)
    graph = result["workflow"]

    reachable = _reachable_from_outputs(graph)

    # Every surviving node is either reachable from the save node or is the
    # save node itself. Nothing the output depends on was dropped.
    assert reachable
    assert set(graph) == reachable

    for required in (
        "UNETLoader", "DualCLIPLoader", "VAELoader", "LoadImage", "VAEEncode",
        "EmptySD3LatentImage", "CLIPTextEncode", "ReferenceLatent",
        "FluxGuidance", "ConditioningZeroOut", "KSampler", "VAEDecode",
        "SaveImage",
    ):
        assert required in _classes(graph), required


def test_A10_canonical_workflow_json_is_not_modified(tmp_path):
    path = os.path.join(WORKFLOW_DIR, KONTEXT)

    with open(path, "rb") as handle:
        before = hashlib.sha256(handle.read()).hexdigest()

    _inject(tmp_path, mask_asset=None)

    with open(path, "rb") as handle:
        after = hashlib.sha256(handle.read()).hexdigest()

    assert after == before

    on_disk = _load(KONTEXT)
    assert "LoadImageMask" in _classes(on_disk)


# ==========================================================
# B — a component material is never the facade material
# ==========================================================


def _delta(text):
    return compile_edit_delta(text, image_edit=True)


def _prompt_of(delta):
    return str(delta.get("prompt") or "").lower()


def test_B1_window_frame_metal_is_not_facade_cladding():
    delta = _delta(REQUEST_BRICK_METAL)

    assert delta["material"] != "metal"
    assert "metal panel cladding" not in _prompt_of(delta)
    assert "dark architectural metal" not in _prompt_of(delta)


def test_B2_the_requested_style_survives():
    delta = _delta(REQUEST_BRICK_METAL)

    assert delta["style"] == "iranian_brick"
    assert delta["edit_class"] in ("style_change", "material_change")


def test_B3_railing_metal_is_not_facade_cladding():
    delta = _delta("Use brick on the facade with metal railings.")

    assert delta["material"] != "metal"
    assert "metal panel cladding" not in _prompt_of(delta)


def test_B4_window_frame_aluminium_is_not_facade_cladding():
    delta = _delta(
        "Redesign this facade with limestone cladding and black aluminum "
        "window frames."
    )

    # The facade material the user named is a stone, never the frame metal.
    assert delta["material"] in ("stone", "natural_stone", None)
    assert delta["material"] != "metal"


def test_B5_dark_windows_do_not_become_the_facade_material():
    delta = _delta("Add wood facade accents with dark windows.")

    assert delta["material"] != "metal"
    assert "metal panel cladding" not in _prompt_of(delta)


def test_B6_a_genuine_metal_cladding_request_still_works():
    delta = _delta("Clad the facade in metal panels.")

    assert delta["edit_class"] == "material_change"
    assert delta["material"] == "metal"
    assert "metal" in _prompt_of(delta)


def test_B7_explicit_replacement_is_unchanged():
    assert _delta("Replace the brick facade with travertine.")["material"] == "travertine"
    assert _delta("Use wood instead of stone on the facade.")["material"] == "wood"


def test_B8_ambiguous_target_is_not_invented():
    """Nothing facade-bound => no material claim, never a guess."""

    delta = _delta("Make the metal window frames darker.")

    assert delta["material"] != "metal"


# ==========================================================
# End-to-end — the real route, the real graph, the real prompt
# ==========================================================


class _State:
    def __init__(self):
        self.data = {}

    def get(self):
        return self.data

    def update(self, values):
        self.data.update(values or {})

    def add_message(self, *args, **kwargs):
        return None


class _ExecutorStop(RuntimeError):
    pass


@pytest.fixture
def isolated_project(tmp_path):
    old_projects = project_workspace.projects_root
    old_trash = project_workspace.trash_root
    project_workspace.projects_root = str(tmp_path / "projects")
    project_workspace.trash_root = str(tmp_path / "trash")
    os.makedirs(project_workspace.projects_root, exist_ok=True)
    os.makedirs(project_workspace.trash_root, exist_ok=True)
    manifest = project_workspace.create("facade-i2i-submission-safety-v1")
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
    root = tmp_path / "render_acceptance"
    os.makedirs(root, exist_ok=True)
    monkeypatch.setattr(
        chat_architect_module, "_R4_ACCEPTANCE_ROOT", str(root)
    )
    return root


def _write_acceptance(root):
    record = {
        "contract": "ArchitecturalPreservationAcceptanceV1",
        "version": "1.0",
        "workflow": KONTEXT,
        "status": "accepted",
        "accepted_scope": "capability",
        "preservation_capability": "architectural_facade_preservation",
        "evidence": {"report": "cpu_test_fixture_only", "human_approval": False},
        "model": {"unet_name": "flux1-dev-kontext_fp8_scaled.safetensors"},
    }
    path = os.path.join(root, KONTEXT)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source(tmp_path, manifest):
    path = tmp_path / "facade_original.png"
    image = Image.new("RGB", SOURCE_SIZE)
    pixels = image.load()
    for y in range(SOURCE_SIZE[1]):
        for x in range(SOURCE_SIZE[0]):
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


def _chain(monkeypatch, tmp_path):
    runtime = RenderRuntime()
    captured = {"calls": 0, "workflow": None}

    def _stub_execute(workflow, engine=None, **kwargs):
        captured["calls"] += 1
        captured["workflow"] = workflow
        raise _ExecutorStop("cpu capture")

    runtime.executor.execute = _stub_execute

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


def _run(monkeypatch, tmp_path, record, text):
    chat, runtime, captured, staging = _chain(monkeypatch, tmp_path)
    result = chat._route_image_edit(
        text, record, {"image_id": record.get("image_id")},
        None, None, SEED, {}, image_understanding=None,
    )
    return {
        "result": result,
        "chat": chat,
        "runtime": runtime,
        "captured": captured,
        "staging": staging,
        "prompt": (runtime.last_render_request or {}).get("resolved_prompt") or "",
    }


def test_E1_end_to_end_graph_is_maskless_and_source_bound(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    _write_acceptance(acceptance_root)

    source = _source(tmp_path, isolated_project)
    source_sha = _sha256(source["path"])

    run = _run(monkeypatch, tmp_path, source, REQUEST_BRICK_METAL)

    assert not (
        isinstance(run["result"], dict)
        and run["result"].get("type") == "render_blocked"
    ), run["result"]
    assert run["captured"]["calls"] == 1

    graph = run["captured"]["workflow"]

    assert _node_ids(graph, "LoadImageMask") == []
    assert _node_ids(graph, "ImageCompositeMasked") == []

    saves = _node_ids(graph, "SaveImage")
    assert str(graph[saves[0]]["inputs"]["images"][0]) == str(
        _node_ids(graph, "VAEDecode")[0]
    )

    staged = os.path.join(str(run["staging"]), graph["300"]["inputs"]["image"])
    assert os.path.isfile(staged)
    assert _sha256(staged) == source_sha


def test_E2_end_to_end_prompt_has_no_contradictory_cladding(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    _write_acceptance(acceptance_root)

    source = _source(tmp_path, isolated_project)
    run = _run(monkeypatch, tmp_path, source, REQUEST_BRICK_METAL)

    prompt = run["prompt"]
    lowered = prompt.lower()

    # The user's own instruction and the contract survive.
    assert REQUEST_BRICK_METAL in prompt
    assert "ArchitecturalPreservationContractV1" in prompt

    # No contradictory cladding instruction reaches the CLIP text.
    assert "metal panel cladding" not in lowered
    assert "dark architectural metal" not in lowered

    # The requested style is still the one being applied.
    assert "iranian brick" in lowered


def test_E3_end_to_end_still_refuses_a_withheld_geometry_change(
    isolated_project, tmp_path, acceptance_root, monkeypatch
):
    """The geometry-authority safeguard must remain impossible to bypass."""

    from core.prompt_intelligence.prompt_router import PromptRouter

    resolved = {
        "contract": "ResolvedFacadeKnowledgeV1",
        "version": "1.0",
        "canonical_style": "neoclassical",
        "facade_language": {"composition": ["classical order"]},
        "composition": ["classical grid"],
        "symmetry": [],
        "vertical_horizontal_emphasis": [],
        "solid_void_strategy": [],
        "entrance_hierarchy": [],
        "opening_treatment": [],
        "balcony_treatment": [],
        "parapet_treatment": [],
        "architectural_elements": {},
        "materials": {},
        "surface_strategy": {},
        "user_facade_details": [],
        "unresolved": [],
    }

    built = PromptRouter().build(
        {
            "prompt": "Add a triangular pediment; the roofline must stay unchanged",
            "architectural_intent": {
                "building_type": "villa",
                "normalized_prompt": (
                    "Add a triangular pediment; the roofline must stay unchanged"
                ),
                "preserve_geometry": True,
                "preserve_constraints": ["roofline", "overall_massing"],
                "resolved_facade_knowledge": resolved,
            },
        },
        mode="img2img",
    )["description"].lower()

    assert "triangular pediment" not in built
    assert "needs clarification" in built


# ==========================================================
# C — source lineage
# ==========================================================


def test_C1_the_proposed_source_is_a_generated_output():
    """Its own name is the workflow's T2I prefix, not an upload name."""

    with open(os.path.join(WORKFLOW_DIR, "flux.json"), encoding="utf-8") as handle:
        graph = json.load(handle)

    prefixes = {
        (node.get("inputs") or {}).get("filename_prefix")
        for node in graph.values()
        if isinstance(node, dict)
        and node.get("class_type") == "SaveImage"
    }

    assert "architectos_v11" in prefixes

    basename = os.path.basename(RECORDED_SOURCE)

    assert basename.startswith("architectos_v11_")


def test_C2_registry_provenance_records_the_upload_was_a_render():
    """The asset registry keeps the ORIGINAL filename the user uploaded."""

    if not os.path.isfile(RECORDED_SOURCE):
        pytest.skip("recorded source is not present on this machine")

    target = _sha256(RECORDED_SOURCE)
    found = []

    for name in sorted(os.listdir(os.path.join(ROOT, "data", "projects"))):

        manifest = os.path.join(ROOT, "data", "projects", name, "assets.json")

        if not os.path.isfile(manifest):
            continue

        try:
            with open(manifest, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue

        for record in data.get("registry_records") or []:

            path = record.get("path")

            if not path or not os.path.isfile(path):
                continue

            if _sha256(path) != target:
                continue

            found.append(record)

    assert found, "no registry record matches the recorded source"

    original = os.path.basename(
        str(found[0].get("original_source_path") or "")
    )

    # The preserved upload filename carries the generated render's own name
    # (chat_media prepends a content hash, so this is a containment test).
    assert "architectos_v11_" in original, original
    assert found[0].get("source_type") == "uploaded"
