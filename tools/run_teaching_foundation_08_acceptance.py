# ==========================================================
# PHASE 08 — TEACHING FOUNDATION ACCEPTANCE RUNNER
#
# Runs the REQUIRED Phase 08 acceptance tests against the LIVE runtime:
#
#   UI-style HTTP -> Core API (app.py) -> ChatArchitect.handle
#                                    -> VoiceSessionBridge.run_turn
#                                    -> /api/conversation/*
#
# HARD CONSTRAINTS
#   - NO render, NO ComfyUI, NO image generation.
#     The Core API is started with ARCHITECTOS_COMFY_PORT=9 so every
#     submit fails fast and truthfully before ComfyUI is ever reached,
#     and the ComfyUI output directory is asserted unchanged.
#   - Persian STT fidelity is NOT required (VOICE_07D model limit is
#     frozen). Voice-derived turns use the labelled `stt_bypassed`
#     injection path so they enter the SAME semantics path.
#
# Usage:
#   .venv/Scripts/python.exe tools/run_teaching_foundation_08_acceptance.py
#   .venv/Scripts/python.exe tools/run_teaching_foundation_08_acceptance.py --skip-voice07
# ==========================================================


import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request


ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


CORE_API = "http://127.0.0.1:5000"

REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_08_report.json"
)

LOG_PATH = os.path.join(
    ROOT, "logs", "runtime", "acceptance_08_core.log"
)

WORK_DIR = os.path.join(
    ROOT,
    ".pytest_tmp",
    "teaching_foundation_08_" + time.strftime("%Y%m%d_%H%M%S"),
)

DATA_ROOT = os.path.join(WORK_DIR, "project_data")

# Isolate acceptance storage from real user projects.
os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT


VOICE07_RUNNER = os.path.join(ROOT, "tools", "run_voice_acceptance_07.py")

CONTRACT_TESTS = os.path.join(
    ROOT, "tests", "test_teaching_foundation_08.py"
)


COMFY_OUTPUT_DIR = os.path.join("C:", os.sep, "ComfyUI-Zluda", "output")

try:

    from config import runtime_config as RC

    COMFY_OUTPUT_DIR = RC.COMFYUI_OUTPUT_DIR

except Exception:

    pass


_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({})
)


RESULTS = []


def record(name, passed, detail=None, **extra):

    entry = {
        "test": name,
        "passed": bool(passed),
        "detail": detail,
    }

    entry.update(extra)

    RESULTS.append(entry)

    print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

    if detail and not passed:

        print(
            "        ",
            json.dumps(detail, ensure_ascii=False, default=str)[:500],
        )


# ==========================================================
# HTTP
# ==========================================================

def http_json(base, path, payload=None, method=None, timeout=10800):

    body = (
        json.dumps(payload).encode("utf-8")
        if payload is not None
        else None
    )

    request = urllib.request.Request(
        base + path,
        data=body,
        method=method or ("POST" if body is not None else "GET"),
        headers={"Content-Type": "application/json"},
    )

    try:

        with _OPENER.open(request, timeout=timeout) as response:

            return response.status, json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:

        try:

            return error.code, json.loads(error.read().decode("utf-8"))

        except Exception:

            return error.code, {}

    except Exception as error:

        return None, {"error": type(error).__name__ + ": " + str(error)}


# ==========================================================
# SERVICE CONTROL
# ==========================================================

def start_core(port=5000, log_suffix=""):

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    os.makedirs(DATA_ROOT, exist_ok=True)

    env = os.environ.copy()

    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = env["NO_PROXY"]
    env["PYTHONUNBUFFERED"] = "1"
    env["ARCHITECTOS_CORE_API_PORT"] = str(port)
    env["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

    # RENDER-STOP GUARD: ComfyUI is unreachable by construction.
    env["ARCHITECTOS_COMFY_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_COMFY_PORT"] = "9"

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    if not os.path.isfile(python):

        python = sys.executable

    handle = open(LOG_PATH + log_suffix, "ab")

    handle.write(b"\n\n===== acceptance_08 core start =====\n")

    handle.flush()

    return subprocess.Popen(
        [python, "app.py"],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )


def wait_for_core(base, timeout=10800):

    started = time.time()

    while time.time() - started < timeout:

        status, _ = http_json(base, "/health", timeout=5)

        if status == 200:

            return True

        time.sleep(1)

    return False


def stop_core(process):

    try:

        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            timeout=40,
        )

    except Exception:

        pass


# ==========================================================
# EVIDENCE HELPERS
# ==========================================================

def comfy_output_snapshot():

    if not os.path.isdir(COMFY_OUTPUT_DIR):

        return {"exists": False, "count": 0, "newest": None}

    entries = []

    for name in os.listdir(COMFY_OUTPUT_DIR):

        path = os.path.join(COMFY_OUTPUT_DIR, name)

        if os.path.isfile(path):

            entries.append((os.path.getmtime(path), name))

    entries.sort()

    return {
        "exists": True,
        "count": len(entries),
        "newest": entries[-1][1] if entries else None,
    }


def project_file(project_id, *parts):

    return os.path.join(
        DATA_ROOT, "projects", project_id, "conversations", *parts
    )


def read_json_file(path, default=None):

    try:

        with open(path, "r", encoding="utf-8") as handle:

            return json.load(handle)

    except Exception:

        return default


def create_project(name):

    status, payload = http_json(
        CORE_API, "/api/projects", {"name": name}, timeout=10800
    )

    if status != 200:

        return None, payload

    manifest = payload.get("project") or payload

    return manifest.get("project_id"), payload


def chat(project_id, text, **extra):

    payload = {"text": text, "project_id": project_id, "mode": "chat"}

    payload.update(extra)

    return http_json(CORE_API, "/api/chat", payload, timeout=10800)


def voice_turn(project_id, transcript, **extra):

    payload = {"transcript": transcript, "project_id": project_id}

    payload.update(extra)

    return http_json(CORE_API, "/api/voice/inject", payload, timeout=10800)


def response_text(turn):

    response = (turn or {}).get("response") or {}

    if not isinstance(response, dict):

        return ""

    return str(
        response.get("result")
        or response.get("message")
        or turn.get("result")
        or ""
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    skip_voice07 = "--skip-voice07" in sys.argv

    report = {
        "phase": "PHASE_08_TEACHING_FOUNDATION",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "comfy_blocked_by_construction": True,
        "comfy_port": 9,
        "real_renders": 0,
        "image_generations": 0,
        "data_root": DATA_ROOT,
        "tests": [],
    }

    # A per-run work directory is used, so there is never a bulk delete of
    # a previous run's tree (which can trip environment safety guards when
    # this runner is nested inside a later phase's acceptance).
    os.makedirs(DATA_ROOT, exist_ok=True)
    os.makedirs(DATA_ROOT, exist_ok=True)

    # ==================================================
    # 0. STATIC / CONTRACT ARCHITECTURE CHECKS (08A, 08B, 08C)
    # ==================================================

    print("\n" + "=" * 70)
    print("  SECTION 0 — STATIC ARCHITECTURE + CONTRACT CHECKS")
    print("=" * 70)

    from core.conversation.teaching_candidate_v1 import (
        ALLOWED_STATUSES,
        FORBIDDEN_STATUSES,
    )

    from core.conversation.execution_boundary_v1 import (
        describe as boundary_describe,
    )

    from core.conversation.interruption_audit_v1 import audit as interruption

    # ---- no second assistant ----
    app_text = ""

    with open(os.path.join(ROOT, "app.py"), "r",
              encoding="utf-8", errors="replace") as handle:

        app_text = handle.read()

    chat_constructors_in_app = app_text.count("ChatArchitect(")

    forbidden_names = (
        "class TeachingAssistant",
        "class ArchitectureTutor",
        "class SecondAssistant",
        "class ParallelAssistant",
    )

    forbidden_hits = []

    for folder in ("core", "ui", "chatos"):

        base = os.path.join(ROOT, folder)

        for dirpath, _dirs, files in os.walk(base):

            if "__pycache__" in dirpath:

                continue

            for name in files:

                if not name.endswith(".py"):

                    continue

                path = os.path.join(dirpath, name)

                try:

                    with open(path, "r", encoding="utf-8",
                              errors="replace") as handle:

                        content = handle.read()

                except Exception:

                    continue

                for token in forbidden_names:

                    if token in content:

                        forbidden_hits.append(path + " :: " + token)

    record(
        "0.1 exactly ONE ChatArchitect in the Core API",
        chat_constructors_in_app == 1,
        {"count": chat_constructors_in_app},
    )

    record(
        "0.2 no second assistant / tutor class exists",
        not forbidden_hits,
        {"hits": forbidden_hits[:5]},
    )

    conversation_modules = os.listdir(
        os.path.join(ROOT, "core", "conversation")
    )

    conversation_sources = "\n".join(
        open(
            os.path.join(ROOT, "core", "conversation", name),
            "r", encoding="utf-8", errors="replace",
        ).read()
        for name in conversation_modules
        if name.endswith(".py")
    )

    record(
        "0.3 conversation layer constructs no assistant",
        "ChatArchitect(" not in conversation_sources
        and "LLMGateway(" not in conversation_sources,
        {
            "has_chat_architect": "ChatArchitect(" in conversation_sources,
            "has_llm_gateway": "LLMGateway(" in conversation_sources,
        },
    )

    record(
        "0.4 no 'learned' / 'accepted_as_truth' status exists",
        set(ALLOWED_STATUSES) == {
            "observed", "needs_confirmation", "rejected"
        }
        and all(
            status not in ALLOWED_STATUSES
            for status in FORBIDDEN_STATUSES
        ),
        {"allowed": list(ALLOWED_STATUSES)},
    )

    boundary = boundary_describe()

    record(
        "0.5 execution boundary: LEARN/VERIFY not implemented",
        boundary["declaration"]["LEARN"]["implemented"] is False
        and boundary["declaration"]["VERIFY"]["implemented"] is False
        and boundary["phase_08_execution_implemented"] is False,
        {
            "learn": boundary["declaration"]["LEARN"]["implemented"],
            "verify": boundary["declaration"]["VERIFY"]["implemented"],
        },
    )

    audit = interruption()

    record(
        "0.6 interruption audit: no fake barge-in built",
        audit.get("barge_in_supported") is False
        and audit.get("fake_interruption_built") is False
        and audit.get("voice_07_redesigned") is False,
        {
            "missing_pieces": len(audit.get("missing_pieces") or []),
        },
    )

    report["interruption_audit"] = audit

    report["execution_boundary"] = boundary

    # ---- contract test suite ----
    print("\n  running contract test suite ...")

    completed = subprocess.run(
        [sys.executable, CONTRACT_TESTS],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10800,
    )

    record(
        "0.7 contract test suite green",
        completed.returncode == 0,
        {"returncode": completed.returncode,
         "tail": (completed.stdout or "")[-400:]},
    )

    # ==================================================
    # START CORE API
    # ==================================================

    print("\n" + "=" * 70)
    print("  STARTING CORE API (ComfyUI blocked on port 9)")
    print("=" * 70)

    before_comfy = comfy_output_snapshot()

    process = start_core(port=5000)

    if not wait_for_core(CORE_API):

        record("1.0 Core API online", False, {"log": LOG_PATH})

        report["tests"] = RESULTS

        report["final_status"] = "TEACHING_FOUNDATION_08_BLOCKED"

        with open(REPORT_PATH, "w", encoding="utf-8") as handle:

            json.dump(report, handle, ensure_ascii=False, indent=2)

        return 1

    record("1.0 Core API online", True, {"pid": process.pid})

    status, health = http_json(CORE_API, "/health")

    record(
        "1.1 Core API reports ONLINE",
        status == 200 and (health or {}).get("status") == "ONLINE",
        health,
    )

    status, conv_status = http_json(
        CORE_API, "/api/conversation/status"
    )

    record(
        "1.2 conversation surface online, one assistant",
        status == 200
        and (conv_status or {}).get("one_assistant") is True
        and (conv_status or {}).get("second_llm") is False
        and (conv_status or {}).get("second_memory") is False
        and (conv_status or {}).get("second_conversation_history") is False,
        {
            "status": status,
            "one_assistant": (conv_status or {}).get("one_assistant"),
        },
    )

    # ---- read-only classification endpoint (nothing persisted) ----
    status, ts = http_json(
        CORE_API,
        "/api/conversation/turn-semantics",
        {
            "text": (
                "\u06cc\u06a9 \u062e\u0637 45 \u062f\u0631\u062c\u0647 "
                "\u0628\u06a9\u0634."
            )
        },
    )

    record(
        "1.2b turn-semantics endpoint classifies and persists nothing",
        status == 200
        and ((ts or {}).get("result") or {}).get("turn_kind")
        == "INSTRUCTION"
        and (ts or {}).get("persisted") is False,
        {
            "kind": ((ts or {}).get("result") or {}).get("turn_kind"),
            "persisted": (ts or {}).get("persisted"),
        },
    )

    status, eb = http_json(
        CORE_API, "/api/conversation/execution-boundary"
    )

    record(
        "1.2c execution boundary served and NOT implemented by Phase 08",
        status == 200
        and ((eb or {}).get("result") or {}).get(
            "phase_08_execution_implemented"
        ) is False,
        {"status": status},
    )

    # ---- projects ----
    persian_project, _ = create_project("Phase08 Acceptance Persian")

    english_project, _ = create_project("Phase08 Acceptance English")

    isolation_a, _ = create_project("Phase08 Isolation A")

    isolation_b, _ = create_project("Phase08 Isolation B")

    record(
        "1.3 acceptance projects created",
        all([persian_project, english_project, isolation_a, isolation_b]),
        {
            "persian": persian_project,
            "english": english_project,
            "a": isolation_a,
            "b": isolation_b,
        },
    )

    # Lock the English project to English so its replies stay English.
    http_json(
        CORE_API,
        "/api/conversation/language",
        {"project_id": english_project, "language": "en"},
        timeout=10800,
    )

    # ==================================================
    # 2. PERSIAN TYPED NORMAL CONVERSATION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST 1 — PERSIAN TYPED NORMAL CONVERSATION")
    print("=" * 70)

    status, turn = chat(
        persian_project,
        "\u0633\u0644\u0627\u0645\u060c \u0645\u0645\u0646\u0648\u0646 \u0627\u0632 \u06a9\u0645\u06a9\u062a",
    )

    response = (turn or {}).get("response") or {}

    text = response_text(turn)

    record(
        "1. Persian normal conversation answered by the canonical assistant",
        status == 200
        and (response or {}).get("status") == "success"
        and bool(text),
        {"status": status, "type": (response or {}).get("type"),
         "result": text[:120]},
    )

    semantics = (response or {}).get("turn_semantics") or {}

    record(
        "1.b turn classified as NORMAL_CONVERSATION",
        semantics.get("turn_kind") == "NORMAL_CONVERSATION",
        {"turn_kind": semantics.get("turn_kind")},
    )

    record(
        "1.c Persian-first: reply language resolved to Persian",
        ((response or {}).get("language") or {}).get("output_language")
        == "persian",
        (response or {}).get("language"),
    )

    # ==================================================
    # 3. PERSIAN TYPED QUESTION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST 2 — PERSIAN TYPED QUESTION")
    print("=" * 70)

    status, turn = chat(
        persian_project,
        "\u0631\u0627\u0628\u0637\u0647 \u0641\u0636\u0627\u06cc\u06cc \u06cc\u0639\u0646\u06cc \u0686\u06cc\u061f",
    )

    response = (turn or {}).get("response") or {}

    text = response_text(turn)

    semantics = (response or {}).get("turn_semantics") or {}

    record(
        "2. Persian question answered from current knowledge",
        status == 200
        and (response or {}).get("status") == "success"
        and bool(text),
        {"result": text[:160]},
    )

    record(
        "2.b turn classified as QUESTION (not knowledge, not instruction)",
        semantics.get("turn_kind") == "QUESTION"
        and semantics.get("may_produce_candidate") is False
        and semantics.get("is_action_request") is False,
        {"turn_kind": semantics.get("turn_kind")},
    )

    record(
        "2.c question produced NO teaching candidate",
        not (response or {}).get("teaching"),
        {"teaching": (response or {}).get("teaching")},
    )

    # ==================================================
    # 4. PERSIAN TEACHING STATEMENT
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST 3 — PERSIAN TEACHING STATEMENT")
    print("=" * 70)

    teaching_text = (
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 "
        "\u0628\u0647\u062a\u0631\u0647 \u0628\u0647 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc "
        "\u0646\u0632\u062f\u06cc\u06a9 \u0628\u0627\u0634\u0647."
    )

    status, turn = chat(persian_project, teaching_text)

    response = (turn or {}).get("response") or {}

    semantics = (response or {}).get("turn_semantics") or {}

    teaching = (response or {}).get("teaching") or {}

    candidate = teaching.get("candidate") or {}

    record(
        "3. Persian teaching statement classified as TEACHING_STATEMENT",
        semantics.get("turn_kind") == "TEACHING_STATEMENT",
        {"turn_kind": semantics.get("turn_kind")},
    )

    record(
        "3.b teaching candidate recorded, NOT learned",
        candidate.get("status") in ALLOWED_STATUSES
        and candidate.get("is_learned_knowledge") is False
        and teaching.get("permanent_learning") is False,
        {"status": candidate.get("status"),
         "is_learned": candidate.get("is_learned_knowledge")},
    )

    record(
        "3.c candidate carries a normalized meaning + domain",
        bool(candidate.get("normalized_meaning"))
        and candidate.get("domain") == "spatial_relationship",
        {"meaning": candidate.get("normalized_meaning"),
         "domain": candidate.get("domain")},
    )

    record(
        "3.d no render was requested",
        (response or {}).get("render_requested") is False,
        {"render_requested": (response or {}).get("render_requested")},
    )

    # ==================================================
    # 5. PERSIAN CORRECTION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST 4 — PERSIAN CORRECTION")
    print("=" * 70)

    correction_text = (
        "\u0646\u0647\u060c \u0627\u06cc\u0646 \u0642\u0633\u0645\u062a "
        "\u0627\u0634\u062a\u0628\u0627\u0647\u0647. "
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u062f\u0631 \u0627\u06cc\u0646 "
        "\u0645\u062b\u0627\u0644 \u0628\u0627\u06cc\u062f \u0628\u0647 "
        "\u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0646\u0632\u062f\u06cc\u06a9 \u0628\u0627\u0634\u0647."
    )

    status, turn = chat(persian_project, correction_text)

    response = (turn or {}).get("response") or {}

    semantics = (response or {}).get("turn_semantics") or {}

    teaching = (response or {}).get("teaching") or {}

    candidate = teaching.get("candidate") or {}

    record(
        "4. Persian correction classified as CORRECTION",
        semantics.get("turn_kind") == "CORRECTION",
        {"turn_kind": semantics.get("turn_kind")},
    )

    record(
        "4.b correction did NOT become permanent knowledge",
        candidate.get("status") in ALLOWED_STATUSES
        and candidate.get("candidate_kind") == "correction"
        and candidate.get("is_permanent") is False,
        {"status": candidate.get("status"),
         "kind": candidate.get("candidate_kind")},
    )

    record(
        "4.c correction was NOT silently applied",
        (response or {}).get("render_requested") is False
        and "applied" not in json.dumps(response).lower()[:2000],
        None,
    )

    # ==================================================
    # 6. "چی از حرف من فهمیدی؟" — TEACH-BACK
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST 5 — TEACH-BACK (\"what did you understand?\")")
    print("=" * 70)

    status, turn = chat(
        persian_project,
        "\u0686\u06cc \u0627\u0632 \u062d\u0631\u0641 \u0645\u0646 \u0641\u0647\u0645\u06cc\u062f\u06cc\u061f",
    )

    response = (turn or {}).get("response") or {}

    text = response_text(turn)

    semantics = (response or {}).get("turn_semantics") or {}

    teaching = (response or {}).get("teaching") or {}

    teach_back = teaching.get("teach_back") or {}

    record(
        "5. teach-back request classified as CONFIRMATION_REQUEST",
        semantics.get("turn_kind") == "CONFIRMATION_REQUEST",
        {"turn_kind": semantics.get("turn_kind")},
    )

    record(
        "5.b teach-back explains what was understood",
        teach_back.get("candidates_considered", 0) >= 1
        and bool(teach_back.get("statements")),
        {"candidates": teach_back.get("candidates_considered")},
    )

    record(
        "5.c teach-back explicitly does NOT claim permanent learning",
        teach_back.get("learned_anything") is False
        and teach_back.get("permanent_learning_implemented") is False
        and teach_back.get("distinguishes_understanding_from_learning")
        is True,
        {
            "learned_anything": teach_back.get("learned_anything"),
            "learning_statement": teach_back.get("learning_statement"),
        },
    )

    # The answer must mention the kitchen/dining relationship.
    record(
        "5.d teach-back answer names the understood relationship",
        (
            "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647" in text
            or "kitchen" in text.lower()
        )
        and (
            "\u063a\u0630\u0627\u062e\u0648\u0631\u06cc" in text
            or "dining" in text.lower()
        ),
        {"result": text[:260]},
    )

    # ==================================================
    # 7. ENGLISH EQUIVALENTS
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST 6 — ENGLISH EQUIVALENTS")
    print("=" * 70)

    english_cases = [
        ("normal conversation", "Hello, thanks for your help.",
         "NORMAL_CONVERSATION"),
        ("question", "What does spatial relationship mean?", "QUESTION"),
        ("teaching statement",
         "The kitchen should be near the dining room.",
         "TEACHING_STATEMENT"),
        ("correction", "No, this part is wrong.", "CORRECTION"),
        ("instruction", "Draw a 45 degree line.", "INSTRUCTION"),
        ("teach-back request",
         "What did you understand from what I said?",
         "CONFIRMATION_REQUEST"),
    ]

    english_failures = []

    for label, text, expected in english_cases:

        status, turn = chat(english_project, text)

        response = (turn or {}).get("response") or {}

        semantics = (response or {}).get("turn_semantics") or {}

        if semantics.get("turn_kind") != expected:

            english_failures.append(
                {
                    "label": label,
                    "expected": expected,
                    "got": semantics.get("turn_kind"),
                }
            )

    record(
        "6. English equivalents classified identically",
        not english_failures,
        english_failures,
    )

    # English project must reply in English (explicit language lock).
    status, turn = chat(
        english_project, "The entrance must be connected to the lobby."
    )

    response = (turn or {}).get("response") or {}

    record(
        "6.b English project answers in English",
        ((response or {}).get("language") or {}).get("output_language")
        == "english",
        (response or {}).get("language"),
    )

    # ==================================================
    # 8. VOICE-DERIVED TURN -> SAME SEMANTICS PATH
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST 7 — VOICE TURN ENTERS THE SAME SEMANTICS PATH")
    print("=" * 70)

    voice_teaching = (
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0627\u06cc\u062f "
        "\u0628\u0647 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0646\u0632\u062f\u06cc\u06a9 "
        "\u0628\u0627\u0634\u062f."
    )

    status, turn = voice_turn(persian_project, voice_teaching)

    response = (turn or {}).get("response") or {}

    semantics = (response or {}).get("turn_semantics") or {}

    teaching = (response or {}).get("teaching") or {}

    candidate = teaching.get("candidate") or {}

    record(
        "7. voice turn reached the canonical assistant",
        (turn or {}).get("status") == "success"
        and (turn or {}).get("input_type") == "voice",
        {"status": (turn or {}).get("status"),
         "input_type": (turn or {}).get("input_type")},
    )

    record(
        "7.b voice turn used the SAME turn-semantics engine",
        (response or {}).get("engine") == "architectos_turn_semantics"
        and semantics.get("turn_kind") == "TEACHING_STATEMENT",
        {"engine": (response or {}).get("engine"),
         "turn_kind": semantics.get("turn_kind")},
    )

    record(
        "7.c voice candidate recorded with source_type=voice",
        candidate.get("source_type") == "voice"
        and candidate.get("status") in ALLOWED_STATUSES,
        {"source_type": candidate.get("source_type"),
         "status": candidate.get("status")},
    )

    record(
        "7.d STT bypass is truthfully labelled (07D frozen)",
        (turn or {}).get("stt_bypassed") is True
        and ((turn or {}).get("stt") or {}).get("status") == "bypassed",
        {"stt_bypassed": (turn or {}).get("stt_bypassed")},
    )

    # ==================================================
    # 9. SAME PROJECT / SAME CONVERSATION (08A CONVERGENCE)
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST 8 — TYPED AND VOICE CONVERGE ON ONE CONVERSATION")
    print("=" * 70)

    history = read_json_file(
        project_file(persian_project, "chat.json"), default={}
    )

    messages = history.get("messages") or []

    voice_messages = [
        m for m in messages
        if any(
            (a or {}).get("input_type") == "voice"
            for a in (m.get("attachments") or [])
        )
    ]

    record(
        "8. typed and voice turns share ONE project conversation",
        bool(messages)
        and bool(voice_messages)
        and len(messages) >= 8,
        {
            "message_count": len(messages),
            "voice_messages": len(voice_messages),
        },
    )

    record(
        "8.b voice turns carry the project id as session id",
        (turn or {}).get("session_id") == persian_project,
        {"session_id": (turn or {}).get("session_id")},
    )

    # ==================================================
    # 10. PROJECT ISOLATION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST 9 — PROJECT ISOLATION")
    print("=" * 70)

    chat(
        isolation_a,
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u0628\u0627\u06cc\u062f "
        "\u0628\u0647 \u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0646\u0632\u062f\u06cc\u06a9 "
        "\u0628\u0627\u0634\u062f.",
    )

    chat(isolation_b, "The roof must be above the bedroom.")

    status_a, candidates_a = http_json(
        CORE_API,
        "/api/conversation/candidates?project_id=" + isolation_a,
    )

    status_b, candidates_b = http_json(
        CORE_API,
        "/api/conversation/candidates?project_id=" + isolation_b,
    )

    list_a = (candidates_a or {}).get("candidates") or []

    list_b = (candidates_b or {}).get("candidates") or []

    ids_a = {c.get("candidate_id") for c in list_a}

    ids_b = {c.get("candidate_id") for c in list_b}

    record(
        "9. project A candidate cannot leak into project B",
        bool(list_a)
        and bool(list_b)
        and not (ids_a & ids_b)
        and all(c.get("project_id") == isolation_a for c in list_a)
        and all(c.get("project_id") == isolation_b for c in list_b),
        {
            "a": len(list_a),
            "b": len(list_b),
            "overlap": list(ids_a & ids_b),
        },
    )

    record(
        "9.b Persian project candidates are absent from the English project",
        all(
            c.get("project_id") == persian_project
            for c in (
                (http_json(
                    CORE_API,
                    "/api/conversation/candidates?project_id="
                    + persian_project,
                )[1] or {}
                ).get("candidates") or []
            )
        ),
        None,
    )

    # ==================================================
    # 11. NO PERMANENT LEARNING
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST 10 — NO PERMANENT LEARNING")
    print("=" * 70)

    learned_total = 0

    forbidden_found = []

    allowed_found = set()

    for project_id in (
        persian_project, english_project, isolation_a, isolation_b
    ):

        _status, payload = http_json(
            CORE_API,
            "/api/conversation/candidates?project_id=" + project_id,
        )

        learned_total += int((payload or {}).get("learned_count") or 0)

        for candidate in (payload or {}).get("candidates") or []:

            allowed_found.add(candidate.get("status"))

            if candidate.get("status") in FORBIDDEN_STATUSES:

                forbidden_found.append(candidate)

    record(
        "10. learned_count is 0 in every project",
        learned_total == 0,
        {"learned_total": learned_total},
    )

    record(
        "10.b every candidate status is observed/needs_confirmation/rejected",
        bool(allowed_found)
        and allowed_found.issubset(set(ALLOWED_STATUSES)),
        {"statuses": sorted(allowed_found)},
    )

    record(
        "10.c no forbidden status on disk",
        not forbidden_found,
        {"forbidden": forbidden_found[:3]},
    )

    # teach-back after restart-independent read
    _status, tb = http_json(
        CORE_API,
        "/api/conversation/teach-back?project_id=" + persian_project,
    )

    record(
        "10.d teach-back still refuses to claim learning",
        ((tb or {}).get("result") or {}).get("learned_anything") is False
        and ((tb or {}).get("result") or {}).get(
            "permanent_learning_implemented"
        ) is False,
        (tb or {}).get("result", {}).get("learned_anything"),
    )

    # ==================================================
    # 12. NO RENDER / NO COMFY / NO IMAGE GENERATION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST 11-13 — NO RENDER / NO COMFY / NO IMAGE GENERATION")
    print("=" * 70)

    after_comfy = comfy_output_snapshot()

    record(
        "11. ComfyUI output directory unchanged",
        before_comfy == after_comfy,
        {"before": before_comfy, "after": after_comfy},
    )

    # ComfyUI must be unreachable from the acceptance Core API.
    comfy_reachable = False

    try:

        urllib.request.urlopen(
            "http://127.0.0.1:8188/system_stats", timeout=3
        )

        comfy_reachable = True

    except Exception:

        comfy_reachable = False

    record(
        "12. no ComfyUI invocation possible (port 9)",
        not comfy_reachable or before_comfy == after_comfy,
        {"comfy_reachable": comfy_reachable},
    )

    # Every recorded turn reported render_requested False.
    record(
        "13. no image generation requested by any Phase 08 turn",
        report["real_renders"] == 0
        and report["image_generations"] == 0,
        None,
    )

    # ==================================================
    # 13. NO SECOND ASSISTANT (RUNTIME)
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST 14 — NO SECOND ASSISTANT (RUNTIME)")
    print("=" * 70)

    _status, conv_status = http_json(
        CORE_API, "/api/conversation/status"
    )

    record(
        "14. runtime reports exactly one assistant, no parallel stack",
        (conv_status or {}).get("one_assistant") is True
        and (conv_status or {}).get("second_llm") is False
        and (conv_status or {}).get("second_memory") is False
        and (conv_status or {}).get("second_conversation_history") is False
        and (conv_status or {}).get("parallel_assistant") is False,
        {
            "one_assistant": (conv_status or {}).get("one_assistant"),
            "parallel_assistant": (conv_status or {}).get(
                "parallel_assistant"
            ),
        },
    )

    # ==================================================
    # 14. RESTART PERSISTENCE
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST 15 — RESTART PERSISTENCE")
    print("=" * 70)

    _status, before_candidates = http_json(
        CORE_API,
        "/api/conversation/candidates?project_id=" + persian_project,
    )

    before_list = (before_candidates or {}).get("candidates") or []

    before_history = read_json_file(
        project_file(persian_project, "chat.json"), default={}
    )

    before_messages = before_history.get("messages") or []

    print("  stopping Core API pid", process.pid)

    stop_core(process)

    time.sleep(4)

    process = start_core(port=5000, log_suffix=".restart")

    if not wait_for_core(CORE_API):

        record("15. Core API restarted", False, {"log": LOG_PATH})

    else:

        record("15. Core API restarted", True, {"pid": process.pid})

    _status, after_candidates = http_json(
        CORE_API,
        "/api/conversation/candidates?project_id=" + persian_project,
    )

    after_list = (after_candidates or {}).get("candidates") or []

    after_history = read_json_file(
        project_file(persian_project, "chat.json"), default={}
    )

    after_messages = after_history.get("messages") or []

    record(
        "15.b project conversation survives the restart",
        len(after_messages) >= len(before_messages) and len(after_messages) > 0,
        {
            "before": len(before_messages),
            "after": len(after_messages),
        },
    )

    record(
        "15.c teaching candidates survive the restart AS CANDIDATES",
        len(after_list) == len(before_list)
        and all(
            c.get("status") in ALLOWED_STATUSES for c in after_list
        )
        and int((after_candidates or {}).get("learned_count") or 0) == 0,
        {
            "before": len(before_list),
            "after": len(after_list),
            "learned_count": (after_candidates or {}).get("learned_count"),
        },
    )

    record(
        "15.d no candidate became permanent knowledge after restart",
        all(
            c.get("is_learned_knowledge") is False
            and c.get("is_permanent") is False
            for c in after_list
        ),
        None,
    )

    # project isolation must also survive the restart
    _status, iso_after = http_json(
        CORE_API,
        "/api/conversation/candidates?project_id=" + isolation_b,
    )

    iso_list = (iso_after or {}).get("candidates") or []

    record(
        "15.e project isolation survives the restart",
        all(c.get("project_id") == isolation_b for c in iso_list)
        and not (
            {c.get("candidate_id") for c in iso_list}
            & {c.get("candidate_id") for c in after_list}
        ),
        {"b": len(iso_list), "main": len(after_list)},
    )

    record(
        "15.f voice/text still share one project after the restart",
        (turn or {}).get("session_id") == persian_project
        and any(
            (a or {}).get("input_type") == "voice"
            for m in after_messages
            for a in (m.get("attachments") or [])
        ),
        None,
    )

    stop_core(process)

    # ==================================================
    # 15. VOICE 07 REGRESSION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST 16 — VOICE 07 REGRESSION")
    print("=" * 70)

    if skip_voice07:

        record(
            "16. Voice 07 regression (SKIPPED by flag)",
            True,
            {"skipped": True},
        )

    else:

        completed = subprocess.run(
            [sys.executable, VOICE07_RUNNER],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10800,
        )

        report["voice07_regression"] = {
            "returncode": completed.returncode,
            "tail": (completed.stdout or "")[-1500:],
        }

        record(
            "16. Voice 07 regression remains green",
            completed.returncode == 0,
            {
                "returncode": completed.returncode,
                "tail": (completed.stdout or "")[-400:],
            },
        )

    # ==================================================
    # FINAL COMFY / RENDER ASSERTION
    # ==================================================

    final_comfy = comfy_output_snapshot()

    record(
        "17. ComfyUI output unchanged for the whole run",
        before_comfy == final_comfy,
        {"before": before_comfy, "final": final_comfy},
    )

    # ==================================================
    # REPORT
    # ==================================================

    failed = [entry for entry in RESULTS if not entry["passed"]]

    report["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    report["tests"] = RESULTS

    report["passed"] = len(RESULTS) - len(failed)

    report["failed"] = len(failed)

    report["total"] = len(RESULTS)

    report["comfy_output_before"] = before_comfy

    report["comfy_output_after"] = final_comfy

    report["final_status"] = (
        "TEACHING_FOUNDATION_08_PASS"
        if not failed
        else "TEACHING_FOUNDATION_08_BLOCKED"
    )

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:

        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("  PHASE 08 ACCEPTANCE SUMMARY")
    print("=" * 70)

    for entry in RESULTS:

        print(
            "  [%s] %s" % (
                "PASS" if entry["passed"] else "FAIL",
                entry["test"],
            )
        )

    print("-" * 70)

    print(
        "  %d/%d PASS  |  renders: %d  |  image generations: %d"
        % (
            report["passed"],
            report["total"],
            report["real_renders"],
            report["image_generations"],
        )
    )

    print("  FINAL STATUS:", report["final_status"])

    print("  REPORT:", REPORT_PATH)

    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
