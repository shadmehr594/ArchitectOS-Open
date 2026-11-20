"""ARCHITECTURAL_VISION_RUNTIME_COMPLETION_V1 — render output -> Vision -> fidelity.

WHY THIS FILE EXISTS
====================
The Vision stack already existed and already worked on produced images, but no
runtime path ever called it: `handle_image_generate` evaluated
DesignConstraintFidelityV1 with `observed=None` on every turn, so a completed
render could never be verified and every verdict was UNVERIFIED forever.

RED evidence before the connection (recorded in
ARCHITECTOS_VISUAL_REFERENCE_UX_AND_DESIGN_FIDELITY_V2.md §6.3 and re-confirmed
by probe): after a real completed render,

    observed = {"available": false, "floors": null, "source": "none"}

while the image itself was on disk and the provider could read it.

These tests pin the connection WITHOUT running the vision model: the provider
call is substituted at its public seam, so the tests stay CPU-only.

NO GPU. NO COMFYUI SUBMISSION. NO OLLAMA. NO NETWORK.
"""

import contextlib
import io
import json
import os
import socket
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from core.vision import design_constraint_fidelity_v1 as fidelity  # noqa: E402


REQUEST = "Design a five-storey residential apartment building at true night."

# A real file that exists in the ComfyUI output root. It is only READ.
REAL_OUTPUT = "architectos_uso_reference_00003_.png"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def _blocked(*a, **k):
        raise RuntimeError("outbound connection refused in test")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


class _Guard:
    def acquire(self):
        return True

    def release(self):
        return True


class _Listener:
    def __init__(self, *a, **k):
        pass

    def start(self):
        return True

    def stop(self):
        return True

    def bind_prompt_id(self, prompt_id):
        pass

    def stats(self):
        return {}


def _install_seams(monkeypatch, observed_contract, *, available=True,
                   release_status="released", output_filename=REAL_OUTPUT):
    import core.runtime.gpu_handoff_v1 as gpu_handoff
    import core.render.render_runtime as rr_module

    calls = {"observe": 0, "release": 0, "paths": []}

    def fake_release(endpoint=None, session=None):
        calls["release"] += 1
        return {"status": release_status, "reason": "test"}

    def fake_observe(path, provider=None):
        calls["observe"] += 1
        calls["paths"].append(path)
        return {
            "available": available,
            "reason": None if available else "provider reports itself unavailable",
            "contract": observed_contract if available else None,
            "provider": "ollama_facade",
            "model": "qwen3.8:27b",
        }

    monkeypatch.setattr(gpu_handoff, "gpu_render_lease", lambda *a, **k: _Guard())
    monkeypatch.setattr(gpu_handoff, "unload_ollama_models_for_render",
                        lambda *a, **k: {"status": "not_running", "reason": "test",
                                         "ownership": None, "unloaded": [],
                                         "skipped_in_use": []})
    monkeypatch.setattr(gpu_handoff, "require_render_vram",
                        lambda *a, **k: {"ok": True, "reason": "test",
                                         "free_mib": 16000, "min_free_mib": 11264,
                                         "measurement_source": "test_stub"})
    monkeypatch.setattr(gpu_handoff, "release_comfyui_for_vision", fake_release)
    monkeypatch.setattr(fidelity, "observe_output", fake_observe)
    monkeypatch.setattr(rr_module, "ComfyProgressListener", _Listener)

    import app as A

    class Executor:
        def __init__(self):
            self.comfy = type("C", (), {"endpoint": "stub"})()

        def execute(self, workflow, engine, on_submitted=None, client_id=None):
            if on_submitted:
                on_submitted("vision-prompt")
            return {
                "status": "completed",
                "prompt_id": "vision-prompt",
                "images": [{"filename": output_filename, "subfolder": "", "type": "output"}],
            }

    runtime = A.chat.render_runtime
    runtime.executor = Executor()
    runtime.result_bridge = type("B", (), {"resolve": lambda s, c: {"status": "ok"}})()

    return A, calls


def _run(monkeypatch, observed_contract, **kwargs):
    A, calls = _install_seams(monkeypatch, observed_contract, **kwargs)

    client = A.app.test_client()
    with contextlib.redirect_stdout(io.StringIO()):
        response = client.post(
            "/api/chat",
            json={"text": REQUEST, "mode": "text_to_image",
                  "reference_id": "CLASSICAL_REF_04",
                  # VISION_LIGHTING_OUTPUT_VERIFICATION_V2 — observation is
                  # now opt-in for EVERY route (it used to fire implicitly on
                  # reference turns, which added minutes to every such
                  # render). These tests are about the connection, not the
                  # trigger, so they request it explicitly.
                  "verify_render": True},
        )

    assert response.status_code == 200
    data = response.get_json() or {}
    structured = ((data.get("response") or {}).get("result_structured") or {})
    return structured, calls, data


def _contract(floors, building_type="residential apartment block"):
    return {
        "visible_floor_count": floors,
        "building_type": building_type,
        "facade_style": "modern",
        "materials": [],
        "roof_features": ["flat roof"],
    }


# ==========================================================
# THE CONNECTION
# ==========================================================

def test_the_produced_png_is_actually_observed(monkeypatch):
    structured, calls, _ = _run(monkeypatch, _contract(3))

    assert calls["observe"] == 1, "the produced image was never inspected"
    assert calls["release"] == 1, "ComfyUI was not released before the vision call"
    assert calls["paths"], "no path was passed to the provider"
    assert calls["paths"][0].endswith(".png"), (
        "the sampler prompt is not evidence; the observation must read the PNG"
    )
    assert REAL_OUTPUT in calls["paths"][0]


def test_observed_contract_reaches_the_fidelity_evaluation(monkeypatch):
    structured, _, _ = _run(monkeypatch, _contract(3))
    fid = structured.get("design_fidelity") or {}

    observed = fid.get("observed") or {}
    assert observed.get("available") is True
    assert observed.get("floors") == 3
    assert observed.get("building_type") == "residential apartment block"


def test_observation_provenance_is_returned(monkeypatch):
    structured, _, _ = _run(monkeypatch, _contract(3))
    obs = structured.get("design_observation") or {}

    assert obs.get("available") is True
    assert obs.get("provider") == "ollama_facade"
    assert obs.get("model") == "qwen3.8:27b"
    assert str(obs.get("image") or "").endswith(".png")


# ==========================================================
# VERDICTS
# ==========================================================

def test_five_requested_three_observed_is_a_mismatch(monkeypatch):
    structured, _, _ = _run(monkeypatch, _contract(3))
    fid = structured.get("design_fidelity") or {}

    assert fid.get("requested", {}).get("floors") == 5
    assert fid.get("floor_status") == "FLOOR_COUNT_MISMATCH"
    assert fid.get("design_accepted") is False


def test_matching_observation_is_verified(monkeypatch):
    structured, _, _ = _run(monkeypatch, _contract(5))
    fid = structured.get("design_fidelity") or {}

    assert fid.get("floor_status") == "FLOOR_COUNT_VERIFIED"
    assert fid.get("building_type_status") == "BUILDING_TYPE_VERIFIED"


def test_cropped_image_stays_unverified(monkeypatch):
    """A provider that cannot count must not produce a verdict."""
    structured, _, _ = _run(monkeypatch, _contract(None))
    fid = structured.get("design_fidelity") or {}

    assert fid.get("floor_status") == "FLOOR_COUNT_UNVERIFIED"
    assert fid.get("design_accepted") is False


def test_unavailable_provider_never_becomes_a_pass(monkeypatch):
    structured, _, _ = _run(monkeypatch, None, available=False)
    fid = structured.get("design_fidelity") or {}

    assert (fid.get("observed") or {}).get("available") is False
    assert fid.get("floor_status") == "FLOOR_COUNT_UNVERIFIED"
    assert fid.get("design_accepted") is False
    assert "PASS" not in json.dumps(fid, ensure_ascii=False)


def test_blocked_comfyui_release_skips_observation(monkeypatch):
    """If ComfyUI cannot release VRAM, we do not guess — we stay UNVERIFIED."""
    structured, calls, _ = _run(monkeypatch, _contract(3), release_status="blocked")
    fid = structured.get("design_fidelity") or {}

    assert calls["observe"] == 0, "observation ran although the GPU was not released"
    assert fid.get("floor_status") == "FLOOR_COUNT_UNVERIFIED"


def test_missing_output_file_is_not_observed(monkeypatch):
    """A render whose file is absent must not be observed or verified.

    The response shape for a turn with no usable image differs (no
    attachment), so the invariant asserted here is the one that matters:
    nothing was inspected and nothing was verified.
    """
    structured, calls, _ = _run(monkeypatch, _contract(3),
                                output_filename="definitely_not_here_00000_.png")

    assert calls["observe"] == 0
    blob = json.dumps(structured, ensure_ascii=False)
    assert "FLOOR_COUNT_VERIFIED" not in blob
    assert "BUILDING_TYPE_VERIFIED" not in blob


# ==========================================================
# OBSERVATION IS NOT INTERPRETATION
# ==========================================================

def test_observation_contract_keeps_provider_certainty(monkeypatch):
    """Provider-stated certainty must survive into the recorded contract."""
    contract = _contract(3)
    contract["certainty"] = {
        "visible_floor_count": "OBSERVED",
        "materials": "INFERRED",
    }
    structured, _, _ = _run(monkeypatch, contract)
    obs = structured.get("design_observation") or {}

    assert (obs.get("contract") or {}).get("certainty", {}).get("materials") == "INFERRED"


def test_evaluate_does_not_upgrade_inferred_materials():
    """The fidelity layer must not treat an INFERRED material as observed."""
    result = fidelity.evaluate(
        {"building_type": "villa", "floors": 2},
        "The building has exactly 2 floors.",
        {"visible_floor_count": 2, "building_type": "villa"},
        requested_text="two-storey villa",
    )

    assert result["observed"]["floors"] == 2
    assert "material" not in json.dumps(result.get("observed", {})).lower()


# ==========================================================
# A CROPPED VIEW CANNOT ESTABLISH A TOTAL FLOOR COUNT
#
# Real evidence (architectos_v11_00260_.png, the Krea night benchmark): the
# provider returned visible_floor_count = 4 with
#   occlusions = ["ground floor obscured by framing"]
#   perspective_limitations = ["view is cropped, showing only a section of
#                              the building", ...]
# and the fidelity layer turned that into FLOOR_COUNT_MISMATCH against a
# five-floor request — asserting the building HAS four floors, when four is
# only a lower bound of what is in frame.
# ==========================================================

CROPPED_CONTRACT = {
    "visible_floor_count": 4,
    "building_type": "residential apartment block",
    "occlusions": ["ground floor obscured by framing"],
    "perspective_limitations": [
        "view is cropped, showing only a section of the building",
        "nighttime lighting obscures surface texture details",
    ],
}

COMPLETE_CONTRACT = {
    "visible_floor_count": 3,
    "building_type": "residential apartment block",
    "occlusions": [],
    "perspective_limitations": ["rear of building not visible",
                                "interior layout not visible"],
}


def test_cropped_view_is_unverified_not_mismatch():
    result = fidelity.evaluate(
        {"building_type": "apartment building", "floors": 5},
        "The building has exactly 5 floors.",
        CROPPED_CONTRACT,
        requested_text="five-storey apartment building",
    )

    assert result["floor_status"] == "FLOOR_COUNT_UNVERIFIED", (
        "a cropped view asserted a total floor count"
    )
    assert result["design_accepted"] is False


def test_cropped_view_keeps_the_visible_count_as_a_lower_bound():
    result = fidelity.evaluate(
        {"building_type": "apartment building", "floors": 5},
        "The building has exactly 5 floors.",
        CROPPED_CONTRACT,
        requested_text="five-storey apartment building",
    )

    assert result["observed"]["floors"] is None
    assert result["observed"]["visible_floor_count_lower_bound"] == 4
    assert result["observed"]["view_partial"] is True


def test_complete_view_still_reports_a_mismatch():
    """3 of 5 with the whole building in frame is a real mismatch."""
    result = fidelity.evaluate(
        {"building_type": "apartment building", "floors": 5},
        "The building has exactly 5 floors.",
        COMPLETE_CONTRACT,
        requested_text="five-storey apartment building",
    )

    assert result["floor_status"] == "FLOOR_COUNT_MISMATCH"
    assert result["observed"]["view_partial"] is False


def test_rear_not_visible_is_not_treated_as_cropped():
    """'rear not visible' is normal for any photograph, not a partial view."""
    observed = fidelity.observed_constraints(COMPLETE_CONTRACT)
    assert observed["view_partial"] is False


def test_building_type_mismatch_is_still_reported_when_cropped():
    """Cropping affects the floor TOTAL, not the observed building type."""
    contract = dict(CROPPED_CONTRACT, building_type="civic or institutional building")
    result = fidelity.evaluate(
        {"building_type": "villa", "floors": 2},
        "The building has exactly 2 floors.",
        contract,
        requested_text="two-storey residential villa",
    )

    assert result["building_type_status"] == "BUILDING_TYPE_MISMATCH"
