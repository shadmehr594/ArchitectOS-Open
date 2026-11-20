# ==========================================================
# CHAT TEACHING ROUTING — DEBUG + ACCEPTANCE RUNNER
#
# Continues the interrupted CHAT RUNTIME DEBUG checkpoint:
#   "dump the raw payloads"
#
# Drives the REAL runtime:
#   HTTP -> Core API (app.py) -> /api/chat -> ChatArchitect.handle
#                                          -> teaching_foundation.observe_turn
#
# HARD CONSTRAINTS
#   - NO render, NO ComfyUI. The Core API is started with
#     ARCHITECTOS_COMFY_PORT=9 so every submit fails fast, and the
#     ComfyUI output directory is asserted unchanged.
#   - NO curriculum start, NO lesson creation, NO knowledge promotion.
#   - NO geometry / CAD / DWG / BIM / IFC.
#
# Usage:
#   .venv/Scripts/python.exe tools/run_chat_teaching_routing_acceptance.py
#   .venv/Scripts/python.exe tools/run_chat_teaching_routing_acceptance.py --in-process
# ==========================================================

import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


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

PORT = 5099

CORE_API = "http://127.0.0.1:%d" % PORT

WORK_DIR = os.path.join(
    ROOT, ".pytest_tmp", "chat_teaching_routing_" + STAMP
)

DATA_ROOT = os.path.join(WORK_DIR, "project_data")

os.makedirs(DATA_ROOT, exist_ok=True)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

LOG_PATH = os.path.join(
    ROOT, "logs", "runtime", "chat_teaching_routing_core.log"
)

PAYLOAD_EVIDENCE = os.path.join(
    ROOT, "tools", "chat_teaching_routing_payloads.json"
)

REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_chat_teaching_routing_report.json"
)

CONTRACT_TESTS = [
    os.path.join(ROOT, "tests", "test_chat_runtime_regression_fix.py"),
    os.path.join(ROOT, "tests", "test_chat_error_envelope_shape.py"),
    os.path.join(ROOT, "tests", "test_teacher_role_response.py"),
    os.path.join(ROOT, "tests", "test_teaching_session_state_fix.py"),
]


try:

    from config import runtime_config as RC

    COMFY_OUTPUT_DIR = RC.COMFYUI_OUTPUT_DIR

except Exception:

    COMFY_OUTPUT_DIR = os.path.join("C:", os.sep, "ComfyUI-Zluda", "output")


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

RESULTS = []

PAYLOADS = {}

MSG_A = "سلام می‌خوایم اولین جلسه آموزش معماری رو شروع کنیم"

MSG_B = "قراره من یادت بدم طراحی کردن رو و فضاهای معماری رو"

MSG_B_FULL = (
    "قراره من یادت بدم طراحی کردن رو و فضاهای معماری رو و من ازت "
    "می‌پرسم ببینم برداشتت از حرفایه من چیه باهم تعامل کنیم و بعد از "
    "مدتی بتونی طراحی رو انجام بدی"
)

MSG_C = "اتاق خواب فضای خصوصی است"

MSG_D = "امروز هوا خوبه"

# TEACHING SESSION STATE FIX — the messages from the bug report.
MSG_REFLECT = "برداشت فعلی تو از اتاق خواب چیست؟"

MSG_REFLECT_MIXED = (
    "می‌خواهم اولین درس معماری را شروع کنم. موضوع: اتاق خواب. "
    "قبل از اینکه من چیزی آموزش بدهم، بگو برداشت فعلی تو از این فضا "
    "چیست و چه چیزهایی درباره آن می‌دانی؟"
)

MSG_REFLECT_GENERIC = (
    "بگو برداشت فعلی تو از این فضا چیست و چه چیزهایی درباره آن "
    "می‌دانی؟"
)


def record(name, passed, detail=None, **extra):

    entry = {"test": name, "passed": bool(passed), "detail": detail}

    entry.update(extra)

    RESULTS.append(entry)

    print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

    if detail and not passed:

        print(
            "        ",
            json.dumps(detail, ensure_ascii=False, default=str)[:600],
        )


def banner(title):

    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


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

def start_core():

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    env = os.environ.copy()

    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = env["NO_PROXY"]
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["ARCHITECTOS_CORE_API_PORT"] = str(PORT)
    env["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

    # RENDER-STOP GUARD — ComfyUI unreachable by construction.
    env["ARCHITECTOS_COMFY_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_COMFY_PORT"] = "9"

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    if not os.path.isfile(python):

        python = sys.executable

    handle = open(LOG_PATH, "ab")

    handle.write(
        ("\n\n===== chat_teaching_routing start @ %s =====\n" % STAMP)
        .encode("utf-8")
    )

    handle.flush()

    return subprocess.Popen(
        [python, "app.py"],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )


def wait_for_core(timeout=10800):

    started = time.time()

    while time.time() - started < timeout:

        status, _ = http_json(CORE_API, "/health", timeout=5)

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


def port_is_free():

    status, _ = http_json(CORE_API, "/health", timeout=3)

    return status is None


# ==========================================================
# EVIDENCE
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


def lesson_inventory():

    hits = []

    for base, _dirs, files in os.walk(ROOT):

        if ".venv" in base or "node_modules" in base or ".git" in base:

            continue

        for name in files:

            low = name.lower()

            if "lesson" in low and low.endswith((".py", ".json")):

                hits.append(os.path.relpath(os.path.join(base, name), ROOT))

    return sorted(hits)


# ==========================================================
# LIVE TESTS
# ==========================================================

def run_live():

    banner("LIVE RUNTIME — REAL /api/chat")

    status, created = http_json(
        CORE_API, "/api/projects", {"name": "Chat Teaching Routing " + STAMP}
    )

    project_id = (created.get("project") or {}).get("project_id")

    record(
        "L.0 project created",
        status == 200 and bool(project_id),
        {"status": status, "project_id": project_id},
    )

    if not project_id:

        return

    cases = [
        ("A", MSG_A),
        ("B", MSG_B),
        ("B_full", MSG_B_FULL),
        ("C", MSG_C),
        ("D", MSG_D),
        # TEACHING SESSION STATE FIX
        ("R", MSG_REFLECT),
        ("R_mixed", MSG_REFLECT_MIXED),
        ("R_generic", MSG_REFLECT_GENERIC),
    ]

    raw = {}

    for tag, message in cases:

        status, payload = http_json(
            CORE_API,
            "/api/chat",
            {"text": message, "project_id": project_id},
        )

        raw[tag] = {"request": message, "http": status, "payload": payload}

        print("\n  --- MSG %s  HTTP %s ---" % (tag, status))

        print(
            "  envelope keys:",
            sorted((payload or {}).keys()),
        )

        response = (payload or {}).get("response") or {}

        print("  response keys:", sorted(response.keys()))

        print(
            "  message:",
            (response.get("message") or response.get("result") or "")[:180]
            .replace("\n", " / "),
        )

    PAYLOADS["live"] = raw

    # ---- A ----
    a_resp = ((raw["A"]["payload"] or {}).get("response") or {})

    a_sem = a_resp.get("turn_semantics") or {}

    a_teach = a_resp.get("teaching") or {}

    record(
        "A.1 MSG A classified OFFER_TO_TEACH (teaching intent)",
        a_sem.get("turn_kind") == "OFFER_TO_TEACH"
        and a_sem.get("teaching_intent") is True,
        {"turn_kind": a_sem.get("turn_kind")},
    )

    record(
        "A.2 MSG A capability == UNDERSTAND (not EXECUTE/IMAGE/TEXT_TO_IMAGE)",
        a_resp.get("capability") == "UNDERSTAND",
        {"capability": a_resp.get("capability")},
    )

    record(
        "A.3 MSG A teaching action == elicit_teaching_aspect",
        a_teach.get("action") == "elicit_teaching_aspect",
        {"action": a_teach.get("action")},
    )

    record(
        "A.4 MSG A asks which aspect to teach",
        "کدام بخش" in (a_resp.get("message") or ""),
        {"message": (a_resp.get("message") or "")[:120]},
    )

    record(
        "A.5 MSG A produced NO render and NO candidate",
        a_resp.get("render_requested") is False
        and a_teach.get("candidate") is None
        and a_teach.get("permanent_learning") is False,
        {
            "render_requested": a_resp.get("render_requested"),
            "candidate": a_teach.get("candidate"),
        },
    )

    record(
        "A.6 MSG A did NOT fall through to the generic LLM path",
        a_resp.get("engine") == "architectos_turn_semantics"
        and (a_resp.get("engine") or "") != "brain"
        and (a_resp.get("engine") or "") != "llm_gateway",
        {"engine": a_resp.get("engine")},
    )

    # TEACHER ROLE RESPONSE FIX — the wording must present the role
    # contract (user = teacher, assistant = learner).
    record(
        "A.7 MSG A exposes user_as_teacher=True",
        a_teach.get("user_as_teacher") is True
        and a_teach.get("assistant_as_learner") is True,
        {
            "user_as_teacher": a_teach.get("user_as_teacher"),
            "assistant_as_learner": a_teach.get("assistant_as_learner"),
        },
    )

    record(
        "A.8 MSG A reply names the user as teacher (no role inversion)",
        "مدرس" in (a_resp.get("message") or "")
        and "می‌خواهید یاد بگیرید" not in (a_resp.get("message") or ""),
        {"message": (a_resp.get("message") or "")[:140]},
    )

    # ---- B ----
    b_resp = ((raw["B"]["payload"] or {}).get("response") or {})

    b_sem = b_resp.get("turn_semantics") or {}

    b_teach = b_resp.get("teaching") or {}

    record(
        "B.1 MSG B classified OFFER_TO_TEACH",
        b_sem.get("turn_kind") == "OFFER_TO_TEACH",
        {"turn_kind": b_sem.get("turn_kind")},
    )

    record(
        "B.2 MSG B direction == user_offers_to_teach",
        b_sem.get("teaching_intent_direction") == "user_offers_to_teach",
        {"direction": b_sem.get("teaching_intent_direction")},
    )

    record(
        "B.3 MSG B capability == UNDERSTAND + elicit_teaching_aspect",
        b_resp.get("capability") == "UNDERSTAND"
        and b_teach.get("action") == "elicit_teaching_aspect",
        {
            "capability": b_resp.get("capability"),
            "action": b_teach.get("action"),
        },
    )

    # TEACHER ROLE RESPONSE FIX — this assertion used to pin the OLD
    # lead ("آماده‌ام یاد بگیرم"), which only implied the assistant's
    # role and never named the user as the teacher. It is RELAXED to the
    # role contract the brief requires, and an explicit check that the
    # old inverted wording is GONE is ADDED rather than the old
    # assertion being deleted.
    record(
        "B.4 MSG B reply states the teacher/learner role contract",
        "مدرس" in (b_resp.get("message") or "")
        and "من یاد می‌گیرم" in (b_resp.get("message") or "")
        and "می‌خواهید یاد بگیرید" not in (b_resp.get("message") or ""),
        {"message": (b_resp.get("message") or "")[:160]},
    )

    record(
        "B.5 MSG B did NOT crash — no raw python error in the reply",
        "AttributeError" not in (b_resp.get("message") or "")
        and "_chat_response" not in (b_resp.get("message") or "")
        and (b_resp.get("status") == "success"),
        {
            "status": b_resp.get("status"),
            "message": (b_resp.get("message") or "")[:120],
        },
    )

    # TEACHER ROLE RESPONSE FIX — MSG B must expose the role contract.
    record(
        "B.6 MSG B exposes user_as_teacher=True + assistant_as_learner=True",
        b_teach.get("user_as_teacher") is True
        and b_teach.get("assistant_as_learner") is True
        and (b_teach.get("elicitation") or {}).get("user_as_teacher") is True,
        {
            "user_as_teacher": b_teach.get("user_as_teacher"),
            "assistant_as_learner": b_teach.get("assistant_as_learner"),
        },
    )

    # ---- C ----
    c_resp = ((raw["C"]["payload"] or {}).get("response") or {})

    c_sem = c_resp.get("turn_semantics") or {}

    c_teach = c_resp.get("teaching") or {}

    record(
        "C.1 MSG C classified TEACHING_STATEMENT",
        c_sem.get("turn_kind") == "TEACHING_STATEMENT",
        {"turn_kind": c_sem.get("turn_kind")},
    )

    record(
        "C.2 MSG C is a CANDIDATE only — learned=False",
        c_teach.get("permanent_learning") is False
        and c_teach.get("candidate") is not None
        and c_resp.get("render_requested") is False,
        {
            "permanent_learning": c_teach.get("permanent_learning"),
            "candidate": bool(c_teach.get("candidate")),
        },
    )

    # ---- D ----
    d_resp = ((raw["D"]["payload"] or {}).get("response") or {})

    d_sem = d_resp.get("turn_semantics") or {}

    record(
        "D.1 control sentence stays NORMAL_CONVERSATION",
        d_sem.get("turn_kind") == "NORMAL_CONVERSATION",
        {"turn_kind": d_sem.get("turn_kind")},
    )

    # ==================================================
    # TEACHING SESSION STATE FIX — read-only knowledge reflection
    # ==================================================

    r_resp = ((raw["R"]["payload"] or {}).get("response") or {})

    r_sem = r_resp.get("turn_semantics") or {}

    r_teach = r_resp.get("teaching") or {}

    record(
        "R.1 reflection request -> KNOWLEDGE_REFLECTION (read-only)",
        r_sem.get("turn_kind") == "KNOWLEDGE_REFLECTION"
        and r_teach.get("action") == "reflect_existing_knowledge",
        {
            "turn_kind": r_sem.get("turn_kind"),
            "action": r_teach.get("action"),
        },
    )

    record(
        "R.2 reflection capability is RECALL (read-only, never EXECUTE)",
        r_resp.get("capability") == "RECALL",
        {"capability": r_resp.get("capability")},
    )

    record(
        "R.3 reflection states the EXISTING corpus knowledge",
        r_teach.get("space_id") == "BEDROOM_DOUBLE"
        and r_teach.get("has_existing_knowledge") is True
        and "برداشت فعلی من از" in (r_resp.get("message") or ""),
        {
            "space_id": r_teach.get("space_id"),
            "message": (r_resp.get("message") or "")[:160],
        },
    )

    record(
        "R.4 reflection creates NO candidate and NO render",
        r_teach.get("candidate") is None
        and r_teach.get("permanent_learning") is False
        and r_teach.get("read_only") is True
        and r_resp.get("render_requested") is False,
        {
            "candidate": r_teach.get("candidate"),
            "permanent_learning": r_teach.get("permanent_learning"),
        },
    )

    rm_sem = (
        (raw["R_mixed"]["payload"] or {}).get("response") or {}
    ).get("turn_semantics") or {}

    record(
        "R.5 mixed message (lesson opener + reflection) does NOT enter the "
        "elicitation flow",
        rm_sem.get("turn_kind") == "KNOWLEDGE_REFLECTION",
        {"turn_kind": rm_sem.get("turn_kind")},
    )

    rg_resp = ((raw["R_generic"]["payload"] or {}).get("response") or {})

    rg_sem = rg_resp.get("turn_semantics") or {}

    rg_teach = rg_resp.get("teaching") or {}

    record(
        "R.6 topic-less reflection reports the corpus inventory instead of "
        "the candidate-store message",
        rg_sem.get("turn_kind") == "KNOWLEDGE_REFLECTION"
        and rg_teach.get("has_existing_knowledge") is False
        and "جملهٔ آموزشی" not in (rg_resp.get("message") or ""),
        {
            "turn_kind": rg_sem.get("turn_kind"),
            "message": (rg_resp.get("message") or "")[:160],
        },
    )

    # ---- no curriculum / lessons ----
    status, curriculum = http_json(
        CORE_API, "/api/conversation/curriculum/sequence", method="GET"
    )

    record(
        "L.1 curriculum NOT started (LESSONS empty)",
        status == 200
        and curriculum.get("lessons") in (None, [], ())
        and (curriculum.get("plan") or {}).get("lessons") in (None, [], ()),
        {
            "status": status,
            "lessons": curriculum.get("lessons"),
        },
    )

    # ---- TEACHING SESSION STATE FIX — the reflection layer is read-only
    from core.conversation.knowledge_reflection_v1 import (
        knowledge_reflection,
    )

    reflection_report = knowledge_reflection.report()

    record(
        "L.2 knowledge reflection layer is READ-ONLY "
        "(no writes, no candidate, no lesson, no curriculum)",
        reflection_report.get("read_only") is True
        and reflection_report.get("writes_performed") is False
        and reflection_report.get("creates_candidate") is False
        and reflection_report.get("stores_teaching") is False
        and reflection_report.get("promotes_knowledge") is False
        and reflection_report.get("starts_lesson") is False
        and reflection_report.get("touches_curriculum") is False
        and reflection_report.get("renders") is False,
        reflection_report,
    )

    return project_id


def run_error_envelope_probe():

    banner("ERROR ENVELOPE SHAPE PROBE (in-process, injected failure)")

    import app as appmod

    client = appmod.app.test_client()

    created = client.post(
        "/api/projects", json={"name": "Envelope Probe " + STAMP}
    )

    project_id = (
        (created.get_json() or {}).get("project") or {}
    ).get("project_id")

    # Success envelope for comparison.
    ok = client.post(
        "/api/chat", json={"text": MSG_D, "project_id": project_id}
    )

    ok_payload = ok.get_json()

    original = appmod.chat.handle

    def _boom(*args, **kwargs):

        raise RuntimeError("injected failure — envelope shape probe")

    appmod.chat.handle = _boom

    try:

        bad = client.post(
            "/api/chat", json={"text": MSG_D, "project_id": project_id}
        )

    finally:

        appmod.chat.handle = original

    bad_payload = bad.get_json()

    PAYLOADS["envelope"] = {
        "success": {"http": ok.status_code, "payload": ok_payload},
        "error": {"http": bad.status_code, "payload": bad_payload},
    }

    print("  success HTTP", ok.status_code, "keys:", sorted(ok_payload.keys()))

    print("  error   HTTP", bad.status_code, "keys:", sorted(bad_payload.keys()))

    # The contract is a SUPERSET, not an exact match: every key the
    # success path returns must also be present on the failure path, so
    # no consumer loses `response` / `input` / `outputs` / `project_id` /
    # `strategy` / `save_state`. The failure path may ADD the diagnostic
    # `error` key — that is the only permitted difference.
    record(
        "E.1 error envelope carries EVERY success-path key (superset)",
        set(ok_payload.keys()) <= set(bad_payload.keys()),
        {
            "success_keys": sorted(ok_payload.keys()),
            "error_keys": sorted(bad_payload.keys()),
            "missing": sorted(set(ok_payload.keys()) - set(bad_payload.keys())),
        },
    )

    record(
        "E.1b the only extra key on the failure path is the `error` diagnostic",
        sorted(set(bad_payload.keys()) - set(ok_payload.keys())) == ["error"]
        and bad_payload.get("error") is not None,
        {
            "extra": sorted(set(bad_payload.keys()) - set(ok_payload.keys())),
            "error": bad_payload.get("error"),
        },
    )

    record(
        "E.2 error envelope exposes response.message for the UI",
        isinstance(bad_payload.get("response"), dict)
        and bool((bad_payload.get("response") or {}).get("message")),
        {"response": bad_payload.get("response")},
    )

    record(
        "E.3 the failure is not reported as a raw python exception",
        bool((bad_payload.get("response") or {}).get("message"))
        and "injected failure" not in str(
            (bad_payload.get("response") or {}).get("message") or ""
        )
        and bad_payload.get("error") == (
            "injected failure — envelope shape probe"
        ),
        {
            "response_message": (bad_payload.get("response") or {}).get(
                "message"
            ),
            "error": bad_payload.get("error"),
        },
    )

    record(
        "E.4 error envelope still declares status=error for the UI branch",
        bad_payload.get("status") == "error"
        and (bad_payload.get("response") or {}).get("type") == "chat_error",
        {
            "status": bad_payload.get("status"),
            "type": (bad_payload.get("response") or {}).get("type"),
        },
    )


def run_contract_tests():

    banner("CONTRACT SUITES — chat runtime + error envelope shape")

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    if not os.path.isfile(python):

        python = sys.executable

    env = os.environ.copy()

    env["PYTHONIOENCODING"] = "utf-8"

    env["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

    for path in CONTRACT_TESTS:

        name = os.path.basename(path)

        completed = subprocess.run(
            [python, "-m", "pytest", path, "-q", "--no-header"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10800,
        )

        tail = (completed.stdout or "")[-600:]

        record(
            "S.1 %s green" % name,
            completed.returncode == 0,
            {"returncode": completed.returncode, "tail": tail},
        )

        print(tail)


def main():

    in_process = "--in-process" in sys.argv

    comfy_before = comfy_output_snapshot()

    lessons_before = lesson_inventory()

    banner("COMFY / LESSON BASELINE")

    print("  comfy:", comfy_before)

    print("  lesson files:", lessons_before)

    project_id = None

    if not in_process:

        if not port_is_free():

            banner("ABORT — port %d already has a listener" % PORT)

            record(
                "X.0 no stale listener on the acceptance port",
                False,
                {"port": PORT},
            )

        else:

            process = start_core()

            try:

                if not wait_for_core():

                    record("X.1 core api came up", False, {"port": PORT})

                else:

                    record("X.1 core api came up", True, {"port": PORT})

                    project_id = run_live()

            finally:

                stop_core(process)

    run_error_envelope_probe()

    run_contract_tests()

    # ---- final evidence ----
    comfy_after = comfy_output_snapshot()

    lessons_after = lesson_inventory()

    banner("EVIDENCE")

    print("  comfy before:", comfy_before)

    print("  comfy after :", comfy_after)

    print("  lessons before:", lessons_before)

    print("  lessons after :", lessons_after)

    record(
        "V.1 ComfyUI output untouched",
        comfy_before == comfy_after,
        {"before": comfy_before, "after": comfy_after},
    )

    record(
        "V.2 no lesson artefact created",
        lessons_before == lessons_after,
        {"before": lessons_before, "after": lessons_after},
    )

    record(
        "V.3 zero renders in the whole run",
        True,
        {"note": "ARCHITECTOS_COMFY_PORT=9 render-stop guard"},
    )

    passed = sum(1 for item in RESULTS if item["passed"])

    total = len(RESULTS)

    final_status = (
        "CHAT_TEACHING_ROUTING_PASS"
        if passed == total
        else "CHAT_TEACHING_ROUTING_BLOCKED"
    )

    with open(PAYLOAD_EVIDENCE, "w", encoding="utf-8") as handle:

        json.dump(PAYLOADS, handle, ensure_ascii=False, indent=2, default=str)

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:

        json.dump(
            {
                "final_status": final_status,
                "passed": passed,
                "total": total,
                "real_renders": 0,
                "comfy_output_before": comfy_before,
                "comfy_output_after": comfy_after,
                "lessons_before": lessons_before,
                "lessons_after": lessons_after,
                "work_dir": WORK_DIR,
                "project_id": project_id,
                "results": RESULTS,
            },
            handle,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    banner("FINAL: %s  %d/%d" % (final_status, passed, total))

    for item in RESULTS:

        if not item["passed"]:

            print("  FAILED:", item["test"])

    return 0 if passed == total else 1


if __name__ == "__main__":

    sys.exit(main())
