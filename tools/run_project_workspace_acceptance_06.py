# ==========================================================
# PROJECT_WORKSPACE_UI_06 — ACCEPTANCE RUNNER
#
# Real persistence acceptance through the LIVE API. No ComfyUI
# render is performed (no production-quality generation).
#
# Tests
#   1. PERSISTENCE RESTART
#        create project -> chat message -> upload -> restart the
#        Core API service -> reopen -> verify chat, assets, ordinals,
#        active image restored, and that a text reference resolves the
#        restored image WITHOUT re-uploading.
#   2. FILE COLLISION
#        upload two DIFFERENT files with the SAME original filename;
#        generated filenames and storage paths must differ and neither
#        file may be overwritten.
#   3. PROJECT ISOLATION
#        two projects each with image ordinal 1; "عکس اول" must
#        resolve inside its own project only.
#
# Usage:
#   python tools/run_project_workspace_acceptance_06.py
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

    sys.path.insert(0, ROOT)


CORE_API = "http://127.0.0.1:5000"

REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_06_report.json"
)

LOG_PATH = os.path.join(
    ROOT, "logs", "runtime", "acceptance_06_core.log"
)


_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({})
)


# Two real render files are used purely as UPLOAD payloads; nothing is
# rendered by this harness.
FILE_A = "C:/ComfyUI-Zluda/output/architectos_v11_00235_.png"
FILE_B = "C:/ComfyUI-Zluda/output/architectos_img2img_edit_00083_.png"


# ==========================================================
# HTTP
# ==========================================================

def http_json(path, payload=None, method=None, timeout=10800):

    body = json.dumps(payload).encode("utf-8") if payload is not None else None

    request = urllib.request.Request(

        CORE_API + path,

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


def http_multipart(path, text, image_path, fields=None, timeout=10800):

    boundary = "----ArchitectOS06Boundary"

    with open(image_path, "rb") as handle:

        image_bytes = handle.read()

    parts = []

    parts.append(
        ("--" + boundary + "\r\n").encode()
        + b'Content-Disposition: form-data; name="text"\r\n\r\n'
        + text.encode("utf-8")
        + b"\r\n"
    )

    for key, value in (fields or {}).items():

        if value is None:

            continue

        parts.append(
            ("--" + boundary + "\r\n").encode()
            + ('Content-Disposition: form-data; name="%s"\r\n\r\n' % key).encode()
            + str(value).encode("utf-8")
            + b"\r\n"
        )

    parts.append(
        ("--" + boundary + "\r\n").encode()
        + (
            'Content-Disposition: form-data; name="image"; '
            'filename="%s"\r\n' % os.path.basename(image_path)
        ).encode()
        + b"Content-Type: image/png\r\n\r\n"
        + image_bytes
        + b"\r\n"
    )

    parts.append(("--" + boundary + "--\r\n").encode())

    body = b"".join(parts)

    request = urllib.request.Request(

        CORE_API + path,

        data=body,

        method="POST",

        headers={
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
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

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    if not os.path.isfile(python):

        python = sys.executable

    handle = open(LOG_PATH, "ab")

    handle.write(b"\n\n===== acceptance_06 core start =====\n")

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

        status, _ = http_json("/health", timeout=5)

        if status == 200:

            return True

        time.sleep(1)

    return False


def stop_core(process):

    try:

        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            timeout=10800,
        )

    except Exception:

        pass


def restart_core(process):

    print("  stopping Core API pid", process.pid)

    stop_core(process)

    time.sleep(3)

    print("  restarting Core API…")

    new_process = start_core()

    if not wait_for_core():

        raise RuntimeError("Core API did not come back after restart")

    print("  Core API back online (pid %s)" % new_process.pid)

    return new_process


# ==========================================================
# RESULT HELPERS
# ==========================================================

RESULTS = []


def record(name, passed, detail=None):

    RESULTS.append({
        "test": name,
        "passed": bool(passed),
        "detail": detail,
    })

    print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

    if detail and not passed:

        print("        ", json.dumps(detail, ensure_ascii=False)[:400])


# ==========================================================
# TEST 1 — PERSISTENCE RESTART
# ==========================================================

def test_persistence_restart(process, report):

    print("\n" + "=" * 70)
    print("  TEST 1 — PERSISTENCE RESTART")
    print("=" * 70)

    status, created = http_json("/api/projects", {"name": "Persistence Test"})

    project_id = (created.get("project") or {}).get("project_id")

    record("1.1 create project", bool(project_id), created)

    if not project_id:

        return process, {}

    # ---- chat message ----
    # A plain conversational turn. Heavy design/plan requests are out of
    # scope for this phase and are deliberately not used here.
    status, chat = http_json("/api/chat", {
        "text": "سلام ArchitectOS",
        "project_id": project_id,
    })

    record(
        "1.2 chat message accepted",
        status == 200
        and isinstance(chat, dict)
        and chat.get("status") == "success",
        chat if status != 200 else None,
    )

    record(
        "1.2b autosave reported after the chat turn",
        isinstance(chat, dict)
        and (chat.get("save_state") or {}).get("state") in ("saved", "saving"),
        (chat or {}).get("save_state"),
    )

    record(
        "1.2c strategy metadata recorded",
        isinstance(chat, dict)
        and isinstance(chat.get("strategy"), dict)
        and chat["strategy"].get("resolved_mode") is not None
        and chat["strategy"].get("routing_source") in ("auto", "manual"),
        (chat or {}).get("strategy"),
    )

    # ---- upload ----
    status, upload = http_multipart(
        "/api/chat",
        "",
        FILE_A,
        fields={"project_id": project_id},
    )

    record("1.3 image upload accepted", status == 200, upload)

    # ---- verify before restart ----
    status, before = http_json("/api/projects/" + project_id)

    recovery_before = before.get("recovery") or {}

    record(
        "1.4 state saved before restart",
        recovery_before.get("asset_count") == 1
        and (recovery_before.get("message_count") or 0) >= 1,
        recovery_before,
    )

    active_before = recovery_before.get("active_asset_id")

    # ---- RESTART ----
    process = restart_core(process)

    # ---- reopen ----
    status, opened = http_json(
        "/api/projects/" + project_id + "/open",
        {},
    )

    record("1.5 project reopened after restart", status == 200, opened)

    recovery = (opened.get("recovery") or {})

    record(
        "1.6 chat history restored",
        (recovery.get("message_count") or 0) >= 1,
        recovery,
    )

    record(
        "1.7 assets restored",
        recovery.get("asset_count") == 1,
        recovery,
    )

    record(
        "1.8 ordinals restored",
        recovery.get("ordinals") == [1],
        recovery.get("ordinals"),
    )

    record(
        "1.9 active image restored",
        bool(recovery.get("active_asset_id")),
        recovery.get("active_asset_id"),
    )

    record(
        "1.10 lineage structure restored",
        isinstance(recovery.get("lineage"), list)
        and len(recovery.get("lineage") or []) == 1,
        recovery.get("lineage"),
    )

    # ---- text reference resolves WITHOUT re-upload ----
    status, resolved = http_json("/api/chat", {
        "text": "همین عکس رو توضیح بده",
        "project_id": project_id,
    })

    vision = ((resolved.get("response") or {}).get("vision") or {})

    reference = vision.get("reference") or {}

    record(
        "1.11 restored image resolves without re-upload",
        reference.get("status") == "resolved"
        and reference.get("target_ordinal") == 1,
        {
            "reference": reference,
            "vision_intent": vision.get("intent"),
        },
    )

    report["persistence_restart"] = {
        "project_id": project_id,
        "recovery_before": recovery_before,
        "recovery_after": recovery,
        "reference_after_restart": reference,
    }

    return process, {"project_id": project_id}


def make_collision_fixtures():

    """Two DIFFERENT files that share the SAME original filename."""

    import shutil

    root = os.path.join(ROOT, ".pytest_tmp", "acceptance06_collision")

    first_dir = os.path.join(root, "first")

    second_dir = os.path.join(root, "second")

    os.makedirs(first_dir, exist_ok=True)

    os.makedirs(second_dir, exist_ok=True)

    name = "test_upload.png"

    first = os.path.join(first_dir, name)

    second = os.path.join(second_dir, name)

    shutil.copy2(FILE_A, first)

    shutil.copy2(FILE_B, second)

    return first, second


# ==========================================================
# TEST 2 — FILE COLLISION
# ==========================================================

def test_file_collision(process, report):

    print("\n" + "=" * 70)
    print("  TEST 2 — FILE COLLISION")
    print("=" * 70)

    status, created = http_json("/api/projects", {"name": "Collision Test"})

    project_id = (created.get("project") or {}).get("project_id")

    record("2.1 collision project created", bool(project_id), created)

    if not project_id:

        return {}

    # Two DIFFERENT files, SAME original filename.
    first, second = make_collision_fixtures()

    status_a, upload_a = http_multipart(
        "/api/chat", "", first,
        fields={"project_id": project_id},
    )

    status_b, upload_b = http_multipart(
        "/api/chat", "", second,
        fields={"project_id": project_id},
    )

    record("2.2 first upload accepted", status_a == 200, upload_a)

    record("2.3 second upload accepted", status_b == 200, upload_b)

    status, gallery = http_json(
        "/api/projects/" + project_id + "/assets"
    )

    assets = ((gallery.get("gallery") or {}).get("assets") or [])

    record("2.4 two assets registered", len(assets) == 2, len(assets))

    if len(assets) == 2:

        a, b = assets

        record(
            "2.5 generated filenames differ",
            a.get("generated_filename") != b.get("generated_filename"),
            [a.get("generated_filename"), b.get("generated_filename")],
        )

        record(
            "2.6 storage paths differ",
            a.get("storage_path") != b.get("storage_path"),
            [a.get("storage_path"), b.get("storage_path")],
        )

        record(
            "2.7 both files exist on disk (neither overwritten)",
            os.path.isfile(a.get("storage_path") or "")
            and os.path.isfile(b.get("storage_path") or ""),
            [a.get("storage_path"), b.get("storage_path")],
        )

        record(
            "2.8 both registry entries valid",
            all(x.get("asset_id") for x in (a, b)),
            [a.get("asset_id"), b.get("asset_id")],
        )

        record(
            "2.9 original filename may legitimately match",
            a.get("original_filename") == b.get("original_filename"),
            [a.get("original_filename"), b.get("original_filename")],
        )

        report["file_collision"] = {
            "project_id": project_id,
            "asset_a": {
                "original_filename": a.get("original_filename"),
                "generated_filename": a.get("generated_filename"),
                "storage_path": a.get("storage_path"),
            },
            "asset_b": {
                "original_filename": b.get("original_filename"),
                "generated_filename": b.get("generated_filename"),
                "storage_path": b.get("storage_path"),
            },
        }

    return {"project_id": project_id}


# ==========================================================
# TEST 3 — PROJECT ISOLATION
# ==========================================================

def test_isolation(process, report):

    print("\n" + "=" * 70)
    print("  TEST 3 — PROJECT ISOLATION")
    print("=" * 70)

    status, a = http_json("/api/projects", {"name": "Isolation A"})
    status, b = http_json("/api/projects", {"name": "Isolation B"})

    project_a = (a.get("project") or {}).get("project_id")
    project_b = (b.get("project") or {}).get("project_id")

    record("3.1 two projects created", bool(project_a and project_b),
           [project_a, project_b])

    if not (project_a and project_b):

        return {}

    http_multipart("/api/chat", "", FILE_A,
                   fields={"project_id": project_a})

    http_multipart("/api/chat", "", FILE_B,
                   fields={"project_id": project_b})

    status, gallery_a = http_json(
        "/api/projects/" + project_a + "/assets"
    )
    status, gallery_b = http_json(
        "/api/projects/" + project_b + "/assets"
    )

    assets_a = ((gallery_a.get("gallery") or {}).get("assets") or [])
    assets_b = ((gallery_b.get("gallery") or {}).get("assets") or [])

    record(
        "3.2 both projects have image ordinal 1",
        [x.get("ordinal") for x in assets_a] == [1]
        and [x.get("ordinal") for x in assets_b] == [1],
        [[x.get("ordinal") for x in assets_a],
         [x.get("ordinal") for x in assets_b]],
    )

    # resolve "عکس اول" inside each project
    status, ra = http_json("/api/chat", {
        "text": "عکس اول رو توضیح بده",
        "project_id": project_a,
    })

    status, rb = http_json("/api/chat", {
        "text": "عکس اول رو توضیح بده",
        "project_id": project_b,
    })

    ref_a = (((ra.get("response") or {}).get("vision") or {})
             .get("reference") or {})
    ref_b = (((rb.get("response") or {}).get("vision") or {})
             .get("reference") or {})

    record(
        "3.3 'عکس اول' resolves in project A",
        ref_a.get("status") == "resolved",
        ref_a,
    )

    record(
        "3.4 'عکس اول' resolves in project B",
        ref_b.get("status") == "resolved",
        ref_b,
    )

    record(
        "3.5 no cross-project leakage (different images)",
        ref_a.get("target_image_id")
        and ref_b.get("target_image_id")
        and ref_a.get("target_image_id") != ref_b.get("target_image_id"),
        [ref_a.get("target_image_id"), ref_b.get("target_image_id")],
    )

    # confirm the two resolved assets live in different project folders
    paths_a = [x.get("storage_path") for x in assets_a]
    paths_b = [x.get("storage_path") for x in assets_b]

    record(
        "3.6 storage is project-scoped",
        bool(paths_a) and bool(paths_b)
        and project_a in (paths_a[0] or "")
        and project_b in (paths_b[0] or ""),
        [paths_a, paths_b],
    )

    report["project_isolation"] = {
        "project_a": project_a,
        "project_b": project_b,
        "reference_a": ref_a,
        "reference_b": ref_b,
        "storage_a": paths_a,
        "storage_b": paths_b,
    }

    return {"project_a": project_a, "project_b": project_b}


# ==========================================================
# MAIN
# ==========================================================

def main():

    report = {
        "phase": "PROJECT_WORKSPACE_UI_06",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "real_renders": 0,
        "tests": [],
        "blockers": [],
    }

    for path in (FILE_A, FILE_B):

        if not os.path.isfile(path):

            report["blockers"].append("missing fixture: " + path)

    if report["blockers"]:

        print("BLOCKED:", report["blockers"])

        return 1

    process = start_core()

    if not wait_for_core():

        stop_core(process)

        report["blockers"].append("core API did not start")

        return 1

    try:

        process, _ = test_persistence_restart(process, report)

        test_file_collision(process, report)

        test_isolation(process, report)

    finally:

        stop_core(process)

    report["tests"] = RESULTS

    passed = sum(1 for r in RESULTS if r["passed"])

    report["passed"] = passed
    report["total"] = len(RESULTS)
    report["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:

        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print("  %d / %d checks passed" % (passed, len(RESULTS)))
    print("  report:", REPORT_PATH)

    return 0 if passed == len(RESULTS) else 2


if __name__ == "__main__":

    sys.exit(main())
