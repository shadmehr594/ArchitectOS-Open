#!/usr/bin/env python3
"""
Localhost ComfyUI API Client, Live Schema Validator (/object_info), Multipart Image Uploader
(/upload/image), and 5-Stage Execution & VRAM Profiler.
Strictly connects to 127.0.0.1:8188. Never modifies unrelated services (no Ollama touching).
"""
from __future__ import annotations
import hashlib
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List, Optional, Tuple


STAGE_BY_CLASS_TYPE = {
    "UNETLoader": "model_loading",
    "DualCLIPLoader": "model_loading",
    "VAELoader": "model_loading",
    "CLIPVisionLoader": "model_loading",
    "LoraLoaderModelOnly": "model_loading",
    "ModelPatchLoader": "model_loading",
    "ControlNetLoader": "model_loading",
    "LoadDA3Model": "model_loading",
    "LoadImage": "conditioning",
    "LoadImageMask": "conditioning",
    "VAEEncode": "conditioning",
    "SetLatentNoiseMask": "conditioning",
    "CLIPVisionEncode": "conditioning",
    "USOStyleReference": "conditioning",
    "CLIPTextEncode": "conditioning",
    "DA3Inference": "conditioning",
    "DA3Render": "conditioning",
    "ControlNetApplyAdvanced": "conditioning",
    "KSampler": "sampler_execution",
    "VAEDecode": "vae_decoding",
    "VAEDecodeTiled": "vae_decoding",
    "SaveImage": "final_output_processing",
}


class LocalComfyClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8188") -> None:
        parsed = urllib.parse.urlparse(base_url)
        if parsed.hostname not in ("127.0.0.1", "localhost"):
            raise ValueError(f"Security constraint: ComfyUI URL must be localhost, got {base_url}")
        self.base_url = base_url.rstrip("/")
        self.client_id = f"architectos_{uuid.uuid4().hex[:10]}"

    def get_system_stats(self, timeout: float = 4.0) -> Dict[str, Any]:
        req = urllib.request.Request(f"{self.base_url}/system_stats", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def sample_vram_mb(self) -> Dict[str, Optional[float]]:
        """Reads real VRAM counters from ComfyUI /system_stats (in MB)."""
        try:
            stats = self.get_system_stats(timeout=2.5)
            devs = stats.get("devices") or []
            if not devs:
                return {"vram_total_mb": None, "vram_free_mb": None, "vram_used_mb": None}
            d0 = devs[0]
            total = d0.get("vram_total")
            free = d0.get("vram_free")
            if total is not None and free is not None:
                total_mb = round(float(total) / (1024 * 1024), 1)
                free_mb = round(float(free) / (1024 * 1024), 1)
                return {
                    "device_name": d0.get("name", "unknown"),
                    "vram_total_mb": total_mb,
                    "vram_free_mb": free_mb,
                    "vram_used_mb": round(total_mb - free_mb, 1),
                }
        except Exception:
            pass
        return {"vram_total_mb": None, "vram_free_mb": None, "vram_used_mb": None}

    def get_object_info(self, timeout: float = 10.0) -> Dict[str, Any]:
        req = urllib.request.Request(f"{self.base_url}/object_info", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def validate_workflow_schema(
        self,
        workflow: Dict[str, Any],
        object_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Validates every node class_type and every required input key against
        ComfyUI's live `/object_info` schema (or offline known schema rules).
        Specifically catches missing `temporal_size` / `temporal_overlap` on VAEDecodeTiled.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Built-in mandatory schema checks for known ComfyUI 0.29.0 nodes
        mandatory_by_class = {
            "VAEDecodeTiled": ["samples", "vae", "tile_size", "overlap", "temporal_size", "temporal_overlap"],
            "VAEDecode": ["samples", "vae"],
            "KSampler": ["model", "seed", "steps", "cfg", "sampler_name", "scheduler", "positive", "negative", "latent_image", "denoise"],
            "ControlNetApplyAdvanced": ["positive", "negative", "control_net", "image", "vae", "strength", "start_percent", "end_percent"],
            "USOStyleReference": ["model", "model_patch", "clip_vision_output"],
            "LoadImage": ["image"],
            "LoadImageMask": ["image", "channel"],
            "SetLatentNoiseMask": ["samples", "mask"],
        }

        for node_id, node in workflow.items():
            ctype = node.get("class_type")
            inputs = node.get("inputs", {})
            if not ctype:
                errors.append(f"Node {node_id} is missing class_type.")
                continue

            # Check built-in known mandatory fields
            for req_key in mandatory_by_class.get(ctype, []):
                if req_key not in inputs:
                    errors.append(f"Node {node_id} ({ctype}) is missing mandatory input `{req_key}`.")

            # Validate internal graph links [source_node_id, output_idx]
            for k, val in inputs.items():
                if isinstance(val, list) and len(val) == 2:
                    ref_id = str(val[0])
                    if ref_id not in workflow:
                        errors.append(f"Node {node_id}.{k} references non-existent node `{ref_id}`.")

            # Live /object_info check when ComfyUI server is reachable
            if object_info is not None:
                if ctype not in object_info:
                    errors.append(f"Node {node_id} class `{ctype}` is not registered in ComfyUI /object_info.")
                else:
                    req_schema = object_info[ctype].get("input", {}).get("required", {})
                    for req_key in req_schema.keys():
                        if req_key not in inputs:
                            errors.append(
                                f"Node {node_id} ({ctype}) missing required input `{req_key}` per live /object_info."
                            )

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def upload_image(
        self,
        file_path: pathlib.Path,
        target_filename: Optional[str] = None,
        overwrite: bool = True,
    ) -> Dict[str, Any]:
        """
        Uploads a local image file to ComfyUI via POST /upload/image (multipart/form-data)
        and verifies that the uploaded image bytes match the local source SHA-256.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Input image does not exist: {file_path}")

        upload_name = target_filename or file_path.name
        raw_bytes = file_path.read_bytes()
        local_sha = hashlib.sha256(raw_bytes).hexdigest()

        boundary = f"----ArchitectOSBoundary{uuid.uuid4().hex}"
        lines: List[bytes] = []

        # image field
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(
            f'Content-Disposition: form-data; name="image"; filename="{upload_name}"\r\n'.encode("utf-8")
        )
        lines.append(b"Content-Type: image/png\r\n\r\n")
        lines.append(raw_bytes + b"\r\n")

        # overwrite field
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(b'Content-Disposition: form-data; name="overwrite"\r\n\r\n')
        lines.append((b"true" if overwrite else b"false") + b"\r\n")

        # type field
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(b'Content-Disposition: form-data; name="type"\r\n\r\n')
        lines.append(b"input\r\n")
        lines.append(f"--{boundary}--\r\n".encode("utf-8"))

        body = b"".join(lines)
        req = urllib.request.Request(
            f"{self.base_url}/upload/image",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10800) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        server_name = result.get("name", upload_name)
        # Verify by fetching back from /view?filename=...&type=input
        view_q = urllib.parse.urlencode({"filename": server_name, "type": "input", "subfolder": result.get("subfolder", "")})
        vreq = urllib.request.Request(f"{self.base_url}/view?{view_q}", method="GET")
        with urllib.request.urlopen(vreq, timeout=10800) as vresp:
            roundtrip_bytes = vresp.read()
        remote_sha = hashlib.sha256(roundtrip_bytes).hexdigest()

        return {
            "uploaded_name": server_name,
            "local_sha256": local_sha,
            "remote_sha256": remote_sha,
            "verified_exact_bytes": local_sha == remote_sha,
        }

    def free_comfy_memory(self, unload_models: bool = True) -> bool:
        """Calls ComfyUI's own /free endpoint (never touches Ollama or external services)."""
        try:
            payload = json.dumps({"unload_models": unload_models, "free_memory": True}).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/free",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def execute_single_workflow_monitored(
        self,
        workflow: Dict[str, Any],
        output_save_dir: pathlib.Path,
        timeout_sec: float = 10800.0,
    ) -> Dict[str, Any]:
        """
        Submits strictly ONE workflow job to ComfyUI, polls execution state and VRAM usage,
        stops immediately if ComfyUI reports an execution error, and downloads saved outputs.
        """
        output_save_dir.mkdir(parents=True, exist_ok=True)
        vram_before = self.sample_vram_mb()
        t_start = time.time()

        payload = json.dumps({"prompt": workflow, "client_id": self.client_id}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10800) as resp:
                submit_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            return {
                "status": "PROMPT_REJECTED_BY_COMFYUI",
                "http_code": exc.code,
                "error_detail": err_body,
                "vram_before": vram_before,
            }

        prompt_id = submit_data.get("prompt_id")
        if not prompt_id:
            return {"status": "INVALID_PROMPT_RESPONSE", "response": submit_data}

        peak_vram_used_mb: float = vram_before.get("vram_used_mb") or 0.0
        vram_samples: List[Dict[str, Any]] = []
        history_entry: Optional[Dict[str, Any]] = None
        stage_durations_sec: Dict[str, float] = {
            "model_loading": 0.0,
            "conditioning": 0.0,
            "sampler_execution": 0.0,
            "vae_decoding": 0.0,
            "final_output_processing": 0.0,
        }
        observed_node_events = False
        last_poll_t = time.time()

        while (time.time() - t_start) < timeout_sec:
            now_t = time.time()
            dt = max(0.0, now_t - last_poll_t)
            last_poll_t = now_t

            v_now = self.sample_vram_mb()
            used_now = v_now.get("vram_used_mb")
            if used_now is not None and used_now > peak_vram_used_mb:
                peak_vram_used_mb = used_now
            vram_samples.append({"t_sec": round(now_t - t_start, 2), **v_now})

            # Poll /history/<prompt_id>
            hreq = urllib.request.Request(f"{self.base_url}/history/{prompt_id}", method="GET")
            with urllib.request.urlopen(hreq, timeout=5.0) as hresp:
                hdata = json.loads(hresp.read().decode("utf-8"))
            if prompt_id in hdata:
                history_entry = hdata[prompt_id]
                break
            time.sleep(0.5)

        total_elapsed = round(time.time() - t_start, 2)
        if history_entry is None:
            return {
                "status": "TIMEOUT_STALLED",
                "prompt_id": prompt_id,
                "elapsed_sec": total_elapsed,
                "peak_vram_used_mb": peak_vram_used_mb,
            }

        status_block = history_entry.get("status", {})
        if status_block.get("status_str") == "error" or not status_block.get("completed", True):
            return {
                "status": "EXECUTION_ERROR",
                "prompt_id": prompt_id,
                "elapsed_sec": total_elapsed,
                "peak_vram_used_mb": peak_vram_used_mb,
                "status_detail": status_block,
            }

        # Download output images generated by SaveImage nodes
        downloaded_files: List[str] = []
        outputs_block = history_entry.get("outputs", {})
        for node_id, node_out in outputs_block.items():
            for img_meta in node_out.get("images", []):
                fname = img_meta.get("filename")
                subfolder = img_meta.get("subfolder", "")
                itype = img_meta.get("type", "output")
                if fname:
                    q = urllib.parse.urlencode({"filename": fname, "subfolder": subfolder, "type": itype})
                    ireq = urllib.request.Request(f"{self.base_url}/view?{q}", method="GET")
                    with urllib.request.urlopen(ireq, timeout=10800) as iresp:
                        img_bytes = iresp.read()
                    local_out = output_save_dir / fname
                    local_out.write_bytes(img_bytes)
                    downloaded_files.append(str(local_out))

        # Parse node-level execution timestamps from ComfyUI status.messages if emitted
        msgs = status_block.get("messages", [])
        node_start_ts: Optional[float] = None
        current_stage: Optional[str] = None
        for entry in msgs:
            if isinstance(entry, list) and len(entry) == 2 and isinstance(entry[1], dict):
                ev_type, ev_data = entry[0], entry[1]
                ts_ms = ev_data.get("timestamp")
                node_id = str(ev_data.get("node", "")) if ev_data.get("node") is not None else ""
                if ts_ms is not None:
                    ts_sec = float(ts_ms) / 1000.0
                    if node_start_ts is not None and current_stage in stage_durations_sec:
                        stage_durations_sec[current_stage] = round(
                            stage_durations_sec[current_stage] + max(0.0, ts_sec - node_start_ts), 3
                        )
                        observed_node_events = True
                    if ev_type in ("execution_start", "executing") and node_id in workflow:
                        ctype = workflow[node_id].get("class_type", "")
                        current_stage = STAGE_BY_CLASS_TYPE.get(ctype, "conditioning")
                        node_start_ts = ts_sec
                    elif ev_type in ("execution_success", "execution_cached"):
                        node_start_ts = ts_sec

        return {
            "status": "COMPLETED",
            "prompt_id": prompt_id,
            "elapsed_sec": total_elapsed,
            "vram_before": vram_before,
            "peak_vram_used_mb": peak_vram_used_mb,
            "per_stage_timing_sec": stage_durations_sec if observed_node_events else "UNAVAILABLE_NO_NODE_TIMESTAMPS_IN_HISTORY",
            "downloaded_outputs": downloaded_files,
            "status_messages": msgs,
        }
