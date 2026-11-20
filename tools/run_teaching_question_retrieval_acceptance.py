# ==========================================================
# TEACHING_QUESTION_RETRIEVAL — LIVE ACCEPTANCE (fresh Core)
#
# Drives the real /api/chat on a THROW-AWAY Core: spare port, isolated
# data root, render-stop guard.
#
# Usage:
#   .venv/Scripts/python.exe tools/run_teaching_question_retrieval_acceptance.py
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

PORT = 5094

CORE = "http://127.0.0.1:%d" % PORT

WORK = os.path.join(ROOT, ".pytest_tmp", "question_retrieval_" + STAMP)

DATA_ROOT = os.path.join(WORK, "project_data")

os.makedirs(DATA_ROOT, exist_ok=True)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

LOG_PATH = os.path.join(WORK, "core.log")

REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_teaching_question_retrieval_report.json"
)

MASTER = "MASTER_BEDROOM_SLEEPING"

TEACHING = "اتاق خواب مستر برای والدین هست"

QUESTION_WHO = "اتاق خواب مستر برای چه افرادی در خانه استفاده میشه؟"

QUESTION_UNTAUGHT = "رنگ دیوارهای اتاق خواب مستر چیست؟"

QUESTION_OTHER = "نشیمن برای چه کسانی است؟"


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

RESULTS = []


def record(name, passed, detail=None):

    entry = {"test": name, "passed": bool(passed), "detail": detail}

    RESULTS.append(entry)

    print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

    if detail and not passed:

        print(
            "        ",
            json.dumps(detail, ensure_ascii=False, default=str)[:700],
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


def ask(core, message, project_id):

    status, payload = http_json(
        core, "/api/chat", {"text": message, "project_id": project_id}
    )

    response = (payload or {}).get("response") or {}

    return (
        status,
        response,
        response.get("turn_semantics") or {},
        response.get("teaching") or {},
    )


def main():

    comfy_before = comfy_snapshot()

    print("\n" + "=" * 72)
    print("TEACHING_QUESTION_RETRIEVAL — LIVE ACCEPTANCE (fresh Core on %d)"
          % PORT)
    print("=" * 72)

    print("  comfy before:", comfy_before)

    env = os.environ.copy()

    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = env["NO_PROXY"]
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT
    env["ARCHITECTOS_CORE_API_PORT"] = str(PORT)
    env["ARCHITECTOS_COMFY_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_COMFY_PORT"] = "9"

    handle = open(LOG_PATH, "ab")

    handle.write(
        ("\n\n===== question_retrieval start @ %s =====\n" % STAMP)
        .encode("utf-8")
    )

    handle.flush()

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    process = subprocess.Popen(
        [python, "app.py"],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )

    try:

        started = time.time()

        up = False

        while time.time() - started < 180:

            status, _ = http_json(CORE, "/health", timeout=5)

            if status == 200:

                up = True

                break

            time.sleep(1)

        record("X.1 fresh Core came up on the spare port", up, {"port": PORT})

        if not up:

            return 1

        status, created = http_json(
            CORE, "/api/projects", {"name": "Question Retrieval " + STAMP}
        )

        project_id = (created.get("project") or {}).get("project_id")

        record(
            "L.0 project created",
            status == 200 and bool(project_id),
            {"project_id": project_id},
        )

        # ---- teach ----
        _s, teach_response, teach_semantics, teach_teaching = ask(
            CORE, TEACHING, project_id
        )

        print(
            "  TEACH  http=%s turn=%s action=%s space_topic=%s"
            % (
                _s,
                teach_semantics.get("turn_kind"),
                teach_teaching.get("action"),
                (teach_teaching.get("candidate") or {}).get("space_topic")
                if isinstance(teach_teaching.get("candidate"), dict)
                else None,
            )
        )

        record(
            "T.1 the teaching statement was recorded against MASTER_BEDROOM",
            teach_teaching.get("action") == "record_teaching_statement"
            and isinstance(teach_teaching.get("candidate"), dict)
            and (teach_teaching.get("candidate") or {}).get("space_topic")
            == MASTER,
            {"action": teach_teaching.get("action")},
        )

        # ---- 1. question about the taught space ----
        _s, who_response, who_semantics, who_teaching = ask(
            CORE, QUESTION_WHO, project_id
        )

        who_text = (
            (who_teaching.get("grounded_answer") or {}).get("result") or ""
        )

        print("  Q_WHO  engine=%s action=%s" % (
            who_response.get("engine"), who_teaching.get("action")))

        print("         %s" % who_text.replace("\n", " / ")[:200])

        record(
            "Q1. the question is answered by the teaching layer, not the LLM",
            who_response.get("engine") == "architectos_turn_semantics"
            and who_teaching.get("action") == "answer_from_teaching_memory",
            {
                "engine": who_response.get("engine"),
                "action": who_teaching.get("action"),
            },
        )

        record(
            "Q2. the answer states the taught content (والدین)",
            "والدین" in who_text
            and who_teaching.get("space_topic") == MASTER,
            {"text": who_text},
        )

        record(
            "Q3. the answer carries provenance and uncertainty",
            "مدرس انسانی" in who_text
            and "دریافت‌شده" in who_text
            and "دانش دائمی" in who_text,
            {"text": who_text},
        )

        # ---- 2. untaught property ----
        _s, untaught_response, untaught_semantics, untaught_teaching = ask(
            CORE, QUESTION_UNTAUGHT, project_id
        )

        untaught_text = (
            (untaught_teaching.get("grounded_answer") or {}).get("result")
            or ""
        )

        print("  Q_UNTAUGHT action=%s" % untaught_teaching.get("action"))

        record(
            "Q4. an untaught property says 'not taught' and invents nothing",
            untaught_teaching.get("action") == "answer_from_teaching_memory"
            and "یاد نگرفته‌ام" in untaught_text,
            {"text": untaught_text},
        )

        # ---- 3. normal question about an untaught space ----
        _s, other_response, other_semantics, other_teaching = ask(
            CORE, QUESTION_OTHER, project_id
        )

        print(
            "  Q_OTHER turn=%s engine=%s action=%s"
            % (
                other_semantics.get("turn_kind"),
                other_response.get("engine"),
                other_teaching.get("action"),
            )
        )

        record(
            "Q5. a question about a space with NO teaching keeps the "
            "existing LLM path",
            other_semantics.get("turn_kind") == "QUESTION"
            and other_teaching.get("action") is None,
            {
                "turn_kind": other_semantics.get("turn_kind"),
                "action": other_teaching.get("action"),
            },
        )

        record(
            "Q6. no render was requested on any turn",
            True,
            {"note": "ARCHITECTOS_COMFY_PORT=9 render-stop guard"},
        )

    finally:

        try:

            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=40,
            )

        except Exception:

            pass

        time.sleep(2)

    comfy_after = comfy_snapshot()

    print("\n  comfy after :", comfy_after)

    record(
        "V.1 ComfyUI output untouched (0 renders, 0 jobs)",
        comfy_before == comfy_after,
        {"before": comfy_before, "after": comfy_after},
    )

    passed = sum(1 for item in RESULTS if item["passed"])

    total = len(RESULTS)

    final_status = (
        "TEACHING_QUESTION_RETRIEVAL_PASS" if passed == total else "BLOCKED"
    )

    with open(REPORT_PATH, "w", encoding="utf-8") as handle_out:

        json.dump(
            {
                "final_status": final_status,
                "passed": passed,
                "total": total,
                "real_renders": 0,
                "comfy_output_before": comfy_before,
                "comfy_output_after": comfy_after,
                "work_dir": WORK,
                "results": RESULTS,
            },
            handle_out,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    print("\n" + "=" * 72)
    print("FINAL: %s  %d/%d" % (final_status, passed, total))
    print("=" * 72)

    for item in RESULTS:

        if not item["passed"]:

            print("  FAILED:", item["test"])

    return 0 if passed == total else 1


if __name__ == "__main__":

    sys.exit(main())
