"""ArchitectOS v20.0 chat bridge.

Wires the three v20 engine modules into the live chat turn:

* ``ConversationalPlanEditor``  - incremental natural-language plan edits
* ``Architectural3DRenderer``   - instant CAD elevation / perspective sheet
* ``ComfyUIRenderBridge``       - ControlNet lineart + ComfyUI render

This module deliberately lives OUTSIDE ``core/planning/multifloor_v1/engine``
because that directory is overwritten wholesale by every release patch.
It only reads from the engine; it never modifies it.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

# --------------------------------------------------------------------------
# Active-project registry (per chat session, in-process only)
# --------------------------------------------------------------------------

_PLAN_STORE: dict = {}


def _session_key() -> str:
    try:
        from core.chat.session_registry_v1 import session_registry

        bundle = session_registry.current() or {}
        return str(bundle.get("session_id") or "default")
    except Exception:
        return "default"


def get_active():
    """Return ``{"project": ..., "saved": {...}}`` for this session, or None."""
    return _PLAN_STORE.get(_session_key())


def set_active(project, saved) -> None:
    _PLAN_STORE[_session_key()] = {
        "project": project,
        "saved": dict(saved or {}),
    }


def clear_active() -> None:
    _PLAN_STORE.pop(_session_key(), None)


# --------------------------------------------------------------------------
# Intent guards
# --------------------------------------------------------------------------

_RENDER_TOKENS = (
    "رندر",
    "نما",
    "پرسپکتیو",
    "پرسپكتيو",
    "سه بعدی",
    "سه‌بعدی",
    "3d",
    "elevation",
    "perspective",
    "render",
)

_EDIT_VERBS = (
    "حذف",
    "پاک کن",
    "اضافه",
    "ببر",
    "جابه",
    "جابجا",
    "بذار",
    "بگذار",
    "بردار",
    "عوض",
    "تغییر",
    "کنار",
    "بچرخون",
    "بزرگ‌تر",
    "کوچک‌تر",
)

# a bare "plan" request should still synthesise a fresh project, so an edit
# command must reference a *modification verb* and not ask for a new plan.
_NEW_PLAN_TOKENS = (
    "طراحی کن",
    "پلان جدید",
    "بساز",
    "ایجاد کن",
)


def is_render_request(text: str) -> bool:
    s = (text or "").lower()
    if not s:
        return False
    if any(t in s for t in _RENDER_TOKENS):
        # a render ask normally also asks to produce an image
        return True
    return False


def is_edit_command(text: str) -> bool:
    s = (text or "").strip().lower()
    if not s:
        return False
    if is_render_request(s):
        return False
    if not any(v in s for v in _EDIT_VERBS):
        return False
    if any(t in s for t in _NEW_PLAN_TOKENS) and "حذف" not in s:
        return False
    return True


# --------------------------------------------------------------------------
# Incremental editing
# --------------------------------------------------------------------------


def apply_edit(project, text):
    """Apply a chat edit command. Returns ``(project, actions)``.

    ``ConversationalPlanEditor`` only matches verb-first phrasing
    (``"حذف ستون B1"``), while users write noun-first
    (``"ستون B1 رو حذف کن"``). The original text is passed through
    untouched and a verb-first restatement is appended, so both phrasings
    resolve without editing the engine (which every patch overwrites).
    """
    from core.planning.multifloor_v1.engine import ConversationalPlanEditor

    return ConversationalPlanEditor.apply_chat_command(
        project, _normalize_for_editor(text)
    )


_COL_NOUN_FIRST = re.compile(
    r"(ستون\s*[A-Da-d]\s*[-–]?\s*[1-4])\s*(?:رو|را)?\s*(?:حذف|پاک)\s*(?:کن|کنی|کنید)?",
    re.I,
)
_ROOM_NOUN_FIRST = re.compile(
    r"(مطبخ|آشپزخانه\s*کثیف)\s*(?:رو|را)?\s*(?:حذف|پاک)\s*(?:کن|کنی|کنید)?",
    re.I,
)


def _normalize_for_editor(text: str) -> str:
    """Append a verb-first restatement so the engine's regexes can match."""
    s = text or ""
    extras = []

    for m in _COL_NOUN_FIRST.finditer(s):
        extras.append("حذف " + m.group(1))
    for m in _ROOM_NOUN_FIRST.finditer(s):
        extras.append("حذف " + m.group(1))

    if not extras:
        return s
    return s + " | " + " | ".join(extras)


def reexport(project, out_dir: str):
    """Re-write svg/dxf/json for an edited project and return the paths."""
    from core.planning.multifloor_v1.engine import (
        export_project_to_svg,
        export_project_to_dxf,
        export_project_to_json,
    )

    os.makedirs(out_dir, exist_ok=True)
    pid = str(project.project_id or "ARCH_PROJECT")

    svg_path = os.path.join(out_dir, pid + ".svg")
    dxf_path = os.path.join(out_dir, pid + ".dxf")
    json_path = os.path.join(out_dir, pid + ".json")

    with open(svg_path, "w", encoding="utf-8") as fh:
        fh.write(export_project_to_svg(project))
    with open(dxf_path, "w", encoding="utf-8") as fh:
        fh.write(export_project_to_dxf(project))
    with open(json_path, "w", encoding="utf-8") as fh:
        fh.write(export_project_to_json(project))

    return {
        "svg": os.path.abspath(svg_path),
        "dxf": os.path.abspath(dxf_path),
        "json": os.path.abspath(json_path),
    }


# --------------------------------------------------------------------------
# SVG lineart -> PNG rasteriser (no cairo / svglib on this machine)
# --------------------------------------------------------------------------

_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _f(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _stroke_width(node, default=1.0):
    return max(1, int(round(_f(node.get("stroke-width"), default))))


def svg_lineart_to_png(svg_path: str, png_path: str, supersample: int = 2) -> str:
    """Rasterise the ControlNet lineart SVG (rect/line/polygon) to PNG.

    The engine's lineart sheet uses only ``rect``, ``line`` and ``polygon``
    with plain hex fills/strokes, so a small dedicated rasteriser is enough
    and avoids a cairo/svglib dependency that is not installed here.
    """
    from PIL import Image, ImageDraw

    tree = ET.parse(svg_path)
    root = tree.getroot()

    vb = (root.get("viewBox") or "").replace(",", " ").split()
    if len(vb) == 4:
        width, height = int(float(vb[2])), int(float(vb[3]))
    else:
        width = int(_f(root.get("width"), 1280))
        height = int(_f(root.get("height"), 768))

    scale = max(1, int(supersample))
    img = Image.new("RGB", (width * scale, height * scale), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    def _tag(node):
        return node.tag.split("}")[-1].lower()

    for node in root.iter():
        tag = _tag(node)
        if tag not in ("rect", "line", "polygon", "polyline"):
            continue

        stroke = node.get("stroke")
        fill = node.get("fill")
        sw = _stroke_width(node) * scale
        outline = stroke if stroke and stroke.lower() not in ("none", "transparent") else None
        fill_c = fill if fill and fill.lower() not in ("none", "transparent") else None

        if tag == "rect":
            x = _f(node.get("x")) * scale
            y = _f(node.get("y")) * scale
            w = _f(node.get("width")) * scale
            h = _f(node.get("height")) * scale
            draw.rectangle([x, y, x + w, y + h], fill=fill_c, outline=outline, width=sw)

        elif tag == "line":
            pts = [
                _f(node.get("x1")) * scale,
                _f(node.get("y1")) * scale,
                _f(node.get("x2")) * scale,
                _f(node.get("y2")) * scale,
            ]
            draw.line(pts, fill=outline or "#FFFFFF", width=sw)

        else:  # polygon / polyline
            raw = _NUM.findall(node.get("points") or "")
            coords = [float(v) * scale for v in raw]
            pts = list(zip(coords[0::2], coords[1::2]))
            if len(pts) >= 2:
                if tag == "polygon":
                    draw.polygon(pts, fill=fill_c, outline=outline)
                    if outline and sw > 1:
                        draw.line(pts + [pts[0]], fill=outline, width=sw)
                else:
                    draw.line(pts, fill=outline or "#FFFFFF", width=sw)

    if scale > 1:
        img = img.resize((width, height), Image.LANCZOS)

    os.makedirs(os.path.dirname(os.path.abspath(png_path)), exist_ok=True)
    img.save(png_path, "PNG")
    return png_path


# --------------------------------------------------------------------------
# Render pipeline
# --------------------------------------------------------------------------


def build_render(project, text: str, out_dir: str) -> dict:
    """Produce facade sheet + controlnet lineart (+PNG). No ComfyUI call."""
    from core.planning.multifloor_v1.engine import (
        Architectural3DRenderer,
        ComfyUIRenderBridge,
    )

    os.makedirs(out_dir, exist_ok=True)
    pid = str(project.project_id or "ARCH_PROJECT")

    req = ComfyUIRenderBridge.parse_render_request_from_chat(text)
    camera_mode = req.get("camera_mode", "PERSPECTIVE_COURTYARD")
    style_key = req.get("style_key")

    facade_svg = os.path.join(out_dir, f"{pid}_facade_perspective.svg")
    Architectural3DRenderer.export_facade_and_perspective_svg(
        project, facade_svg, style_key
    )

    cn_svg = os.path.join(out_dir, f"{pid}_controlnet_{camera_mode}.svg")
    ComfyUIRenderBridge.export_controlnet_lineart_svg(project, cn_svg, camera_mode)

    cn_png = os.path.join(out_dir, f"{pid}_controlnet_{camera_mode}.png")
    svg_lineart_to_png(cn_svg, cn_png)

    return {
        "request": req,
        "camera_mode": camera_mode,
        "style_key": style_key,
        "facade_svg": os.path.abspath(facade_svg),
        "controlnet_svg": os.path.abspath(cn_svg),
        "controlnet_png": os.path.abspath(cn_png),
    }


def _comfy_json(url: str, payload=None, timeout: int = 20):
    import json
    import urllib.request

    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _pick(options, preferred, fallbacks=()):
    """Choose an installed model, preferring a known-good name."""
    opts = list(options or [])
    for name in (preferred,) + tuple(fallbacks):
        if name in opts:
            return name
    return opts[0] if opts else None


def _discover_models(base: str) -> dict:
    """Read the models actually installed on this ComfyUI, not assumed ones."""
    unets = _comfy_json(base + "/object_info/UNETLoader")["UNETLoader"]["input"]["required"]["unet_name"][0]
    clips = _comfy_json(base + "/object_info/DualCLIPLoader")["DualCLIPLoader"]["input"]["required"]
    vaes = _comfy_json(base + "/object_info/VAELoader")["VAELoader"]["input"]["required"]["vae_name"][0]
    cns = _comfy_json(base + "/object_info/ControlNetLoader")["ControlNetLoader"]["input"]["required"]["control_net_name"][0]

    clip_names = clips["clip_name1"][0]
    return {
        "unet": _pick(unets, "flux1-dev-fp8.safetensors"),
        "clip_l": _pick(clip_names, "clip_l.safetensors"),
        "t5": _pick(clip_names, "t5xxl_fp8_e4m3fn.safetensors", ("t5xxl_fp16.safetensors",)),
        "vae": _pick(vaes, "ae.safetensors"),
        "controlnet": _pick(cns, "flux1-dev-controlnet-union-pro-2.0-fp8.safetensors"),
    }


def _flux_controlnet_workflow(models: dict, uploaded_image: str, positive: str,
                              negative: str, width: int = 1280, height: int = 768,
                              seed: int = 12345, steps: int = 20,
                              strength: float = 0.75) -> dict:
    """A Flux + ControlNet-union graph.

    The engine's shipped workflow hardcodes ``sd_xl_base_1.0`` and
    ``control-lora-canny-rank256``, neither of which is installed on this
    machine, so it is rejected by ComfyUI with HTTP 400. This graph is built
    from the models actually present (Flux dev fp8 + union-pro) and mirrors
    the same ControlNet conditioning intent.
    """
    return {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": models["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "DualCLIPLoader",
              "inputs": {"clip_name1": models["clip_l"], "clip_name2": models["t5"],
                         "type": "flux"}},
        "3": {"class_type": "CLIPTextEncodeFlux",
              "inputs": {"clip": ["2", 0], "clip_l": positive[:400],
                         "t5xxl": positive, "guidance": 3.5}},
        "4": {"class_type": "FluxGuidance",
              "inputs": {"conditioning": ["3", 0], "guidance": 3.5}},
        "5": {"class_type": "CLIPTextEncodeFlux",
              "inputs": {"clip": ["2", 0], "clip_l": "", "t5xxl": negative, "guidance": 3.5}},
        "6": {"class_type": "LoadImage", "inputs": {"image": uploaded_image}},
        "7": {"class_type": "ControlNetLoader",
              "inputs": {"control_net_name": models["controlnet"]}},
        "8": {"class_type": "ControlNetApplyAdvanced",
              "inputs": {"positive": ["4", 0], "negative": ["5", 0],
                         "control_net": ["7", 0], "image": ["6", 0],
                         "strength": strength, "start_percent": 0.0,
                         "end_percent": 1.0, "vae": ["11", 0]}},
        "9": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "10": {"class_type": "KSampler",
               "inputs": {"model": ["1", 0], "positive": ["8", 0], "negative": ["8", 1],
                          "latent_image": ["9", 0], "seed": seed, "steps": steps,
                          "cfg": 1.0, "sampler_name": "euler",
                          "scheduler": "simple", "denoise": 1.0}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": models["vae"]}},
        "12": {"class_type": "VAEDecode",
               "inputs": {"samples": ["10", 0], "vae": ["11", 0]}},
        "13": {"class_type": "SaveImage",
               "inputs": {"images": ["12", 0], "filename_prefix": "architectos_v20"}},
    }


def _upload_image(base: str, png_path: str) -> str:
    import json
    import os
    import urllib.request
    import uuid

    boundary = "----ArchitectOSBoundary" + uuid.uuid4().hex
    name = os.path.basename(png_path)
    blob = open(png_path, "rb").read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + blob + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        base + "/upload/image", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=10800) as resp:
        return json.loads(resp.read().decode("utf-8")).get("name", name)


def run_comfyui(project, text: str, controlnet_png: str, out_dir: str,
                timeout_sec: int = 10800) -> dict:
    """Render through ComfyUI with a workflow built from installed models."""
    import json
    import os
    import time
    import urllib.parse
    import urllib.request

    base = (os.environ.get("ARCHITECTOS_COMFYUI_URL") or "http://127.0.0.1:8188").rstrip("/")
    os.makedirs(out_dir, exist_ok=True)

    try:
        models = _discover_models(base)
    except Exception as exc:
        return {"status": "COMFYUI_UNAVAILABLE",
                "reason": f"ComfyUI model discovery failed: {exc}",
                "controlnet_png_path": controlnet_png}

    from core.planning.multifloor_v1.engine import Architectural3DRenderer

    positive = Architectural3DRenderer.build_photorealistic_prompt(project, text)
    negative = "blurry, text, watermark, distorted, deformed, cartoon, low quality"

    try:
        uploaded = _upload_image(base, controlnet_png)
        workflow = _flux_controlnet_workflow(models, uploaded, positive, negative)

        wf_path = os.path.join(out_dir, f"{project.project_id}_comfyui_flux_workflow.json")
        with open(wf_path, "w", encoding="utf-8") as fh:
            json.dump(workflow, fh, ensure_ascii=False, indent=2)

        queued = _comfy_json(base + "/prompt",
                             {"prompt": workflow, "client_id": "architectos-v20"})
        pid = queued.get("prompt_id")
        if not pid:
            return {"status": "COMFYUI_REJECTED", "detail": queued,
                    "controlnet_png_path": controlnet_png, "workflow_json_path": wf_path}

        deadline = time.time() + max(30, int(timeout_sec))
        while time.time() < deadline:
            hist = _comfy_json(f"{base}/history/{pid}", timeout=10800)
            if pid in hist:
                entry = hist[pid]
                state = entry.get("status", {}).get("status_str")
                if state == "error":
                    msg = ""
                    for m in entry.get("status", {}).get("messages", []):
                        if m and m[0] == "execution_error":
                            msg = (m[1] or {}).get("exception_message", "")
                    return {"status": "COMFYUI_ERROR", "detail": msg,
                            "prompt_id": pid, "controlnet_png_path": controlnet_png,
                            "workflow_json_path": wf_path}

                images = []
                for _nid, out in (entry.get("outputs") or {}).items():
                    images.extend(out.get("images") or [])
                if images:
                    img = images[0]
                    query = urllib.parse.urlencode({
                        "filename": img.get("filename"),
                        "subfolder": img.get("subfolder", ""),
                        "type": img.get("type", "output"),
                    })
                    local = os.path.join(out_dir, f"{project.project_id}_comfyui_render.png")
                    with urllib.request.urlopen(f"{base}/view?{query}", timeout=10800) as resp:
                        open(local, "wb").write(resp.read())
                    return {"status": "COMFYUI_RENDERED", "prompt_id": pid,
                            "render_png_path": os.path.abspath(local),
                            "controlnet_png_path": controlnet_png,
                            "workflow_json_path": wf_path,
                            "models": models}
            time.sleep(3)

        return {"status": "COMFYUI_TIMEOUT", "prompt_id": pid,
                "controlnet_png_path": controlnet_png,
                "workflow_json_path": wf_path, "models": models}

    except Exception as exc:
        return {"status": "COMFYUI_ERROR", "detail": str(exc),
                "controlnet_png_path": controlnet_png}
