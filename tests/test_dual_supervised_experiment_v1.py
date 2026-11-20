"""Focused CPU-only tests for the independent supervised runner."""

import copy
import json
import os
from pathlib import Path

import pytest

from core.render.dual_supervised_experiment_v1 import (
    EXPERIMENT_ID, FIXED_PROFILE, WORKFLOW_SHA256, ExperimentBlocked,
    InputSpec, build_effective_graph, canonical_sha256, cpu_preflight,
    execute_supervised, file_sha256, validate_bound_permit, validate_profile,
    write_cpu_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
IMAGE_A = Path(os.environ.get("ARCHITECTOS_TEST_IMAGE_A", str(ROOT / "tests" / "assets" / "sample_a.jpg")))
IMAGE_B = ROOT / "uploads" / "chat_media" / "c4b77de5d388_Gemini_Generated_Image_2cc3us2cc3us2cc3.jpg"
WORKFLOW = ROOT / "core" / "render" / "workflows" / "flux_img2img_dual_conditioned.json"


def models_ready(**_):
    return {"status": "ready", "hash_verified": False, "present": {"all": True},
            "missing": [], "invalid": []}


@pytest.fixture(scope="module")
def prepared():
    return cpu_preflight(InputSpec(str(IMAGE_A), str(IMAGE_B)), str(WORKFLOW),
                         profile=FIXED_PROFILE, model_verifier=models_ready)


class Lease:
    def __init__(self, ok=True): self.ok, self.released = ok, False
    def acquire(self): return self.ok
    def release(self): self.released = True


class Transport:
    manages_comfyui_lease = True
    def __init__(self, queue=None, error=None):
        self.queue = queue or {"ok": True, "running": [], "pending": []}
        self.error, self.calls = error, 0
    def queue_state(self): return copy.deepcopy(self.queue)
    def execute(self, graph):
        self.calls += 1
        if self.error: raise self.error
        return {"status": "success", "prompt_id": "test-prompt", "outputs": []}


def permit_for(evidence, graph):
    graph_hash = canonical_sha256(graph)
    return {
        "id": "permit-1", "experiment": EXPERIMENT_ID,
        "graph_sha256": graph_hash, "effective_graph_sha256": graph_hash,
        "image_a_sha256": evidence["inputs"]["image_a"]["sha256"],
        "image_b_sha256": evidence["inputs"]["image_b"]["sha256"],
        "workflow_sha256": evidence["workflow"]["sha256"],
        "profile_sha256": evidence["profile_sha256"],
    }


def run_fake(prepared, tmp_path, transport=None, permit=None, lease=None,
             consumer=None, vram=None):
    evidence, graph = prepared
    permit = permit or permit_for(evidence, graph)
    transport = transport or Transport()
    lease = lease or Lease()
    consumer = consumer or (lambda experiment, graph_hash, base, dry:
                            {"id": permit["id"], "state": "consumed",
                             "experiment": experiment, "graph_sha256": graph_hash})
    return execute_supervised(
        evidence, graph, str(tmp_path), str(tmp_path / "permit"), transport,
        lambda _: permit, consumer, lambda wait=0: lease,
        vram or (lambda **_: {"ok": True, "free_mib": 15000}),
    ), transport, lease


def test_a_correct_identity_binding_and_authority(prepared):
    evidence, graph = prepared
    assert evidence["inputs"]["image_a"]["role"] == "style_reference"
    assert evidence["inputs"]["image_b"]["role"] == "target_building"
    assert graph["302"]["inputs"]["image"] == evidence["planned_staged_filenames"]["image_a"]
    assert graph["300"]["inputs"]["image"] == evidence["planned_staged_filenames"]["image_b"]
    assert graph["301"]["inputs"]["pixels"] == ["300", 0]
    assert graph["306"]["inputs"]["image"] == ["300", 0]


def test_b_wrong_source_hash_refused():
    spec = InputSpec(str(IMAGE_A), str(IMAGE_B), image_a_sha256="0" * 64)
    with pytest.raises(ExperimentBlocked, match="wrong_image_hash_a"):
        cpu_preflight(spec, str(WORKFLOW), model_verifier=models_ready)


def test_c_swapped_image_roles_refused():
    spec = InputSpec(str(IMAGE_B), str(IMAGE_A))
    with pytest.raises(ExperimentBlocked, match="wrong_image_hash_a"):
        cpu_preflight(spec, str(WORKFLOW), model_verifier=models_ready)


def test_d_missing_image_refused(tmp_path):
    spec = InputSpec(str(tmp_path / "missing.jpg"), str(IMAGE_B))
    with pytest.raises(ExperimentBlocked, match="missing_image_a"):
        cpu_preflight(spec, str(WORKFLOW), model_verifier=models_ready)


def test_e_wrong_workflow_hash_refused(tmp_path):
    path = tmp_path / "workflow.json"
    path.write_bytes(WORKFLOW.read_bytes() + b"\n")
    with pytest.raises(ExperimentBlocked, match="wrong_workflow_hash"):
        cpu_preflight(InputSpec(str(IMAGE_A), str(IMAGE_B)), str(path),
                      model_verifier=models_ready)


def test_f_model_identity_mismatch_refused():
    blocked = lambda **_: {"status": "blocked", "missing": [{"role": "style_encoder"}]}
    with pytest.raises(ExperimentBlocked, match="model_identity_mismatch"):
        cpu_preflight(InputSpec(str(IMAGE_A), str(IMAGE_B)), str(WORKFLOW),
                      model_verifier=blocked)


def test_g_missing_or_unverified_profile_refused():
    with pytest.raises(ExperimentBlocked, match="safe_profile_missing"):
        validate_profile({})
    bad = copy.deepcopy(FIXED_PROFILE); bad["resource_safety_verified"] = False
    with pytest.raises(ExperimentBlocked, match="safe_profile_unverified"):
        validate_profile(bad)


def test_h_missing_gpu_authorization_refused(prepared):
    evidence, graph = prepared
    with pytest.raises(ExperimentBlocked, match="gpu_authorization_missing"):
        validate_bound_permit({}, evidence, canonical_sha256(graph))


def test_i_permit_replay_refused(prepared, tmp_path):
    run_fake(prepared, tmp_path)
    with pytest.raises(ExperimentBlocked, match="submission_state_exists_no_replay"):
        run_fake(prepared, tmp_path)


def test_j_duplicate_submission_prevented(prepared, tmp_path):
    _, transport, _ = run_fake(prepared, tmp_path)
    with pytest.raises(ExperimentBlocked):
        run_fake(prepared, tmp_path, transport=transport)
    assert transport.calls == 1


def test_k_timeout_is_uncertain_and_never_resubmitted(prepared, tmp_path):
    transport = Transport(error=TimeoutError("simulated"))
    with pytest.raises(ExperimentBlocked, match="submission_uncertain_no_automatic_retry"):
        run_fake(prepared, tmp_path, transport=transport)
    with pytest.raises(ExperimentBlocked, match="submission_state_exists_no_replay"):
        run_fake(prepared, tmp_path, transport=transport)
    assert transport.calls == 1
    record = json.loads((tmp_path / "submission_attempt.json").read_text())
    assert record["state"] == "SUBMISSION_UNCERTAIN"


def test_l_crash_restart_cannot_reuse_consumed_permit(prepared, tmp_path):
    consumed = []
    def consume(*args):
        if consumed: raise RuntimeError("permit already consumed")
        consumed.append(args); return {"id": "permit-1", "state": "consumed"}
    with pytest.raises(ExperimentBlocked):
        run_fake(prepared, tmp_path, transport=Transport(error=SystemExit("crash")),
                 consumer=consume)
    with pytest.raises(ExperimentBlocked, match="submission_state_exists_no_replay"):
        run_fake(prepared, tmp_path, consumer=consume)
    assert len(consumed) == 1


def test_m_busy_resource_or_queue_refused(prepared, tmp_path):
    with pytest.raises(ExperimentBlocked, match="gpu_render_lease_unavailable"):
        run_fake(prepared, tmp_path / "gpu", lease=Lease(False))
    busy = Transport(queue={"ok": True, "running": ["other"], "pending": []})
    with pytest.raises(ExperimentBlocked, match="comfyui_queue_not_empty"):
        run_fake(prepared, tmp_path / "queue", transport=busy)
    no_owner = Transport(); no_owner.manages_comfyui_lease = False
    with pytest.raises(ExperimentBlocked, match="comfyui_lease_owner_missing"):
        run_fake(prepared, tmp_path / "comfy", transport=no_owner)


def test_n_effective_graph_profile_and_conditioning(prepared):
    evidence, graph = prepared
    assert evidence["wiring"]["status"] == "wired"
    assert graph["210"]["inputs"] | {} == graph["210"]["inputs"]
    sampler = graph["210"]["inputs"]
    assert (sampler["steps"], sampler["cfg"], sampler["denoise"], sampler["seed"]) == (30, 5.0, .30, 20261030)
    assert sampler["latent_image"] == ["301", 0]
    assert graph["311"]["inputs"]["image"] == ["307", 0]


def test_o_evidence_is_experimental_not_production(prepared, tmp_path):
    evidence, _ = prepared
    path = tmp_path / "runs" / "dual" / "cpu.json"
    write_cpu_evidence(str(path), evidence)
    assert path.is_file()
    assert "data/render_acceptance" not in path.as_posix()
    assert evidence["production_asset_registered"] is False


def test_p_production_r4_remains_fail_closed():
    from core.chat.chat_architect import _r4_acceptance_record
    record = _r4_acceptance_record("flux_img2img_dual_conditioned.json")
    assert record["accepted"] is False
    assert record["reason"] in {"no_acceptance_record", "acceptance_record_unreadable"}


def test_q_no_fake_preservation_record_or_acceptance_claim(prepared, tmp_path):
    evidence, _ = prepared
    write_cpu_evidence(str(tmp_path / "cpu.json"), evidence)
    text = (tmp_path / "cpu.json").read_text(encoding="utf-8")
    assert '"preservation_status": "UNVERIFIED"' in text
    assert '"visual_review_status": "NOT_REVIEWED"' in text
    assert '"ACCEPTED"' not in text


def test_r_cpu_preflight_has_zero_external_work(prepared):
    evidence, _ = prepared
    assert evidence["zero_external_work"] == {
        "gpu_jobs": 0, "comfyui_submissions": 0,
        "ollama_inference": 0, "production_chat_posts": 0,
    }
    assert evidence["submission_attempt_count"] == 0
    assert evidence["output"] is None
    assert evidence["leases"] == {"gpu_render": "NOT_ACQUIRED", "comfyui": "NOT_ACQUIRED"}
