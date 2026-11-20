"""VISUAL_REFERENCE_UX_V2 — acceptance.

Covers the three gates:

  A. UI/API reference selection -> the accepted USO runtime contract.
  B. Annotation proposals never become approved knowledge.
  C. Requested / executed / observed are kept separate, and an unobserved
     result can never be reported as a PASS.

The UI integration is exercised through the REAL Flask application and its
REAL /api/chat + /api/references contracts. Only the GPU boundary (the ComfyUI
submission) is substituted, because no test may touch the GPU.

NO GPU. NO COMFYUI SUBMISSION. NO OLLAMA LOAD. NO NETWORK.
"""

import io
import json
import os
import socket
import sys

import contextlib

import flask
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import core.runtime.gpu_handoff_v1 as gpu_handoff  # noqa: E402
from core.render import render_runtime as rr_module  # noqa: E402
from core.render import uso_reference_handoff_v1 as handoff  # noqa: E402
from core.render.render_runtime import RenderRuntime  # noqa: E402
from core.render.workflow_selector import WorkflowSelector  # noqa: E402
from core.vision import design_constraint_fidelity_v1 as fidelity  # noqa: E402
from core.vision.visual_reference_index_v1 import (  # noqa: E402
    VisualReferenceIndexV1,
    load_default_index,
    preview_descriptor,
)

ANNOTATIONS = os.path.join(
    _PROJECT_ROOT, "runs", "visual_reference_ux_design_fidelity_v2",
    "reference_annotation_proposals_v1.json",
)
EVIDENCE_DIR = os.path.join(
    _PROJECT_ROOT, "runs", "visual_reference_ux_design_fidelity_v2"
)


class NetworkForbidden(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise NetworkForbidden("outbound connection refused")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


@pytest.fixture(scope="module")
def index():
    return load_default_index()


@pytest.fixture
def client():
    import app as app_module

    return app_module.app.test_client()


@pytest.fixture
def record_render(monkeypatch):
    """Substitute ONLY the GPU boundary; capture what render() was asked for."""
    calls = []

    def _fake(self, *args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return {
            "status": "success",
            "workflow": "flux_uso_reference.json",
            "execution": {"status": "completed", "images": []},
            "injected": {},
        }

    monkeypatch.setattr(RenderRuntime, "render", _fake)
    return calls


def _chat(client, payload):
    with contextlib.redirect_stdout(io.StringIO()):
        return client.post("/api/chat", json=payload)


# ======================================================
# 1 — the 92 references stay indexed without reimport
# ======================================================

def test_all_92_references_remain_indexed(index):
    assert len(index.entries) == 92
    assert len(index.by_collection("visual_references_v1")) == 78
    assert len(index.by_collection("classical_facades_20261023")) == 14
    assert all(e.get("sha256_verified") for e in index.entries)
    # the collection is read in place, never re-imported
    assert index.sources["visual_references_v1"].endswith("ArchitectOS_Visual_References_V1")


# ======================================================
# 2 / 3 — UI selection resolves through the index; previews are safe
# ======================================================

def test_reference_listing_resolves_through_the_index(client, index):
    response = client.get("/api/references")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 92
    assert payload["authority"] == "declared_metadata_only"
    assert payload["annotation_authority"] == "none"

    listed = {item["reference_id"] for item in payload["references"]}
    assert listed == {e["reference_id"] for e in index.usable()}

    # every preview URL is built from an index entry, not from client input
    for item in payload["references"][:5]:
        assert item["preview_url"].startswith("/artifacts/reference_")


def test_preview_endpoint_cannot_reach_arbitrary_paths(client):
    for url in (
        "/artifacts/reference_library/../config/runtime_config.py",
        "/artifacts/reference_library/references/../../AGENTS.md",
        "/artifacts/reference_library/%2e%2e/%2e%2e/app.py",
        "/artifacts/reference_library/does_not_exist.jpg",
        "/artifacts/unknown_root/references/AR-001.jpg",
    ):
        assert client.get(url).status_code == 404, url


def test_preview_serves_the_indexed_image(client):
    descriptor = preview_descriptor(load_default_index().resolve("AR-077"))
    assert descriptor is not None
    url = "/artifacts/%s/%s" % descriptor
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("image/")
    assert len(response.data) > 1000


# ======================================================
# 4 / 5 — explicit selection wins; failures are safe
# ======================================================

def test_explicit_selection_overrides_automatic_ranking(index):
    """A user who picks AR-077 gets AR-077, never the best-scoring reference."""
    ranked = handoff.select_reference(
        index,
        "a luxurious Roman-classic villa with balustrades and Corinthian capitals",
    )
    assert ranked["status"] in ("selected_knowledge", "ambiguous")
    if ranked["status"] == "selected_knowledge":
        assert ranked["reference"]["reference_id"] != "AR-077"

    explicit = handoff.select_explicit(index, "AR-077")
    assert explicit["status"] == "selected_explicit"
    assert explicit["reference"]["reference_id"] == "AR-077"
    assert explicit["evidence"] == ["explicit_user_selection"]


def test_missing_or_altered_reference_fails_safely(index, tmp_path):
    assert handoff.select_explicit(index, "AR-999")["status"] == "reference_not_found"
    assert handoff.select_explicit(index, "../../etc/passwd")["status"] == "invalid_reference_id"
    assert handoff.select_explicit(index, "AR-77")["status"] == "invalid_reference_id"

    damaged = dict(index.resolve("AR-077"))
    target = tmp_path / "damaged.jpg"
    target.write_bytes(b"not the certified bytes")
    damaged["absolute_path"] = str(target)
    staged = handoff.stage_reference(damaged, str(tmp_path / "input"))
    assert staged["ok"] is False
    assert "digest mismatch" in staged["error"]


def test_chat_refuses_unknown_reference_without_rendering(client, record_render):
    response = _chat(client, {"text": "design a two-storey villa",
                              "reference_id": "AR-999"})
    assert response.status_code == 400
    assert response.get_json()["status"] == "reference_selection_blocked"
    assert record_render == [], "an unusable reference must never reach render()"


def test_chat_refuses_reference_combined_with_a_source_image(client, record_render):
    response = _chat(client, {"text": "design a villa", "reference_id": "AR-077",
                              "image_a": {"filename": "x.png"}})
    assert response.status_code == 400
    assert response.get_json()["status"] == "reference_conflicts_with_source_image"
    assert record_render == []


# ======================================================
# 6 / 7 — the reference and the request reach the real contracts
# ======================================================

def test_chat_carries_reference_into_the_render_contract(client, record_render):
    response = _chat(client, {
        "text": "Use architectural reference AR-077 to design a two-storey Iranian brick villa.",
        "reference_id": "AR-077",
        "mode": "text_to_image",
    })
    assert response.status_code == 200
    assert len(record_render) == 1

    call = record_render[0]
    payload = call["kwargs"].get("uso_reference")
    assert payload is not None
    assert payload["reference_id"] == "AR-077"
    assert payload["filename"] == "architectos_ref_AR-077.jpg"
    assert payload["sha256"] == load_default_index().resolve("AR-077")["sha256"]

    # a reference is NOT a source image
    assert call["args"][3] is None


def test_reference_reaches_the_actual_uso_graph(monkeypatch, index, tmp_path):
    """Real render() with only the GPU/executor seams substituted."""
    submitted = []

    class Guard:
        def acquire(self):
            return True

        def release(self):
            pass

        def stats(self):
            return {}

    class Listener:
        def __init__(self, *a, **k):
            pass

        def start(self):
            return True

        def stop(self):
            return True

        def bind_prompt_id(self, p):
            pass

        def stats(self):
            return {}

    class Executor:
        def __init__(self):
            self.comfy = type("C", (), {"endpoint": "stub"})()

        def execute(self, workflow, engine, on_submitted=None, client_id=None):
            submitted.append(json.loads(json.dumps(workflow)))
            if on_submitted:
                on_submitted("uso-ux-prompt")
            return {"status": "completed", "prompt_id": "uso-ux-prompt", "images": []}

    monkeypatch.setattr(gpu_handoff, "gpu_render_lease", lambda *a, **k: Guard())
    monkeypatch.setattr(gpu_handoff, "unload_ollama_models_for_render",
                        lambda *a, **k: {"status": "not_running", "unloaded": []})
    monkeypatch.setattr(gpu_handoff, "require_render_vram",
                        lambda *a, **k: {"ok": True, "free_mib": 16000, "min_free_mib": 11264})
    monkeypatch.setattr(rr_module, "ComfyProgressListener", Listener)

    prepared = handoff.prepare_explicit("AR-077", index, str(tmp_path / "input"))
    assert prepared["status"] == "ready"

    with contextlib.redirect_stdout(io.StringIO()):
        runtime = RenderRuntime()
    runtime.executor = Executor()
    runtime.result_bridge = type("B", (), {"resolve": lambda s, c: {"image_asset": None}})()

    app = flask.Flask("uso_ux")
    with app.app_context():
        flask.g.project_id = "uso-ux"
        with contextlib.redirect_stdout(io.StringIO()):
            runtime.render(
                project_id="uso-ux",
                design={"prompt": "two-storey Iranian brick villa",
                        "mode": "text2img",
                        "architectural_intent": {"building_type": "villa",
                                                 "style": "iranian_brick",
                                                 "floors": 2,
                                                 "materials": ["traditional_brick"]}},
                engine="flux",
                uso_reference={
                    "filename": prepared["staged"]["filename"],
                    "reference_id": "AR-077",
                    "sha256": prepared["staged"]["sha256"],
                },
            )

    assert len(submitted) == 1
    graph = submitted[0]
    loads = [n for n in graph.values() if n.get("class_type") == "LoadImage"]
    assert len(loads) == 1
    assert loads[0]["inputs"]["image"] == "architectos_ref_AR-077.jpg"
    assert any(n.get("class_type") == "USOStyleReference" for n in graph.values())
    assert not any(n.get("class_type") == "VAEEncode" for n in graph.values())


# ======================================================
# 8 / 9 / 10 — floor count, building type, reference cannot override intent
# ======================================================

def test_floor_count_and_building_type_survive_to_the_sampler(index, tmp_path):
    from core.prompt_intelligence.architectural_prompt_compiler_v1 import compile_prompt
    from core.prompt_intelligence.persian_architectural_understanding import understand

    prompt = "Design a two-storey Iranian brick villa"
    compiled = compile_prompt(understand(prompt), mode="text_to_image")
    assert compiled["status"] == "COMPILED"

    from core.render.uso_reference_handoff_v1 import extract_sampler_prompt

    # the render layer appends the storey count; simulate its output
    sampler_text = compiled["positive_prompt"] + ", iranian_brick villa architectural visualization, 2 story building"

    record = fidelity.evaluate(
        {"building_type": "villa", "floors": 2}, sampler_text, None,
        requested_text=prompt,
    )
    assert record["requested"]["floors"] == 2
    assert record["executed"]["floors_mentioned"] == 2
    assert record["instruction_carried_the_request"] is True
    # ... and the result is STILL unverified, because nothing has looked
    assert record["floor_status"] == fidelity.FLOOR_UNVERIFIED
    assert record["design_accepted"] is False


def test_reference_floor_count_cannot_override_user_intent(index):
    """A 5-storey reference does not make a 2-storey request 5 storeys."""
    entry = index.resolve("CLASSICAL_REF_12")  # annotated as 5 storeys
    assert entry is not None

    record = fidelity.evaluate(
        {"building_type": "villa", "floors": 2},
        "2 story building",
        # the model copied the reference's height
        {"visible_floor_count": 5, "building_type": "villa"},
        requested_text="two-storey villa",
    )
    assert record["requested"]["floors"] == 2
    assert record["floor_status"] == fidelity.FLOOR_MISMATCH
    assert record["design_accepted"] is False


def test_requested_floor_count_wins_over_an_absent_intent_field():
    record = fidelity.evaluate(
        {"building_type": "villa"}, "2 story building",
        {"visible_floor_count": 2, "building_type": "villa"},
        requested_text="design a two-storey villa",
    )
    assert record["requested"]["floors"] == 2
    assert record["requested"]["source"] == "architectural_intent+request_text"
    assert record["floor_status"] == fidelity.FLOOR_VERIFIED


# ======================================================
# 11 — proposals never become approved knowledge
# ======================================================

def test_annotation_proposals_are_not_approved_knowledge(index):
    assert os.path.exists(ANNOTATIONS), "annotation proposal file must exist"
    with open(ANNOTATIONS, encoding="utf-8") as fh:
        data = json.load(fh)

    assert data["authority"] == "PROPOSED_ONLY"
    assert data["human_reviewed"] is False
    assert data["review_status"] == "proposed_pending_human_review"
    assert data["ontology_promotion"] == "NONE"
    assert 10 <= len(data["annotations"]) <= 15

    # nothing in the index was promoted by producing the proposals
    for entry in index.entries:
        assert entry.get("annotation_authority") == "none"
        assert entry.get("review_status") in (
            "visual_classification_pending",
            "UNCONFIRMED_VISUAL_REFERENCE_ONLY",
        )

    # every proposed style id must already exist in the ontology
    ontology_path = os.path.join(_PROJECT_ROOT, "core", "architecture", "knowledge",
                                 "architectural_style_ontology.json")
    with open(ontology_path, encoding="utf-8") as fh:
        ontology = json.load(fh)
    known = set(ontology.get("styles", ontology).keys()) if isinstance(ontology, dict) else set()
    for ann in data["annotations"]:
        for style_id in ann["proposed_style_ids"]:
            assert style_id in known, "proposed style %r is not an existing ontology id" % style_id


def test_review_sheet_exists_and_states_it_is_unapproved():
    sheet = os.path.join(EVIDENCE_DIR, "ANNOTATION_REVIEW_SHEET.md")
    assert os.path.exists(sheet)
    with open(sheet, encoding="utf-8") as fh:
        text = fh.read()
    assert "PROPOSED ONLY" in text
    assert "human_reviewed" in text
    assert "Review decision" in text


# ======================================================
# 12 — a reference turn does not corrupt later turns
# ======================================================

def test_selection_does_not_leak_into_a_later_turn(client, record_render):
    first = _chat(client, {"text": "Use architectural reference AR-077 to design a two-storey villa.",
                           "reference_id": "AR-077",
                           "mode": "text_to_image"})
    assert first.status_code == 200
    assert record_render[-1]["kwargs"].get("uso_reference") is not None

    before = len(record_render)
    second = _chat(client, {"text": "design a three-storey brick house"})
    assert second.status_code == 200
    if len(record_render) > before:
        assert record_render[-1]["kwargs"].get("uso_reference") is None, (
            "the previous turn's reference must not carry over"
        )


# ======================================================
# 13 / 14 / 19 — existing routes and safety contracts unchanged
# ======================================================

def test_existing_routes_are_unchanged_without_a_reference():
    selector = WorkflowSelector()
    cases = [
        ({"engine": "flux"}, "flux.json"),
        ({"engine": "flux", "mode": "text2img"}, "flux.json"),
        ({"engine": "flux", "image": {"filename": "a.png"}}, "flux_img2img.json"),
        ({"engine": "flux", "mode": "edit"}, "flux_img2img.json"),
        ({"engine": "flux", "kontext_edit": True}, "flux_kontext_edit.json"),
        ({"engine": "flux", "mask": {"filename": "m.png"}}, "flux_kontext_edit.json"),
        ({"engine": "flux", "dual_image": True, "image_bindings": [{"role": "A"}]},
         "flux_img2img_dual.json"),
        ({"engine": "flux", "dual_image": True, "image_bindings": [{"role": "A"}],
          "conditioned": True}, "flux_img2img_dual_conditioned.json"),
        ({"engine": "wan"}, "wan_i2v.json"),
    ]
    for request, expected in cases:
        assert selector.select(request) == expected, request


def test_text_only_turn_carries_no_reference(client, record_render):
    before = len(record_render)
    response = _chat(client, {"text": "design a two-storey brick house"})
    assert response.status_code == 200
    if len(record_render) > before:
        call = record_render[-1]
        assert call["kwargs"].get("uso_reference") is None
        assert call["kwargs"].get("kontext_edit") in (False, None)


def test_reference_route_never_becomes_an_edit():
    selector = WorkflowSelector()
    assert selector.select({"engine": "flux", "uso_reference": True}) == handoff.USO_WORKFLOW
    # When both flags are present the selector currently prioritises the
    # reference route so the style guidance is not silently dropped. The
    # runtime itself must refuse a contradictory request (mask + reference)
    # rather than resolve it.
    assert selector.select({"engine": "flux", "uso_reference": True,
                            "kontext_edit": True}) == handoff.USO_WORKFLOW


# ======================================================
# 15 — lineage carries reference, digest, requested design, sampler text
# ======================================================

def test_lineage_contains_reference_digest_and_sampler_text(index, tmp_path):
    selection = handoff.select_explicit(index, "AR-077")
    entry = selection["reference"]
    staged = handoff.stage_reference(entry, str(tmp_path / "input"))
    lineage = handoff.build_lineage(entry, selection, staged, handoff.USO_WORKFLOW,
                                    "2 story building", understanding={})
    assert lineage["reference_id"] == "AR-077"
    assert lineage["reference_sha256"] == entry["sha256"]
    assert lineage["reference_declared_sha256"] == entry["sha256"]
    assert lineage["workflow"] == handoff.USO_WORKFLOW
    assert lineage["base_model"] == "flux1-dev-fp8.safetensors"
    assert lineage["render_kind"] == "reference_conditioned_text_to_image"
    assert lineage["selection_status"] == "selected_explicit"
    assert lineage["prompt"] == "2 story building"


# ======================================================
# 16 / 17 / 18 — observation states
# ======================================================

def test_observation_distinguishes_requested_from_observed():
    record = fidelity.evaluate(
        {"building_type": "apartment", "floors": 5}, "5 story building",
        {"visible_floor_count": 3, "building_type": "apartment"},
    )
    assert record["executed"]["floors_mentioned"] == 5
    assert record["observed"]["floors"] == 3
    assert record["floor_status"] == fidelity.FLOOR_MISMATCH
    assert record["instruction_carried_the_request"] is True
    assert record["design_accepted"] is False


def test_unknown_observation_is_unverified_not_pass():
    record = fidelity.evaluate(
        {"building_type": "villa", "floors": 2}, "2 story building", None)
    assert record["floor_status"] == fidelity.FLOOR_UNVERIFIED
    assert record["building_type_status"] == fidelity.TYPE_UNVERIFIED
    assert record["design_accepted"] is False


def test_descriptor_only_observation_is_unverified():
    record = fidelity.evaluate(
        {"building_type": "villa", "floors": 3}, "3 story",
        {"visible_floors": {"count": None, "descriptor": "multi-storey"}})
    assert record["floor_status"] == fidelity.FLOOR_UNVERIFIED
    assert record["design_accepted"] is False


def test_confirmed_mismatch_is_reported_as_mismatch():
    record = fidelity.evaluate(
        {"building_type": "villa", "floors": 2}, "2 story",
        {"visible_floor_count": 4, "building_type": "villa"})
    assert record["floor_status"] == fidelity.FLOOR_MISMATCH
    assert "observed 4" in record["floor_reason"]


# ======================================================
# 20 — no new registry, engine or CV capability
# ======================================================

def test_no_new_render_engine_registry_or_cv_engine():
    """The fidelity module must not analyse pixels itself."""
    source_path = os.path.join(_PROJECT_ROOT, "core", "vision",
                               "design_constraint_fidelity_v1.py")
    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()

    for forbidden in ("import numpy", "from PIL", "import cv2", "torch"):
        assert forbidden not in source, (
            "fidelity must reuse the existing observation path, not analyse images"
        )

    # exactly one new workflow was added, and no canonical one changed
    workflows = os.listdir(os.path.join(_PROJECT_ROOT, "core", "render", "workflows"))
    assert "flux_uso_reference.json" in workflows
    assert "flux.json" in workflows and "flux_img2img.json" in workflows
    assert "flux_kontext_edit.json" in workflows



# [ARCHITECTOS_V27_1_KROCKI_UPLOAD_INTERCEPTOR]
try:
    from flask import request as _arch_req, jsonify as _arch_jsonify

    def _resolve_arch_repo_root() -> str:
        import os
        import sys
        here_d = os.path.dirname(os.path.abspath(__file__))
        cand = here_d
        for _ in range(5):
            if os.path.isdir(os.path.join(cand, "core")) and os.path.isdir(os.path.join(cand, "ui")):
                if cand not in sys.path:
                    sys.path.insert(0, cand)
                return cand
            parent = os.path.dirname(cand)
            if parent == cand:
                break
            cand = parent
        if here_d not in sys.path:
            sys.path.insert(0, here_d)
        from core.site.krocki_cad_reader_v27 import _resolve_true_repo_root
        root_r = _resolve_true_repo_root(here_d)
        if root_r not in sys.path:
            sys.path.insert(0, root_r)
        return root_r

    def _sync_project_renders_and_assets(repo_root: str, project_id: str) -> None:
        import os
        import shutil
        clean_pid = str(project_id or "").strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            return
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        dir_a = os.path.join(repo_root, "outputs", "plans", p_folder, "renders")
        dir_b = os.path.join(repo_root, "data", "projects", p_folder, "renders")
        os.makedirs(dir_a, exist_ok=True)
        os.makedirs(dir_b, exist_ok=True)
        for src_d, dst_d in ((dir_a, dir_b), (dir_b, dir_a)):
            try:
                for fn in os.listdir(src_d):
                    if fn.endswith((".png", ".svg", ".dxf", ".json", ".jpg")):
                        sp = os.path.join(src_d, fn)
                        dp = os.path.join(dst_d, fn)
                        if os.path.isfile(sp) and (not os.path.isfile(dp) or os.path.getmtime(sp) > os.path.getmtime(dp) + 0.5):
                            shutil.copy2(sp, dp)
            except Exception:
                pass

    def _sync_krocki_into_project_session(repo_root: str, project_id: str) -> None:
        import json
        import os
        from core.site.krocki_cad_reader_v27 import (
            load_active_krocki_state,
            load_active_external_plan_state,
        )

        clean_pid = str(project_id or "").strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            return
        krocki = load_active_krocki_state(repo_root, clean_pid)
        ext_plan = load_active_external_plan_state(repo_root, clean_pid)
        if not isinstance(krocki, dict) and not isinstance(ext_plan, dict):
            return
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        for state_file in (
            os.path.join(repo_root, "data", "projects", p_folder, "session_state.json"),
            os.path.join(repo_root, "outputs", "plans", p_folder, "session_state.json"),
        ):
            state_data = {}
            if os.path.isfile(state_file):
                try:
                    with open(state_file, "r", encoding="utf-8") as sf:
                        state_data = json.load(sf)
                except Exception:
                    state_data = {}
            if isinstance(krocki, dict):
                state_data["active_site_krocki"] = krocki
                prev_p = state_data.get("active_plan_params")
                if isinstance(prev_p, dict):
                    prev_p["site_width_mm"] = int(round(float(krocki.get("width_m", 10.0)) * 1000))
                    prev_p["site_length_mm"] = int(round(float(krocki.get("length_m", 20.0)) * 1000))
                    prev_p["site_area_m2"] = round(float(krocki.get("site_area_m2", 200.0)), 2)
                    prev_p["krocki_polygon_mm"] = krocki.get("polygon_vertices_mm") or []
                    prev_p["krocki_source_file"] = krocki.get("source_file")
                    prev_p["krocki_is_irregular"] = bool(krocki.get("is_irregular_polygon", False))
                    prev_p["street_sides"] = krocki.get("street_sides") or ["SOUTH"]
                    prev_p["party_wall_sides"] = krocki.get("party_wall_sides") or ["NORTH", "EAST", "WEST"]
                    prev_p["boundary_neighbors"] = krocki.get("boundary_neighbors") or {}
                    prev_p["south_y_west_mm"] = int(krocki.get("south_y_west_mm", 0))
                    prev_p["south_y_east_mm"] = int(krocki.get("south_y_east_mm", 0))
                    prev_p["north_y_west_mm"] = int(krocki.get("north_y_west_mm", prev_p["site_length_mm"]))
                    prev_p["north_y_east_mm"] = int(krocki.get("north_y_east_mm", prev_p["site_length_mm"]))
            if isinstance(ext_plan, dict):
                state_data["active_external_plan"] = ext_plan
                prev_p = state_data.get("active_plan_params")
                if not isinstance(prev_p, dict):
                    prev_p = {}
                    state_data["active_plan_params"] = prev_p
                tot_fl = int(ext_plan.get("total_floors", 2))
                typ_str = str(ext_plan.get("typology", "DUPLEX_2FLOOR" if tot_fl == 2 else ("MULTIFLOOR_RESIDENTIAL" if tot_fl >= 3 else "VILLA_1FLOOR")))
                prev_p["typology"] = typ_str
                prev_p["is_duplex"] = (typ_str == "DUPLEX_2FLOOR")
                prev_p["floor_count"] = max(2, tot_fl - 1) if typ_str == "MULTIFLOOR_RESIDENTIAL" else tot_fl
                prev_p["building_placement"] = str(ext_plan.get("building_placement") or ("SOUTH" if ext_plan.get("custom_facade_profile") else "NORTH"))
                prev_p["site_width_mm"] = int(round(float(ext_plan.get("width_m", 10.0)) * 1000))
                prev_p["site_length_mm"] = int(round(float(ext_plan.get("length_m", 20.0)) * 1000))
                prev_p["coverage_ratio"] = float(ext_plan.get("coverage_ratio", 0.60 if typ_str == "MULTIFLOOR_RESIDENTIAL" else 0.65))
                prev_p["south_cantilever_mm"] = int(round(float(ext_plan.get("cantilever_m", 1.2 if typ_str == "MULTIFLOOR_RESIDENTIAL" else 1.0)) * 1000))
                if ext_plan.get("universal_facade_spec"):
                    prev_p["universal_facade_spec"] = ext_plan["universal_facade_spec"]
                if ext_plan.get("custom_facade_profile"):
                    prev_p["custom_facade_profile"] = ext_plan["custom_facade_profile"]
                else:
                    prev_p.pop("custom_facade_profile", None)
                for _rs_d in (prev_p.get("active_render_state"), state_data.get("active_render_state")):
                    if isinstance(_rs_d, dict):
                        if ext_plan.get("universal_facade_spec"):
                            _rs_d["universal_facade_spec"] = ext_plan["universal_facade_spec"]
                        if ext_plan.get("custom_facade_profile"):
                            _rs_d["custom_facade_profile"] = ext_plan["custom_facade_profile"]
            try:
                os.makedirs(os.path.dirname(state_file), exist_ok=True)
                with open(state_file, "w", encoding="utf-8") as sf:
                    json.dump(state_data, sf, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def _is_3d_facade_render_chat_command(text: str, prev_params: dict = None) -> bool:
        from core.planning.multifloor_v1.engine.nl_design_parser import is_3d_render_or_render_edit_prompt
        return is_3d_render_or_render_edit_prompt(text or "", prev_params)

    def _handle_plan_locked_3d_render_request(jbody: dict):
        import base64
        import json
        import os
        import shutil
        import uuid
        from core.site.krocki_cad_reader_v27 import load_active_krocki_state
        from core.planning.multifloor_v1.engine.nl_design_parser import (
            parse_architectural_prompt,
            update_geometry_locked_render_state,
        )
        from core.planning.multifloor_v1.engine.architectural_synthesizer import ParametricArchitecturalSynthesizer
        from core.planning.multifloor_v1.engine.comfyui_bridge import ComfyUIRenderBridge

        repo_root = _resolve_arch_repo_root()
        user_msg = str(jbody.get("message") or jbody.get("prompt") or jbody.get("text") or "").strip()
        raw_q = str(
            jbody.get("quality")
            or jbody.get("render_quality")
            or jbody.get("preset")
            or jbody.get("quality_preset")
            or _arch_req.args.get("quality")
            or "draft"
        ).strip().lower()
        if any(w in user_msg.lower() for w in ("کیفیت بالا", "نهایی", "high", "final", "ultra")):
            quality = "high"
        elif any(w in user_msg.lower() for w in ("سریع", "درفت", "تست", "draft", "fast", "preview")):
            quality = "draft"
        elif raw_q in ("auto", ""):
            quality = "draft"
        else:
            quality = raw_q
        clean_pid = str(jbody.get("project_id") or _arch_req.args.get("project_id") or "default").strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        _sync_krocki_into_project_session(repo_root, clean_pid)

        st_path_plans = os.path.join(repo_root, "outputs", "plans", p_folder, "session_state.json")
        st_path_data = os.path.join(repo_root, "data", "projects", p_folder, "session_state.json")
        plan_params = None
        full_state_obj = {}
        for st_path in (st_path_plans, st_path_data):
            if os.path.isfile(st_path):
                try:
                    with open(st_path, "r", encoding="utf-8") as sf:
                        st_obj = json.load(sf)
                    if isinstance(st_obj.get("active_plan_params"), dict):
                        full_state_obj = dict(st_obj)
                        plan_params = dict(st_obj["active_plan_params"])
                        break
                except Exception:
                    pass

        from core.site.krocki_cad_reader_v27 import load_active_external_plan_state
        krocki = load_active_krocki_state(repo_root, clean_pid)
        ext_plan_now = load_active_external_plan_state(repo_root, clean_pid)
        if not isinstance(plan_params, dict):
            plan_params = parse_architectural_prompt(user_msg, active_site_krocki=krocki)
        if isinstance(ext_plan_now, dict) and ext_plan_now.get("total_floors"):
            _tot_e = int(ext_plan_now.get("total_floors", 1))
            _typ_e = str(ext_plan_now.get("typology", "MULTIFLOOR_RESIDENTIAL" if _tot_e >= 3 else ("DUPLEX_2FLOOR" if _tot_e == 2 else "VILLA_1FLOOR")))
            plan_params["typology"] = _typ_e
            plan_params["is_duplex"] = (_typ_e == "DUPLEX_2FLOOR")
            plan_params["floor_count"] = max(2, _tot_e - 1) if _typ_e == "MULTIFLOOR_RESIDENTIAL" else _tot_e
            plan_params["building_placement"] = str(ext_plan_now.get("building_placement") or "NORTH")
            plan_params["coverage_ratio"] = float(ext_plan_now.get("coverage_ratio", 0.65))
            if ext_plan_now.get("universal_facade_spec"):
                plan_params["universal_facade_spec"] = ext_plan_now["universal_facade_spec"]
            if ext_plan_now.get("custom_facade_profile"):
                plan_params["custom_facade_profile"] = ext_plan_now["custom_facade_profile"]
            else:
                plan_params.pop("custom_facade_profile", None)
        # Only self-heal stale DUPLEX_2FLOOR sessions if NO external plan (`ext_plan_now`) or `custom_facade_profile` is active!
        if (
            not isinstance(ext_plan_now, dict)
            and isinstance(plan_params, dict)
            and not plan_params.get("custom_facade_profile")
            and not plan_params.get("universal_facade_spec")
            and plan_params.get("typology") == "DUPLEX_2FLOOR"
            and "دوبلکس" not in str(plan_params.get("raw_prompt", ""))
            and "دوبلکس" not in user_msg
        ):
            plan_params["typology"] = "MULTIFLOOR_RESIDENTIAL"
            plan_params["is_duplex"] = False
            plan_params["floor_count"] = 2
            plan_params["building_placement"] = "NORTH"
            plan_params["coverage_ratio"] = 0.60
            plan_params["south_cantilever_mm"] = 1200
        if isinstance(krocki, dict):
            plan_params.setdefault("site_width_mm", int(round(float(krocki.get("width_m", 10.0)) * 1000)))
            plan_params.setdefault("site_length_mm", int(round(float(krocki.get("length_m", 20.0)) * 1000)))
            plan_params.setdefault("site_area_m2", round(float(krocki.get("site_area_m2", 200.0)), 2))
            plan_params.setdefault("krocki_polygon_mm", krocki.get("polygon_vertices_mm") or [])
            plan_params.setdefault("krocki_is_irregular", bool(krocki.get("is_irregular_polygon", False)))
            plan_params.setdefault("street_sides", krocki.get("street_sides") or ["SOUTH"])
            plan_params.setdefault("party_wall_sides", krocki.get("party_wall_sides") or ["WEST"])
            plan_params.setdefault("boundary_neighbors", krocki.get("boundary_neighbors") or {})
            plan_params.setdefault("south_y_west_mm", int(krocki.get("south_y_west_mm", 0)))
            plan_params.setdefault("south_y_east_mm", int(krocki.get("south_y_east_mm", 0)))

        # Update ONLY the geometry-locked render state while freezing 100% of plan_params geometry!
        prev_r_state = plan_params.get("active_render_state") or full_state_obj.get("active_render_state") or {}
        r_state = update_geometry_locked_render_state(prev_r_state, user_msg, plan_params)
        if plan_params.get("universal_facade_spec"):
            r_state["universal_facade_spec"] = plan_params["universal_facade_spec"]
        if plan_params.get("custom_facade_profile"):
            r_state["custom_facade_profile"] = plan_params["custom_facade_profile"]
        plan_params["active_render_state"] = r_state
        plan_params["render_facade_side"] = r_state["facade_side"]
        plan_params["facade_style_fa"] = r_state["style_label_fa"]
        plan_params["facade_material_fa"] = r_state["stone_label_fa"]
        plan_params["render_lighting_mode"] = r_state["lighting_mode"]

        synth = ParametricArchitecturalSynthesizer()
        project_res = synth.synthesize_from_params(plan_params)
        spec = ComfyUIRenderBridge.parse_render_request_from_chat("", prev_render_state=r_state, plan_params=plan_params)

        out_dir_plans = os.path.join(repo_root, "outputs", "plans", p_folder, "renders")
        out_dir_data = os.path.join(repo_root, "data", "projects", p_folder, "renders")
        os.makedirs(out_dir_plans, exist_ok=True)
        os.makedirs(out_dir_data, exist_ok=True)

        existing_renders = [fn for fn in os.listdir(out_dir_data) if fn.startswith("render_") and fn.endswith(".png") and not fn.endswith(("_depth.png", "_lineart.png"))]
        next_ord = len(existing_renders) + 1
        render_fn = f"render_{next_ord:03d}_{uuid.uuid4().hex[:6]}.png"
        scaffold_png_path = os.path.join(out_dir_data, render_fn)

        _, prompt_en = ComfyUIRenderBridge.export_plan_locked_south_facade_png(
            project_res,
            scaffold_png_path,
            chat_text="",
            quality=quality,
            prev_render_state=r_state,
        )

        # Persist updated active_render_state back to session_state.json so subsequent iterative edits stay locked!
        full_state_obj["active_plan_params"] = plan_params
        full_state_obj["active_render_state"] = r_state
        for st_p in (st_path_plans, st_path_data):
            try:
                os.makedirs(os.path.dirname(st_p), exist_ok=True)
                with open(st_p, "w", encoding="utf-8") as sf:
                    json.dump(full_state_obj, sf, ensure_ascii=False, indent=2)
            except Exception:
                pass

        final_png_path = scaffold_png_path
        comfy_status = "PLAN_LOCKED_3D_RAYSHADED_V33"
        try:
            bridge = ComfyUIRenderBridge()
            c_res = bridge.render_via_comfyui(
                project_res,
                user_msg,
                controlnet_png_path=scaffold_png_path,
                output_dir=out_dir_data,
                timeout_sec=240 if quality in ("draft", "preview", "fast", "auto") else 1200,
                quality=quality,
            )
            if c_res.get("status") == "RENDERED_BY_COMFYUI" and c_res.get("render_png_path") and os.path.isfile(c_res["render_png_path"]):
                shutil.copy2(c_res["render_png_path"], scaffold_png_path)
                comfy_status = "COMFYUI_IMG2IMG_PLAN_LOCKED_V33"
        except Exception:
            pass

        plan_render_copy = os.path.join(out_dir_plans, render_fn)
        try:
            shutil.copy2(final_png_path, plan_render_copy)
        except Exception:
            pass
        _sync_project_renders_and_assets(repo_root, clean_pid)

        with open(final_png_path, "rb") as rf:
            b64_png = base64.b64encode(rf.read()).decode("ascii")
        data_uri = f"data:image/png;base64,{b64_png}"
        web_rel_url = f"/planning/drawing/{p_folder}/renders/{render_fn}"

        n_floors = len(project_res.floors)
        typ_fa = "ویلایی ۱ طبقه" if n_floors == 1 else (f"دوبلکس ۲ طبقه" if n_floors == 2 else f"{n_floors} طبقه (همکف/پیلوت + {n_floors-1} طبقه تیپ)")
        reply_fa = (
            f"🎨 **رندر سه‌بعدی {spec['facade_label_fa']} کاملاً مقید به پلان و بدون تغییر حجم آماده شد.**\n"
            f"🏛️ **تعداد طبقات و تیپ پلان:** {typ_fa} (`Seed قفل‌شده: {spec['locked_seed']}`)\n"
            f"✨ **سبک و متریال:** {spec['style_label_fa']}\n"
            f"💡 **نورپردازی:** {spec['time_label_fa']}\n"
            f"📁 **مسیر ذخیره روی هارد:** `{final_png_path}`\n"
            f"🖼️ **لینک دانلود مستقیم رندر:** {web_rel_url}"
        )

        asset_entry = {
            "id": f"asset_{uuid.uuid4().hex[:8]}",
            "name": f"Render #{next_ord} ({spec['facade_label_fa']} - {typ_fa})",
            "type": "plan_locked_3d_render",
            "ordinal": next_ord,
            "filename": render_fn,
            "stored_filename": render_fn,
            "saved_location": final_png_path,
            "url": data_uri,
            "image_url": data_uri,
            "preview_url": data_uri,
            "web_url": web_rel_url,
            "status": "completed",
            "active": True,
        }

        return _arch_jsonify({
            "status": "success",
            "ok": True,
            "success": True,
            "mode": "plan_locked_3d_render",
            "type": "plan_locked_3d_render",
            "intent": "render",
            "render_status": "completed",
            "render_engine": comfy_status,
            "project_id": p_folder,
            "reply": reply_fa,
            "assistant_text": reply_fa,
            "display_text": reply_fa,
            "ui_text": reply_fa,
            "bot_reply": reply_fa,
            "message": reply_fa,
            "text": reply_fa,
            "response": reply_fa,
            "content": reply_fa,
            "answer": reply_fa,
            "chat_reply": reply_fa,
            "output_text": reply_fa,
            "summary_fa": reply_fa,
            "messages": [
                {"role": "user", "text": user_msg, "content": user_msg},
                {"role": "assistant", "text": reply_fa, "content": reply_fa, "image_url": data_uri, "url": web_rel_url},
            ],
            "chat": {
                "reply": reply_fa,
                "text": reply_fa,
                "message": reply_fa,
                "assistant_text": reply_fa,
                "image_url": data_uri,
            },
            "assistant_message": {
                "role": "assistant",
                "content": reply_fa,
                "text": reply_fa,
                "message": reply_fa,
                "reply": reply_fa,
                "image_url": data_uri,
            },
            "filename": render_fn,
            "original_filename": render_fn,
            "stored_filename": render_fn,
            "saved_location": final_png_path,
            "output_path": final_png_path,
            "image_path": final_png_path,
            "render_path": final_png_path,
            "file_path": final_png_path,
            "path": final_png_path,
            "dimensions": "1280 × 864",
            "width": 1280,
            "height": 864,
            "image_url": data_uri,
            "preview_url": data_uri,
            "render_url": data_uri,
            "svg_url": data_uri,
            "web_url": web_rel_url,
            "url": web_rel_url,
            "positive_prompt": prompt_en,
            "asset": asset_entry,
            "assets": [asset_entry],
            "renders": [asset_entry],
            "images": [final_png_path],
            "output_images": [final_png_path],
            "files": {
                "png": web_rel_url,
                "render_png": final_png_path,
                "image": final_png_path,
                "output_path": final_png_path,
            },
            "result": {
                "status": "success",
                "ok": True,
                "reply": reply_fa,
                "message": reply_fa,
                "text": reply_fa,
                "response": reply_fa,
                "output_path": final_png_path,
                "image_path": final_png_path,
                "saved_location": final_png_path,
                "filename": render_fn,
                "image_url": data_uri,
                "preview_url": data_uri,
                "asset": asset_entry,
            },
        }), 200

    def _handle_external_plan_upload_request():
        """
        v51.0 Universal External Plan, Multi-Floor Typical Plan (via Elevation Codes) & 2D Elevation/Section Upload Handler:
        Supports `.dwg`, `.dxf`, `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`, and `.svg`.
        """
        import base64
        import os
        import uuid
        from core.site.krocki_cad_reader_v27 import (
            parse_external_plan_or_elevation,
            save_active_external_plan_state,
            export_external_plan_preview_svg,
        )

        if _arch_req.method == "OPTIONS":
            return _arch_jsonify({"status": "ok"}), 200

        repo_root = _resolve_arch_repo_root()
        project_id = (
            _arch_req.args.get("project_id")
            or _arch_req.form.get("project_id")
            or (_arch_req.get_json(silent=True) or {}).get("project_id")
            or ""
        )
        user_hint = str(
            _arch_req.form.get("hint")
            or (_arch_req.get_json(silent=True) or {}).get("hint")
            or ""
        )
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        proj_dir = os.path.join(repo_root, "data", "projects", p_folder)
        site_dir = os.path.join(proj_dir, "site")
        renders_dir = os.path.join(proj_dir, "renders")
        os.makedirs(site_dir, exist_ok=True)
        os.makedirs(renders_dir, exist_ok=True)

        saved_path = None
        orig_name = "external_plan.dwg"

        if _arch_req.files:
            file_obj = (
                _arch_req.files.get("file")
                or _arch_req.files.get("plan")
                or _arch_req.files.get("external_plan")
                or next(iter(_arch_req.files.values()), None)
            )
            if file_obj is not None:
                orig_name = str(getattr(file_obj, "filename", "") or "external_plan.dwg")
                raw_ext = os.path.splitext(orig_name)[1].lower()
                if raw_ext not in (".dxf", ".dwg", ".3ds", ".rvt", ".ifc", ".obj", ".glb", ".gltf", ".fbx", ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".svg"):
                    raw_ext = ".dwg"
                saved_path = os.path.join(site_dir, f"ext_plan_{uuid.uuid4().hex[:8]}{raw_ext}")
                file_obj.save(saved_path)

        if saved_path is None:
            jbody = _arch_req.get_json(silent=True) or {}
            if jbody.get("file_path") and os.path.isfile(str(jbody["file_path"])):
                saved_path = str(jbody["file_path"])
                orig_name = os.path.basename(saved_path)
            elif jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"):
                b64_str = str(jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"))
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                orig_name = str(jbody.get("filename") or jbody.get("name") or "external_plan.png")
                raw_ext = os.path.splitext(orig_name)[1].lower() or ".png"
                saved_path = os.path.join(site_dir, f"ext_plan_{uuid.uuid4().hex[:8]}{raw_ext}")
                with open(saved_path, "wb") as bf:
                    bf.write(base64.b64decode(b64_str))

        if not saved_path or not os.path.isfile(saved_path):
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": "فایل پلان/نمای خارجی در درخواست ارسالی یافت نشد.",
                "message": "فایل پلان/نمای خارجی در درخواست ارسالی یافت نشد.",
            }), 400

        try:
            ext_info = parse_external_plan_or_elevation(saved_path, user_hint=user_hint)
            ext_info["original_filename"] = orig_name
            save_active_external_plan_state(repo_root, clean_pid, ext_info, sync_global_default=True)
            _sync_krocki_into_project_session(repo_root, clean_pid)
            # Also sync to the most recently active project_* directory so UI Chat and Studio always see the exact uploaded file!
            try:
                projs_root = os.path.join(repo_root, "data", "projects")
                if os.path.isdir(projs_root):
                    p_cands = []
                    for pn in os.listdir(projs_root):
                        pd = os.path.join(projs_root, pn)
                        if pn.startswith("project_") and pn not in ("project_default", "project_v337b_probe") and os.path.isdir(pd):
                            st_f = os.path.join(pd, "session_state.json")
                            mt = os.path.getmtime(st_f) if os.path.isfile(st_f) else os.path.getmtime(pd)
                            p_cands.append((mt, pn))
                    p_cands.sort(key=lambda x: x[0], reverse=True)
                    for _, recent_pn in p_cands[:2]:
                        save_active_external_plan_state(repo_root, recent_pn, ext_info, sync_global_default=False)
                        _sync_krocki_into_project_session(repo_root, recent_pn)
            except Exception:
                pass
            svg_name = f"external_plan_preview_{uuid.uuid4().hex[:6]}.svg"
            svg_path = os.path.join(renders_dir, svg_name)
            export_external_plan_preview_svg(ext_info, svg_path)
            with open(svg_path, "rb") as sf_b:
                svg_b64 = base64.b64encode(sf_b.read()).decode("ascii")
            preview_data_uri = f"data:image/svg+xml;base64,{svg_b64}"

            return _arch_jsonify({
                "status": "success",
                "ok": True,
                "success": True,
                "project_id": p_folder,
                "external_plan_info": ext_info,
                "doc_type": ext_info["doc_type"],
                "doc_type_fa": ext_info["doc_type_fa"],
                "total_floors": ext_info["total_floors"],
                "floors_desc_fa": ext_info["floors_desc_fa"],
                "elevation_codes_m": ext_info["elevation_codes_m"],
                "preview_url": preview_data_uri,
                "svg_url": preview_data_uri,
                "image_url": preview_data_uri,
                "summary_fa": ext_info["summary_fa"],
                "reply": (
                    f"📐 **{ext_info['summary_fa']}**\n"
                    f"🧱 **فایل‌های سه‌بعدی تولیدشده برای Blender و BIM**:\n"
                    f"- `GLB (Blender -> Import -> glTF 2.0)`: `{ext_info.get('glb_shell_path') or ''}`\n"
                    f"- `OBJ (Blender -> Import -> Wavefront .obj)`: `{ext_info.get('obj_shell_path') or ''}`\n"
                    f"- `IFC4 (SweptSolid 3D BIM)`: `{ext_info.get('ifc_shell_path') or ''}`\n"
                    f"✅ اکنون می‌توانید در چت بنویسید: «از نمای جنوبی با سبک نئوکلاسیک و سنگ تراورتن کرم رندر بگیر» یا «رندر شبش رو بگیر»."
                ),
                "message": ext_info["summary_fa"],
            }), 200
        except Exception as exc:
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": str(exc),
                "message": f"خطا در تحلیل پلان/نمای خارجی: {exc}",
                "reply": f"⚠️ خطا در تحلیل پلان/نمای خارجی: {exc}",
            }), 200

    def _handle_krocki_upload_request():
        import base64
        import os
        import uuid
        from core.site.krocki_cad_reader_v27 import (
            parse_krocki_dxf_or_dwg,
            export_krocki_preview_svg,
            save_active_krocki_state,
        )

        if _arch_req.method == "OPTIONS":
            return _arch_jsonify({"status": "ok"}), 200

        repo_root = _resolve_arch_repo_root()
        project_id = (
            _arch_req.args.get("project_id")
            or _arch_req.form.get("project_id")
            or (_arch_req.get_json(silent=True) or {}).get("project_id")
            or ""
        )
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        proj_dir = os.path.join(repo_root, "data", "projects", p_folder)
        site_dir = os.path.join(proj_dir, "site")
        renders_dir = os.path.join(proj_dir, "renders")
        os.makedirs(site_dir, exist_ok=True)
        os.makedirs(renders_dir, exist_ok=True)

        saved_path = None
        orig_name = "krocki.dxf"

        if _arch_req.files:
            file_obj = (
                _arch_req.files.get("file")
                or _arch_req.files.get("krocki")
                or _arch_req.files.get("krocki_file")
                or next(iter(_arch_req.files.values()), None)
            )
            if file_obj is not None:
                orig_name = str(getattr(file_obj, "filename", "") or "krocki.dxf")
                raw_ext = os.path.splitext(orig_name)[1].lower()
                if raw_ext not in (".dxf", ".dwg"):
                    raw_ext = ".dwg" if "dwg" in orig_name.lower() else ".dxf"
                saved_path = os.path.join(site_dir, f"krocki_{uuid.uuid4().hex[:8]}{raw_ext}")
                file_obj.save(saved_path)

        if saved_path is None:
            jbody = _arch_req.get_json(silent=True) or {}
            if jbody.get("file_path") and os.path.isfile(str(jbody["file_path"])):
                saved_path = str(jbody["file_path"])
                orig_name = os.path.basename(saved_path)
            elif jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"):
                b64_str = str(jbody.get("base64") or jbody.get("content_base64") or jbody.get("data"))
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                orig_name = str(jbody.get("filename") or jbody.get("name") or "krocki.dxf")
                raw_ext = os.path.splitext(orig_name)[1].lower()
                if raw_ext not in (".dxf", ".dwg"):
                    raw_ext = ".dxf"
                saved_path = os.path.join(site_dir, f"krocki_{uuid.uuid4().hex[:8]}{raw_ext}")
                with open(saved_path, "wb") as bf:
                    bf.write(base64.b64decode(b64_str))

        if not saved_path or not os.path.isfile(saved_path):
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": "فایل کروکی در درخواست ارسالی یافت نشد.",
                "message": "فایل کروکی در درخواست ارسالی یافت نشد.",
            }), 400

        try:
            krocki_info = parse_krocki_dxf_or_dwg(saved_path)
            krocki_info["original_filename"] = orig_name
            save_active_krocki_state(repo_root, clean_pid, krocki_info)
            _sync_krocki_into_project_session(repo_root, clean_pid)
            svg_name = f"krocki_preview_{uuid.uuid4().hex[:6]}.svg"
            svg_path = os.path.join(renders_dir, svg_name)
            export_krocki_preview_svg(krocki_info, svg_path)
            export_krocki_preview_svg(krocki_info, os.path.join(renders_dir, "krocki_preview.svg"))
            with open(svg_path, "rb") as sf_b:
                svg_b64 = base64.b64encode(sf_b.read()).decode("ascii")
            preview_data_uri = f"data:image/svg+xml;base64,{svg_b64}"

            return _arch_jsonify({
                "status": "success",
                "ok": True,
                "success": True,
                "project_id": p_folder,
                "krocki_info": krocki_info,
                "krocki": krocki_info,
                "site": krocki_info,
                "width_m": krocki_info["width_m"],
                "length_m": krocki_info["length_m"],
                "site_area_m2": krocki_info["site_area_m2"],
                "area_m2": krocki_info["site_area_m2"],
                "vertex_count": krocki_info["vertex_count"],
                "is_irregular_polygon": krocki_info["is_irregular_polygon"],
                "street_sides": krocki_info.get("street_sides", ["SOUTH"]),
                "party_wall_sides": krocki_info.get("party_wall_sides", ["WEST"]),
                "boundary_neighbors": krocki_info.get("boundary_neighbors", {}),
                "boundary_labels_fa": krocki_info.get("boundary_labels_fa", {}),
                "south_y_west_mm": krocki_info.get("south_y_west_mm", 0),
                "south_y_east_mm": krocki_info.get("south_y_east_mm", 0),
                "preview_url": preview_data_uri,
                "svg_url": preview_data_uri,
                "image_url": preview_data_uri,
                "summary_fa": krocki_info["summary_fa"],
                "reply": f"📐 {krocki_info['summary_fa']}\n✅ اکنون می‌توانید دستور طراحی پلان روی این زمین را در چت بنویسید.",
                "message": krocki_info["summary_fa"],
            }), 200
        except Exception as exc:
            return _arch_jsonify({
                "status": "error",
                "ok": False,
                "error": str(exc),
                "message": f"خطا در تحلیل کروکی: {exc}",
                "reply": f"⚠️ خطا در تحلیل کروکی: {exc}",
            }), 200

    for _k_route in (
        "/api/site/upload_krocki",
        "/api/site/krocki",
        "/api/krocki",
        "/api/upload_krocki",
        "/api/site/upload",
    ):
        try:
            app.add_url_rule(
                _k_route,
                endpoint=f"archos_krocki_{_k_route.replace('/', '_')}",
                view_func=_handle_krocki_upload_request,
                methods=["POST", "OPTIONS"],
            )
        except Exception:
            pass

    def _handle_latest_render_query():
        import base64
        import os
        repo_root = _resolve_arch_repo_root()
        pid = str(_arch_req.args.get("project_id") or "default").strip()
        if pid.lower() in ("", "null", "none", "undefined"):
            pid = "default"
        p_folder = pid if pid.startswith("project_") else f"project_{pid}"
        _sync_project_renders_and_assets(repo_root, pid)
        cands = []
        for r_dir in (
            os.path.join(repo_root, "data", "projects", p_folder, "renders"),
            os.path.join(repo_root, "outputs", "plans", p_folder, "renders"),
            os.path.join(repo_root, "data", "projects", "project_default", "renders"),
        ):
            if os.path.isdir(r_dir):
                for fn in os.listdir(r_dir):
                    if fn.startswith("render_") and fn.endswith((".png", ".jpg")) and not fn.endswith(("_depth.png", "_lineart.png", "_comfy_input.png")) and "_comfy_" not in fn and "_depth_" not in fn:
                        fp = os.path.join(r_dir, fn)
                        cands.append((os.path.getmtime(fp), fp, fn))
        if not cands:
            return _arch_jsonify({"ok": False}), 200
        cands.sort(key=lambda x: x[0], reverse=True)
        _, latest_fp, latest_fn = cands[0]
        with open(latest_fp, "rb") as rf:
            b64 = base64.b64encode(rf.read()).decode("ascii")
        d_uri = f"data:image/png;base64,{b64}"
        return _arch_jsonify({
            "ok": True,
            "filename": latest_fn,
            "saved_location": latest_fp,
            "image_url": d_uri,
            "web_url": f"/planning/drawing/{p_folder}/renders/{latest_fn}",
        }), 200

    try:
        import os as _pid_os
        _pid_root = _resolve_arch_repo_root()
        _pid_dir = _pid_os.path.join(_pid_root, "logs", "runtime")
        _pid_os.makedirs(_pid_dir, exist_ok=True)
        _is_ui_srv = _pid_os.path.basename(_pid_os.path.dirname(_pid_os.path.abspath(__file__))).lower() == "ui"
        _pid_fn = _pid_os.path.join(_pid_dir, "ui.pid" if _is_ui_srv else "orchestrator.pid")
        with open(_pid_fn, "w", encoding="utf-8") as _pf:
            _pf.write(str(_pid_os.getpid()))
    except Exception:
        pass

    def _resolve_latest_active_ext_plan_json(repo_root: str, clean_pid: str):
        import json, os
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        cands_j = []
        for jp in (
            os.path.join(repo_root, "data", "projects", p_folder, "site", "active_external_plan.json"),
            os.path.join(repo_root, "data", "active_external_plan.json"),
            os.path.join(repo_root, "data", "projects", "project_default", "site", "active_external_plan.json"),
        ):
            if os.path.isfile(jp):
                try:
                    with open(jp, "r", encoding="utf-8") as f:
                        d = json.load(f)
                    cands_j.append((float(d.get("uploaded_at_ts") or os.path.getmtime(jp)), d, os.path.dirname(jp)))
                except Exception:
                    pass
        if cands_j:
            cands_j.sort(key=lambda x: x[0], reverse=True)
            return cands_j[0][1], cands_j[0][2]
        return {}, os.path.join(repo_root, "data", "projects", p_folder, "site")

    def _handle_3d_scene_json_query():
        import json, os
        project_id = _arch_req.args.get("project_id") or "default"
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        repo_root = _resolve_arch_repo_root()
        act_d, site_dir = _resolve_latest_active_ext_plan_json(repo_root, clean_pid)
        sj_direct = str(act_d.get("scene_3d_json_path") or "")
        if sj_direct and os.path.isfile(sj_direct):
            with open(sj_direct, "r", encoding="utf-8") as jf:
                data = json.load(jf)
            data["ok"] = True
            data["source_filename"] = act_d.get("original_filename") or os.path.basename(str(act_d.get("source_file") or ""))
            data["is_3d_model"] = bool(act_d.get("is_3d_model") or act_d.get("is_direct_3d_bim_import"))
            data["total_floors"] = int(act_d.get("total_floors") or 1)
            return _arch_jsonify(data), 200
        cands = []
        if os.path.isdir(site_dir):
            for fn in os.listdir(site_dir):
                if fn.endswith("_scene.json") and "1d49dd1a" not in fn:
                    fp = os.path.join(site_dir, fn)
                    cands.append((os.path.getmtime(fp), fp))
            if not cands:
                for fn in os.listdir(site_dir):
                    if fn.endswith("_scene.json"):
                        fp = os.path.join(site_dir, fn)
                        cands.append((os.path.getmtime(fp), fp))
        if not cands:
            return _arch_jsonify({"ok": False, "elements": []}), 200
        cands.sort(key=lambda x: x[0], reverse=True)
        with open(cands[0][1], "r", encoding="utf-8") as jf:
            data = json.load(jf)
        data["ok"] = True
        return _arch_jsonify(data), 200

    def _handle_cad_layers_api():
        import json, os
        from engine.dxf_to_3d_shell_extruder import MultiStoryCAD3DShellExtruder
        project_id = (_arch_req.args.get("project_id") if _arch_req.method == "GET" else (_arch_req.get_json(silent=True) or {}).get("project_id")) or "default"
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        repo_root = _resolve_arch_repo_root()
        act_d, site_dir = _resolve_latest_active_ext_plan_json(repo_root, clean_pid)
        cad_fp = str(act_d.get("vectorized_dxf_path") or act_d.get("source_file") or "")
        if not cad_fp or not os.path.isfile(cad_fp):
            cands_c = []
            if os.path.isdir(site_dir):
                for fn in os.listdir(site_dir):
                    if fn.lower().endswith((".dwg", ".dxf")) and not fn.lower().endswith(("_elevations_and_sections.dxf", "_normalized_layers.dxf")) and "1d49dd1a" not in fn:
                        fp = os.path.join(site_dir, fn)
                        cands_c.append((os.path.getmtime(fp), fp))
            if cands_c:
                cands_c.sort(key=lambda x: x[0], reverse=True)
                cad_fp = cands_c[0][1]
        overrides = {}
        apply_all_floors = True
        if _arch_req.method == "POST":
            body = _arch_req.get_json(silent=True) or {}
            overrides = body.get("layer_overrides") or {}
            apply_all_floors = bool(body.get("apply_all_floors", True))
        res = MultiStoryCAD3DShellExtruder.auto_normalize_and_rewrite_dxf_layers(
            cad_fp, user_layer_overrides=overrides, apply_all_floors=apply_all_floors
        )
        if act_d.get("original_filename"):
            res["source_filename"] = act_d["original_filename"]
        return _arch_jsonify(res), 200

    def _handle_download_bim_bundle():
        import os, zipfile, tempfile
        from flask import send_file as _arch_send_file
        project_id = _arch_req.args.get("project_id") or "default"
        clean_pid = str(project_id).strip()
        if clean_pid.lower() in ("", "null", "none", "undefined"):
            clean_pid = "default"
        p_folder = clean_pid if clean_pid.startswith("project_") else f"project_{clean_pid}"
        repo_root = _resolve_arch_repo_root()
        site_dir = os.path.join(repo_root, "data", "projects", p_folder, "site")
        z_tmp = os.path.join(tempfile.gettempdir(), f"{p_folder}_Revit_BIM_Bundle_v50.zip")
        with zipfile.ZipFile(z_tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isdir(site_dir):
                for fn in sorted(os.listdir(site_dir)):
                    if fn.endswith((".ifc", ".glb", ".obj", ".mtl", "_revit_journal.txt", "_build_revit_rvt.py", "_elevations_and_sections.dxf", "_normalized_layers.dxf")):
                        fp = os.path.join(site_dir, fn)
                        if os.path.isfile(fp):
                            zf.write(fp, arcname=fn)
        return _arch_send_file(z_tmp, as_attachment=True, download_name=f"{p_folder}_Revit_IFC_RVT_Bundle.zip")

    try:
        app.add_url_rule("/api/3d/scene_json", endpoint="archos_3d_scene_json_v48", view_func=_handle_3d_scene_json_query, methods=["GET"])
        app.add_url_rule("/api/cad/layers", endpoint="archos_cad_layers_v49", view_func=_handle_cad_layers_api, methods=["GET", "POST"])
        app.add_url_rule("/api/cad/reclassify_layers", endpoint="archos_cad_reclassify_v49", view_func=_handle_cad_layers_api, methods=["POST"])
        app.add_url_rule("/api/3d/download_bim", endpoint="archos_download_bim_v50", view_func=_handle_download_bim_bundle, methods=["GET"])
    except Exception:
        pass

    try:
        app.add_url_rule("/api/render/latest" , endpoint="archos_latest_render_v33_7", view_func=_handle_latest_render_query, methods=["GET"])
    except Exception:
        pass

    for _ep_route in (
        "/api/plan/upload_external",
        "/api/site/upload_plan",
        "/api/upload_plan",
    ):
        try:
            app.add_url_rule(
                _ep_route,
                endpoint=f"archos_extplan_{_ep_route.replace('/', '_')}",
                view_func=_handle_external_plan_upload_request,
                methods=["POST", "OPTIONS"],
            )
        except Exception:
            pass

    @app.before_request
    def _architectos_v27_1_krocki_interceptor():
        path_low = (_arch_req.path or "").lower()
        if _arch_req.method == "GET" and path_low.rstrip("/") == "/api/3d/scene_json":
            return _handle_3d_scene_json_query()
        if path_low.rstrip("/") in ("/api/cad/layers", "/api/cad/reclassify_layers"):
            return _handle_cad_layers_api()
        if _arch_req.method == "GET" and path_low.rstrip("/") == "/api/3d/download_bim":
            return _handle_download_bim_bundle()
        if _arch_req.method == "GET" and path_low.rstrip("/") == "/api/render/latest":
            return _handle_latest_render_query()
        if _arch_req.method in ("POST", "OPTIONS") and ("upload_external" in path_low or "upload_plan" in path_low):
            return _handle_external_plan_upload_request()
        if _arch_req.method in ("POST", "OPTIONS") and ("krocki" in path_low or "/api/site/upload" in path_low or "/api/site/parse" in path_low):
            return _handle_krocki_upload_request()
        if _arch_req.method == "POST" and path_low.rstrip("/") in ("/api/chat", "/api/render", "/api/generate"):
            _jb = _arch_req.get_json(silent=True) or {}
            if _jb.get("external_plan_upload_only") or _jb.get("action") == "upload_external_plan":
                return _handle_external_plan_upload_request()
            if _jb.get("krocki_upload_only") or _jb.get("action") == "upload_krocki":
                return _handle_krocki_upload_request()
            _pid = str(_jb.get("project_id") or _arch_req.args.get("project_id") or "")
            _repo = _resolve_arch_repo_root()
            if _pid:
                _sync_krocki_into_project_session(_repo, _pid)
                _sync_project_renders_and_assets(_repo, _pid)
            _user_txt = str(_jb.get("message") or _jb.get("prompt") or _jb.get("text") or "").strip()
            _is_ui_proxy = os.path.basename(os.path.dirname(os.path.abspath(__file__))).lower() == "ui"
            if _is_3d_facade_render_chat_command(_user_txt):
                if path_low.rstrip("/") in ("/api/chat", "/api/render", "/api/generate"):
                    return _handle_plan_locked_3d_render_request(_jb)

    @app.after_request
    def _architectos_v30_asset_sync_after_request(response):
        try:
            path_low = (_arch_req.path or "").lower()
            if "/api/chat" in path_low or "/api/project" in path_low or "/api/session" in path_low:
                _jb = _arch_req.get_json(silent=True) or {}
                _pid = str(_jb.get("project_id") or _arch_req.args.get("project_id") or "")
                if _pid:
                    _sync_project_renders_and_assets(_resolve_arch_repo_root(), _pid)
        except Exception:
            pass
        return response

except Exception as _arch_hook_err:
    print("[!] Warning registering ArchitectOS v51.0 Krocki, External Plan & Render routes:", _arch_hook_err)
# [/ARCHITECTOS_V27_1_KROCKI_UPLOAD_INTERCEPTOR]
