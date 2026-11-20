# ==========================================================
# ArchitectOS TEXT_TO_IMAGE_COMFY_03 — REAL Acceptance Runner
#
# Performs the required REAL end-to-end Text-to-Image acceptance
# through the live API path:
#
#   POST /chat -> ChatArchitect -> compiled_render_prompt
#              -> RenderRuntime -> preset -> flux.json
#              -> WorkflowExecutor -> ComfyHTTPRuntime
#              -> ComfyUI :8188 -> output asset
#
# Required cases (3 real renders, no more):
#   A. Persian exterior day
#   B. Persian exterior night / sunset
#   C. English interior render
#
# Also performs the duplicate Core API process check before testing.
#
# Usage:
#   python tools/run_real_render_acceptance_03.py
# ==========================================================


import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if ROOT not in sys.path:

    sys.path.insert(
        0,
        ROOT
    )


CORE_API = "http://127.0.0.1:5000"
COMFY_API = "http://127.0.0.1:8188"

REPORT_PATH = os.path.join(
    ROOT,
    "tools",
    "acceptance_03_report.json"
)

LOG_PATH = os.path.join(
    ROOT,
    "logs",
    "runtime",
    "acceptance_03_api.log"
)


# Proxy-free opener: localhost must never go through an HTTP proxy.
_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({})
)


CASES = [

    {
        "id": "A",
        "label": "Persian exterior day",
        "language": "fa",
        "expect_preset": "exterior_day",
        "text": (
            "یک رندر واقع‌گرایانه از نمای روز ویلا "
            "با متریال شیشه و نور طبیعی بساز"
        ),
    },

    {
        "id": "B",
        "label": "Persian exterior night",
        "language": "fa",
        "expect_preset": "exterior_night",
        "text": (
            "یک رندر از نمای ویلا در شب "
            "با نورپردازی گرم بساز"
        ),
    },

    {
        "id": "C",
        "label": "English interior render",
        "language": "en",
        "expect_preset": "interior_warm",
        "text": (
            "photorealistic interior render of a modern living room "
            "with warm lighting and large windows"
        ),
    },
]



# ==========================================================
# HELPERS
# ==========================================================

def http_get(url, timeout=10):

    try:

        with _OPENER.open(url, timeout=timeout) as response:

            return response.status, response.read().decode(
                "utf-8", errors="replace"
            )

    except urllib.error.HTTPError as e:

        return e.code, ""

    except Exception as e:

        return None, str(e)



def http_post_json(url, payload, timeout, headers=None):

    body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
    )

    with _OPENER.open(request, timeout=timeout) as response:

        return response.status, json.loads(
            response.read().decode("utf-8")
        )



def listeners_on(port):
    """PIDs currently LISTENING on a local TCP port."""

    try:

        out = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=10800
        ).stdout

    except Exception:

        return []


    pids = set()

    needle = ":" + str(port)

    for line in out.splitlines():

        parts = line.split()

        if len(parts) < 5:

            continue

        if parts[0].upper() not in ("TCP", "TCPV6"):

            continue

        if parts[3].upper() != "LISTENING":

            continue

        local = parts[1]

        if local.endswith(needle) or local.endswith(needle + "]"):

            pids.add(parts[4])

    return sorted(pids)



def png_size(path):
    """Read PNG width/height from the IHDR chunk (stdlib only)."""

    try:

        with open(path, "rb") as f:

            head = f.read(26)

        if head[:8] != b"\x89PNG\r\n\x1a\n":

            return None

        return (
            int.from_bytes(head[16:20], "big"),
            int.from_bytes(head[20:24], "big"),
        )

    except Exception:

        return None



def stop_pid(pid):

    try:

        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            timeout=10800
        )

    except Exception:

        pass



# ==========================================================
# 10. DUPLICATE PROCESS CHECK
# ==========================================================

def ensure_single_core_api():

    print("=" * 66)
    print("  STEP 0 — DUPLICATE CORE API PROCESS CHECK (port 5000)")
    print("=" * 66)

    pids = listeners_on(5000)

    print("  listeners on 5000:", pids if pids else "none")


    if len(pids) > 1:

        print(
            "  !! DUPLICATE Core API processes detected:",
            pids
        )

        for pid in pids:

            print("     stopping stale pid", pid)

            stop_pid(pid)

        time.sleep(3)

        pids = listeners_on(5000)

        print("  listeners after cleanup:", pids if pids else "none")

        assert len(pids) <= 1, (
            "could not reduce to a single Core API process: " + str(pids)
        )

        return {"duplicates_found": True, "stopped": True}


    if len(pids) == 1:

        print("  exactly one Core API process already listening")

        return {"duplicates_found": False, "stopped": False}


    print("  no Core API process running (will start a clean one)")

    return {"duplicates_found": False, "stopped": False}



# ==========================================================
# CORE API LIFECYCLE
# ==========================================================

def start_core_api():

    os.makedirs(
        os.path.dirname(LOG_PATH),
        exist_ok=True
    )

    env = os.environ.copy()

    bypass = "127.0.0.1,localhost,::1"

    env["NO_PROXY"] = bypass
    env["no_proxy"] = bypass

    python = os.path.join(
        ROOT, ".venv", "Scripts", "python.exe"
    )

    if not os.path.isfile(python):

        python = sys.executable


    handle = open(LOG_PATH, "ab")

    handle.write(
        b"\n\n===== acceptance_03 api start =====\n"
    )

    handle.flush()


    process = subprocess.Popen(
        [python, "app.py"],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )

    print("  started Core API pid", process.pid)

    return process



def wait_for_core_api(timeout=10800):

    started = time.time()

    while time.time() - started < timeout:

        status, _ = http_get(CORE_API + "/health", timeout=5)

        if status == 200:

            print(
                "  Core API ready in",
                round(time.time() - started, 1),
                "s"
            )

            return True

        time.sleep(1)

    return False



# ==========================================================
# EVIDENCE EXTRACTION
# ==========================================================

def extract_evidence(case, payload, duration):

    response = payload.get("response") or {}

    trace = response.get("render_handoff") or {}

    metadata = trace.get("render_request_metadata") or {}

    asset = metadata.get("output_asset") or {}


    evidence = {

        "case": case["id"],
        "label": case["label"],
        "language": case["language"],

        "original_prompt": trace.get("original_user_prompt"),
        "normalized_prompt": trace.get("normalized_prompt"),
        "compiled_render_prompt": trace.get("compiled_render_prompt"),
        "compiled_prompt_source": trace.get("compiled_prompt_source"),

        "selected_preset": metadata.get("preset"),
        "preset_source": metadata.get("preset_source"),
        "preset_reason": metadata.get("preset_reason"),

        "final_prompt": metadata.get("final_prompt"),
        "prompt_source": metadata.get("prompt_source"),

        "workflow_name": metadata.get("workflow_name"),
        "seed": metadata.get("seed"),
        "width": metadata.get("width"),
        "height": metadata.get("height"),
        "steps": metadata.get("steps"),

        "execution_status": metadata.get("execution_status"),
        "render_status": metadata.get("status"),

        "output_path": asset.get("path"),
        "output_filename": asset.get("filename"),
        "output_exists_flag": metadata.get("output_asset_exists"),

        "api_status": payload.get("status"),
        "runtime_duration_s": duration,

    }


    path = evidence["output_path"]

    if path:

        evidence["file_exists"] = os.path.isfile(path)

        evidence["file_size_bytes"] = (
            os.path.getsize(path)
            if evidence["file_exists"]
            else None
        )

        evidence["image_dimensions"] = (
            png_size(path)
            if evidence["file_exists"]
            else None
        )

    else:

        evidence["file_exists"] = False
        evidence["file_size_bytes"] = None
        evidence["image_dimensions"] = None


    return evidence



# ==========================================================
# MAIN
# ==========================================================

def main():

    report = {
        "phase": "TEXT_TO_IMAGE_COMFY_03",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cases": [],
        "blockers": [],
    }


    duplicate_check = ensure_single_core_api()

    report["duplicate_process_check"] = duplicate_check


    print("\n" + "=" * 66)
    print("  STEP 1 — COMFYUI + CORE API READINESS")
    print("=" * 66)


    status, _ = http_get(COMFY_API + "/system_stats", timeout=10)

    print("  ComfyUI /system_stats ->", status)

    if status != 200:

        report["blockers"].append("ComfyUI unreachable on 8188")

        print("BLOCKED: ComfyUI unreachable")

        return 1


    process = start_core_api()

    if not wait_for_core_api():

        report["blockers"].append("Core API did not become ready")

        print("BLOCKED: Core API did not become ready")

        stop_pid(str(process.pid))

        return 1


    # ------------------------------------------------------
    # REAL RENDERS
    # ------------------------------------------------------

    print("\n" + "=" * 66)
    print("  STEP 2 — REAL TEXT-TO-IMAGE RENDERS (3 cases)")
    print("=" * 66)


    try:

        for case in CASES:

            print(
                "\n  --- "
                + case["id"]
                + " | "
                + case["label"]
                + " ---"
            )

            print("  request:", case["text"])


            started = time.time()

            headers = {
                "X-Session-Id": "acceptance_03_" + case["id"],
            }

            if case.get("explicit_preset"):

                headers["X-Render-Preset"] = case["explicit_preset"]


            try:

                status, payload = http_post_json(
                    CORE_API + "/chat",
                    {"text": case["text"]},
                    timeout=10800,
                    headers=headers,
                )

            except Exception as e:

                print("  REQUEST FAILED:", type(e).__name__, e)

                report["cases"].append({

                    "case": case["id"],
                    "label": case["label"],
                    "error": type(e).__name__ + ": " + str(e),

                })

                continue


            duration = round(time.time() - started, 1)

            evidence = extract_evidence(case, payload, duration)

            evidence["expected_preset"] = case["expect_preset"]

            evidence["preset_as_expected"] = (
                evidence["selected_preset"] == case["expect_preset"]
            )

            report["cases"].append(evidence)


            print("  preset      :", evidence["selected_preset"],
                  "(", evidence["preset_source"], ")")

            print("  final prompt:", str(evidence["final_prompt"])[:110])

            print("  exec status :", evidence["execution_status"])

            print("  render stat :", evidence["render_status"])

            print("  output      :", evidence["output_path"])

            print("  file exists :", evidence["file_exists"],
                  "| size:", evidence["file_size_bytes"],
                  "| dims:", evidence["image_dimensions"])

            print("  duration    :", duration, "s")

    finally:

        print("\n  stopping Core API pid", process.pid)

        stop_pid(str(process.pid))


    # ------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------

    print("\n" + "=" * 66)
    print("  ACCEPTANCE SUMMARY")
    print("=" * 66)

    rendered = 0

    for evidence in report["cases"]:

        if evidence.get("error"):

            print("  " + evidence["case"] + " : ERROR " + evidence["error"])

            continue

        success = (
            evidence.get("execution_status") == "completed"
            and evidence.get("render_status") == "success"
            and evidence.get("file_exists") is True
        )

        if success:

            rendered += 1

        print(
            "  "
            + evidence["case"]
            + " : preset=" + str(evidence["selected_preset"])
            + " exec=" + str(evidence["execution_status"])
            + " status=" + str(evidence["render_status"])
            + " file=" + str(evidence["file_exists"])
            + " dims=" + str(evidence["image_dimensions"])
            + " " + str(evidence["runtime_duration_s"]) + "s"
            + ("  OK" if success else "  !! NOT SUCCESS")
        )

    report["real_renders_completed"] = rendered
    report["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")


    with open(REPORT_PATH, "w", encoding="utf-8") as f:

        json.dump(report, f, ensure_ascii=False, indent=2)


    print("\n  report written:", REPORT_PATH)

    print("  successful real renders:", rendered, "/", len(CASES))

    return 0 if rendered == len(CASES) else 2



if __name__ == "__main__":

    sys.exit(main())
