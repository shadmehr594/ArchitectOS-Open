"""RENDER_INTENT_RELIABILITY_V1 — night intent + design-fidelity response.

WHY THIS FILE EXISTS
====================
The night/floor benchmark preflight (ARCHITECTOS_NIGHT_FLOOR_MODEL_BENCHMARK_V1,
§3) found two application-level defects in the compiled instruction:

1. A request for an EXTERIOR night building that mentions warm INTERIOR lights
   visible through the windows selected the **interior** render preset. The
   terminology layer emits `interior space` for the bare word "interior", and
   `resolve_preset` tests interior before night, so an exterior building render
   became an interior room render (704x768, "camera inside the room").

2. The same request said "not dusk", and the terminology layer emitted
   `dusk lighting` **affirmatively** while the instruction layer correctly
   emitted "Do NOT use or repeat: dusk." The prompt asked for and forbade the
   same thing in one sentence.

ROOT CAUSE (both in one owner)
------------------------------
`core/cognition/architectural_terminology_v1.extract_terms()` matches raw
substrings with no negation awareness, and `("interior space", (..., "interior"))`
treats the light qualifier "interior lights" as a room.

This file pins the behaviour BEFORE the correction (RED) and after (GREEN).

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

from core.cognition.architectural_terminology_v1 import (  # noqa: E402
    extract_terms,
    normalize_architectural_terms,
)
from core.render.render_preset_v1 import resolve_preset  # noqa: E402


# ----------------------------------------------------------
# THE REQUESTS
# ----------------------------------------------------------

EN_EXTERIOR_NIGHT = (
    "Warm interior lights visible through the windows of an exterior building at night."
)

EN_TRUE_NIGHT = "Design an exterior building at true night, not dusk."

FA_EXTERIOR_NIGHT = (
    "نمای خارجی ساختمان در شب با نورهای گرم داخلی که از پنجره‌ها دیده می‌شود"
)

FA_TRUE_NIGHT = "نمای ساختمان شبانه باشد، نه گرگ‌ومیش"

EN_INTERIOR_DESIGN = "Design a warm interior living room at night."

EN_DAYLIGHT = "Design an exterior facade in bright natural daylight."


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def _blocked(*a, **k):
        raise RuntimeError("outbound connection refused in test")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


def _terms(text):
    with contextlib.redirect_stdout(io.StringIO()):
        return normalize_architectural_terms(text)


def _preset(text):
    with contextlib.redirect_stdout(io.StringIO()):
        return resolve_preset(terminology=_terms(text))


def _canonical(text):
    return set(_terms(text).get("canonical_terms") or [])


# ==========================================================
# RED 1 — exterior night must not become an interior room
# ==========================================================

def test_exterior_night_with_interior_window_lights_selects_exterior_night():
    preset = _preset(EN_EXTERIOR_NIGHT)
    assert preset["name"] == "exterior_night", (
        "an exterior night building selected %r — interior lights through "
        "windows describe LIGHT SOURCES, not an interior space"
        % (preset["name"],)
    )


def test_interior_light_qualifier_does_not_emit_interior_space():
    terms = _canonical(EN_EXTERIOR_NIGHT)
    assert "interior space" not in terms
    assert "exterior space" in terms


def test_exterior_night_keeps_night_and_lighting():
    terms = _canonical(EN_EXTERIOR_NIGHT)
    assert "night lighting" in terms
    assert "lighting" in terms


# ==========================================================
# RED 2 — "not dusk" must not create an affirmative dusk term
# ==========================================================

def test_true_night_not_dusk_does_not_emit_dusk():
    terms = _canonical(EN_TRUE_NIGHT)
    assert "dusk lighting" not in terms, (
        "the explicitly REJECTED time of day was emitted as an affirmative "
        "requirement"
    )
    assert "night lighting" in terms


def test_true_night_not_dusk_still_selects_exterior_night():
    assert _preset(EN_TRUE_NIGHT)["name"] == "exterior_night"


def test_negation_still_reaches_the_instruction_layer():
    """The rejected span must remain recorded — the fix removes the affirmative
    term, it does not discard the user's rejection."""
    from core.cognition.architectural_render_instruction_v1 import (
        build_render_instruction,
    )

    with contextlib.redirect_stdout(io.StringIO()):
        instruction = build_render_instruction(EN_TRUE_NIGHT)

    text = json.dumps(instruction, ensure_ascii=False).lower()
    assert "dusk" in text, "the user's rejection of dusk was lost entirely"


# ==========================================================
# RED 3 — Persian equivalents
# ==========================================================

def test_persian_exterior_night_selects_exterior_night():
    preset = _preset(FA_EXTERIOR_NIGHT)
    assert preset["name"] == "exterior_night", (
        "Persian exterior night selected %r" % (preset["name"],)
    )


def test_persian_exterior_night_has_no_interior_space():
    assert "interior space" not in _canonical(FA_EXTERIOR_NIGHT)


def test_persian_true_night_not_dusk_has_no_dusk_term():
    terms = _canonical(FA_TRUE_NIGHT)
    assert "dusk lighting" not in terms
    assert "night lighting" in terms


# ==========================================================
# GUARD — genuine interior requests must stay interior
# ==========================================================

def test_explicit_interior_design_still_selects_interior():
    preset = _preset(EN_INTERIOR_DESIGN)
    assert preset["name"].startswith("interior"), (
        "a genuine interior request was routed to %r" % (preset["name"],)
    )


def test_explicit_interior_space_phrase_still_signals_interior():
    assert "interior space" in _canonical("Design an interior space with warm lighting.")


def test_persian_interior_request_stays_interior():
    preset = _preset("یک اتاق نشیمن داخلی با نور گرم طراحی کن")
    assert preset["name"].startswith("interior")


# ==========================================================
# GUARD — daylight unchanged
# ==========================================================

def test_daylight_request_stays_daylight():
    preset = _preset(EN_DAYLIGHT)
    assert preset["name"] == "exterior_day"


def test_daylight_is_not_read_as_dusk():
    assert "dusk lighting" not in _canonical(EN_DAYLIGHT)


# ==========================================================
# GUARD — explicit architectural constraints survive
# ==========================================================

def test_floor_count_and_building_type_survive_night_correction():
    """The night fix must not disturb the explicit architectural constraints.

    Floor count lives in the understanding/intent contract and building type
    reaches the prompt through the terminology tail, so both layers are
    asserted rather than the compiler (which legitimately produces nothing for
    a request that names no style or material).
    """
    from core.prompt_intelligence.persian_architectural_understanding import understand

    text = ("Design a five-storey residential apartment building at true night, "
            "not dusk, with warm interior lights glowing through the windows.")

    with contextlib.redirect_stdout(io.StringIO()):
        understanding = understand(text)
        terms = _canonical(text)

    assert understanding.get("scope") is not None
    assert "apartment building" in terms, "building type was lost"
    assert "night lighting" in terms
    assert "dusk lighting" not in terms, "the rejected time of day was emitted"


# ==========================================================
# INTEGRATION — the COMPLETE final prompt on the real app path
# ==========================================================

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


def _node206(graph):
    for node in graph.values():
        if isinstance(node, dict) and node.get("class_type") == "KSampler":
            link = (node.get("inputs") or {}).get("positive")
            if isinstance(link, list) and link:
                t = graph.get(str(link[0]))
                if isinstance(t, dict):
                    return (t.get("inputs") or {}).get("text")
    return None


def _run_real_app(text):
    import core.runtime.gpu_handoff_v1 as gpu_handoff
    import core.render.render_runtime as rr_module
    import app as A

    submitted = []

    class Executor:
        def __init__(self):
            self.comfy = type("C", (), {"endpoint": "stub"})()

        def execute(self, workflow, engine, on_submitted=None, client_id=None):
            submitted.append(json.loads(json.dumps(workflow)))
            if on_submitted:
                on_submitted("intent-prompt")
            return {"status": "completed", "prompt_id": "intent-prompt", "images": []}

    gpu_handoff.gpu_render_lease = lambda *a, **k: _Guard()
    gpu_handoff.unload_ollama_models_for_render = lambda *a, **k: {
        "status": "not_running", "reason": "test", "ownership": None,
        "unloaded": [], "skipped_in_use": [],
    }
    gpu_handoff.require_render_vram = lambda *a, **k: {
        "ok": True, "reason": "test", "free_mib": 16000,
        "min_free_mib": 11264, "measurement_source": "test_stub",
    }
    rr_module.ComfyProgressListener = _Listener

    runtime = A.chat.render_runtime
    runtime.executor = Executor()
    runtime.result_bridge = type(
        "B", (), {"resolve": lambda s, c: {"image_asset": None, "status": "ok"}}
    )()

    client = A.app.test_client()
    with contextlib.redirect_stdout(io.StringIO()):
        response = client.post("/api/chat", json={"text": text, "mode": "text_to_image"})

    assert response.status_code == 200
    assert submitted, "the real path never reached submission"
    return submitted[-1], (response.get_json() or {})


def test_real_app_path_final_prompt_is_exterior_night(monkeypatch):
    graph, data = _run_real_app(EN_EXTERIOR_NIGHT)
    text = (_node206(graph) or "").lower()

    # the prompt must describe an exterior night building
    assert "night" in text
    assert "exterior" in text or "facade" in text

    # and must NOT carry the interior-room tail
    for forbidden in ("camera inside the room", "interior viewpoint",
                      "interior composition", "cozy ambient light"):
        assert forbidden not in text, (
            "interior-room instruction %r leaked into an exterior night render"
            % (forbidden,)
        )

    # the resolved preset is reported on the render handoff
    handoff = json.dumps(data, ensure_ascii=False)
    assert "exterior_night" in handoff


# ==========================================================
# TASK 2 — the design-fidelity contract must survive the response
#
# RED evidence before the correction: the same call returned
#   "design_fidelity present in final response: False"
# because `result_bridge.resolve()` builds a new dict and
# `ImageResponseAdapter.adapt()` copies only its own keys.
# ==========================================================

RECORDED_OUTPUT = "architectos_uso_reference_00003_.png"

FIDELITY_REQUEST = (
    "Design a two-storey neoclassical villa with limestone facade."
)


def _run_image_turn_with_recorded_output(text, reference_id="CLASSICAL_REF_04"):
    import core.runtime.gpu_handoff_v1 as gpu_handoff
    import core.render.render_runtime as rr_module
    import app as A

    class Executor:
        def __init__(self):
            self.comfy = type("C", (), {"endpoint": "stub"})()

        def execute(self, workflow, engine, on_submitted=None, client_id=None):
            if on_submitted:
                on_submitted("fidelity-prompt")
            return {
                "status": "completed",
                "prompt_id": "fidelity-prompt",
                "images": [{"filename": RECORDED_OUTPUT, "subfolder": "", "type": "output"}],
            }

    gpu_handoff.gpu_render_lease = lambda *a, **k: _Guard()
    gpu_handoff.unload_ollama_models_for_render = lambda *a, **k: {
        "status": "not_running", "reason": "test", "ownership": None,
        "unloaded": [], "skipped_in_use": [],
    }
    gpu_handoff.require_render_vram = lambda *a, **k: {
        "ok": True, "reason": "test", "free_mib": 16000,
        "min_free_mib": 11264, "measurement_source": "test_stub",
    }
    rr_module.ComfyProgressListener = _Listener

    runtime = A.chat.render_runtime
    runtime.executor = Executor()
    # The bridge returns a NEW dict without the fidelity contract, which is
    # exactly the real-world shape that used to lose it.
    runtime.result_bridge = type("B", (), {"resolve": lambda s, c: {"status": "ok"}})()

    client = A.app.test_client()
    with contextlib.redirect_stdout(io.StringIO()):
        response = client.post(
            "/api/chat",
            json={"text": text, "mode": "text_to_image", "reference_id": reference_id},
        )
    assert response.status_code == 200
    return response.get_json() or {}


def _fidelity(data):
    return ((data.get("response") or {}).get("result_structured") or {}).get(
        "design_fidelity"
    ) or {}


def test_successful_image_response_retains_design_fidelity():
    data = _run_image_turn_with_recorded_output(FIDELITY_REQUEST)
    fid = _fidelity(data)

    assert fid, "the design-fidelity contract was dropped from a successful image response"
    assert fid.get("contract") == "DesignConstraintFidelityV1"


def test_fidelity_retains_requested_executed_and_observed():
    fid = _fidelity(_run_image_turn_with_recorded_output(FIDELITY_REQUEST))

    requested = fid.get("requested") or {}
    executed = fid.get("executed") or {}
    observed = fid.get("observed") or {}

    assert requested.get("floors") == 2
    assert requested.get("building_type") == "villa"
    assert executed.get("source") == "sampler_positive_prompt"
    assert "observed" in fid
    assert observed.get("available") is False


def test_fidelity_reports_verification_statuses():
    fid = _fidelity(_run_image_turn_with_recorded_output(FIDELITY_REQUEST))

    assert fid.get("floor_status") == "FLOOR_COUNT_UNVERIFIED"
    assert fid.get("building_type_status") == "BUILDING_TYPE_UNVERIFIED"
    assert fid.get("design_accepted") is False


def test_unverified_is_never_upgraded_to_pass():
    """No observation was made, so nothing may be reported as verified."""
    fid = _fidelity(_run_image_turn_with_recorded_output(FIDELITY_REQUEST))

    assert "PASS" not in json.dumps(fid, ensure_ascii=False)
    assert fid.get("design_accepted") is not True
    assert (fid.get("observed") or {}).get("floors") is None


def test_response_retains_reference_provenance():
    data = _run_image_turn_with_recorded_output(FIDELITY_REQUEST)
    blob = json.dumps(data, ensure_ascii=False)

    assert "CLASSICAL_REF_04" in blob
    assert "5025c0c93f246ea32e2919b1fdf7f0b6538047bad152bdb7b720ec1a03342a31" in blob


def test_response_retains_the_output_path():
    data = _run_image_turn_with_recorded_output(FIDELITY_REQUEST)
    assert RECORDED_OUTPUT in json.dumps(data, ensure_ascii=False)
