# ==========================================================
# ARCHITECTURAL_VISION_GROUNDING_V1 — LIVE ACCEPTANCE
#
# Proves, on a THROW-AWAY Core (spare port, isolated data root,
# render-stop guard), that:
#
#   * the two payloads the provider ACTUALLY returned for the reported
#     image no longer produce a visible window, and no longer announce an
#     observed closet as "not visible"
#   * the expected zones that were never reported are surfaced as
#     unknown gaps instead of silent omissions
#   * the grounding reaches a REAL image turn over HTTP, and the answer
#     carries the evidence check
#   * no element is ever published as visible without an object claim
#   * nothing is learned, stored, rendered or sent to ComfyUI
#
# Usage:
#   .venv/Scripts/python.exe tools/run_architectural_vision_grounding_01_acceptance.py
#
# Add --skip-contract to skip the suites (fast path).
# ==========================================================

import io
import json
import os
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

PORT = 5092

CORE = "http://127.0.0.1:%d" % PORT

WORK = os.path.join(ROOT, ".pytest_tmp", "vision_grounding_01_" + STAMP)

DATA_ROOT = os.path.join(WORK, "project_data")

os.makedirs(DATA_ROOT, exist_ok=True)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

LOG_PATH = os.path.join(WORK, "core.log")

REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_architectural_vision_grounding_01_report.json"
)


# ---- the provider payloads, verbatim from core_api.log ----

RUN_A = {
    "image_type": "floor_plan_or_sketch",
    "confidence": "HIGH",
    "observed": [
        "two side-by-side floor plans", "furniture icons", "Persian text",
        "mirror-image layout", "door symbols", "window symbols",
        "watermark text",
    ],
    "inferred": ["parental suite", "alternative layout options", "bedroom layout"],
    "unresolved": [
        "room dimensions", "material specifications",
        "unverified from image: bedroom layout",
    ],
    "architectural_elements": ["bed", "wardrobe", "desk", "chair", "door", "window"],
    "text_labels_if_visible": ["حریم خصوصی در اتاق والدین", "اتاق والدین"],
    "safety": {"supports_region_grounding": False},
}

RUN_B = {
    "image_type": "floor_plan_or_sketch",
    "confidence": "HIGH",
    "observed": [
        "two side-by-side floor plans", "mirrored layouts", "Persian text",
        "furniture icons", "bed", "wardrobe", "desk", "door symbols",
    ],
    "inferred": ["parental suite", "alternative layout options", "bedroom layout"],
    "unresolved": [
        "exact dimensions", "material specifications", "actual scale",
        "unverified from image: bedroom layout",
    ],
    "architectural_elements": ["bed", "wardrobe", "desk", "chair", "door", "wall"],
    "text_labels_if_visible": ["حریم خصوصی در اتاق والدین", "اتاق والدین"],
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
            json.dumps(detail, ensure_ascii=False, default=str)[:800],
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

    """A small floor-plan-like PNG, built here (no fixture file)."""

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


def shell_suite(name, relative):

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    finished = subprocess.run(
        [python, "-u", relative],
        cwd=ROOT,
        env=core_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    text = finished.stdout.decode("utf-8", errors="replace")

    lines = [line for line in text.splitlines() if "PASS" in line or "FAIL" in line]

    record(
        name,
        finished.returncode == 0 and "FAIL" not in text,
        {"summary": (lines[-1] if lines else "")[-200:], "rc": finished.returncode},
    )


def _visible_without_object_claim(grounding):

    """Elements published as visible with NO object-class claim."""

    bad = []

    for entry in grounding.get("elements") or []:

        if entry.get("status") != "visible":

            continue

        if not any(
            claim.get("class") == "object"
            for claim in entry.get("evidence") or []
        ):

            bad.append(entry.get("element"))

    return bad


# ==========================================================

def main():

    skip_contract = "--skip-contract" in sys.argv

    comfy_before = comfy_snapshot()

    print("\n" + "=" * 76)
    print("ARCHITECTURAL_VISION_GROUNDING_V1 — LIVE ACCEPTANCE")
    print("  core=%s" % CORE)
    print("  data root=%s" % DATA_ROOT)
    print("=" * 76)

    print("  comfy before:", comfy_before)

    # --------------------------------------------------
    # THE REPORTED PAYLOADS (in-process, deterministic)
    # --------------------------------------------------

    from core.vision.architectural_vision_grounding_v1 import (  # noqa: E402
        ground_vision_evidence,
        render_grounding,
    )

    from core.vision.architectural_vision_interpreter_v1 import (  # noqa: E402
        interpret_architectural_vision,
    )

    from core.vision.vision_report_v1 import render_vision_report  # noqa: E402

    grounding_a = ground_vision_evidence(RUN_A, space_type="master bedroom")

    interpretation_a = interpret_architectural_vision(RUN_A)

    window_status = next(
        (
            entry.get("status") for entry in grounding_a.get("elements") or []
            if entry.get("element") == "window"
        ),
        None,
    )

    record(
        "R.1 THE REPORTED FALSE POSITIVE — a plan-symbol window is NOT "
        "published as visible",
        window_status == "symbol_reading"
        and "daylight opening visible"
        not in (interpretation_a.get("observed_elements") or []),
        {
            "window_status": window_status,
            "observed_elements": interpretation_a.get("observed_elements"),
        },
    )

    answer_a = render_vision_report(interpretation_a, "fa")

    record(
        "R.2 the claim is still REPORTED (as unverified), so nothing is "
        "hidden from the teacher",
        "پنجره" in answer_a and "تأییدنشده" in answer_a,
        {"answer": answer_a[-320:]},
    )

    grounding_b = ground_vision_evidence(RUN_B, space_type="master bedroom")

    interpretation_b = interpret_architectural_vision(RUN_B)

    unknowns_b = " ".join(interpretation_b.get("unknowns") or [])

    record(
        "R.3 THE REPORTED FALSE NEGATIVE — an observed closet is visible and "
        "no longer announced as 'not visible'",
        "storage or dressing element visible"
        in (interpretation_b.get("observed_elements") or [])
        and "dressing or closet zone is not visible" not in unknowns_b,
        {
            "observed_elements": interpretation_b.get("observed_elements"),
            "unknowns": interpretation_b.get("unknowns"),
        },
    )

    gaps_b = {
        entry.get("element") for entry in grounding_b.get("expected_gaps") or []
    }

    record(
        "R.4 the expected-but-never-reported zones are surfaced as UNKNOWN "
        "gaps (bathroom / WC / circulation)",
        {"bathroom_or_ensuite", "wc", "circulation"}.issubset(gaps_b),
        {"gaps": sorted(gaps_b)},
    )

    record(
        "R.5 no element is published as visible without an object claim "
        "(the core invariant)",
        not _visible_without_object_claim(grounding_a)
        and not _visible_without_object_claim(grounding_b),
        {
            "run_a": _visible_without_object_claim(grounding_a),
            "run_b": _visible_without_object_claim(grounding_b),
        },
    )

    record(
        "R.6 the layer is read-only (no LLM / network / storage / render / "
        "geometry / ComfyUI)",
        grounding_a.get("llm_used") is False
        and grounding_a.get("network_used") is False
        and grounding_a.get("storage_used") is False
        and grounding_a.get("render_requested") is False
        and grounding_a.get("geometry_touched") is False
        and grounding_a.get("comfy_invoked") is False,
        {},
    )

    record(
        "R.7 the old behaviour is still reachable (ground=False)",
        "private bathroom connection is not visible"
        in (
            interpret_architectural_vision(RUN_A, ground=False)
            .get("unknowns") or []
        ),
        {},
    )

    # --------------------------------------------------
    # STATIC ARCHITECTURE
    # --------------------------------------------------

    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as handle:

        app_source = handle.read()

    record(
        "A.1 exactly one ChatArchitect is constructed in app.py",
        app_source.count("ChatArchitect(") == 1,
        {"count": app_source.count("ChatArchitect(")},
    )

    module_path = os.path.join(
        ROOT, "core", "vision", "architectural_vision_grounding_v1.py"
    )

    with open(module_path, encoding="utf-8") as handle:

        module_source = handle.read()

    forbidden = [
        token for token in (
            "\nclass ",
            "requests.",
            "llm_gateway",
            "import comfy",
            "app.run",
            ".save(",
            ".record(",
        )
        if token in module_source
    ]

    record(
        "A.2 the grounding layer defines no class and contains no network, "
        "LLM, storage or render call",
        not forbidden,
        {"forbidden": forbidden},
    )

    # --------------------------------------------------
    # LIVE HTTP — A REAL IMAGE TURN
    # --------------------------------------------------

    core = start_core("core")

    if not wait_for_core():

        record("X.1 fresh Core came up on the spare port", False, {"port": PORT})

        core.kill()

        return 1

    record("X.1 fresh Core came up on the spare port", True, {"port": PORT})

    try:

        status, created = http_json(
            CORE, "/api/projects", {"name": "Vision Grounding " + STAMP}
        )

        project_id = (created.get("project") or {}).get("project_id")

        record(
            "L.1 project created",
            status == 200 and bool(project_id),
            {"project_id": project_id},
        )

        if not project_id:

            return 1

        image_path = write_png(os.path.join(WORK, "plan.png"))

        response = multipart_image(image_path, "تحلیلت از این عکس چیه؟", project_id)

        raw = response.content

        payload = json.loads(raw.decode("utf-8"))

        answer = (payload.get("response") or {})

        interpretation = (
            answer.get("architectural_interpretation")
            or answer.get("result")
            or {}
        )

        if isinstance(interpretation, dict) and "contract" not in interpretation:

            interpretation = answer.get("architectural_interpretation") or {}

        grounding = (
            interpretation.get("grounding")
            if isinstance(interpretation, dict)
            else None
        ) or {}

        print("  provider=%s image_type=%s" % (
            grounding.get("provider"), grounding.get("image_type")))

        record(
            "L.2 the image turn is an analysis and carries the grounding "
            "contract over HTTP",
            response.status_code == 200
            and grounding.get("contract") == "ArchitecturalVisionGroundingV1",
            {
                "status": response.status_code,
                "contract": grounding.get("contract"),
            },
        )

        record(
            "L.3 no element reached `visible` without an object claim "
            "(live payload)",
            not _visible_without_object_claim(grounding),
            {"bad": _visible_without_object_claim(grounding)},
        )

        record(
            "L.4 the answer never claims the private bathroom is not visible "
            "without evidence, and reports the gaps instead",
            "اتصال سرویس خصوصی دیده نمی‌شود" not in (answer.get("message") or "")
            or "denied" in json.dumps(grounding, ensure_ascii=False),
            {"message_tail": (answer.get("message") or "")[-300:]},
        )

        record(
            "L.5 the answer ends with the evidence check (or the analysis is "
            "empty and says so)",
            "بررسی شواهد تصویری" in (answer.get("message") or "")
            or "از تصویر قابل تعیین نیست" in (answer.get("message") or ""),
            {"message_tail": (answer.get("message") or "")[-300:]},
        )

        record(
            "L.6 the grounding carries the expected set and its gaps",
            isinstance(grounding.get("expected_elements"), list)
            and isinstance(grounding.get("expected_gaps"), list),
            {
                "expected": len(grounding.get("expected_elements") or []),
                "gaps": len(grounding.get("expected_gaps") or []),
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
            "G.1 the grounding contract suite passes",
            os.path.join("tests", "test_architectural_vision_grounding_v1.py"),
        )

        shell_suite(
            "G.2 the ARCHITECTURAL_VISION_INTERPRETER_V1 suite passes",
            os.path.join("tests", "test_architectural_vision_interpreter_v1.py"),
        )

        shell_suite(
            "G.3 VISION_REPORT_LANGUAGE_01 regression",
            os.path.join("tests", "test_vision_report_language_01.py"),
        )

        shell_suite(
            "G.4 ARCHITECTURAL_KNOWLEDGE_STRUCTURER_V1 regression",
            os.path.join("tests", "test_architectural_knowledge_structurer_v1.py"),
        )

        shell_suite(
            "G.5 SUBJECT_SCOPE_AND_TURN_RECOVERY_01 regression",
            os.path.join("tests", "test_subject_scope_and_recovery_01.py"),
        )

        shell_suite(
            "G.6 TEACHING_QUESTION_RETRIEVAL regression",
            os.path.join("tests", "test_teaching_question_retrieval.py"),
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
        "phase": "ARCHITECTURAL_VISION_GROUNDING_V1",
        "final_status": (
            "ARCHITECTURAL_VISION_GROUNDING_V1_PASS"
            if not failed
            else "ARCHITECTURAL_VISION_GROUNDING_V1_BLOCKED"
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
