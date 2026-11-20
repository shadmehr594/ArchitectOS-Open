# ==========================================================
# ArchitectOS TEXT_TO_IMAGE_COMFY_03B — REAL Acceptance Runner
#
# Validates PRESET SEMANTICS only (not geometry identity):
#   A. exterior_day  -> clear daytime exterior, no dusk/night dominance
#   B. exterior_night -> SAME architectural base + SAME seed as A,
#                        only the preset / time-of-day changes
#   C. interior_warm  -> camera physically inside the room,
#                        interior composition (not exterior facade)
#
# MAX 3 REAL RENDERS.
#
# Also performs the duplicate Core API process check before testing.
#
# Usage:
#   python tools/run_real_render_acceptance_03b.py
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
    "acceptance_03b_report.json"
)

LOG_PATH = os.path.join(
    ROOT,
    "logs",
    "runtime",
    "acceptance_03b_api.log"
)


_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({})
)


# Shared between A and B so ONLY the preset / time-of-day differs.
SHARED_BASE = "رندر واقع‌گرایانه نمای یک ویلای مدرن"

SHARED_SEED = 20260929


CASES = [

    {
        "id": "A",
        "label": "Persian exterior day",
        "expect_preset": "exterior_day",
        "text": SHARED_BASE + " در روز روشن",
        "seed": SHARED_SEED,
        "expect": "clear daytime exterior, no dusk/night dominance",
    },

    {
        "id": "B",
        "label": "Persian exterior night (same base + same seed as A)",
        "expect_preset": "exterior_night",
        "text": SHARED_BASE + " در شب",
        "seed": SHARED_SEED,
        "expect": "night lighting preset behavior",
    },

    {
        "id": "C",
        "label": "Persian interior warm",
        "expect_preset": "interior_warm",
        "text": "رندر واقع‌گرایانه فضای داخلی نشیمن یک ویلای مدرن با نور گرم",
        "seed": None,
        "expect": "camera inside the room, interior composition",
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



def ensure_single_core_api():

    print("=" * 68)
    print("  STEP 0 — DUPLICATE CORE API PROCESS CHECK (port 5000)")
    print("=" * 68)

    pids = listeners_on(5000)

    print("  listeners on 5000:", pids if pids else "none")


    if len(pids) > 1:

        print("  !! DUPLICATE Core API processes:", pids)

        for pid in pids:

            print("     stopping stale pid", pid)

            stop_pid(pid)

        time.sleep(3)

        pids = listeners_on(5000)

        print("  listeners after cleanup:", pids if pids else "none")

        assert len(pids) <= 1, "could not reduce to one process: " + str(pids)

        return {"duplicates_found": True, "stopped": True}


    return {"duplicates_found": False, "stopped": False}



def start_core_api():

    os.makedirs(
        os.path.dirname(LOG_PATH),
        exist_ok=True
    )

    env = os.environ.copy()

    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = env["NO_PROXY"]

    python = os.path.join(
        ROOT, ".venv", "Scripts", "python.exe"
    )

    if not os.path.isfile(python):

        python = sys.executable


    handle = open(LOG_PATH, "ab")

    handle.write(b"\n\n===== acceptance_03b api start =====\n")

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



def extract_evidence(case, payload, duration):

    response = payload.get("response") or {}

    trace = response.get("render_handoff") or {}

    metadata = trace.get("render_request_metadata") or {}

    asset = metadata.get("output_asset") or {}


    evidence = {

        "case": case["id"],
        "label": case["label"],
        "expectation": case["expect"],

        "original_prompt": trace.get("original_user_prompt"),
        "normalized_prompt": trace.get("normalized_prompt"),
        "compiled_render_prompt": trace.get("compiled_render_prompt"),

        "selected_preset": metadata.get("preset"),
        "preset_source": metadata.get("preset_source"),
        "preset_reason": metadata.get("preset_reason"),
        "expected_preset": case["expect_preset"],
        "preset_as_expected": (
            metadata.get("preset") == case["expect_preset"]
        ),

        # ---- TEXT_TO_IMAGE_COMFY_03B trace ----
        "removed_conflicting_tail_terms": metadata.get(
            "removed_conflicting_tail_terms"
        ),
        "removed_conflicting_tail_segments": metadata.get(
            "removed_conflicting_tail_segments"
        ),
        "retained_builder_tail": metadata.get("retained_builder_tail"),
        "preset_reinforcement": metadata.get("preset_reinforcement"),

        "final_prompt": metadata.get("final_prompt"),
        "prompt_source": metadata.get("prompt_source"),

        "workflow_name": metadata.get("workflow_name"),
        "seed": metadata.get("seed"),
        "seed_requested": case.get("seed"),
        "width": metadata.get("width"),
        "height": metadata.get("height"),
        "steps": metadata.get("steps"),

        "execution_status": metadata.get("execution_status"),
        "render_status": metadata.get("status"),

        "output_path": asset.get("path"),
        "output_filename": asset.get("filename"),
        "output_exists_flag": metadata.get("output_asset_exists"),

        "runtime_duration_s": duration,

    }


    # final-prompt level assertions
    final = (evidence["final_prompt"] or "").lower()

    evidence["final_prompt_has_golden_hour"] = "golden hour" in final

    evidence["final_prompt_has_facade"] = "facade" in final

    evidence["final_prompt_has_interior_viewpoint"] = (
        "interior viewpoint" in final
    )


    path = evidence["output_path"]

    if path:

        evidence["file_exists"] = os.path.isfile(path)

        evidence["file_size_bytes"] = (
            os.path.getsize(path) if evidence["file_exists"] else None
        )

        evidence["image_dimensions"] = (
            png_size(path) if evidence["file_exists"] else None
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
        "phase": "TEXT_TO_IMAGE_COMFY_03B",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "shared_base_prompt": SHARED_BASE,
        "shared_seed": SHARED_SEED,
        "cases": [],
        "blockers": [],
    }


    report["duplicate_process_check"] = ensure_single_core_api()


    print("\n" + "=" * 68)
    print("  STEP 1 — COMFYUI + CORE API READINESS")
    print("=" * 68)

    status, _ = http_get(COMFY_API + "/system_stats", timeout=10)

    print("  ComfyUI /system_stats ->", status)

    if status != 200:

        report["blockers"].append("ComfyUI unreachable on 8188")

        print("BLOCKED: ComfyUI unreachable")

        return 1


    process = start_core_api()

    if not wait_for_core_api():

        report["blockers"].append("Core API did not become ready")

        stop_pid(str(process.pid))

        return 1


    print("\n" + "=" * 68)
    print("  STEP 2 — REAL PRESET ACCEPTANCE RENDERS (3 cases, max)")
    print("=" * 68)


    try:

        for case in CASES:

            print(
                "\n  --- " + case["id"] + " | " + case["label"] + " ---"
            )

            print("  request :", case["text"])

            print("  expect  :", case["expect"])


            headers = {
                "X-Session-Id": "acceptance_03b_" + case["id"],
            }

            if case.get("seed") is not None:

                headers["X-Render-Seed"] = str(case["seed"])


            started = time.time()

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

            report["cases"].append(evidence)


            print("  preset      :", evidence["selected_preset"],
                  "(", evidence["preset_source"], ")")

            print("  removed     :", evidence["removed_conflicting_tail_terms"])

            print("  reinforcement:", evidence["preset_reinforcement"])

            print("  final prompt:", str(evidence["final_prompt"])[:150])

            print("  seed        :", evidence["seed"])

            print("  exec/status :", evidence["execution_status"],
                  "/", evidence["render_status"])

            print("  output      :", evidence["output_path"])

            print("  file        :", evidence["file_exists"],
                  "| dims:", evidence["image_dimensions"])

            print("  duration    :", duration, "s")

    finally:

        print("\n  stopping Core API pid", process.pid)

        stop_pid(str(process.pid))


    # ------------------------------------------------------
    # CROSS-CASE CHECKS
    # ------------------------------------------------------

    by_id = {
        c["case"]: c for c in report["cases"] if not c.get("error")
    }

    a = by_id.get("A")
    b = by_id.get("B")
    c = by_id.get("C")


    checks = {}

    if a and b:

        checks["A_B_same_seed"] = a.get("seed") == b.get("seed")

        checks["A_B_same_base_prompt"] = (
            a.get("normalized_prompt") is not None
            and b.get("normalized_prompt") is not None
            and a["normalized_prompt"] != b["normalized_prompt"]
            and SHARED_BASE in a["normalized_prompt"]
            and SHARED_BASE in b["normalized_prompt"]
        )

        checks["A_B_different_preset"] = (
            a.get("selected_preset") != b.get("selected_preset")
        )

    if a:

        checks["A_no_golden_hour_in_final"] = not a.get(
            "final_prompt_has_golden_hour", True
        )

    if c:

        checks["C_has_interior_viewpoint"] = c.get(
            "final_prompt_has_interior_viewpoint", False
        )

        checks["C_no_facade_in_final"] = not c.get(
            "final_prompt_has_facade", True
        )

    report["cross_case_checks"] = checks


    print("\n" + "=" * 68)
    print("  CROSS-CASE CHECKS")
    print("=" * 68)

    for key, value in checks.items():

        print("  " + ("[ OK ]" if value else "[FAIL]") + " " + key)

    # ------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------

    print("\n" + "=" * 68)
    print("  ACCEPTANCE SUMMARY")
    print("=" * 68)

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
            "  " + evidence["case"]
            + " : preset=" + str(evidence["selected_preset"])
            + " removed=" + str(len(evidence.get("removed_conflicting_tail_terms") or []))
            + " exec=" + str(evidence["execution_status"])
            + " status=" + str(evidence["render_status"])
            + " file=" + str(evidence["file_exists"])
            + " dims=" + str(evidence["image_dimensions"])
            + " seed=" + str(evidence["seed"])
            + " " + str(evidence["runtime_duration_s"]) + "s"
            + ("  OK" if success else "  !! NOT SUCCESS")
        )

    report["real_renders_completed"] = rendered
    report["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")


    with open(REPORT_PATH, "w", encoding="utf-8") as f:

        json.dump(report, f, ensure_ascii=False, indent=2)


    print("\n  report written:", REPORT_PATH)

    print("  successful real renders:", rendered, "/", len(CASES))

    print(
        "  cross-case checks passed:",
        sum(1 for v in checks.values() if v),
        "/",
        len(checks)
    )


    return 0 if rendered == len(CASES) else 2



if __name__ == "__main__":

    sys.exit(main())
