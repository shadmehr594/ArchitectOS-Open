"""VISION_LIGHTING_OUTPUT_VERIFICATION_V2 — lighting, floor confidence, routes.

WHY THIS FILE EXISTS
====================
The V1 completion connected render output to the existing Vision provider, but
three demonstrated gaps remained:

1. The observation contract had NO lighting / time-of-day field, so night
   quality could not be verified from pixels at all. The benchmark's two night
   images were unverifiable for the exact property they were rendered for.
2. `visible_floor_count` was a single integer with no notion of what it meant.
   A cropped view, a fully framed view with no legible storey divisions, and a
   confidently established total all collapsed into the same number. V1 patched
   only the cropped case via a partial-view guard.
3. Observation ran only on reference-guided turns, so Krea text-only and
   Kontext edits were never verified.

These tests pin the additive contract extension and the confidence model.
NO GPU. NO RENDER. The model call itself is substituted at its seam.
"""

import contextlib
import io
import json
import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from core.vision import design_constraint_fidelity_v1 as fidelity  # noqa: E402
from core.vision.facade_reference_vision_provider_v1 import (  # noqa: E402
    map_to_contract,
)


# ==========================================================
# A — LIGHTING OBSERVATION (additive contract)
# ==========================================================

def test_lighting_block_survives_mapping():
    mapped = map_to_contract({
        "building_type": "residential apartment block",
        "lighting": {
            "time_of_day": "night",
            "facade_readability": "clear",
            "artificial_lighting_visible": True,
            "evidence": "dark sky, warm lit windows",
            "confidence": 0.9,
        },
    })

    lighting = mapped.get("lighting") or {}
    assert lighting.get("time_of_day") == "night"
    assert lighting.get("facade_readability") == "clear"
    assert lighting.get("artificial_lighting_visible") is True
    assert lighting.get("confidence") == pytest.approx(0.9)


def test_dusk_and_daylight_are_distinct_values():
    for value in ("dusk", "daylight"):
        mapped = map_to_contract({"lighting": {"time_of_day": value}})
        assert (mapped.get("lighting") or {}).get("time_of_day") == value


def test_unknown_lighting_is_allowed():
    mapped = map_to_contract({"lighting": {"time_of_day": "unknown"}})
    assert (mapped.get("lighting") or {}).get("time_of_day") == "unknown"


def test_lighting_keeps_exposure_separate_from_time_of_day():
    """A floodlit night facade is still night; readability is its own axis."""
    mapped = map_to_contract({
        "lighting": {
            "time_of_day": "night",
            "facade_readability": "clear",
            "artificial_lighting_visible": True,
        }
    })

    lighting = mapped["lighting"]
    assert lighting["time_of_day"] == "night"
    assert lighting["facade_readability"] == "clear"


def test_missing_lighting_does_not_invent_a_time_of_day():
    mapped = map_to_contract({"building_type": "villa"})
    assert "lighting" not in mapped or not (mapped.get("lighting") or {}).get("time_of_day")


def test_lighting_reaches_the_fidelity_observation():
    observed = fidelity.observed_constraints({
        "visible_floor_count": 3,
        "building_type": "residential apartment block",
        "lighting": {"time_of_day": "night", "facade_readability": "clear"},
    })

    assert (observed.get("lighting") or {}).get("time_of_day") == "night"


# ==========================================================
# B — FLOOR COUNT CONFIDENCE
# ==========================================================

def test_total_count_type_is_verified():
    result = fidelity.evaluate(
        {"building_type": "apartment building", "floors": 5},
        "x",
        {
            "visible_floor_count": 5,
            "building_type": "residential apartment block",
            "floor_observation": {
                "count": 5, "count_type": "TOTAL",
                "storey_divisions_legible": True,
            },
        },
        requested_text="five-storey apartment building",
    )

    assert result["floor_status"] == "FLOOR_COUNT_VERIFIED"


def test_visible_levels_without_legible_divisions_is_unverified():
    """A fully framed image does not make its count reliable."""
    result = fidelity.evaluate(
        {"building_type": "villa", "floors": 2},
        "x",
        {
            "visible_floor_count": 2,
            "building_type": "villa",
            "floor_observation": {
                "count": 2, "count_type": "VISIBLE_LEVELS",
                "storey_divisions_legible": False,
            },
        },
        requested_text="two-storey villa",
    )

    assert result["floor_status"] == "FLOOR_COUNT_UNVERIFIED"


def test_lower_bound_count_is_unverified_and_preserved():
    result = fidelity.evaluate(
        {"building_type": "apartment building", "floors": 5},
        "x",
        {
            "visible_floor_count": 4,
            "building_type": "residential apartment block",
            "floor_observation": {"count": 4, "count_type": "LOWER_BOUND"},
        },
        requested_text="five-storey apartment building",
    )

    assert result["floor_status"] == "FLOOR_COUNT_UNVERIFIED"
    assert result["observed"]["visible_floor_count_lower_bound"] == 4


def test_ambiguous_count_is_unverified():
    result = fidelity.evaluate(
        {"building_type": "villa", "floors": 2},
        "x",
        {
            "visible_floor_count": 2,
            "building_type": "villa",
            "floor_observation": {"count": 2, "count_type": "AMBIGUOUS"},
        },
        requested_text="two-storey villa",
    )

    assert result["floor_status"] == "FLOOR_COUNT_UNVERIFIED"


def test_visible_levels_reason_does_not_contradict_legibility():
    """VISIBLE_LEVELS can coexist with legible divisions.

    The first version of the reason text asserted "storey divisions are not
    legible" even when the observation said they WERE legible — the reason
    contradicted its own evidence.
    """
    result = fidelity.evaluate(
        {"building_type": "villa", "floors": 2},
        "x",
        {
            "visible_floor_count": 2,
            "building_type": "villa",
            "floor_observation": {
                "count": 2, "count_type": "VISIBLE_LEVELS",
                "storey_divisions_legible": True,
            },
        },
        requested_text="two-storey villa",
    )

    assert result["floor_status"] == "FLOOR_COUNT_UNVERIFIED"
    assert "not legible" not in result["floor_reason"]
    assert "did not establish" in result["floor_reason"]


def test_legacy_contract_without_floor_observation_still_works():
    """Backward compatibility: older contracts keep the V1 behaviour."""
    result = fidelity.evaluate(
        {"building_type": "apartment building", "floors": 5},
        "x",
        {
            "visible_floor_count": 3,
            "building_type": "residential apartment block",
            "occlusions": [],
            "perspective_limitations": ["rear of building not visible"],
        },
        requested_text="five-storey apartment building",
    )

    assert result["floor_status"] == "FLOOR_COUNT_MISMATCH"


def test_old_fields_are_not_removed_by_the_extension():
    mapped = map_to_contract({
        "visible_floor_count": 3,
        "building_type": "villa",
        "facade_style": "modern",
        "lighting": {"time_of_day": "night"},
        "floor_observation": {"count": 3, "count_type": "TOTAL"},
    })

    for legacy in ("visible_floor_count", "building_type", "facade_style",
                   "occlusions", "perspective_limitations", "uncertainties"):
        assert legacy in mapped


# ==========================================================
# C — ROUTE COVERAGE (opt-in, not automatic)
# ==========================================================

def _run_turn(monkeypatch, *, reference_id=None, kontext_edit=False,
              verify_render=None, observe_calls=None):
    import core.runtime.gpu_handoff_v1 as gpu_handoff
    import core.render.render_runtime as rr_module

    calls = observe_calls if observe_calls is not None else {"n": 0, "paths": []}

    def fake_observe(path, provider=None):
        calls["n"] += 1
        calls["paths"].append(path)
        return {
            "available": True,
            "reason": None,
            "contract": {
                "visible_floor_count": 5,
                "building_type": "residential apartment block",
                "floor_observation": {"count": 5, "count_type": "TOTAL"},
                "lighting": {"time_of_day": "night"},
            },
            "provider": "ollama_facade",
            "model": "qwen3.8:27b",
        }

    monkeypatch.setattr(fidelity, "observe_output", fake_observe)
    monkeypatch.setattr(gpu_handoff, "gpu_render_lease",
                        lambda *a, **k: type("G", (), {"acquire": lambda s: True,
                                                       "release": lambda s: True})())
    monkeypatch.setattr(gpu_handoff, "unload_ollama_models_for_render",
                        lambda *a, **k: {"status": "not_running", "reason": "t",
                                         "ownership": None, "unloaded": [],
                                         "skipped_in_use": []})
    monkeypatch.setattr(gpu_handoff, "require_render_vram",
                        lambda *a, **k: {"ok": True, "reason": "t", "free_mib": 16000,
                                         "min_free_mib": 11264,
                                         "measurement_source": "test_stub"})
    monkeypatch.setattr(gpu_handoff, "release_comfyui_for_vision",
                        lambda *a, **k: {"status": "released", "reason": "t"})
    monkeypatch.setattr(rr_module, "ComfyProgressListener",
                        type("L", (), {"__init__": lambda s, *a, **k: None,
                                       "start": lambda s: True,
                                       "stop": lambda s: True,
                                       "bind_prompt_id": lambda s, p: None,
                                       "stats": lambda s: {}}))

    import app as A

    class Executor:
        def __init__(self):
            self.comfy = type("C", (), {"endpoint": "stub"})()

        def execute(self, workflow, engine, on_submitted=None, client_id=None):
            if on_submitted:
                on_submitted("route-prompt")
            return {"status": "completed", "prompt_id": "route-prompt",
                    "images": [{"filename": "architectos_v11_00260_.png",
                                "subfolder": "", "type": "output"}]}

    runtime = A.chat.render_runtime
    runtime.executor = Executor()
    runtime.result_bridge = type("B", (), {"resolve": lambda s, c: {"status": "ok"}})()

    payload = {"text": "Design a five-storey residential apartment building at night.",
               "mode": "text_to_image"}
    if reference_id:
        payload["reference_id"] = reference_id
    if kontext_edit:
        payload["kontext_edit"] = True
    if verify_render is not None:
        payload["verify_render"] = verify_render

    with contextlib.redirect_stdout(io.StringIO()):
        response = A.app.test_client().post("/api/chat", json=payload)

    assert response.status_code == 200
    data = response.get_json() or {}
    structured = ((data.get("response") or {}).get("result_structured") or {})
    return structured, calls


def test_text_only_route_is_not_observed_by_default(monkeypatch):
    """Vision must not silently add minutes to every render."""
    structured, calls = _run_turn(monkeypatch)

    assert calls["n"] == 0


def test_text_only_route_is_observed_when_verify_render_is_requested(monkeypatch):
    structured, calls = _run_turn(monkeypatch, verify_render=True)

    assert calls["n"] == 1, "verify_render did not trigger output observation"
    obs = structured.get("design_observation") or {}
    assert obs.get("available") is True


def test_reference_guided_route_observes_only_when_requested(monkeypatch):
    """USO is covered by the same opt-in: no implicit multi-minute latency."""
    _, without = _run_turn(monkeypatch, reference_id="CLASSICAL_REF_04")
    assert without["n"] == 0

    _, with_verify = _run_turn(monkeypatch, reference_id="CLASSICAL_REF_04",
                               verify_render=True)
    assert with_verify["n"] == 1


def test_observation_gate_does_not_branch_on_route():
    """The gate is the opt-in alone, so Kontext is covered by construction.

    A route-conditional gate would silently exclude Kontext; this asserts the
    handler contains no such branch.
    """
    import inspect
    from core.chat.handlers import image_handler as handler_module

    source = inspect.getsource(handler_module._observe_rendered_output)
    for route_token in ("kontext", "uso_reference", "engine =="):
        assert route_token not in source, (
            "output observation must not depend on the render route"
        )
