"""Independent, fail-closed runner for one supervised dual-image experiment.

This module is deliberately outside ChatArchitect/R4.  CPU preflight is pure:
it reads and hashes files and builds a nonexecuting graph.  The execution
entry point requires a separately issued, digest-bound, crash-safe permit and
uses the existing GPU/ComfyUI ownership primitives.  Completing a graph never
creates a production acceptance record.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from core.render.dual_image_binding_v1 import (
    NODE_A, NODE_B, ROLE_A, ROLE_B, bind_role_bindings,
)
from core.render.dual_image_conditioning_v1 import (
    MODEL_SPEC, verify_conditioning_graph, verify_conditioning_models,
)
from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)


CONTRACT = "DualConditionedSupervisedExperimentV1"
VERSION = "1.0"
EXPERIMENT_ID = "dual_conditioned_neoclassical_reference_v1"
WORKFLOW_SHA256 = "343c91f367a9f82fd436d04631128a65867c5bb391467afeb5173235184f09f3"
IMAGE_A_SHA256 = "d0caba185a3479e0568f184d0b7401e7958013e18680dc0e33f257b181e82657"
IMAGE_B_SHA256 = "8052c743189202425e37e41bf82b3681d2aebcb155ee2c7d73f585c1cb64c872"

DEFAULT_PROMPT = (
    "Restyle IMAGE B as a restrained neoclassical cream-natural-stone facade. "
    "Use IMAGE A for appearance language only: subtle stone texture, pilasters, "
    "decorative capitals, classical window surrounds, stringcourses, cornices, "
    "and stone balustrade language. IMAGE B remains authoritative for massing, "
    "structural frame, floor count, openings, terrace edges, roof, site, and "
    "camera. Do not copy IMAGE A arches, pediment, balcony positions, windows, "
    "entrances, gates, floor count, building geometry, or surrounding site."
)

NEGATIVE_PROMPT = (
    "geometry replacement, changed floor count, closed openings, invented bays, "
    "copied reference pediment, copied reference arches, copied reference site, "
    "gold veining, baroque sculpture"
)


class ExperimentBlocked(RuntimeError):
    """A stable fail-closed refusal; it never authorizes a retry."""


@dataclass(frozen=True)
class InputSpec:
    image_a: str
    image_b: str
    image_a_sha256: str = IMAGE_A_SHA256
    image_b_sha256: str = IMAGE_B_SHA256
    image_a_dimensions: tuple[int, int] = (756, 1024)
    image_b_dimensions: tuple[int, int] = (1792, 2400)


FIXED_PROFILE = {
    "contract": "DualConditionedSupervisedProfileV1",
    "name": "dual_conditioned_768x1024_measured_v1",
    "source_staging": {
        "method": "contain_center_pad_no_crop",
        "width": 768,
        "height": 1024,
        "format": "PNG",
    },
    "sampler_dimensions": [768, 1024],
    "sampler": "euler",
    "scheduler": "simple",
    "steps": 30,
    "cfg": 5.0,
    "denoise": 0.30,
    "seed": 20261030,
    "controlnet": {"strength": 0.8, "start_percent": 0.0, "end_percent": 0.8},
    "min_free_vram_mib": 11264.0,
    "maximum_gpu_allocation_expectation_mib": 16384.0,
    "maximum_expected_card_class": "single 16-GiB-class adapter",
    "models": (["base_unet", "clip_l", "t5xxl", "vae"] +
               [entry["role"] for entry in MODEL_SPEC]),
    "resource_safety_verified": True,
    "preservation_verified": False,
    "quality_verified_for_current_pair": False,
    "provenance": [
        "ARCHITECTOS_FACADE_REFERENCE_STYLE_DUAL_GPU_ACCEPTANCE_V1.md",
        "ARCHITECTOS_FACADE_DUAL_RENDER_V5_RESULT.md",
    ],
    "provenance_note": (
        "The same installed workflow and 768x1024/30-step profile completed on "
        "the installed hardware. This verifies bounded executability only; it "
        "does not prove preservation, style transfer, or current-pair quality."
    ),
}

BASE_MODEL_SPEC = (
    ("base_unet", "diffusion_models", "flux1-krea-dev_fp8_scaled.safetensors",
     11904639672, "b17a8c21703c4d6ffb0e300dd920eff3cfd35c9a72a1abaf107e3788e408b8d8"),
    ("clip_l", "text_encoders", "clip_l.safetensors", 246144152,
     "660c6f5b1abae9dc498ac2d21e1347d2abdb0cf6c0c0c8576cd796491d9a6cdd"),
    ("t5xxl", "text_encoders", "t5xxl_fp16.safetensors", 9787841024,
     "6e480b09fae049a72d2a8c5fbccb8d3e92febeb233bbe9dfe7256958a9167635"),
    ("vae", "vae", "ae.safetensors", 335304388,
     "afc8e28272cd15db3919bacdb6918ce9c1ed22e96cb12c4d5ed0fba823529e38"),
)


def canonical_sha256(value) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def text_sha256(value) -> str:
    """SHA256 of the exact UTF-8 instruction bytes (no JSON wrapper)."""
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_all_models(comfy_root=None, verify_hash=True):
    """Exact disk identity for base and conditioning assets; never loads them."""
    if comfy_root is None:
        from config import runtime_config as RC
        comfy_root = RC.COMFYUI_ROOT
    conditioning = verify_conditioning_models(comfy_root, verify_hash=verify_hash)
    base = []
    for role, folder, filename, expected_bytes, expected_hash in BASE_MODEL_SPEC:
        path = os.path.join(comfy_root, "models", folder, filename)
        record = {"role": role, "path": path, "filename": filename,
                  "expected_bytes": expected_bytes, "expected_sha256": expected_hash,
                  "present": os.path.isfile(path), "valid": False}
        if record["present"]:
            record["bytes"] = os.path.getsize(path)
            record["sha256"] = file_sha256(path) if verify_hash else None
            record["valid"] = (record["bytes"] == expected_bytes and
                               (not verify_hash or record["sha256"] == expected_hash))
        base.append(record)
    ready = conditioning.get("status") == "ready" and all(item["valid"] for item in base)
    return {"status": "ready" if ready else "blocked", "hash_verified": bool(verify_hash),
            "comfy_root": comfy_root, "conditioning": conditioning,
            "base_models": base,
            "missing": [item for item in base if not item["present"]],
            "invalid": [item for item in base if item["present"] and not item["valid"]]}


def image_dimensions(path: str) -> tuple[int, int]:
    from PIL import Image, ImageOps
    with Image.open(path) as image:
        upright = ImageOps.exif_transpose(image)
        return tuple(int(v) for v in upright.size)


def _validate_image(path, expected_hash, expected_dimensions, label):
    if not path or not os.path.isfile(path):
        raise ExperimentBlocked("missing_image_" + label)
    actual_hash = file_sha256(path)
    if actual_hash != expected_hash:
        raise ExperimentBlocked("wrong_image_hash_" + label)
    actual_dimensions = image_dimensions(path)
    if actual_dimensions != tuple(expected_dimensions):
        raise ExperimentBlocked("wrong_image_dimensions_" + label)
    return {"path": os.path.abspath(path), "sha256": actual_hash,
            "dimensions": list(actual_dimensions)}


def validate_profile(profile) -> dict:
    if not isinstance(profile, dict) or not profile:
        raise ExperimentBlocked("safe_profile_missing")
    if profile.get("resource_safety_verified") is not True:
        raise ExperimentBlocked("safe_profile_unverified")
    required = ("sampler_dimensions", "sampler", "scheduler", "steps", "cfg",
                "denoise", "seed", "controlnet", "min_free_vram_mib")
    if any(key not in profile for key in required):
        raise ExperimentBlocked("safe_profile_incomplete")
    if list(profile["sampler_dimensions"]) != [768, 1024]:
        raise ExperimentBlocked("safe_profile_dimensions_unverified")
    return copy.deepcopy(profile)


def planned_staged_filenames(spec: InputSpec, profile) -> dict:
    """Stable names make the CPU graph exactly permit-bindable before staging."""
    profile_tag = canonical_sha256(profile)[:12]
    return {
        "image_a": "architectos_dual_%s_a_%s_768x1024.png" %
                   (spec.image_a_sha256[:12], profile_tag),
        "image_b": "architectos_dual_%s_b_%s_768x1024.png" %
                   (spec.image_b_sha256[:12], profile_tag),
    }


def stage_fixed_inputs(spec: InputSpec, profile, comfy_input: str) -> dict:
    """Future-execution staging only: contain + centre-pad, never crop/upscale.

    CPU preflight never calls this function. Existing destination files are
    accepted only if byte-identical to the deterministic derivation; they are
    never overwritten on mismatch.
    """
    from PIL import Image, ImageOps

    profile = validate_profile(profile)
    names = planned_staged_filenames(spec, profile)
    target_size = tuple(profile["sampler_dimensions"])
    os.makedirs(comfy_input, exist_ok=True)
    records = {}
    for key, source in (("image_a", spec.image_a), ("image_b", spec.image_b)):
        destination = os.path.join(comfy_input, names[key])
        temp = destination + ".tmp.%s" % os.getpid()
        try:
            with Image.open(source) as image:
                upright = ImageOps.exif_transpose(image).convert("RGB")
                contained = ImageOps.contain(upright, target_size,
                                             method=Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", target_size, (127, 127, 127))
                offset = ((target_size[0] - contained.width) // 2,
                          (target_size[1] - contained.height) // 2)
                canvas.paste(contained, offset)
                canvas.save(temp, format="PNG", optimize=False)
            derived_hash = file_sha256(temp)
            if os.path.exists(destination):
                if file_sha256(destination) != derived_hash:
                    raise ExperimentBlocked("staged_destination_collision:" + key)
                os.unlink(temp)
            else:
                os.replace(temp, destination)
            if image_dimensions(destination) != target_size:
                raise ExperimentBlocked("staged_dimensions_invalid:" + key)
            records[key] = {"filename": names[key], "path": destination,
                            "sha256": derived_hash, "dimensions": list(target_size),
                            "derived_from_sha256": (spec.image_a_sha256 if key == "image_a"
                                                    else spec.image_b_sha256)}
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    return records


def bind_resolved_architectural_instruction(
    base_prompt=DEFAULT_PROMPT,
    architectural_instruction=None,
) -> tuple[str, dict]:
    """Bind one already-resolved RenderConstraintBlockV1 to the experiment.

    The runner never sees or reparses the user's source-language request. It
    accepts only the existing instruction owner's resolved contract and uses
    the existing render prompt resolver. Absence preserves the historical
    DEFAULT_PROMPT byte-for-byte.
    """

    base = str(base_prompt or "")
    if architectural_instruction is None:
        return base, {
            "mode": "DEFAULT_PROMPT",
            "instruction_bound": False,
            "node_id": "206",
            "base_prompt_sha256": text_sha256(base),
            "effective_positive_instruction": base,
            "effective_positive_instruction_sha256": text_sha256(base),
            "instruction_truncated": False,
            "source_contract": None,
        }

    if not isinstance(architectural_instruction, dict):
        raise ExperimentBlocked("architectural_instruction_contract_invalid")
    if architectural_instruction.get("contract") != "RenderConstraintBlockV1":
        raise ExperimentBlocked("architectural_instruction_contract_invalid")

    block = str(
        architectural_instruction.get("constraint_block")
        or architectural_instruction.get("english_instruction")
        or ""
    ).strip()
    completion = architectural_instruction.get(
        "architectural_completion_handoff"
    )
    if not block or not isinstance(completion, dict) or not completion:
        raise ExperimentBlocked("architectural_instruction_completion_missing")
    if completion.get("source_contract") != "ArchitecturalPreservationIntentV1":
        raise ExperimentBlocked("architectural_instruction_provenance_invalid")
    if completion.get("hard_preservation_claimed") is not False:
        raise ExperimentBlocked("architectural_instruction_hard_claim_invalid")
    if completion.get("render_executed") is not False:
        raise ExperimentBlocked("architectural_instruction_execution_state_invalid")

    spatial = completion.get("spatial_authority") or {}
    if (
        not isinstance(spatial, dict)
        or spatial.get("status") != "SEMANTIC_ONLY_NOT_SPATIALLY_VERIFIED"
        or any(spatial.get(key) is not None for key in (
            "mask", "pixel_coordinates", "segmentation"
        ))
    ):
        raise ExperimentBlocked("architectural_instruction_spatial_authority_invalid")

    resolved = resolve_render_prompt(
        compiled_prompt=base,
        builder_prompt="",
        architectural_instruction=architectural_instruction,
        max_instruction_chars=2400,
    )
    if resolved.get("instruction_applied") is not True:
        raise ExperimentBlocked("architectural_instruction_not_applied")
    if resolved.get("instruction_truncated") is not False:
        raise ExperimentBlocked("architectural_instruction_truncated")

    effective = str(resolved.get("final_prompt") or "")
    if not effective or block not in effective:
        raise ExperimentBlocked("architectural_instruction_binding_failed")

    return effective, {
        "mode": "RESOLVED_RENDER_CONSTRAINT_BLOCK",
        "instruction_bound": True,
        "node_id": "206",
        "base_prompt_sha256": text_sha256(base),
        "constraint_block": block,
        "constraint_block_sha256": text_sha256(block),
        "effective_positive_instruction": effective,
        "effective_positive_instruction_sha256": text_sha256(effective),
        "instruction_chars": resolved.get("instruction_chars"),
        "instruction_truncated": resolved.get("instruction_truncated"),
        "source_contract": architectural_instruction.get("contract"),
        "render_constraint_provenance": copy.deepcopy(
            architectural_instruction.get("provenance") or {}
        ),
        "architectural_completion_handoff": copy.deepcopy(completion),
    }


def build_effective_graph(workflow, profile, image_a_filename, image_b_filename,
                          prompt=DEFAULT_PROMPT, architectural_instruction=None):
    effective_prompt, instruction_binding = bind_resolved_architectural_instruction(
        prompt,
        architectural_instruction,
    )
    graph, binding = bind_role_bindings(workflow, {
        ROLE_A: {"node_id": NODE_A, "filename": image_a_filename},
        ROLE_B: {"node_id": NODE_B, "filename": image_b_filename},
    })
    if binding.get("errors"):
        raise ExperimentBlocked("role_binding_failed:" + ",".join(binding["errors"]))

    sampler = graph["210"]["inputs"]
    sampler.update({
        "seed": int(profile["seed"]), "steps": int(profile["steps"]),
        "cfg": float(profile["cfg"]), "sampler_name": profile["sampler"],
        "scheduler": profile["scheduler"], "denoise": float(profile["denoise"]),
    })
    control = graph["311"]["inputs"]
    control.update({
        "strength": float(profile["controlnet"]["strength"]),
        "start_percent": float(profile["controlnet"]["start_percent"]),
        "end_percent": float(profile["controlnet"]["end_percent"]),
    })
    graph["206"]["inputs"]["text"] = effective_prompt
    graph["212"]["inputs"]["text"] = NEGATIVE_PROMPT

    wired = verify_conditioning_graph(graph)
    if wired.get("status") != "wired":
        raise ExperimentBlocked("effective_graph_wiring_invalid")
    if graph["300"]["inputs"]["image"] != image_b_filename:
        raise ExperimentBlocked("geometry_authority_reversed")
    if graph["302"]["inputs"]["image"] != image_a_filename:
        raise ExperimentBlocked("style_authority_reversed")
    binding = copy.deepcopy(binding)
    binding["architectural_instruction"] = instruction_binding
    return graph, binding, wired


def cpu_preflight(spec: InputSpec, workflow_path: str, comfy_root=None,
                  profile=None, model_verifier=verify_all_models,
                  architectural_instruction=None):
    """Read-only validation. No staging, lease, network, GPU, or inference."""
    profile = validate_profile(profile or FIXED_PROFILE)
    image_a = _validate_image(spec.image_a, spec.image_a_sha256,
                              spec.image_a_dimensions, "a")
    image_b = _validate_image(spec.image_b, spec.image_b_sha256,
                              spec.image_b_dimensions, "b")
    if image_a["sha256"] == image_b["sha256"]:
        raise ExperimentBlocked("image_roles_swapped_or_collided")
    if not os.path.isfile(workflow_path):
        raise ExperimentBlocked("workflow_missing")
    workflow_hash = file_sha256(workflow_path)
    if workflow_hash != WORKFLOW_SHA256:
        raise ExperimentBlocked("wrong_workflow_hash")
    with open(workflow_path, encoding="utf-8") as handle:
        workflow = json.load(handle)
    models = model_verifier(comfy_root=comfy_root, verify_hash=True)
    if models.get("status") != "ready":
        raise ExperimentBlocked("model_identity_mismatch")
    staged_names = planned_staged_filenames(spec, profile)
    graph, binding, wired = build_effective_graph(
        workflow, profile, staged_names["image_a"], staged_names["image_b"],
        architectural_instruction=architectural_instruction,
    )
    instruction_binding = copy.deepcopy(
        binding.get("architectural_instruction") or {}
    )
    instruction_binding["negative_instruction"] = NEGATIVE_PROMPT
    instruction_binding["negative_instruction_sha256"] = text_sha256(
        NEGATIVE_PROMPT
    )
    evidence = {
        "contract": CONTRACT, "version": VERSION, "mode": "CPU_PREFLIGHT",
        "experiment_id": EXPERIMENT_ID,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "status": "ready", "nonexecuting": True,
        "inputs": {
            "image_a": {**image_a, "role": ROLE_A, "authority": "style_only"},
            "image_b": {**image_b, "role": ROLE_B, "authority": "geometry"},
        },
        "workflow": {"path": os.path.abspath(workflow_path), "sha256": workflow_hash},
        "models": models, "profile": profile,
        "planned_staged_filenames": staged_names,
        "profile_sha256": canonical_sha256(profile),
        "effective_graph_sha256": canonical_sha256(graph),
        "instruction_binding": instruction_binding,
        "bindings": binding, "wiring": wired,
        "permit": {"identity": None, "state": "NOT_ISSUED"},
        "leases": {"gpu_render": "NOT_ACQUIRED", "comfyui": "NOT_ACQUIRED"},
        "submission_attempt_count": 0, "prompt_id": None,
        "queue_history": [], "output": None,
        "visual_review_status": "NOT_REVIEWED",
        "preservation_status": "UNVERIFIED",
        "production_r4_admission_changed": False,
        "production_asset_registered": False,
        "claims": {
            "resource_profile_verified": True,
            "conditioning_wired": True,
            "conditioning_runtime_verified_for_current_pair": False,
            "preservation_verified": False,
        },
        "zero_external_work": {"gpu_jobs": 0, "comfyui_submissions": 0,
                               "ollama_inference": 0, "production_chat_posts": 0},
    }
    return evidence, graph


def _atomic_write_json(path: str, value, exclusive=False):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    data = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        try:
            os.write(fd, data); os.fsync(fd)
        finally:
            os.close(fd)
        return
    temp = path + ".tmp.%s" % os.getpid()
    with open(temp, "wb") as handle:
        handle.write(data); handle.flush(); os.fsync(handle.fileno())
    os.replace(temp, path)


def write_cpu_evidence(path: str, evidence):
    if evidence.get("mode") != "CPU_PREFLIGHT" or not evidence.get("nonexecuting"):
        raise ExperimentBlocked("not_cpu_preflight_evidence")
    _atomic_write_json(path, evidence)


def validate_bound_permit(permit, evidence, effective_graph_sha256):
    required = {
        "experiment": EXPERIMENT_ID,
        "graph_sha256": effective_graph_sha256,
        "effective_graph_sha256": effective_graph_sha256,
        "image_a_sha256": evidence["inputs"]["image_a"]["sha256"],
        "image_b_sha256": evidence["inputs"]["image_b"]["sha256"],
        "workflow_sha256": evidence["workflow"]["sha256"],
        "profile_sha256": evidence["profile_sha256"],
    }
    if not isinstance(permit, dict) or not permit.get("id"):
        raise ExperimentBlocked("gpu_authorization_missing")
    for key, expected in required.items():
        if permit.get(key) != expected:
            raise ExperimentBlocked("gpu_authorization_binding_mismatch:" + key)
    return permit


def _queue_empty(queue):
    return (isinstance(queue, dict) and queue.get("ok") is True
            and not queue.get("running") and not queue.get("pending"))


def execute_supervised(evidence, effective_graph, evidence_dir, permit_dir,
                       transport, permit_reader, permit_consumer, lease_factory,
                       vram_checker):
    """Future GPU boundary. Tests use doubles; this milestone never calls it live.

    The transport must declare ``manages_comfyui_lease=True``; the production
    WorkflowExecutor/ComfyHTTPRuntime submit path owns that established lease.
    The runner owns ``gpu_render`` for the full queue-check/submit/wait period.
    """
    if evidence.get("status") != "ready" or evidence.get("mode") != "CPU_PREFLIGHT":
        raise ExperimentBlocked("preflight_not_ready")
    validate_profile(evidence.get("profile"))
    if getattr(transport, "manages_comfyui_lease", False) is not True:
        raise ExperimentBlocked("comfyui_lease_owner_missing")
    graph_hash = canonical_sha256(effective_graph)
    permit = validate_bound_permit(permit_reader(permit_dir), evidence, graph_hash)

    attempt_path = os.path.join(evidence_dir, "submission_attempt.json")
    if os.path.exists(attempt_path):
        raise ExperimentBlocked("submission_state_exists_no_replay")

    lease = lease_factory(wait=0)
    try:
        if not lease.acquire():
            raise ExperimentBlocked("gpu_render_lease_unavailable")
        queue_before = transport.queue_state()
        if not _queue_empty(queue_before):
            raise ExperimentBlocked("comfyui_queue_not_empty_or_unreadable")
        vram = vram_checker(min_free_mib=evidence["profile"]["min_free_vram_mib"])
        if not isinstance(vram, dict) or vram.get("ok") is not True:
            raise ExperimentBlocked("render_vram_gate_failed")

        attempt = {
            "contract": CONTRACT, "experiment_id": EXPERIMENT_ID,
            "permit_id": permit["id"], "effective_graph_sha256": graph_hash,
            "state": "ATTEMPT_RECORDED", "submission_attempt_count": 1,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "queue_before": queue_before, "vram_gate": vram,
            "visual_review_status": "NOT_REVIEWED",
            "preservation_status": "UNVERIFIED",
        }
        _atomic_write_json(attempt_path, attempt, exclusive=True)
        consumed = permit_consumer(EXPERIMENT_ID, graph_hash, permit_dir, False)
        attempt["permit"] = consumed
        attempt["state"] = "PERMIT_CONSUMED_SUBMISSION_PENDING"
        _atomic_write_json(attempt_path, attempt)

        submitted_count = 0
        try:
            submitted_count += 1
            result = transport.execute(effective_graph)
        except BaseException as error:
            prompt_id = getattr(transport, "last_prompt_id", None)
            try:
                queue_after_error = transport.queue_state()
            except BaseException as queue_error:
                queue_after_error = {"ok": False, "reason": repr(queue_error)}
            history = None
            if prompt_id and callable(getattr(transport, "history", None)):
                try:
                    history = transport.history(prompt_id)
                except BaseException as history_error:
                    history = {"status": "unreadable", "error": repr(history_error)}
            attempt.update({"state": "SUBMISSION_UNCERTAIN", "error": repr(error),
                            "submission_attempt_count": submitted_count,
                            "prompt_id": prompt_id,
                            "queue_after_error": queue_after_error,
                            "history_reconciliation": history})
            _atomic_write_json(attempt_path, attempt)
            raise ExperimentBlocked("submission_uncertain_no_automatic_retry") from error

        attempt.update({
            "state": "EXECUTION_RECORDED", "submission_attempt_count": submitted_count,
            "result": result, "prompt_id": result.get("prompt_id") if isinstance(result, dict) else None,
            "queue_after": transport.queue_state(),
            "visual_review_status": "NOT_REVIEWED", "preservation_status": "UNVERIFIED",
        })
        _atomic_write_json(attempt_path, attempt)
        return attempt
    finally:
        lease.release()


def production_transport():
    """Constructed only by an explicitly authorized future CLI invocation."""
    from core.render.workflow_executor import WorkflowExecutor

    class _Transport:
        manages_comfyui_lease = True
        def __init__(self):
            self.executor = WorkflowExecutor()
            self.last_prompt_id = None
        def queue_state(self):
            return self.executor.comfy.queue_state()
        def history(self, prompt_id):
            return self.executor.comfy.history(prompt_id)
        def execute(self, graph):
            def remember(prompt_id):
                self.last_prompt_id = prompt_id
            return self.executor.execute(graph, "comfyui", on_submitted=remember)
    return _Transport()
