"""ARCHITECTURAL_REQUEST_FIDELITY_REPAIR_V1 — request-information survival.

WHY THIS FILE EXISTS
====================
The V2 GPU acceptance (job a946fd95, output
`architectos_uso_reference_00003_.png`) executed correctly and produced an
image that FAILED architectural acceptance. The executed prompt at node 206
showed the request had been generalized on the way in:

    request : "Design a new two-storey neoclassical residential villa with a
               central arched entrance and limestone facade."
    node 206: "... Adopt a restrained neoclassical architectural language.
               Use natural stone. REQUIRED ARCHITECTURAL ELEMENTS — include
               meaningful arches with proper voussoirs; ... neoclassical style,
               villa. The building has exactly 2 floors. ..."

Two explicit instructions did not survive:

  * `limestone`  -> `natural stone`   (material specificity generalized)
  * `central arched entrance` -> generic `arches` (entrance hierarchy dropped)

WHAT IS *NOT* A DEFECT — recorded here so nobody "fixes" it later
================================================================
The earlier, richer USO run (`00002`) carried six ornamental elements and a
complete-building framing instruction. That run used a DIFFERENT request and a
DIFFERENT reference image. Those elements were never authorized by the short
request, so their absence from CASE_A is correct, not a loss. CASE_A must NOT
inherit them, and this file asserts exactly that.

FLOOR COUNT is deliberately out of scope here: it is appended by the render
layer (`architectural_render_instruction_v1`), not by the compiler, and the
live trace already showed "The building has exactly 2 floors." at node 206.

NO GPU. NO COMFYUI SUBMISSION. NO OLLAMA LOAD. NO NETWORK.
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

from core.prompt_intelligence.persian_architectural_understanding import (  # noqa: E402
    understand,
)
from core.prompt_intelligence.architectural_prompt_compiler_v1 import (  # noqa: E402
    compile_prompt,
)


# ----------------------------------------------------------
# CASE A — the short real user request
# ----------------------------------------------------------

CASE_A = (
    "Design a new two-storey neoclassical residential villa with a central "
    "arched entrance and limestone facade."
)

# ----------------------------------------------------------
# CASE B — the accepted longer neoclassical brief
# (tests/test_classical_facade_execution_v2.py :: T2I_V2)
# ----------------------------------------------------------

CASE_B = (
    "Design a complete luxurious two-storey Roman-classic and ornate neoclassical "
    "stone villa, seen in a full-building front-three-quarter architectural view. The "
    "entire facade, roofline, both floors, entrance steps and surrounding landscaped "
    "ground must be visible within the frame. Create a balanced monumental central "
    "entrance framed by correctly proportioned classical columns and finely carved "
    "Corinthian or Composite capitals. Include richly articulated cornices, "
    "architectural relief carving, elegant window pediments, appropriately supported "
    "stone balustraded balconies and realistic light warm-ivory natural stone "
    "cladding. Show convincing large-scale ashlar courses with recessed joints, "
    "subtle per-block stone variations, deep architectural shadows and precise "
    "construction logic. Professional high-detail daylight architectural photography. "
    "No cropped roof or missing building edges, no advertising, no watermark."
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise RuntimeError("outbound connection refused in test")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


def _compile(text):
    with contextlib.redirect_stdout(io.StringIO()):
        understanding = understand(text)
        compiled = compile_prompt(understanding, mode="text_to_image")
    return understanding, compiled


def _positive(text):
    _, compiled = _compile(text)
    assert compiled["status"] == "COMPILED", compiled.get("status")
    return compiled["positive_prompt"]


# ==========================================================
# RED 1 — material specificity must survive understanding
# ==========================================================

def test_case_a_limestone_is_recognised_as_limestone():
    """`limestone` must not collapse to the generic `stone` id."""
    with contextlib.redirect_stdout(io.StringIO()):
        understanding = understand(CASE_A)

    primary = (understanding.get("materials") or {}).get("primary")

    assert primary == "limestone", (
        "limestone was generalized to %r before compilation" % (primary,)
    )


# ==========================================================
# RED 2 — material specificity must reach the compiled prompt
# ==========================================================

def test_case_a_limestone_reaches_the_compiled_prompt():
    positive = _positive(CASE_A)

    assert "limestone" in positive.lower()
    assert "natural stone" not in positive.lower(), (
        "explicitly requested limestone was rewritten as unspecified natural stone"
    )


# ==========================================================
# RED 3 — the central entrance must survive as a central entrance
# ==========================================================

def test_case_a_central_entrance_survives():
    positive = _positive(CASE_A).lower()

    assert "entrance" in positive, "the requested entrance did not reach the prompt"
    assert "central" in positive, (
        "the requested CENTRAL entrance hierarchy was dropped; a generic arch "
        "instruction is not the same instruction"
    )


# ==========================================================
# RED 4 — the same loss occurs in the rich brief, so the fix is general
# ==========================================================

def test_case_b_central_entrance_survives():
    positive = _positive(CASE_B).lower()

    assert "entrance" in positive
    assert "central" in positive


# ==========================================================
# GUARD — CASE A must not inherit unrequested ornaments
# ==========================================================

def test_case_a_does_not_invent_unrequested_ornaments():
    positive = _positive(CASE_A).lower()

    for absent in ("capital", "cornice", "balustrade", "pediment", "quoins"):
        assert absent not in positive, (
            "%r was added although the short request never authorized it" % (absent,)
        )


def test_case_a_keeps_its_single_authorized_ornament():
    positive = _positive(CASE_A).lower()

    assert "arches with proper voussoirs" in positive


# ==========================================================
# GUARD — framing follows the request, never the other way round
# ==========================================================

def test_case_a_does_not_acquire_complete_building_framing():
    positive = _positive(CASE_A).lower()

    assert "complete building" not in positive
    assert "do not crop" not in positive


def test_case_b_keeps_complete_building_framing():
    positive = _positive(CASE_B)

    assert "COMPLETE building" in positive
    assert "Do not crop the roof" in positive


def test_detail_only_request_never_gets_complete_building_framing():
    positive = _positive("Design a close-up detail study of a classical stone cornice.")

    # The full-building FRAMING INSTRUCTION must be absent. The words
    # "complete building" legitimately appear inside the detail-only sentence
    # ("...rather than a complete building view"), so the instruction itself
    # is what is asserted, not the substring.
    assert "Do not crop the roof" not in positive
    assert "close architectural detail study" in positive.lower()


# ==========================================================
# GUARD — CASE B keeps all seven authorized elements
# ==========================================================

def test_case_b_keeps_every_authorized_element():
    positive = _positive(CASE_B).lower()

    for phrase in (
        "classical columns",
        "corinthian or composite capitals",
        "cornices with dentils or modillions",
        "arches with proper voussoirs",
        "window pediments",
        "balustraded balconies with visible balusters",
        "relief carving",
    ):
        assert phrase in positive, "authorized element %r was dropped" % (phrase,)


# ==========================================================
# GUARD — style contamination controls
# ==========================================================

def test_iranian_traditional_request_does_not_gain_classical_columns():
    positive = _positive(
        "Design a two-storey Iranian brick villa with traditional brick lattice screens."
    ).lower()

    assert "classical columns" not in positive
    assert "corinthian" not in positive


def test_modern_request_does_not_gain_classical_ornament():
    positive = _positive(
        "Design a modern glass and concrete office building with clean horizontal lines."
    ).lower()

    for absent in ("corinthian", "capital", "balustrade", "pediment"):
        assert absent not in positive


# ==========================================================
# GUARD — preservation turns must not turn into element demands
# ==========================================================

def test_entrance_without_central_is_not_made_central():
    """Specificity guard: an entrance alone must not become a central entrance.

    Only `central` authorizes centrality. This is the control that stops the
    entrance fix from over-firing on every request that mentions an entrance.
    """
    positive = _positive(
        "Design a neoclassical stone villa with a generous main entrance."
    ).lower()

    assert "central" not in positive


# ==========================================================
# GUARD — explicit negations survive
# ==========================================================

def test_explicit_negation_survives():
    """Explicit negation must reach the NEGATIVE prompt, not be swallowed.

    The supported negation vocabulary is the Persian marker set, so the
    control uses it rather than asserting English negation the detector has
    never claimed to handle.
    """
    with contextlib.redirect_stdout(io.StringIO()):
        understanding = understand("یک ویلای دو طبقه با نمای سنگ طراحی کن، ولی قوس زیاد نشه")
        compiled = compile_prompt(understanding, mode="text_to_image")

    assert compiled["status"] == "COMPILED"
    assert understanding["negative_constraints"], "negation was not detected"
    assert "Avoid excessive use of arches" in (compiled.get("negative_prompt") or "")


# ==========================================================
# GUARD — no duplicated material instruction
# ==========================================================

def test_material_instruction_is_not_duplicated():
    positive = _positive(CASE_A).lower()

    assert positive.count("limestone") <= 1, (
        "the material instruction was emitted more than once"
    )


# ==========================================================
# INTEGRATION — the REAL application path, final node 206 text
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
                terminal = graph.get(str(link[0]))
                if isinstance(terminal, dict):
                    return (terminal.get("inputs") or {}).get("text")
    return None


def _run_real_app_case(text, reference_id=None):
    """Drive the REAL app path; substitute only the GPU/executor seams."""
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
                on_submitted("fidelity-prompt")
            return {"status": "completed", "prompt_id": "fidelity-prompt", "images": []}

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

    # The ChatArchitect singleton already exists, so the LIVE instance is
    # re-seamed; patching __init__ would never run for it.
    runtime = A.chat.render_runtime
    runtime.executor = Executor()
    runtime.result_bridge = type(
        "B", (), {"resolve": lambda s, c: {"image_asset": None, "status": "ok"}}
    )()

    payload = {"text": text, "mode": "text_to_image"}
    if reference_id:
        payload["reference_id"] = reference_id

    client = A.app.test_client()
    with contextlib.redirect_stdout(io.StringIO()):
        response = client.post("/api/chat", json=payload)

    assert response.status_code == 200
    assert submitted, "the real path never reached submission"
    return submitted[-1], (response.get_json() or {})


def test_real_app_path_node206_preserves_the_request(monkeypatch):
    graph, _ = _run_real_app_case(CASE_A, reference_id="CLASSICAL_REF_04")
    text = (_node206(graph) or "").lower()

    assert "limestone" in text, "limestone lost on the real path"
    assert "natural stone" not in text
    assert "central" in text
    assert "entrance" in text
    assert "exactly 2 floors" in text
    assert "neoclassical" in text


def test_real_app_path_keeps_uso_reference_binding(monkeypatch):
    graph, _ = _run_real_app_case(CASE_A, reference_id="CLASSICAL_REF_04")

    types = {n.get("class_type") for n in graph.values() if isinstance(n, dict)}
    assert "USOStyleReference" in types
    assert "VAEEncode" not in types, "reference-guided T2I must not become img2img"

    loads = [n for n in graph.values()
             if isinstance(n, dict) and n.get("class_type") == "LoadImage"]
    assert len(loads) == 1
    assert loads[0]["inputs"]["image"] == "architectos_ref_CLASSICAL_REF_04.jpg"


# ==========================================================
# RESULT RESPONSE CONTRACT — CPU only, recorded executor response
# ==========================================================

RECORDED_OUTPUT = "architectos_uso_reference_00003_.png"


def _run_case_with_recorded_output(text, reference_id="CLASSICAL_REF_04"):
    """Same real path, but the executor reports the RECORDED output filename.

    No image is produced and no GPU is touched: the recorded filename is the
    one job a946fd95 actually wrote, used here only to check that a completed
    result can carry its output back through the API.
    """
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
    runtime.result_bridge = type(
        "B", (), {"resolve": lambda s, c: {"image_asset": None, "status": "ok"}}
    )()

    client = A.app.test_client()
    with contextlib.redirect_stdout(io.StringIO()):
        response = client.post(
            "/api/chat",
            json={"text": text, "mode": "text_to_image", "reference_id": reference_id},
        )
    assert response.status_code == 200
    return response.get_json() or {}


def test_completed_result_carries_its_output_and_reference_back(monkeypatch):
    data = _run_case_with_recorded_output(CASE_A)
    blob = json.dumps(data, ensure_ascii=False)

    assert RECORDED_OUTPUT in blob, "the completed output path was not retained"
    assert "CLASSICAL_REF_04" in blob, "the selected reference lineage was not retained"
    assert data.get("status") == "success"


def test_missing_observation_is_unverified_never_pass():
    """The fidelity verdict must not turn an absent observation into a PASS."""
    from core.vision.design_constraint_fidelity_v1 import evaluate

    result = evaluate(
        {"building_type": "villa", "floors": 2},
        "The building has exactly 2 floors. Use limestone.",
        None,
        requested_text=CASE_A,
    )

    assert result["observed"]["floors"] is None
    assert result["floor_status"] == "FLOOR_COUNT_UNVERIFIED"
    assert result["design_accepted"] is False


def test_completion_is_not_claimed_without_an_image(monkeypatch):
    """A render that produced no image must not report success."""
    import core.runtime.gpu_handoff_v1 as gpu_handoff
    import core.render.render_runtime as rr_module
    import app as A

    class Executor:
        def __init__(self):
            self.comfy = type("C", (), {"endpoint": "stub"})()

        def execute(self, workflow, engine, on_submitted=None, client_id=None):
            if on_submitted:
                on_submitted("fidelity-prompt")
            return {"status": "completed", "prompt_id": "fidelity-prompt", "images": []}

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
        response = client.post(
            "/api/chat",
            json={"text": CASE_A, "mode": "text_to_image", "reference_id": "CLASSICAL_REF_04"},
        )

    payload = response.get_json() or {}
    structured = ((payload.get("response") or {}).get("result_structured") or {})

    assert structured.get("status") == "completed_no_image"
    assert structured.get("status") != "success"
