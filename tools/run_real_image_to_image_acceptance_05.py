# ==========================================================
# ArchitectOS IMAGE_TO_IMAGE_05 — REAL Acceptance Runner
#
# CONTINUATION / RECOVERY BUDGET: at most 2 NEW real renders.
#
#   A. "همینو شب کن"                 (active image -> night)
#   B. "رندر قبلی رو سنگ روشن کن"     (last render -> light stone)
#
# Both use the DRAFT/PREVIEW profile (low steps) per the locked
# test-render policy.
#
# Plus a NEGATIVE test that must NOT render:
#   N. "این پنجره رو 80 سانت ببر راست"
#      -> unsupported precise-geometry edit, no execution
#
# Also performs the duplicate Core API process check first.
#
# Usage:
#   python tools/run_real_image_to_image_acceptance_05.py
#   python tools/run_real_image_to_image_acceptance_05.py --negative-only
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
    ROOT, "tools", "acceptance_05_report.json"
)

# --negative-only runs must not overwrite the real-edit evidence.
NEGATIVE_REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_05_negative_report.json"
)

LOG_PATH = os.path.join(
    ROOT, "logs", "runtime", "acceptance_05_api.log"
)


# Source image for the edit chain (an existing text-to-image render).
SOURCE_IMAGE = "C:/ComfyUI-Zluda/output/architectos_v11_00235_.png"


SESSION = "acceptance_05"


# Draft/preview steps for functional acceptance (test budget policy).
#
# CONSTRAINT (reported, not hidden): ComfyUI's KSampler treats
# `denoise` as a FRACTION of `steps`, so the effective sampler steps
# are int(steps * denoise).
#
# IMAGE_TO_IMAGE_05 UPDATE — this harness now drives the CODE-ENFORCED
# render profile instead of a bare step number:
#
#   ARCHITECTOS_RENDER_PROFILE=PREVIEW   (DRAFT | PREVIEW | QUALITY | FINAL)
#   ARCHITECTOS_PREVIEW_LONG_EDGE=448    (approved band 384-512)
#
# DRAFT/PREVIEW additionally downscale the source into a TEMPORARY
# working copy, so a functional render no longer runs at the
# production source resolution (768x704) at all. The original asset
# stays authoritative and untouched.
#
# Legacy step values are still honoured as a fallback.
DRAFT_STEPS = 8

RENDER_PROFILE = "PREVIEW"

PREVIEW_LONG_EDGE = 448


_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({})
)


CASES = (

    {
        "id": "A",
        "label": "active image -> night",
        "text": "همینو شب کن",
        "expect_reference": "active",
        "expect_level": "high_preservation",
        "expect_class": "time_of_day_change",
    },

    {
        "id": "B",
        "label": "last render -> light stone",
        "text": "رندر قبلی رو سنگ روشن کن",
        "expect_reference": "last_render",
        "expect_level": "balanced",
        "expect_class": "material_change",
    },
)


NEGATIVE = {
    "id": "N",
    "label": "unsupported precise-geometry edit",
    "text": "این پنجره رو 80 سانت ببر راست",
}



# ==========================================================
# HTTP HELPERS
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



def http_post_multipart(url, text, image_path, headers=None, timeout=10800):
    """Minimal multipart POST (no external deps)."""

    boundary = "----ArchitectOS05Boundary"

    with open(image_path, "rb") as handle:

        image_bytes = handle.read()


    parts = []

    parts.append(
        ("--" + boundary + "\r\n").encode()
        + b'Content-Disposition: form-data; name="text"\r\n\r\n'
        + text.encode("utf-8")
        + b"\r\n"
    )

    parts.append(
        ("--" + boundary + "\r\n").encode()
        + (
            'Content-Disposition: form-data; name="image"; '
            'filename="source.png"\r\n'
        ).encode()
        + b"Content-Type: image/png\r\n\r\n"
        + image_bytes
        + b"\r\n"
    )

    parts.append(
        ("--" + boundary + "--\r\n").encode()
    )

    body = b"".join(parts)

    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "multipart/form-data; boundary=" + boundary,
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

        if parts[1].endswith(needle) or parts[1].endswith(needle + "]"):

            pids.add(parts[4])

    return sorted(pids)



def png_size(path):

    try:

        with open(path, "rb") as handle:

            head = handle.read(26)

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

    print("=" * 70)
    print("  STEP 0 — DUPLICATE CORE API PROCESS CHECK (port 5000)")
    print("=" * 70)

    pids = listeners_on(5000)

    print("  listeners on 5000:", pids if pids else "none")


    if len(pids) > 1:

        print("  !! DUPLICATE Core API processes:", pids)

        for pid in pids:

            stop_pid(pid)

        time.sleep(3)

        pids = listeners_on(5000)

        print("  after cleanup:", pids if pids else "none")

        assert len(pids) <= 1

        return {"duplicates_found": True, "stopped": True}


    return {"duplicates_found": False, "stopped": False}



def start_core_api():

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    env = os.environ.copy()

    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = env["NO_PROXY"]
    env["PYTHONUNBUFFERED"] = "1"

    # IMAGE_TO_IMAGE_05 — TEST BUDGET POLICY (code enforced).
    # Functional acceptance renders use the PREVIEW profile, which
    # downscales the source into a temporary working copy.
    env["ARCHITECTOS_RENDER_PROFILE"] = RENDER_PROFILE
    env["ARCHITECTOS_PREVIEW_LONG_EDGE"] = str(PREVIEW_LONG_EDGE)

    # Legacy switches kept in sync for older code paths.
    env["ARCHITECTOS_RENDER_DRAFT"] = "1"
    env["ARCHITECTOS_RENDER_DRAFT_STEPS"] = str(DRAFT_STEPS)

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    if not os.path.isfile(python):

        python = sys.executable


    handle = open(LOG_PATH, "ab")

    handle.write(b"\n\n===== acceptance_05 api start =====\n")

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


def assert_test_render_profile():

    """Refuse to spend render budget on a production profile."""

    print("=" * 70)
    print("  STEP 0b — TEST-RENDER PROFILE GUARD")
    print("=" * 70)

    from core.render.render_draft_v1 import (
        assert_test_profile,
        resolve_profile,
        PROFILE_ORDER,
    )

    resolved = resolve_profile(explicit=RENDER_PROFILE)

    assert_test_profile(resolved)

    print("  profile      :", resolved.get("name"))
    print("  steps        :", resolved.get("steps"))
    print("  preview edge :", resolved.get("long_edge"))
    print("  production res:", resolved.get("production_resolution"))
    print("  upscale       :", resolved.get("upscale"))
    print("  quality pass  :", resolved.get("quality_pass"))
    print("  available     :", PROFILE_ORDER)

    return resolved



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
# EVIDENCE
# ==========================================================

def extract_evidence(case, payload, duration):

    response = payload.get("response") or {}

    vision = response.get("vision") or {}

    reference = vision.get("reference") or {}

    preservation = response.get("preservation") or response.get(
        "edit_preservation"
    ) or {}

    render_metadata = response.get("render_metadata") or {}

    edit_delta = response.get("edit_delta") or {}


    attachments = response.get("attachments") or []

    output_path = None

    if attachments:

        output_path = attachments[0].get("url")


    evidence = {

        "case": case["id"],
        "label": case["label"],
        "text": case["text"],

        "api_status": payload.get("status"),
        "type": response.get("type"),
        "engine": response.get("engine"),
        "status": response.get("status"),

        "reference_status": reference.get("status"),
        "reference_kind": reference.get("reference_kind"),
        "reference_ordinal": reference.get("target_ordinal"),
        "expect_reference": case.get("expect_reference"),

        "intent": vision.get("intent"),
        "intent_reason": vision.get("intent_reason"),

        # ---- IMAGE_TO_IMAGE_05 — prompt / delta authority ----
        "edit_class": edit_delta.get("edit_class"),
        "edit_material": edit_delta.get("material"),
        "edit_material_tone": edit_delta.get("material_tone"),
        "edit_time_of_day": edit_delta.get("time_of_day"),
        "expect_class": case.get("expect_class"),

        "compiled_render_prompt": response.get("compiled_render_prompt"),
        "delta_prompt": edit_delta.get("prompt"),

        "final_comfy_prompt": render_metadata.get("final_prompt"),

        "edit_conflict_terms": render_metadata.get("edit_conflict_terms"),
        "removed_conflicting_tail_terms": render_metadata.get(
            "removed_conflicting_tail_terms"
        ),

        "preservation_level": preservation.get("level"),
        "preservation_denoise": preservation.get("denoise"),
        "preservation_source": preservation.get("source"),
        "expect_level": case.get("expect_level"),

        "parent_image_id": response.get("parent_image_id"),

        "draft_mode": render_metadata.get("draft_mode"),

        # ---- IMAGE_TO_IMAGE_05 — test-render profile + preview source ----
        "render_profile": render_metadata.get("render_profile"),

        "source_preview": render_metadata.get("source_preview"),

        "edit_capability": render_metadata.get("edit_capability"),

        "injected_steps": render_metadata.get("steps"),

        "injected_denoise": render_metadata.get("denoise"),

        "injected_seed": render_metadata.get("seed"),

        "final_prompt": render_metadata.get("final_prompt"),

        "render": response.get("render"),

        "output_url": output_path,

        "runtime_duration_s": duration,

    }


    return evidence



def main():

    # --negative-only: verify the guard without spending any render.
    negative_only = "--negative-only" in sys.argv


    report = {
        "phase": "IMAGE_TO_IMAGE_05",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "session": SESSION,
        "source_image": SOURCE_IMAGE,
        "draft_mode": True,
        "draft_steps": DRAFT_STEPS,
        "render_profile": RENDER_PROFILE,
        "preview_long_edge": PREVIEW_LONG_EDGE,
        "negative_only": negative_only,
        "cases": [],
        "negative": None,
        "blockers": [],
    }


    report["duplicate_process_check"] = ensure_single_core_api()


    report["test_render_profile"] = assert_test_render_profile()


    # IMAGE_TO_IMAGE_05 — truthful capability contract for the record.
    try:

        from core.render.image_edit_capability_v1 import audit as audit_capability

        report["capability_audit"] = audit_capability()

    except Exception as error:

        report["capability_audit"] = {
            "error": type(error).__name__ + ": " + str(error)
        }


    print("\n" + "=" * 70)
    print("  STEP 1 — COMFYUI + CORE API READINESS")
    print("=" * 70)

    status, _ = http_get(COMFY_API + "/system_stats", timeout=10)

    print("  ComfyUI /system_stats ->", status)

    if status != 200:

        report["blockers"].append("ComfyUI unreachable on 8188")

        print("BLOCKED: ComfyUI unreachable")

        return 1


    if not os.path.isfile(SOURCE_IMAGE):

        report["blockers"].append("source image missing: " + SOURCE_IMAGE)

        print("BLOCKED: source image missing")

        return 1


    process = start_core_api()

    if not wait_for_core_api():

        report["blockers"].append("Core API did not become ready")

        stop_pid(str(process.pid))

        return 1


    try:

        # --------------------------------------------------
        # STEP 2 — seed the session with a source image
        # --------------------------------------------------

        print("\n" + "=" * 70)
        print("  STEP 2 — SEED SESSION WITH A SOURCE IMAGE")
        print("=" * 70)

        status, payload = http_post_multipart(
            CORE_API + "/chat",
            "",
            SOURCE_IMAGE,
            headers={"X-Session-Id": SESSION},
        )

        response = payload.get("response") or {}

        vision = response.get("vision") or {}

        print("  upload type   :", response.get("type"))

        print("  upload status :", response.get("status"))

        print("  image_id      :", vision.get("image_id"))

        print("  ordinal       :", vision.get("ordinal"))

        report["source_registration"] = {
            "type": response.get("type"),
            "image_id": vision.get("image_id"),
            "ordinal": vision.get("ordinal"),
        }

        source_image_id = vision.get("image_id")


        # --------------------------------------------------
        # STEP 3 — REAL EDIT CHAIN
        # --------------------------------------------------

        print("\n" + "=" * 70)
        print("  STEP 3 — REAL IMG2IMG EDITS (3 renders max)")
        print("=" * 70)

        if negative_only:

            print("  SKIPPED (--negative-only: no render budget spent)")

        for case in (() if negative_only else CASES):

            print(
                "\n  --- " + case["id"] + " | " + case["label"] + " ---"
            )

            print("  request:", case["text"])

            started = time.time()

            try:

                status, payload = http_post_json(
                    CORE_API + "/chat",
                    {"text": case["text"]},
                    timeout=10800,
                    headers={"X-Session-Id": SESSION},
                )

            except Exception as e:

                print("  REQUEST FAILED:", type(e).__name__, e)

                report["cases"].append({
                    "case": case["id"],
                    "error": type(e).__name__ + ": " + str(e),
                })

                continue


            duration = round(time.time() - started, 1)

            evidence = extract_evidence(case, payload, duration)

            report["cases"].append(evidence)

            print("  reference   :", evidence["reference_status"],
                  evidence["reference_kind"], "-> ordinal",
                  evidence["reference_ordinal"])

            print("  intent      :", evidence["intent"])

            print("  edit class  :", evidence["edit_class"],
                  "| material", evidence["edit_material"],
                  "| time_of_day", evidence["edit_time_of_day"])

            print("  preservation:", evidence["preservation_level"],
                  "| denoise", evidence["preservation_denoise"],
                  "|", evidence["preservation_source"])

            print("  draft       :", evidence["draft_mode"],
                  "| injected steps", evidence["injected_steps"],
                  "| seed", evidence["injected_seed"])

            print("  parent      :", evidence["parent_image_id"])

            print("  status      :", evidence["status"])

            print("  render      :", evidence["render"])

            print("  duration    :", duration, "s")

            _final = (evidence.get("final_comfy_prompt") or "").lower()

            _delta_ok = bool(evidence.get("delta_prompt")) and bool(
                evidence.get("compiled_render_prompt")
            )

            print("  delta reached Comfy prompt :", _delta_ok)

            print("  removed tail conflicts     :",
                  evidence.get("removed_conflicting_tail_terms"))

            print("  final prompt contains 'natural lighting' :",
                  "natural lighting" in _final)

            print("  final prompt contains 'night' :",
                  "night" in _final)

            print("  final prompt contains 'light natural stone' :",
                  "light natural stone" in _final)


        # --------------------------------------------------
        # STEP 4 — NEGATIVE TEST (must NOT render)
        # --------------------------------------------------

        print("\n" + "=" * 70)
        print("  STEP 4 — NEGATIVE: unsupported precise-geometry edit")
        print("=" * 70)

        print("  request:", NEGATIVE["text"])

        started = time.time()

        status, payload = http_post_json(
            CORE_API + "/chat",
            {"text": NEGATIVE["text"]},
            timeout=10800,
            headers={"X-Session-Id": SESSION},
        )

        duration = round(time.time() - started, 1)

        response = payload.get("response") or {}

        report["negative"] = {

            "case": "N",
            "text": NEGATIVE["text"],
            "type": response.get("type"),
            "status": response.get("status"),
            "unsupported_edit": response.get("unsupported_edit"),
            "render": response.get("render"),
            "result": str(response.get("result"))[:300],
            "runtime_duration_s": duration,

        }

        print("  type   :", response.get("type"))

        print("  status :", response.get("status"))

        print("  guard  :", (response.get("unsupported_edit") or {}).get("reason"))

        print("  render :", response.get("render"))

        print("  answer :", str(response.get("result"))[:160])

        print("  duration:", duration, "s")

    finally:

        print("\n  stopping Core API pid", process.pid)

        stop_pid(str(process.pid))


    # ------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------

    print("\n" + "=" * 70)
    print("  ACCEPTANCE SUMMARY")
    print("=" * 70)

    rendered = 0

    for evidence in report["cases"]:

        if evidence.get("error"):

            print("  " + evidence["case"] + " : ERROR " + evidence["error"])

            continue

        success = (
            evidence.get("status") == "success"
            and evidence.get("render", {}).get("status") == "success"
        )

        if success:

            rendered += 1

        # ---- deterministic PROMPT-level acceptance (not visual) ----
        _final = (evidence.get("final_comfy_prompt") or "").lower()

        checks = {
            "delta_present": bool(evidence.get("delta_prompt")),
            "compiled_authoritative": bool(
                evidence.get("compiled_render_prompt")
            ),
            "delta_in_final_prompt": bool(
                evidence.get("delta_prompt")
                and evidence.get("delta_prompt")[:40].lower() in _final
            ),
            "daylight_conflict_removed": (
                "natural lighting" not in _final
                if evidence.get("edit_class") == "time_of_day_change"
                else None
            ),
            "material_delta_in_prompt": (
                "light natural stone" in _final
                if evidence.get("edit_class") == "material_change"
                else None
            ),
        }

        evidence["prompt_checks"] = checks

        print(
            "  " + evidence["case"]
            + " : ref=" + str(evidence.get("reference_kind"))
            + " class=" + str(evidence.get("edit_class"))
            + " level=" + str(evidence.get("preservation_level"))
            + " denoise=" + str(evidence.get("preservation_denoise"))
            + " parent=" + str(evidence.get("parent_image_id"))
            + " status=" + str(evidence.get("status"))
            + " " + str(evidence.get("runtime_duration_s")) + "s"
            + ("  OK" if success else "  !! NOT SUCCESS")
        )

        print("        prompt checks:", checks)


    negative = report.get("negative") or {}

    negative_ok = (
        negative.get("status") == "unsupported_edit"
        and negative.get("render") is None
    )

    print(
        "  N : status=" + str(negative.get("status"))
        + " render=" + str(negative.get("render"))
        + ("  OK (refused, no render)" if negative_ok else "  !! FAILED")
    )


    report["real_renders_completed"] = rendered
    report["negative_refused"] = negative_ok
    report["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")


    with open(
        NEGATIVE_REPORT_PATH if negative_only else REPORT_PATH,
        "w",
        encoding="utf-8"
    ) as handle:

        json.dump(report, handle, ensure_ascii=False, indent=2)


    print(
        "\n  report written:",
        NEGATIVE_REPORT_PATH if negative_only else REPORT_PATH
    )

    print("  successful real edits:", rendered, "/", len(CASES))

    print("  negative test refused:", negative_ok)

    if negative_only:

        return 0 if negative_ok else 2

    return 0 if (rendered == len(CASES) and negative_ok) else 2



if __name__ == "__main__":

    sys.exit(main())
