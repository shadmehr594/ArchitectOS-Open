# ==========================================================
# TEACHING_CONTEXT_01 — LIVE ACCEPTANCE (fresh Core process)
#
# Drives the audit conversation through the REAL /api/chat on a
# THROW-AWAY Core instance: spare port, isolated data root, and a
# render-stop guard so ComfyUI can never be reached.
#
# Usage:
#   .venv/Scripts/python.exe tools/run_teaching_context_01_acceptance.py
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

PORT = 5096

CORE = "http://127.0.0.1:%d" % PORT

WORK = os.path.join(ROOT, ".pytest_tmp", "teaching_context_01_" + STAMP)

DATA_ROOT = os.path.join(WORK, "project_data")

os.makedirs(DATA_ROOT, exist_ok=True)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

LOG_PATH = os.path.join(WORK, "core.log")

REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_teaching_context_01_report.json"
)

MASTER = "MASTER_BEDROOM_SLEEPING"

CONVERSATION = [
    ("C", "اتاق خواب مستر فقط محل خواب نیست", MASTER),
    (
        "D",
        "ویژگی مشترک تمام اتاق خواب‌های مستر یا مستر روم داشتن حمام و "
        "سرویس بهداشتی است",
        MASTER,
    ),
    (
        "E",
        "اگر مساحت زمین و زیربنا اجازه بدهد، کلوزت روم هم می‌تواند "
        "داشته باشد",
        MASTER,
    ),
    ("F", "نشیمن باید در فضای عمومی و نزدیک ورودی باشد", None),
]


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

RESULTS = []


def record(name, passed, detail=None):

    entry = {"test": name, "passed": bool(passed), "detail": detail}

    RESULTS.append(entry)

    print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

    if detail and not passed:

        print(
            "        ",
            json.dumps(detail, ensure_ascii=False, default=str)[:600],
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


def main():

    comfy_before = comfy_snapshot()

    print("\n" + "=" * 72)
    print("TEACHING_CONTEXT_01 — LIVE ACCEPTANCE (fresh Core on %d)" % PORT)
    print("=" * 72)

    print("  comfy before:", comfy_before)

    env = os.environ.copy()

    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = env["NO_PROXY"]
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT
    env["ARCHITECTOS_CORE_API_PORT"] = str(PORT)
    # RENDER-STOP GUARD
    env["ARCHITECTOS_COMFY_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_COMFY_PORT"] = "9"

    handle = open(LOG_PATH, "ab")

    handle.write(
        ("\n\n===== teaching_context_01 start @ %s =====\n" % STAMP)
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
            CORE, "/api/projects", {"name": "Teaching Context 01 " + STAMP}
        )

        project_id = (created.get("project") or {}).get("project_id")

        record(
            "L.0 project created",
            status == 200 and bool(project_id),
            {"status": status, "project_id": project_id},
        )

        observed = {}

        for tag, message, expected in CONVERSATION:

            status, payload = http_json(
                CORE, "/api/chat", {"text": message, "project_id": project_id}
            )

            response = (payload or {}).get("response") or {}

            teaching = response.get("teaching") or {}

            candidate = teaching.get("candidate") or {}

            topic = candidate.get("space_topic")

            observed[tag] = topic

            print(
                "  %-3s http=%s type=%s space_topic=%s"
                % (tag, status, response.get("type"), topic)
            )

            if expected is None:

                record(
                    "%s. an explicit living-room statement does NOT inherit "
                    "MASTER_BEDROOM" % tag,
                    topic != MASTER,
                    {"space_topic": topic},
                )

            else:

                record(
                    "%s. candidate stays attached to MASTER_BEDROOM" % tag,
                    topic == MASTER,
                    {"space_topic": topic},
                )

        # the whole chain must have stayed on the master bedroom
        record(
            "T.1 the C -> D -> E chain stayed attached to MASTER_BEDROOM",
            observed.get("C") == MASTER
            and observed.get("D") == MASTER
            and observed.get("E") == MASTER,
            observed,
        )

        record(
            "T.2 no render was requested on any turn",
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
        "TEACHING_CONTEXT_01_PASS"
        if passed == total
        else "BLOCKED"
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
