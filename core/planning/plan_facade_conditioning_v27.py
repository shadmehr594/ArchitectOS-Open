"""FACADE_FROM_PLAN_V27 — condition a render on the ACTIVE plan's elevation.

A user who has just approved a plan says "از همین ساختمان یه رندر از نمای
جنوبی بگیر". That is neither a new design brief nor a free text-to-image wish:
the building already exists as `active_plan_params`, so the render must be
conditioned on THAT plan — its floor count, window positions, entrance steps
and duplex void — or the facade and the plan disagree.

`ComfyUIRenderBridge.export_plan_locked_south_facade_png` extrudes exactly that
elevation from `project.floors`. This module owns the decision (is this turn
about the active plan?) and the staging (put the PNG where ComfyUI can read it),
so the two call sites that can reach a render share ONE implementation.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import shutil
from typing import Any, Dict, Optional, Tuple

CONTRACT = "PlanFacadeConditioningV27"
VERSION = "1.0"

#: Phrases that name the ACTIVE plan's building rather than a new one.
PLAN_FACADE_MARKERS = (
    "همین ساختمان",
    "همین پلان",
    "این ساختمان",
    "این پلان",
    "همین نما",
    "این نما",
    "همون نما",
    "اون نما",
    "آن نما",
    "نمای جنوبی",
    "نمای شمالی",
    "نمای شرقی",
    "نمای غربی",
    "از پلان رندر",
    "از همین پلان",
    "از این پلان",
)

#: A facade phrase alone is not a render request.
_RENDER_VERBS = ("رندر", "render", "بگیر", "بده", "نما")


def is_plan_locked_facade_request(text: str) -> bool:
    """True when the turn renders the building the active plan describes."""

    low = str(text or "").lower().replace("\u200c", " ")

    if not any(marker in low for marker in PLAN_FACADE_MARKERS):

        return False

    return any(verb in low for verb in _RENDER_VERBS)


def _current_project_id() -> str:
    """The open project, which is the plan session's key."""

    try:

        from core.project.project_session_v1 import project_session

        return str(project_session.current_project_id() or "default")

    except Exception:  # noqa: BLE001

        return "default"


def build_plan_facade_conditioning(
    text: str,
    project_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return the conditioning payload for this turn, or ``None``.

    ``None`` is returned — never an exception — when the turn is not about the
    active plan, when no plan exists, or when the elevation cannot be built.
    The caller then renders unconditioned and records that the plan link was
    not applied.
    """

    if not is_plan_locked_facade_request(text):

        return None

    try:

        from core.planning import plan_session_v25 as plan_session

        from core.planning.multifloor_v1.engine import (
            ComfyUIRenderBridge,
            ParametricArchitecturalSynthesizer,
        )

        resolved_project_id = str(project_id or _current_project_id())

        state = plan_session.load_state(resolved_project_id)

        params = state.get("active_plan_params") or {}

        if not params:

            return None

        project = ParametricArchitecturalSynthesizer().synthesize_from_params(
            params
        )

        renders_dir = plan_session.project_dir(resolved_project_id) / "renders"

        renders_dir.mkdir(parents=True, exist_ok=True)

        cond_path = renders_dir / "plan_facade_cond.png"

        out_png, plan_prompt_en = (
            ComfyUIRenderBridge.export_plan_locked_south_facade_png(
                project,
                str(cond_path),
                str(text or ""),
            )
        )

        digest = hashlib.sha256(
            pathlib.Path(out_png).read_bytes()
        ).hexdigest()[:16]

        name = "architectos_v27_plan_facade_%s.png" % digest

        from config import runtime_config as runtime_config

        target = os.path.join(runtime_config.COMFYUI_INPUT_DIR, name)

        if not os.path.exists(target):

            shutil.copy2(out_png, target)

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "project_id": resolved_project_id,
            "control_image": name,
            "cond_png": str(cond_path),
            "prompt_en": plan_prompt_en,
            "floors": len(project.floors),
        }

    except Exception as exc:  # noqa: BLE001

        # The render still runs, unconditioned. The caller records the gap
        # instead of claiming the plan was applied.
        print("⚠️ PLAN FACADE CONDITIONING UNAVAILABLE:", exc)

        return None


def trace(conditioning: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The observable decision, safe to attach to a response."""

    if not conditioning:

        return None

    return {
        "applied": True,
        "contract": CONTRACT,
        "project_id": conditioning.get("project_id"),
        "control_image": conditioning.get("control_image"),
        "cond_png": conditioning.get("cond_png"),
        "floors": conditioning.get("floors"),
        "prompt_en": conditioning.get("prompt_en"),
    }
