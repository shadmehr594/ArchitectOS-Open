"""V25_PLAN_SESSION — persistent per-project plan + render session state.

Owns the multi-turn state machine for the v25 parametric engine:

* ``active_plan_params``  — the live parametric plan configuration.
* ``active_plan_files``   — urls of the last exported svg/png/dxf/json.
* ``active_render_state`` — floors / style / materials / lighting / camera and
  the last day + last render paths.

State is a plain dict persisted to ``<project_dir>/session_state.json`` so an
unlimited number of plan edits survives a process restart.

Routing rules (the whole point of the module):

1. A design prompt with no active plan  -> ``parse_architectural_prompt``.
2. A modification prompt with an active plan -> ``apply_incremental_plan_edit``.
3. Both cases re-synthesize and export ``plan_rev_<N>.{svg,dxf,png,json}`` and
   return the image plus clickable download links — never a text-only reply.

The engine is imported through a scoped ``sys.path`` entry, exactly like the
server does, so the parametric package's ``engine``/``ui`` namespaces can never
shadow this project's ``core`` or ``ui`` packages.
"""

from __future__ import annotations

import importlib
import json
import os
import pathlib
import sys
from typing import Any, Dict, Optional, Tuple

CONTRACT = "V25PlanSessionV1"
VERSION = "1.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ENGINE_ROOT = REPO_ROOT / "core" / "planning" / "multifloor_v1"
PROJECTS_ROOT = REPO_ROOT / "outputs" / "plans"

PLAN_STATE_FILENAME = "session_state.json"

_ENGINE = None


# ---------------------------------------------------------------------------
# Engine access
# ---------------------------------------------------------------------------

def load_engine():
    """Import the parametric engine once, leaving ``sys.path`` unchanged."""

    global _ENGINE

    if _ENGINE is not None:
        return _ENGINE

    root = str(ENGINE_ROOT)

    if not os.path.isdir(root):
        raise RuntimeError("multifloor_engine_missing: %s" % root)

    if root not in sys.path:
        sys.path.insert(0, root)

    try:
        engine = importlib.import_module("engine")
    finally:
        while root in sys.path:
            sys.path.remove(root)

    origin = os.path.abspath(getattr(engine, "__file__", "") or "")

    if not origin.startswith(os.path.abspath(root) + os.sep):
        raise RuntimeError("multifloor_engine_origin_mismatch: %s" % origin)

    _ENGINE = engine

    return _ENGINE


def parser():
    """The v25 natural-language design parser."""

    # The submodule import only resolves once the package itself has been
    # loaded through the scoped sys.path entry, so this is never called cold.
    load_engine()

    return importlib.import_module("engine.nl_design_parser")


# ---------------------------------------------------------------------------
# Session persistence
# ---------------------------------------------------------------------------

def project_dir(project_id: str) -> pathlib.Path:
    """Directory that owns one project's plan revisions and session state."""

    safe = "".join(
        ch for ch in str(project_id or "default")
        if ch.isalnum() or ch in ("-", "_", ".")
    ) or "default"

    return PROJECTS_ROOT / safe


def state_path(project_id: str) -> pathlib.Path:
    return project_dir(project_id) / PLAN_STATE_FILENAME


def empty_state(project_id: str) -> Dict[str, Any]:
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "project_id": str(project_id or "default"),
        "active_plan_params": {},
        "active_plan_files": {},
        "active_render_state": {},
        # KROCKI_SITE_STATE_V27 — the parsed land survey (DXF/DWG) that the
        # next plan-creation turn builds on. `None` until a krocki is uploaded.
        "active_site_krocki": None,
        "plan_revision": 0,
        "render_revision": 0,
    }


def load_state(project_id: str) -> Dict[str, Any]:
    """Read the persisted state, or a clean one when nothing is on disk."""

    path = state_path(project_id)

    if not path.is_file():
        return empty_state(project_id)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty_state(project_id)

    if not isinstance(data, dict):
        return empty_state(project_id)

    state = empty_state(project_id)
    state.update(data)

    for key in ("active_plan_params", "active_plan_files", "active_render_state"):
        if not isinstance(state.get(key), dict):
            state[key] = {}

    return state


def save_state(project_id: str, state: Dict[str, Any]) -> pathlib.Path:
    path = state_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def set_active_site_krocki(project_id: str, krocki_info: Dict[str, Any]) -> pathlib.Path:
    """Persist a parsed land survey so the next design turn builds on it.

    The krocki is a SITE fact, not a plan fact: it survives a new-plan turn
    (which replaces `active_plan_params`) because the land does not change
    when the building does.
    """

    state = load_state(project_id)
    state["active_site_krocki"] = krocki_info
    return save_state(project_id, state)


def clear_active_site_krocki(project_id: str) -> pathlib.Path:
    state = load_state(project_id)
    state["active_site_krocki"] = None
    return save_state(project_id, state)


# ---------------------------------------------------------------------------
# KROCKI_GLOBAL_STATE_V27_1
#
# The upload route can be reached before a project is open, and the browser
# may send `project_id = "null"`. Both land on the `"default"` bucket, but the
# design turn that follows is keyed by a REAL project id — so a site fact
# stored only under `"default"` would be invisible to it and the plan would be
# built on the 10x20 m fallback while the user is looking at their own parcel.
#
# A single global record, read as a fallback, closes that gap without letting
# one project's survey leak into another: the per-project state always wins.
# ---------------------------------------------------------------------------

GLOBAL_KROCKI_DIRNAME = pathlib.Path("data") / "projects"
GLOBAL_KROCKI_FILENAME = "_global_active_krocki.json"


def _global_krocki_path(repo_root: Optional[pathlib.Path] = None) -> pathlib.Path:
    root = pathlib.Path(repo_root) if repo_root else REPO_ROOT
    return root / GLOBAL_KROCKI_DIRNAME / GLOBAL_KROCKI_FILENAME


def save_active_krocki_state(
    repo_root,
    project_id: str,
    krocki_info: Dict[str, Any],
) -> Dict[str, str]:
    """Persist the survey BOTH per project and globally.

    Returns the two paths so the caller can report them.
    """

    project_path = set_active_site_krocki(project_id, krocki_info)

    global_path = _global_krocki_path(repo_root)

    global_path.parent.mkdir(parents=True, exist_ok=True)

    global_path.write_text(
        json.dumps(
            {
                "contract": "GlobalActiveKrockiV271",
                "version": "1.1",
                "project_id": str(project_id or "default"),
                "active_site_krocki": krocki_info,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "project_state_path": str(project_path),
        "global_state_path": str(global_path),
    }


def _as_krocki_payload(payload) -> Optional[Dict[str, Any]]:
    """Accept BOTH shapes this file can find on disk.

    KROCKI_DUAL_SHAPE_V29 — `plan_session_v25` writes
    ``{"active_site_krocki": {...}}``, but v29's reader writes the survey
    dict ITSELF into `_global_active_krocki.json`. Reading only the wrapper
    made a perfectly good 237.15 m² survey invisible and the plan silently
    fell back to the 10x20 default.
    """

    if not isinstance(payload, dict) or not payload:

        return None

    nested = payload.get("active_site_krocki")

    if isinstance(nested, dict) and nested:

        return nested

    # A bare survey: it must look like one, not like some other state file.
    if "site_area_m2" in payload or (
        "width_m" in payload and "length_m" in payload
    ):

        return payload

    return None


def load_active_krocki_state(
    repo_root,
    project_id: str,
) -> Optional[Dict[str, Any]]:
    """The project's own survey, else the global one.

    Three stores are consulted because two writers exist:
      1. this module's plan-session state  (`outputs/plans/<pid>/...`)
      2. v29's reader store                (`data/projects/<pid>/...`)
      3. the global record                 (either shape)
    """

    state = load_state(project_id)

    krocki = _as_krocki_payload(state)

    if krocki:

        return krocki

    # v29's reader keeps the per-project copy next to the global record.
    alt_path = (
        pathlib.Path(repo_root)
        / GLOBAL_KROCKI_DIRNAME
        / str(project_id or "default")
        / PLAN_STATE_FILENAME
    )

    if alt_path.is_file():

        try:

            krocki = _as_krocki_payload(
                json.loads(alt_path.read_text(encoding="utf-8"))
            )

        except (OSError, ValueError):

            krocki = None

        if krocki:

            return krocki

    global_path = _global_krocki_path(repo_root)

    if not global_path.is_file():

        return None

    try:

        payload = json.loads(global_path.read_text(encoding="utf-8"))

    except (OSError, ValueError):

        return None

    return _as_krocki_payload(payload)


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def rasterize_svg(svg_path: pathlib.Path, png_path: pathlib.Path, dpi: int = 110) -> bool:
    """Rasterise a plan sheet to PNG.

    Returns False when no rasteriser is installed — the caller records
    ``png_unavailable`` rather than pretending an image exists.
    """

    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
    except Exception:
        return False

    try:
        drawing = svg2rlg(str(svg_path))

        if drawing is None:
            return False

        renderPM.drawToFile(drawing, str(png_path), fmt="PNG", dpi=dpi)

        return png_path.is_file() and png_path.stat().st_size > 0

    except Exception:
        return False


def _asset_url(project_id: str, filename: str) -> str:
    """URL served by the existing /planning/drawing/<path:filename> route."""

    return "/planning/drawing/%s/renders/%s" % (project_id, filename)


def export_plan_revision(
    project_id: str,
    project,
    revision: int,
) -> Dict[str, Any]:
    """Write svg/dxf/json/png for one revision and return urls + paths."""

    engine = load_engine()

    renders_dir = project_dir(project_id) / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)

    stem = "plan_rev_%d" % int(revision)

    svg_path = renders_dir / (stem + ".svg")
    dxf_path = renders_dir / (stem + ".dxf")
    json_path = renders_dir / (stem + ".json")
    png_path = renders_dir / (stem + ".png")

    engine.export_project_to_svg(project, str(svg_path))
    engine.export_project_to_dxf(project, str(dxf_path))
    engine.export_project_to_json(project, str(json_path))

    # ==========================================================
    # PLAN_PNG_RENDERER_V27 — Pillow, not a generic SVG rasteriser
    #
    # `rasterize_svg` hands the sheet to svglib, which lays out `<text>`
    # WITHOUT bidi reordering: every Persian label came out mirrored. v27
    # ships `render_project_to_png_pillow`, which shapes the string itself
    # (`_reshape_persian_rtl_full`) and draws it with `ImageFont.Layout.BASIC`,
    # so the labels are connected and right-to-left by construction.
    #
    # The renderer that actually produced the file is recorded, so a silent
    # downgrade to the mirrored path can never be mistaken for success.
    # ==========================================================

    png_renderer = None

    png_ok = False

    try:

        engine.render_project_to_png_pillow(project, str(png_path))

        png_ok = png_path.is_file() and png_path.stat().st_size > 0

        png_renderer = "pillow_rtl" if png_ok else None

    except Exception as _png_exc:  # noqa: BLE001

        print("⚠️ PLAN PILLOW PNG FAILED:", _png_exc)

    if not png_ok:

        # Truthful fallback. The sheet still exists, but the labels may be
        # mirrored — `png_renderer` says so instead of hiding it.
        png_ok = rasterize_svg(svg_path, png_path)

        png_renderer = "svglib_fallback" if png_ok else None

    files = {
        "svg_url": _asset_url(project_id, svg_path.name),
        "dxf_url": _asset_url(project_id, dxf_path.name),
        "json_url": _asset_url(project_id, json_path.name),
        "png_url": _asset_url(project_id, png_path.name) if png_ok else None,
        "svg_path": str(svg_path),
        "dxf_path": str(dxf_path),
        "json_path": str(json_path),
        "png_path": str(png_path) if png_ok else None,
        "png_available": bool(png_ok),
        "png_renderer": png_renderer,
    }

    return files


# ---------------------------------------------------------------------------
# Plan routing
# ---------------------------------------------------------------------------

def is_render_request(text: str) -> bool:
    """A render turn is never a plan turn."""

    lowered = str(text or "").lower()

    return any(
        token in lowered
        for token in ("رندر", "render", "کامفی", "comfy", "نورپردازی شب")
    )


def _wants_new_plan(text: str) -> bool:
    lowered = str(text or "").lower()

    return any(
        token in lowered
        for token in ("پلان جدید", "از اول", "جدید طراحی", "پلان متفاوت")
    )


def route_plan_turn(project_id: str, text: str) -> Dict[str, Any]:
    """Apply one plan turn: create, or edit the active plan.

    Returns the response payload the chat UI needs: the rendered plan image
    plus clickable svg/dxf/png links. It never returns a text-only answer.
    """

    engine = load_engine()
    nl = parser()

    state = load_state(project_id)

    params = state.get("active_plan_params") or {}

    # KROCKI_GLOBAL_STATE_V27_1 — the project's own survey, else the global
    # one written by an upload that arrived before a project was open.
    active_site_krocki = (
        state.get("active_site_krocki")
        or load_active_krocki_state(REPO_ROOT, project_id)
    )

    text = str(text or "").strip()

    mode = None

    # ==========================================================
    # PLAN_CREATE_VS_EDIT_V27
    #
    # A NEW building/site specification is ALWAYS a create turn — even when a
    # plan is already active. The v25 rule asked `is_plan_modification_prompt`
    # first whenever params existed, and that detector matches ordinary design
    # vocabulary (`طبقه`, `ویلایی`, `آشپزخانه`). Measured consequence:
    # "یک ساختمان ویلایی با ۱۵۰ متر مربع در زمینی به مساحت ۲۵۰ متر مربع …"
    # was applied as an INCREMENTAL EDIT to the previous plan, so the new
    # 250 m² site was silently ignored and the old footprint was kept.
    #
    # `is_new_plan_creation_prompt` looks for a full site/building
    # specification and for the absence of an explicit edit verb, so the two
    # intents are separated before either handler runs.
    # ==========================================================

    if nl.is_new_plan_creation_prompt(text):

        params = nl.parse_architectural_prompt(
            text,
            active_site_krocki=active_site_krocki,
        )

        mode = "create"

    elif params and nl.is_plan_modification_prompt(text):

        params = nl.apply_incremental_plan_edit(
            params,
            text,
            active_site_krocki=active_site_krocki,
        )

        mode = "edit"

    elif not params and nl.is_architectural_design_prompt(text):

        params = nl.parse_architectural_prompt(
            text,
            active_site_krocki=active_site_krocki,
        )

        mode = "create"

    else:

        return {
            "status": "not_a_plan_turn",
            "contract": CONTRACT,
            "reason": "no_design_or_modification_signal",
        }

    project = engine.ParametricArchitecturalSynthesizer().synthesize_from_params(params)

    revision = int(state.get("plan_revision", 0)) + 1

    files = export_plan_revision(project_id, project, revision)

    state["active_plan_params"] = params
    state["active_plan_files"] = files
    state["plan_revision"] = revision

    save_state(project_id, state)

    floors = getattr(project, "floors", []) or []
    first = floors[0] if floors else None

    return {
        "status": "ok",
        "contract": CONTRACT,
        "mode": mode,
        "plan_revision": revision,
        "image_url": files.get("png_url") or files.get("svg_url"),
        "assets": {
            "svg": files.get("svg_url"),
            "dxf": files.get("dxf_url"),
            "png": files.get("png_url"),
            "json": files.get("json_url"),
        },
        # PLAN_PHYSICAL_PATHS_V27 — the exact Windows paths on disk, beside
        # the served URLs. A browser link is not the file the user opens in
        # AutoCAD, and the v25 reply only ever gave the link.
        "local_paths": {
            "svg": files.get("svg_path"),
            "dxf": files.get("dxf_path"),
            "png": files.get("png_path"),
            "json": files.get("json_path"),
        },
        "png_renderer": files.get("png_renderer"),
        "active_site_krocki": active_site_krocki,
        "downloads": [
            {"label": "SVG", "url": files.get("svg_url")},
            {"label": "DXF", "url": files.get("dxf_url")},
            {"label": "PNG", "url": files.get("png_url")},
            {"label": "JSON", "url": files.get("json_url")},
        ],
        "plan": {
            "project_id": getattr(project, "project_id", None),
            "title_fa": getattr(project, "project_title_fa", None),
            "floors": len(floors),
            "rooms": len(getattr(first, "rooms", []) or []),
            "columns": len(getattr(first, "columns", []) or []),
            "doors": len(getattr(first, "doors", []) or []),
            "windows": len(getattr(first, "windows", []) or []),
            "audit_status": getattr(
                getattr(project, "audit", None), "status", None
            ).value if getattr(getattr(project, "audit", None), "status", None) else None,
        },
        "active_plan_params": params,
    }


# ---------------------------------------------------------------------------
# Render routing (plan -> render handoff, multi-turn render editing)
# ---------------------------------------------------------------------------

def route_render_turn(
    project_id: str,
    text: str,
    *,
    render_fn=None,
) -> Dict[str, Any]:
    """Turn a render request into a render state and a dispatch decision.

    ``render_fn`` is the actual ComfyUI executor. It is injected rather than
    imported so the routing decision can be verified on CPU without a GPU; a
    caller that has a live pipeline passes the real executor in.
    """

    nl = parser()

    state = load_state(project_id)

    plan_params = state.get("active_plan_params") or {}
    prev_render = state.get("active_render_state") or {}

    if not plan_params and not prev_render:
        return {
            "status": "no_plan",
            "contract": CONTRACT,
            "reason": "no_active_plan_and_no_previous_render",
        }

    render_state = nl.build_render_state_from_plan_or_prev_render(
        plan_params, text, prev_render
    )

    floors = int(render_state.get("floors") or 1)
    lighting = render_state.get("lighting")
    has_day = bool(render_state.get("last_day_render_path"))

    # Case A — locked night relight of an existing day render.
    if lighting == "night" and has_day:
        chain = "locked_night_relight"
        render_state["use_locked_night_chain"] = True
        render_state["night_denoise"] = 0.30
        scaffold_name = None

    # Case B — everything else is a fresh conditioned render.
    else:
        chain = "conditioned_t2i"
        render_state["use_locked_night_chain"] = False
        scaffold_name = None

        if floors >= 6:
            chain = "exact_floors_t2i"
            render_state["scaffold_path"] = build_floor_scaffold(floors)
            scaffold_name = os.path.basename(render_state["scaffold_path"])

    revision = int(state.get("render_revision", 0)) + 1
    render_state["render_revision"] = revision

    dispatch = {
        "status": "dispatched" if render_fn else "planned",
        "chain": chain,
        "floors": floors,
        "lighting": lighting,
        "style": render_state.get("style"),
        "materials": render_state.get("materials"),
        "camera_view": render_state.get("camera_view"),
        "use_locked_night_chain": bool(render_state.get("use_locked_night_chain")),
        "scaffold": scaffold_name,
        "source_day_render": render_state.get("last_day_render_path"),
    }

    if render_fn is not None:

        result = render_fn(render_state) or {}

        path = result.get("image_path")

        if path:
            render_state["last_render_path"] = path
            if lighting == "day":
                render_state["last_day_render_path"] = path
            dispatch["image_path"] = path

        dispatch["renderer"] = {
            k: v for k, v in result.items() if k != "image_path"
        }

    state["active_render_state"] = render_state
    state["render_revision"] = revision

    save_state(project_id, state)

    dispatch["render_state"] = render_state

    return dispatch


def build_floor_scaffold(floors: int) -> str:
    """Stage the exact-N-storey wireframe into ComfyUI's input directory."""

    from config import runtime_config as RC

    from core.render.experimental.architectos_v22_highrise_night_v1 import (
        synthesize_exact_n_story_tower_controlnet,
        write_png,
    )

    image, meta = synthesize_exact_n_story_tower_controlnet(int(floors))

    name = "scaffold_N%d_%s.png" % (
        int(floors),
        str(meta.get("sha256_png") or "")[:12],
    )

    target = pathlib.Path(RC.COMFYUI_INPUT_DIR) / name

    if not target.exists():
        write_png(target, image)

    return str(target)
