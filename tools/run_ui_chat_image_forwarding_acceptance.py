# ==========================================================
# UI CHAT IMAGE MULTIPART FORWARDING — ACCEPTANCE RUNNER
#
# Validates the IMAGE ANALYSIS INPUT FAILURE FIX:
#   ui/routes/chat_routes.py :: chat_proxy now forwards
#   multipart/form-data as multipart, exactly like /api/image.
#
# HARD CONSTRAINTS
#   - NO render, NO ComfyUI, NO image generation. The CORE API is
#     started with ARCHITECTOS_COMFY_PORT=9 so every submit fails fast,
#     and the ComfyUI output directory is asserted unchanged.
#   - NO curriculum change, NO lesson, NO knowledge promotion.
#   - The UI is started on a spare port against the throw-away CORE.
#
# Usage:
#   .venv/Scripts/python.exe tools/run_ui_chat_image_forwarding_acceptance.py
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

CORE_PORT = 5097

UI_PORT = 3097

CORE = "http://127.0.0.1:%d" % CORE_PORT

UI = "http://127.0.0.1:%d" % UI_PORT

# A REAL architectural image. tests/assets/*.png are 21-22 byte ASCII
# stubs and would make the vision provider fail legitimately.
IMAGE = os.path.join(
    ROOT, "uploads", "01c162e9-6a2c-4731-94da-30ed312c7037_villa.png"
)

WORK = os.path.join(ROOT, ".pytest_tmp", "ui_img_fwd_" + STAMP)

DATA_ROOT = os.path.join(WORK, "project_data")

os.makedirs(DATA_ROOT, exist_ok=True)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

CORE_LOG = os.path.join(WORK, "core.log")

UI_LOG = os.path.join(WORK, "ui.log")

REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_ui_chat_image_forwarding_report.json"
)

TEXT_MESSAGE = "سلام"

IMAGE_MESSAGE = (
    "این تصویر را فقط تحلیل کن. بگو چه فضای معماری می‌بینی، چه چیزهایی "
    "از آن برداشت می‌کنی و چه چیزهایی برایت نامشخص است. فعلاً آموزش "
    "نمی‌دهم."
)


try:

    from config import runtime_config as RC

    COMFY_OUTPUT_DIR = RC.COMFYUI_OUTPUT_DIR

except Exception:

    COMFY_OUTPUT_DIR = os.path.join("C:", os.sep, "ComfyUI-Zluda", "output")


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

RESULTS = []

EVIDENCE = {}


def record(name, passed, detail=None):

    entry = {"test": name, "passed": bool(passed), "detail": detail}

    RESULTS.append(entry)

    print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

    if detail and not passed:

        print(
            "        ",
            json.dumps(detail, ensure_ascii=False, default=str)[:600],
        )


def banner(title):

    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


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

        try:

            return error.code, json.loads(error.read().decode("utf-8"))

        except Exception:

            return error.code, {}

    except Exception as error:

        return None, {"error": type(error).__name__ + ": " + str(error)}


def http_multipart(base, path, text, image_path, project_id, timeout=10800):

    import requests

    with open(image_path, "rb") as handle:

        files = {
            "image": (
                os.path.basename(image_path),
                handle,
                "image/png",
            )
        }

        data = {
            "text": text,
            "project_id": project_id or "",
            "mode": "auto",
            "quality": "standard",
            "seed_mode": "reroll",
        }

        try:

            response = requests.post(
                base + path,
                files=files,
                data=data,
                timeout=timeout,
                proxies={"http": None, "https": None},
            )

            try:

                return response.status_code, response.json()

            except Exception:

                return response.status_code, {"raw": response.text[:400]}

        except Exception as error:

            return None, {"error": type(error).__name__ + ": " + str(error)}


def start_service(script, name, extra_env=None):

    env = os.environ.copy()

    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = env["NO_PROXY"]
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

    # RENDER-STOP GUARD — ComfyUI unreachable by construction.
    env["ARCHITECTOS_COMFY_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_COMFY_PORT"] = "9"

    env["ARCHITECTOS_CORE_API_PORT"] = str(CORE_PORT)
    env["ARCHITECTOS_UI_PORT"] = str(UI_PORT)

    if extra_env:

        env.update(extra_env)

    log_path = CORE_LOG if name == "core" else UI_LOG

    handle = open(log_path, "ab")

    handle.write(
        ("\n\n===== %s start @ %s =====\n" % (name, STAMP)).encode("utf-8")
    )

    handle.flush()

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    return subprocess.Popen(
        [python, script],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )


def wait_for(base, path, timeout=10800):

    started = time.time()

    while time.time() - started < timeout:

        status, _ = http_json(base, path, timeout=5)

        if status == 200:

            return True

        time.sleep(1)

    return False


def stop(process):

    try:

        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            timeout=40,
        )

    except Exception:

        pass


def read_log(path):

    try:

        with open(path, "r", encoding="utf-8", errors="replace") as handle:

            return handle.read()

    except Exception:

        return ""


def comfy_snapshot():

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

        if ".venv" in base or "node_modules" in base:

            continue

        for name in files:

            low = name.lower()

            if "lesson" in low and low.endswith((".py", ".json")):

                hits.append(os.path.relpath(os.path.join(base, name), ROOT))

    return sorted(hits)


def main():

    comfy_before = comfy_snapshot()

    lessons_before = lesson_inventory()

    banner("BASELINE")

    print("  comfy:", comfy_before)

    print("  lessons:", lessons_before)

    print("  image:", IMAGE, "exists:", os.path.isfile(IMAGE))

    core = start_service("app.py", "core")

    ui = None

    try:

        if not wait_for(CORE, "/health"):

            record("X.1 core api came up", False, {"port": CORE_PORT})

            return 1

        record("X.1 core api came up", True, {"port": CORE_PORT})

        ui = start_service("ui/app.py", "ui")

        if not wait_for(UI, "/status"):

            record("X.2 ui came up", False, {"port": UI_PORT})

            return 1

        record("X.2 ui came up", True, {"port": UI_PORT})

        status, created = http_json(
            CORE, "/api/projects", {"name": "UI Image Forwarding " + STAMP}
        )

        project_id = (created.get("project") or {}).get("project_id")

        record(
            "L.0 project created",
            status == 200 and bool(project_id),
            {"status": status, "project_id": project_id},
        )

        # ==================================================
        # TEST 1 — TEXT ONLY (the JSON path must be unchanged)
        # ==================================================
        banner("TEST 1 — text only through the UI proxy (JSON path)")

        s1, p1 = http_json(
            UI, "/api/chat", {"text": TEXT_MESSAGE, "project_id": project_id}
        )

        EVIDENCE["text"] = {"http": s1, "payload": p1}

        print("  HTTP", s1)

        print(
            "  status:",
            (p1 or {}).get("status"),
            "| type:",
            ((p1 or {}).get("response") or {}).get("type"),
            "| engine:",
            ((p1 or {}).get("response") or {}).get("engine"),
        )

        record(
            "T1.1 text request still succeeds through the UI proxy",
            s1 == 200
            and (p1 or {}).get("status") == "success"
            and (p1 or {}).get("message") != "empty input",
            {"payload": p1},
        )

        record(
            "T1.2 text request is NOT reported as empty input",
            (p1 or {}).get("message") != "empty input"
            and "empty input" not in json.dumps(p1, default=str),
            {"message": (p1 or {}).get("message")},
        )

        # ==================================================
        # TEST 2 — REAL PNG + ANALYSIS MESSAGE (multipart)
        # ==================================================
        banner("TEST 2 — real PNG + analysis message through the UI proxy")

        s2, p2 = http_multipart(
            UI, "/api/chat", IMAGE_MESSAGE, IMAGE, project_id
        )

        EVIDENCE["image"] = {"http": s2, "payload": p2}

        resp = (p2 or {}).get("response") or {}

        vision = resp.get("vision") or {}

        print("  HTTP", s2)

        print("  status:", (p2 or {}).get("status"))
        print("  type:", resp.get("type"))
        print("  engine:", resp.get("engine"))
        print("  input:", json.dumps((p2 or {}).get("input"), ensure_ascii=False))
        print("  vision.provider:", vision.get("provider"))
        print("  vision.model:", vision.get("model"))
        print("  vision.analysis_status:", vision.get("analysis_status"))
        print("  vision.intent:", vision.get("intent"))
        print("  message:", (resp.get("message") or "")[:160])

        record(
            "T2.1 image request reaches the CORE API (no 'empty input')",
            s2 == 200
            and (p2 or {}).get("status") == "success"
            and "empty input" not in json.dumps(p2, default=str),
            {"payload": p2},
        )

        record(
            "T2.2 type == image_analysis",
            resp.get("type") == "image_analysis",
            {"type": resp.get("type"), "engine": resp.get("engine")},
        )

        record(
            "T2.3 the CORE saw has_image == true",
            ((p2 or {}).get("input") or {}).get("has_image") is True,
            {"input": (p2 or {}).get("input")},
        )

        record(
            "T2.4 the vision layer actually analysed the image",
            bool(vision.get("provider"))
            and vision.get("analysis_status")
            not in (None, "FAILED")
            and vision.get("intent") == "analyze",
            {
                "provider": vision.get("provider"),
                "analysis_status": vision.get("analysis_status"),
                "intent": vision.get("intent"),
            },
        )

        record(
            "T2.5 NOT an Image-to-Image generation / render",
            resp.get("type") not in ("render", "image", "img2img")
            and not resp.get("render_requested")
            and resp.get("type") == "image_analysis",
            {
                "type": resp.get("type"),
                "render_requested": resp.get("render_requested"),
            },
        )

        record(
            "T2.6 NO design proposal and NO teaching candidate",
            not resp.get("attachments")
            and not (resp.get("teaching") or {}).get("candidate"),
            {
                "attachments": resp.get("attachments"),
                "teaching": resp.get("teaching"),
            },
        )

        # ==================================================
        # LOG EVIDENCE
        # ==================================================
        banner("LOG EVIDENCE")

        ui_text = read_log(UI_LOG)

        core_text = read_log(CORE_LOG)

        multipart_line = "UI GATEWAY MULTIPART REQUEST" in ui_text

        json_line = "UI GATEWAY REQUEST:" in ui_text

        core_saw_image = "DEBUG IMAGE VALUE: <FileStorage" in core_text

        print("  UI logged MULTIPART gateway line:", multipart_line)

        print("  UI logged JSON gateway line    :", json_line)

        print("  CORE logged a real FileStorage :", core_saw_image)

        record(
            "E.1 the UI multipart branch ran",
            multipart_line,
            {"ui_log_tail": ui_text[-600:]},
        )

        record(
            "E.2 the UI JSON branch still ran for the text request",
            json_line,
            {"ui_log_tail": ui_text[-600:]},
        )

        record(
            "E.3 the CORE API received the image as a real upload",
            core_saw_image,
            {"core_log_tail": core_text[-600:]},
        )

    finally:

        if ui is not None:

            stop(ui)

        stop(core)

        time.sleep(2)

    # ==================================================
    # FINAL EVIDENCE
    # ==================================================
    comfy_after = comfy_snapshot()

    lessons_after = lesson_inventory()

    banner("FINAL EVIDENCE")

    print("  comfy before:", comfy_before)

    print("  comfy after :", comfy_after)

    record(
        "V.1 ComfyUI output untouched (zero renders)",
        comfy_before == comfy_after,
        {"before": comfy_before, "after": comfy_after},
    )

    record(
        "V.2 no lesson artefact created",
        lessons_before == lessons_after,
        {"before": lessons_before, "after": lessons_after},
    )

    passed = sum(1 for item in RESULTS if item["passed"])

    total = len(RESULTS)

    final_status = (
        "UI_CHAT_IMAGE_FORWARDING_PASS"
        if passed == total
        else "UI_CHAT_IMAGE_FORWARDING_BLOCKED"
    )

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:

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
                "evidence": EVIDENCE,
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
