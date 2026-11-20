# ==========================================================
# VISION_OBSERVATION_MODE_SEPARATION_V1 — LIVE ACCEPTANCE
#
# Proves, on a THROW-AWAY Core (spare port, isolated data root,
# render-stop guard), that:
#
#   * the image path has TWO output shapes, not one: a request for
#     visible evidence is answered by the OBSERVATION layer (elements +
#     evidence + confidence, and NOTHING else) and an interpretation
#     request is answered by the INTERPRETATION layer, unchanged
#   * a bed is a sleeping element and NEVER a master bedroom; only the
#     interpretation layer may say "possible master bedroom", and only
#     from MULTIPLE evidence sources
#   * the observation reaches the user: `response.result` is the rendered
#     TEXT (the UI renders `result || message`) and the structured
#     contract is exposed under `observation`
#   * a response declaring "persian" renders Persian
#   * no render, no ComfyUI call, no teaching change, no network call
#     added by the observation layer
#
# Usage:
#   .venv/Scripts/python.exe tools/run_vision_observation_separation_01_acceptance.py
#
# Add --skip-contract to skip the suites (fast path).
# ==========================================================

import ast
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zlib


sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer, encoding="utf-8", errors="replace"
)

sys.stderr = io.TextIOWrapper(
    sys.stderr.buffer, encoding="utf-8", errors="replace"
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


STAMP = time.strftime("%Y%m%d_%H%M%S")

PORT = 5093

CORE = "http://127.0.0.1:%d" % PORT

WORK = os.path.join(ROOT, ".pytest_tmp", "vision_observation_01_" + STAMP)

DATA_ROOT = os.path.join(WORK, "project_data")

os.makedirs(DATA_ROOT, exist_ok=True)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

LOG_PATH = os.path.join(WORK, "core.log")

REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_vision_observation_separation_01_report.json"
)


# ---- the two requests of the brief ----

OBSERVATION_REQUEST = "فقط عناصر قابل مشاهده تصویر را لیست کن"

INTERPRETATION_REQUEST = "این تصویر چه فضای معماری را نشان می‌دهد؟"


# ---- the images of the brief, as provider payloads ----

BEDROOM_FURNITURE = {
    "image_type": "architectural_render_or_photo",
    "confidence": "HIGH",
    "observed": ["bed visible", "wardrobe visible", "desk visible"],
    "inferred": [],
    "unresolved": [],
    "architectural_elements": ["bed", "wardrobe", "desk"],
    "safety": {"supports_region_grounding": False},
}

MASTER_SUITE = {
    "image_type": "floor_plan_or_sketch",
    "confidence": "HIGH",
    "observed": [
        "bed visible",
        "dressing room visible",
        "ensuite bathroom visible",
    ],
    "inferred": [],
    "unresolved": [],
    "architectural_elements": ["bed", "wardrobe", "bathroom"],
    "safety": {"supports_region_grounding": False},
}

# ---- the provider's own payload for the reported image ----

RUN_B = {
    "image_type": "floor_plan_or_sketch",
    "confidence": "HIGH",
    "observed": [
        "two side-by-side floor plans", "mirrored layouts", "Persian text",
        "furniture icons", "bed", "wardrobe", "desk", "door symbols",
    ],
    "inferred": ["parental suite", "alternative layout options"],
    "unresolved": ["exact dimensions"],
    "architectural_elements": ["bed", "wardrobe", "desk", "chair", "door", "wall"],
    "text_labels_if_visible": ["حریم خصوصی در اتاق والدین"],
    "safety": {"supports_region_grounding": False},
}


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

RESULTS = []


def record(name, passed, detail=None):

    entry = {"test": name, "passed": bool(passed), "detail": detail}

    RESULTS.append(entry)

    print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

    if detail and not passed:

        print(
            "        ",
            json.dumps(detail, ensure_ascii=False, default=str)[:900],
        )


def http_json(base, path, payload=None, timeout=10800):

    body = json.dumps(payload).encode("utf-8") if payload is not None else None

    request = urllib.request.Request(
        base + path,
        data=body,
        method="POST" if body is not None else "GET",
        headers={"Content-Type": "application/json"},
    )

    try:

        with _OPENER.open(request, timeout=timeout) as response:

            return response.status, json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:

        return error.code, {}

    except Exception as error:

        return None, {"error": type(error).__name__ + ": " + str(error)}


def comfy_snapshot():

    try:

        from config import runtime_config as RC

        directory = RC.COMFYUI_OUTPUT_DIR

    except Exception:

        return {"exists": False, "count": 0, "newest": None}

    if not os.path.isdir(directory):

        return {"exists": False, "count": 0, "newest": None}

    entries = []

    for name in os.listdir(directory):

        path = os.path.join(directory, name)

        if os.path.isfile(path):

            entries.append((os.path.getmtime(path), name))

    entries.sort()

    return {
        "exists": True,
        "count": len(entries),
        "newest": entries[-1][1] if entries else None,
    }


def core_env():

    env = os.environ.copy()

    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = env["NO_PROXY"]
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT
    env["ARCHITECTOS_CORE_API_PORT"] = str(PORT)
    env["ARCHITECTOS_CORE_API_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_CORE_API_BIND_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_COMFY_HOST"] = "127.0.0.1"
    # Render-stop guard: every ComfyUI submit fails fast and truthfully.
    env["ARCHITECTOS_COMFY_PORT"] = "9"

    return env


def start_core(label):

    handle = open(LOG_PATH, "ab")

    handle.write(
        ("\n\n===== %s start @ %s =====\n" % (label, STAMP)).encode("utf-8")
    )

    handle.flush()

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    return subprocess.Popen(
        [python, "-u", "app.py"],
        cwd=ROOT,
        env=core_env(),
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )


def wait_for_core(timeout=10800):

    started = time.time()

    while time.time() - started < timeout:

        status, _ = http_json(CORE, "/health", timeout=5)

        if status == 200:

            return True

        time.sleep(1)

    return False


def write_png(path, width=120, height=90):

    """A small floor-plan-like PNG, built here (no fixture file).

    `tests/assets/test_upload.png` is 22 bytes of ASCII and makes the
    provider fail; a real PNG is required for a real end-to-end turn.
    """

    def chunk(tag, data):

        payload = tag + data

        return (
            struct.pack(">I", len(data))
            + payload
            + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
        )

    rows = []

    for y in range(height):

        row = bytearray()

        row.append(0)

        for x in range(width):

            edge = (
                x in (0, 1, width - 2, width - 1)
                or y in (0, 1, height - 2, height - 1)
            )

            inner = 30 <= x <= 60 and 20 <= y <= 50

            if edge:

                pixel = (35, 35, 35)

            elif inner:

                pixel = (160, 160, 160)

            else:

                pixel = (247, 247, 247)

            row.extend(pixel)

        rows.append(bytes(row))

    raw = b"".join(rows)

    with open(path, "wb") as handle:

        handle.write(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b"")
        )

    return path


def multipart_image(image_path, text, project_id):

    import requests

    session = requests.Session()

    session.trust_env = False

    with open(image_path, "rb") as handle:

        return session.post(
            CORE + "/chat",
            files={"image": (os.path.basename(image_path), handle, "image/png")},
            data={
                "text": text,
                "project_id": project_id,
                "mode": "auto",
                "quality": "auto",
                "seed_mode": "random",
            },
            timeout=10800,
        )


def resolve_image(work_dir):

    """A REAL architectural image, so the live element contract is exercised.

    The reported floor plan (the very image the grounding checkpoint is
    about) is copied read-only when present; a synthetic PNG is the
    fallback. `tests/assets/test_upload.png` is 22 bytes of ASCII and must
    never be used — the provider correctly rejects it and the whole run
    then "proves" nothing.
    """

    candidates = [
        os.path.join(
            ROOT, "data", "projects", "project_e89fe613", "uploads",
            "image_007_6c3dca.png",
        ),
        os.path.join(
            ROOT, "data", "projects", "project_e89fe613", "uploads",
            "image_001_986891.png",
        ),
    ]

    for candidate in candidates:

        if os.path.isfile(candidate) and os.path.getsize(candidate) > 20000:

            target = os.path.join(work_dir, "reported_plan.png")

            shutil.copyfile(candidate, target)

            return target, candidate

    return write_png(os.path.join(work_dir, "plan.png")), "synthetic"


def shell_suite(name, relative, mode="script"):

    """Run a suite and report its OWN verdict.

    Three shapes live in `tests/`, and they must be run differently:

      * SCRIPT-style with a `_RESULTS` list — records into it and returns a
        bool, so its own `N/M PASS` line is the only honest verdict.
      * BARE/`main()` scripts (no `_RESULTS`) — assert and exit non-zero on
        failure; pytest collects NOTHING from them (rc=5), so a pytest run
        would report a false red.
      * PYTEST-style — have no `__main__`, so `python <file>` executes
        nothing and exits 0: a false green.

    The verdict is therefore parsed from the suite's own summary line, and
    `FAIL` is never searched for as a bare substring — one of this phase's
    own test LABELS contains the word ("NEGATIVE CONTROL").
    """

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    command = (
        [python, "-u", relative]
        if mode == "script"
        else [python, "-m", "pytest", relative, "-q"]
    )

    finished = subprocess.run(
        command,
        cwd=ROOT,
        env=core_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    text = finished.stdout.decode("utf-8", errors="replace")

    summary = ""

    ok = finished.returncode == 0

    if mode == "script":

        match = re.search(r"(\d+)\s*/\s*(\d+)\s+PASS", text)

        if match:

            summary = match.group(0)

            ok = ok and match.group(1) == match.group(2)

        else:

            summary = text.strip().splitlines()[-1] if text.strip() else ""

            ok = ok and "Traceback" not in text

    else:

        match = re.search(r"(\d+)\s+passed", text)

        summary = match.group(0) if match else ""

        ok = ok and bool(match)

    record(name, ok, {"summary": summary[-200:], "rc": finished.returncode})


def _element_names(observation):

    return [
        entry.get("name") for entry in (observation or {}).get("elements") or []
    ]


def _interpretation_vocabulary(observation):

    """Interpretation words in the observation's STRUCTURAL data only.

    Two traps are handled here, and both would otherwise produce a false
    red:

      * The scope note deliberately NAMES what is excluded ("no privacy or
        zoning, no design reasoning"), so scanning the prose would flag the
        module's own disclaimer — the `comfy_invoked` trap.
      * Scanning a serialised dict also scans its KEY names, and one of the
        contract's own keys is `possible_function`. Only the VALUES are
        inspected.
    """

    values = [
        observation.get("space_type"),
        observation.get("architectural_interpretation"),
        observation.get("spatial_relations"),
        observation.get("possible_function"),
        observation.get("design_reasoning"),
        observation.get("elements"),
        observation.get("unknowns"),
        observation.get("not_confirmed"),
    ]

    blob = json.dumps(values, ensure_ascii=False, default=str).lower()

    forbidden = (
        "master", "privacy", "zoning", "design intent", "circulation",
        "function", "public", "private",
        "مستر", "حریم", "کاربری", "عمومی", "خصوصی", "استدلال",
    )

    return [word for word in forbidden if word in blob]


# ==========================================================

def main():

    skip_contract = "--skip-contract" in sys.argv

    comfy_before = comfy_snapshot()

    print("\n" + "=" * 76)
    print("VISION_OBSERVATION_MODE_SEPARATION_V1 — LIVE ACCEPTANCE")
    print("  core=%s" % CORE)
    print("  data root=%s" % DATA_ROOT)
    print("=" * 76)

    print("  comfy before:", comfy_before)

    # --------------------------------------------------
    # THE BRIEF'S SEMANTICS (in-process, deterministic)
    # --------------------------------------------------

    from core.vision.vision_observation_mode_v1 import (  # noqa: E402
        build_observation,
        render_observation,
        detect_observation_request,
    )

    from core.vision.image_intent_v1 import (  # noqa: E402
        classify_image_intent,
        INTENT_OBSERVE,
        INTENT_ANALYZE,
    )

    from core.vision.architectural_vision_interpreter_v1 import (  # noqa: E402
        interpret_architectural_vision,
    )

    # ---- R.1 the request is its own intent, and analysis is not ----

    observe_intent = classify_image_intent(OBSERVATION_REQUEST)["intent"]

    analyze_intent = classify_image_intent(INTERPRETATION_REQUEST)["intent"]

    record(
        "R.1 the brief's two requests are two intents: the visible-evidence "
        "request is `observe`, the interpretation request stays `analyze`",
        observe_intent == INTENT_OBSERVE
        and analyze_intent == INTENT_ANALYZE
        and detect_observation_request("این تصویر را فقط تحلیل کن") is False,
        {"observe": observe_intent, "analyze": analyze_intent},
    )

    # ---- R.2 the brief's case 1 ----

    observation_1 = build_observation(BEDROOM_FURNITURE, language="fa")

    text_1 = render_observation(observation_1, "fa")

    names_1 = _element_names(observation_1)

    record(
        "R.2 CASE 1 — a bedroom image + 'list the visible elements': the bed "
        "is detected as a sleeping element, and NO master-bedroom "
        "classification is produced",
        "sleeping_element" in names_1
        and observation_1.get("space_type") is None
        and observation_1.get("possible_function") == []
        and observation_1.get("architectural_interpretation") == []
        and "مستر" not in text_1
        and "تخت" in text_1,
        {
            "elements": names_1,
            "space_type": observation_1.get("space_type"),
        },
    )

    record(
        "R.3 every listed element carries its EVIDENCE and its CONFIDENCE "
        "(the brief's observation contract)",
        bool(observation_1.get("elements"))
        and all(
            entry.get("evidence")
            and entry.get("confidence")
            and entry.get("status") in ("visible", "symbol_reading")
            for entry in observation_1["elements"]
        )
        and observation_1.get("mode") == "OBSERVATION"
        and isinstance(observation_1.get("unknowns"), list),
        {"elements": observation_1.get("elements")},
    )

    # ---- R.4 the brief's case 2 ----

    observation_2 = build_observation(MASTER_SUITE, language="fa")

    names_2 = _element_names(observation_2)

    interpretation_2 = interpret_architectural_vision(MASTER_SUITE)

    record(
        "R.4 CASE 2 — bed + closet + bathroom: the OBSERVATION lists elements "
        "only, while the INTERPRETATION layer may say 'possible master "
        "bedroom'",
        set(names_2) == {"sleeping_element", "wardrobe_or_closet",
                         "bathroom_or_ensuite"}
        and observation_2.get("space_type") is None
        and interpretation_2.get("space_type") == "master bedroom"
        and all(
            "possible" in value
            for value in interpretation_2.get("possible_function") or []
        )
        and len(interpretation_2.get("classification_basis") or []) >= 3,
        {
            "observation_elements": names_2,
            "interpretation_space_type": interpretation_2.get("space_type"),
            "basis": interpretation_2.get("classification_basis"),
        },
    )

    # ---- R.5 a bed is never a master bedroom ----

    single_bed = interpret_architectural_vision(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["bed visible"],
            "architectural_elements": ["bed"],
            "confidence": "MEDIUM",
        }
    )

    record(
        "R.5 the brief's central rule: a bed does NOT equal master bedroom "
        "— one bed gives `bedroom` with a single basis",
        single_bed.get("space_type") == "bedroom"
        and single_bed.get("classification_basis") == ["sleeping element"],
        {
            "space_type": single_bed.get("space_type"),
            "basis": single_bed.get("classification_basis"),
        },
    )

    # ---- R.6 the observation never carries interpretation vocabulary ----

    leaked_1 = _interpretation_vocabulary(observation_1)

    leaked_2 = _interpretation_vocabulary(observation_2)

    record(
        "R.6 the observation's STRUCTURAL data carries no space / privacy / "
        "zoning / design-intent vocabulary (the scope note that NAMES them "
        "is excluded, like the module's own flags)",
        not leaked_1 and not leaked_2,
        {"bedroom": leaked_1, "master_suite": leaked_2},
    )

    # ---- R.7 the evidence hierarchy, graded by class not by spelling ----

    bare = build_observation(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["bed"],
            "architectural_elements": ["bed"],
            "confidence": "HIGH",
        },
        language="fa",
    )

    symbol = build_observation(
        {
            "image_type": "floor_plan_or_sketch",
            "observed": ["window symbols"],
            "architectural_elements": ["window"],
        },
        language="fa",
    )

    bare_by_name = {entry["name"]: entry for entry in bare["elements"]}

    record(
        "R.7 the evidence hierarchy is graded by CLASS: a visible object is "
        "HIGH whether or not the phrase says 'visible'; a plan symbol is "
        "MEDIUM and flagged",
        bare_by_name.get("sleeping_element", {}).get("confidence") == "high"
        and bare_by_name.get("sleeping_element", {}).get("explicit_assertion")
        is False
        and symbol["elements"][0].get("confidence") == "medium"
        and symbol["elements"][0].get("status") == "symbol_reading",
        {"bare": bare_by_name, "symbol": symbol["elements"]},
    )

    # ---- R.8 the reported payload: nothing invented, nothing dropped ----

    inferred_payload = {
        "image_type": "floor_plan_or_sketch",
        "observed": ["bed visible", "window symbols"],
        "inferred": ["ensuite bathroom"],
        "architectural_elements": ["bed", "window", "bathroom"],
        "confidence": "MEDIUM",
    }

    inferred_observation = build_observation(inferred_payload, language="fa")

    reported = build_observation(RUN_B, language="fa")

    reported_names = _element_names(reported)

    record(
        "R.8 nothing is invented and nothing is dropped: an INFERRED element "
        "is never listed and carries an `inference` reason, an element-list "
        "claim is reported as unconfirmed, and the observation is "
        "deterministic",
        "bathroom_or_ensuite" not in _element_names(inferred_observation)
        and any(
            entry.get("reason_code") == "inference"
            for entry in inferred_observation.get("not_confirmed") or []
        )
        and any(
            entry.get("reason_code") == "mention_only"
            for entry in reported.get("not_confirmed") or []
        )
        and json.dumps(reported, ensure_ascii=False, sort_keys=True)
        == json.dumps(
            build_observation(RUN_B, language="fa"),
            ensure_ascii=False,
            sort_keys=True,
        ),
        {
            "inferred_elements": _element_names(inferred_observation),
            "inferred_not_confirmed": inferred_observation.get("not_confirmed"),
            "reported_not_confirmed": reported.get("not_confirmed"),
        },
    )

    # ---- R.9 read-only, provably ----

    record(
        "R.9 the observation layer is read-only: no provider call, no LLM, "
        "no network, no storage, no render, no geometry, no ComfyUI, no "
        "teaching",
        reported.get("provider_calls") == 0
        and reported.get("llm_used") is False
        and reported.get("network_used") is False
        and reported.get("storage_used") is False
        and reported.get("render_requested") is False
        and reported.get("geometry_touched") is False
        and reported.get("comfy_invoked") is False
        and reported.get("teaching_used") is False
        and reported.get("read_only") is True,
        {},
    )

    # --------------------------------------------------
    # STATIC ARCHITECTURE
    # --------------------------------------------------

    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as handle:

        app_source = handle.read()

    record(
        "A.1 exactly one ChatArchitect is constructed in app.py (no parallel "
        "assistant)",
        app_source.count("ChatArchitect(") == 1,
        {"count": app_source.count("ChatArchitect(")},
    )

    module_path = os.path.join(
        ROOT, "core", "vision", "vision_observation_mode_v1.py"
    )

    with open(module_path, encoding="utf-8") as handle:

        module_source = handle.read()

    # Parse the IMPORTS with ast — the module legitimately *discusses* the
    # forbidden words in comments and exposes `comfy_invoked: False`, so a
    # text grep would collide with its own flag names.
    tree = ast.parse(module_source)

    imported = set()

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            for alias in node.names:

                imported.add(alias.name.split(".")[0])

        elif isinstance(node, ast.ImportFrom):

            if node.module:

                imported.add(node.module.split(".")[0])

    forbidden_imports = sorted(
        imported & {"requests", "urllib", "http", "socket", "comfy", "ollama"}
    )

    # Call SHAPES, not bare prefixes.
    forbidden_shapes = [
        token for token in ("\nclass ", "requests.", ".save(", ".record(",
                            "app.run", "import comfy")
        if token in module_source
    ]

    record(
        "A.2 the observation layer defines no class and contains no network, "
        "LLM, storage or render call (imports parsed with ast, calls by "
        "shape)",
        not forbidden_imports and not forbidden_shapes,
        {"imports": forbidden_imports, "shapes": forbidden_shapes},
    )

    # --------------------------------------------------
    # LIVE HTTP — A REAL IMAGE TURN, TWICE
    # --------------------------------------------------

    core = start_core("core")

    if not wait_for_core():

        record("X.1 fresh Core came up on the spare port", False, {"port": PORT})

        core.kill()

        return 1

    record("X.1 fresh Core came up on the spare port", True, {"port": PORT})

    try:

        status, created = http_json(
            CORE, "/api/projects", {"name": "Vision Observation " + STAMP}
        )

        project_id = (created.get("project") or {}).get("project_id")

        record(
            "L.1 project created",
            status == 200 and bool(project_id),
            {"project_id": project_id},
        )

        if not project_id:

            return 1

        image_path, image_source = resolve_image(WORK)

        print("  live image: %s" % image_source)

        # ---- turn 1: the OBSERVATION request --------------------------

        response_1 = multipart_image(image_path, OBSERVATION_REQUEST, project_id)

        payload_1 = json.loads(response_1.content.decode("utf-8"))

        answer_1 = payload_1.get("response") or {}

        routing_1 = payload_1.get("routing") or {}

        observation = answer_1.get("observation") or {}

        print(
            "  turn1: http=%s type=%s mode=%s render=%s elements=%d"
            % (
                response_1.status_code,
                answer_1.get("type"),
                routing_1.get("mode"),
                routing_1.get("render"),
                len(observation.get("elements") or []),
            )
        )

        record(
            "L.2 the observation request is routed as its OWN mode over HTTP "
            "and never renders",
            response_1.status_code == 200
            and routing_1.get("mode") == "IMAGE_OBSERVATION"
            and routing_1.get("render") is False
            and answer_1.get("type") == "image_observation",
            {
                "status": response_1.status_code,
                "mode": routing_1.get("mode"),
                "type": answer_1.get("type"),
            },
        )

        record(
            "L.3 the live observation carries the contract, with NO space "
            "classification, NO function and NO relations",
            observation.get("contract") == "VisionObservationV1"
            and observation.get("mode") == "OBSERVATION"
            and observation.get("space_type") is None
            and observation.get("possible_function") == []
            and observation.get("architectural_interpretation") == []
            and observation.get("spatial_relations") == [],
            {
                "contract": observation.get("contract"),
                "space_type": observation.get("space_type"),
            },
        )

        record(
            "L.4 THE DISCARD DEFECT — the observation reaches the user: "
            "response.result is the rendered TEXT (the UI renders "
            "`result || message`) and the contract is exposed under "
            "`observation`",
            isinstance(answer_1.get("result"), str)
            and bool(answer_1.get("result"))
            and "Possible architectural space" not in answer_1["result"]
            and isinstance(answer_1.get("observation"), dict),
            {
                "result_type": type(answer_1.get("result")).__name__,
                "has_observation": isinstance(answer_1.get("observation"), dict),
            },
        )

        message_1 = answer_1.get("message") or ""

        record(
            "L.5 the live answer is PERSIAN (the response declares persian) "
            "and never names a master bedroom",
            "عناصر قابل مشاهده" in message_1
            and "Elements visible" not in message_1
            and "مستر" not in message_1
            and "فضای معماری" not in message_1,
            {"message": message_1[:400]},
        )

        record(
            "L.6 every live element carries evidence + confidence, the live "
            "observation detected real elements, and its structural data "
            "carries no interpretation vocabulary",
            all(
                entry.get("evidence")
                and entry.get("confidence")
                and entry.get("status") in ("visible", "symbol_reading")
                for entry in observation.get("elements") or []
            )
            and len(observation.get("elements") or []) >= 1
            and not _interpretation_vocabulary(observation),
            {
                "elements": _element_names(observation),
                "count": len(observation.get("elements") or []),
                "leaked": _interpretation_vocabulary(observation),
            },
        )

        # ---- turn 2: the INTERPRETATION request, SAME image ----------

        response_2 = multipart_image(
            image_path, INTERPRETATION_REQUEST, project_id
        )

        payload_2 = json.loads(response_2.content.decode("utf-8"))

        answer_2 = payload_2.get("response") or {}

        routing_2 = payload_2.get("routing") or {}

        interpretation = answer_2.get("architectural_interpretation") or {}

        print(
            "  turn2: http=%s type=%s mode=%s space_type=%s"
            % (
                response_2.status_code,
                answer_2.get("type"),
                routing_2.get("mode"),
                interpretation.get("space_type"),
            )
        )

        record(
            "L.7 the interpretation request on the SAME image is STILL an "
            "analysis (existing behaviour unchanged) and never renders",
            response_2.status_code == 200
            and routing_2.get("mode") == "IMAGE_ANALYSIS"
            and routing_2.get("render") is False
            and answer_2.get("type") == "image_analysis"
            and isinstance(interpretation.get("space_type"), str)
            and bool(interpretation.get("space_type"))
            and (
                "Possible architectural space" in (answer_2.get("message") or "")
                or "فضای معماری" in (answer_2.get("message") or "")
            ),
            {
                "status": response_2.status_code,
                "mode": routing_2.get("mode"),
                "type": answer_2.get("type"),
                "space_type": interpretation.get("space_type"),
                "message": (answer_2.get("message") or "")[:200],
            },
        )

        record(
            "L.8 the two turns are genuinely different shapes: the "
            "observation has NO space_type and no interpretation lists, while "
            "the interpretation contract carries the space classification",
            observation.get("space_type") is None
            and observation.get("possible_function") == []
            and observation.get("architectural_interpretation") == []
            and isinstance(interpretation.get("space_type"), str)
            and bool(interpretation.get("space_type"))
            and isinstance(interpretation.get("unknowns"), list),
            {
                "observation_space_type": observation.get("space_type"),
                "interpretation_space_type": interpretation.get("space_type"),
            },
        )

        # ---- restart mid-run ------------------------------------------

        core.kill()

        time.sleep(2)

        core = start_core("core-restart")

        up = wait_for_core()

        record("Z.1 the Core restarted", up, {})

        if up:

            status, _ = http_json(CORE, "/api/projects/" + project_id)

            record(
                "Z.2 the project survived the restart",
                status == 200,
                {"status": status},
            )

    finally:

        try:

            core.kill()

        except Exception:

            pass

    # --------------------------------------------------
    # REGRESSION
    # --------------------------------------------------

    if not skip_contract:

        shell_suite(
            "G.1 the VISION_OBSERVATION_MODE_SEPARATION_V1 contract suite",
            os.path.join("tests", "test_vision_observation_mode_separation_v1.py"),
            mode="script",
        )

        shell_suite(
            "G.2 the ARCHITECTURAL_VISION_GROUNDING_V1 suite",
            os.path.join("tests", "test_architectural_vision_grounding_v1.py"),
            mode="script",
        )

        shell_suite(
            "G.3 the ARCHITECTURAL_VISION_INTERPRETER_V1 suite",
            os.path.join("tests", "test_architectural_vision_interpreter_v1.py"),
            mode="pytest",
        )

        shell_suite(
            "G.4 VISION_REPORT_LANGUAGE_01 regression",
            os.path.join("tests", "test_vision_report_language_01.py"),
            mode="script",
        )

        shell_suite(
            "G.5 IMAGE_MODE_ROUTING_CONTRACT regression",
            os.path.join("tests", "test_image_mode_routing_contract.py"),
            mode="script",
        )

        shell_suite(
            "G.6 RESPONSE_ADAPTER_V1 regression",
            os.path.join("tests", "test_response_adapter_v1.py"),
            mode="script",
        )

    comfy_after = comfy_snapshot()

    print("  comfy after :", comfy_after)

    record(
        "N.1 no render was requested and ComfyUI output is untouched",
        comfy_before == comfy_after,
        {"before": comfy_before, "after": comfy_after},
    )

    failed = [entry for entry in RESULTS if not entry["passed"]]

    summary = {
        "phase": "VISION_OBSERVATION_MODE_SEPARATION_V1",
        "final_status": (
            "VISION_OBSERVATION_MODE_SEPARATION_V1_PASS"
            if not failed
            else "VISION_OBSERVATION_MODE_SEPARATION_V1_BLOCKED"
        ),
        "passed": len(RESULTS) - len(failed),
        "total": len(RESULTS),
        "real_renders": 0,
        "comfy_output_before": comfy_before,
        "comfy_output_after": comfy_after,
        "data_root": DATA_ROOT,
        "results": RESULTS,
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:

        json.dump(summary, handle, ensure_ascii=False, indent=2)

    print("-" * 76)
    print(
        "  %d/%d PASS — %s"
        % (summary["passed"], summary["total"], summary["final_status"])
    )
    print("  report:", REPORT_PATH)
    print("=" * 76 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
