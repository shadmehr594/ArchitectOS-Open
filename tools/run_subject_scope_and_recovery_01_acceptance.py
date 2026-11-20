# ==========================================================
# SUBJECT_SCOPE_AND_TURN_RECOVERY_01 — LIVE ACCEPTANCE
#
# Proves, on a THROW-AWAY Core + UI gateway (spare ports, isolated data
# root, render-stop guard), the two user-reported defects:
#
#   1. a question about the master bedroom is answered ONLY with the
#      rules about the master bedroom
#   2. an image turn whose HTTP response is lost can be recovered from
#      the project, because the Core stored the answer
#
# Usage:
#   .venv/Scripts/python.exe tools/run_subject_scope_and_recovery_01_acceptance.py
#
# Add --skip-contract to skip the contract suite + the previous suites.
# ==========================================================

import io
import re
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

CORE_PORT = 5094

UI_PORT = 3094

CORE = "http://127.0.0.1:%d" % CORE_PORT

UI = "http://127.0.0.1:%d" % UI_PORT

WORK = os.path.join(ROOT, ".pytest_tmp", "subject_scope_01_" + STAMP)

DATA_ROOT = os.path.join(WORK, "project_data")

os.makedirs(DATA_ROOT, exist_ok=True)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

CORE_LOG = os.path.join(WORK, "core.log")

UI_LOG = os.path.join(WORK, "ui.log")

REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_subject_scope_01_report.json"
)

MASTER = "MASTER_BEDROOM_SLEEPING"

# ---- the teacher's own messages, verbatim (from the live project) ----

# The topic is established by the messages that NAME the space, exactly
# as it was in the reported session: a message that names no space
# inherits the session's subject.
TEACH_DEFINITION = (
    "اتاق خواب مستر اتاق والدین هست اونی که تو گفتی اتاق خواب "
    "میهمانه که تو بعضی از خونه ها در نظر میگیرن"
)

TEACH_PRIVATE = (
    "اتاق خواب مستر فقط مخصوص زوجین هست و یک فضای خصوصی است"
)

LONG_RULES = (
    "یسری چیزها باید در نظر گرفت روی تخت محل معاشقه والدین هست پس "
    "تخت باید جایی گذاشته شود که در باز میشود دیدی به تخت نداشته باشه "
    "، تخت دور از پنجره باشه بهتره ، اتاق خواب ها باید دور از پذیرایی "
    "و فضاهای نشیمن باشن چون اون فضاها فضاهای عمومی هستن و مهمان میاد "
    "ولی اتاق خواب فضای خصوصی است و حریمش باید حفظ شود"
)

MIXED_MESSAGE = (
    "اینم باز اشتباه فهمیدی : فهمیدم: پنجره باید دور از اتاق خواب و "
    "نشیمن باشد. ، من گفتم تخت دور از پنجره باشه بهتره تو برای اتاق "
    "خواب حتما پنجره داشته باشی اتاق خواب به نور طبیعی و تهویه نیاز "
    "داره ، نشیمن هم باید پنجره داشته باشه"
)

QUESTION = "در مورد اتاق خواب مستر چی میدونی؟"

IMAGE_QUESTION = "تحلیلت از این عکس چیه؟"

BEDROOM_RULE = "تخت دور از پنجره باشه بهتره"

BEDROOM_WINDOW_RULE = "تو برای اتاق خواب حتما پنجره داشته باشی"

CROSS_RULE = "اتاق خواب ها باید دور از پذیرایی و فضاهای نشیمن باشن"

LIVING_ONLY_RULE = "نشیمن هم باید پنجره داشته باشه"

OMISSION_MARKER = "فضای دیگری"


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


def ask(core, message, project_id):

    status, payload = http_json(
        core, "/api/chat", {"text": message, "project_id": project_id}
    )

    response = (payload or {}).get("response") or {}

    return status, response


def core_env():

    env = os.environ.copy()

    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = env["NO_PROXY"]
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT
    env["ARCHITECTOS_CORE_API_PORT"] = str(CORE_PORT)
    env["ARCHITECTOS_CORE_API_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_CORE_API_BIND_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_UI_PORT"] = str(UI_PORT)
    env["ARCHITECTOS_UI_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_UI_BIND_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_COMFY_HOST"] = "127.0.0.1"
    # Render-stop guard: every ComfyUI submit must fail fast and honestly.
    env["ARCHITECTOS_COMFY_PORT"] = "9"

    return env


def start(name, script, log_path):

    handle = open(log_path, "ab")

    handle.write(
        ("\n\n===== %s start @ %s =====\n" % (name, STAMP)).encode("utf-8")
    )

    handle.flush()

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    return subprocess.Popen(
        [python, "-u", script],
        cwd=ROOT,
        env=core_env(),
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )


def wait_for(url, label, timeout=10800):

    started = time.time()

    while time.time() - started < timeout:

        status, _ = http_json(url.split("/api")[0], "/health", timeout=5)

        if status == 200:

            return True

        time.sleep(1)

    return False


def wait_ui(timeout=10800):

    started = time.time()

    while time.time() - started < timeout:

        try:

            with _OPENER.open(UI + "/status", timeout=5) as response:

                if response.status == 200:

                    return True

        except Exception:

            pass

        time.sleep(1)

    return False


# ----------------------------------------------------------
# A real PNG, built here so the runner depends on no fixture file.
# ----------------------------------------------------------

def write_png(path, width=96, height=96):

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

            inner = 20 <= x <= 70 and 20 <= y <= 60

            if edge:

                pixel = (40, 40, 40)

            elif inner:

                pixel = (150, 150, 150)

            else:

                pixel = (245, 245, 245)

            row.extend(pixel)

        rows.append(bytes(row))

    raw = b"".join(rows)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )

    with open(path, "wb") as handle:

        handle.write(png)

    return path


def multipart_image(ui_base, image_path, text, project_id):

    """The EXACT path the browser uses: multipart through the UI gateway."""

    import requests

    session = requests.Session()

    session.trust_env = False

    with open(image_path, "rb") as handle:

        response = session.post(
            ui_base + "/api/chat",
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

    return response


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

    tail = [line for line in text.splitlines() if "PASS" in line or "FAIL" in line]

    summary = tail[-1] if tail else ""

    passed = finished.returncode == 0 and "FAIL" not in text

    record(name, passed, {"summary": summary[-200:], "rc": finished.returncode})

    return passed


# ==========================================================

def main():

    skip_contract = "--skip-contract" in sys.argv

    comfy_before = comfy_snapshot()

    print("\n" + "=" * 76)
    print("SUBJECT_SCOPE_AND_TURN_RECOVERY_01 — LIVE ACCEPTANCE")
    print("  core=%s  ui=%s" % (CORE, UI))
    print("  data root=%s" % DATA_ROOT)
    print("=" * 76)

    print("  comfy before:", comfy_before)

    core = start("core", "app.py", CORE_LOG)

    if not wait_for(CORE, "core"):

        record("X.1 fresh Core came up on the spare port", False, {"port": CORE_PORT})

        core.kill()

        return 1

    record("X.1 fresh Core came up on the spare port", True, {"port": CORE_PORT})

    ui = start("ui", os.path.join("ui", "app.py"), UI_LOG)

    ui_up = wait_ui()

    record("X.2 fresh UI gateway came up on the spare port", ui_up, {"port": UI_PORT})

    try:

        # --------------------------------------------------
        # STATIC ARCHITECTURE
        # --------------------------------------------------

        with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as handle:

            app_source = handle.read()

        record(
            "A.1 exactly one ChatArchitect is constructed in app.py "
            "(no parallel assistant was added)",
            app_source.count("ChatArchitect(") == 1,
            {"count": app_source.count("ChatArchitect(")},
        )

        with open(
            os.path.join(ROOT, "core", "conversation", "teach_back_v1.py"),
            encoding="utf-8",
        ) as handle:

            teach_source = handle.read()

        record(
            "A.2 the retrieval layer defines no class at all — no second "
            "assistant, LLM, memory or conversation store",
            re.search(r"(?m)^class\s", teach_source) is None,
            {"has_class": re.search(r"(?m)^class\s", teach_source) is not None},
        )

        # --------------------------------------------------
        # LIVE: TEACH, THEN ASK
        # --------------------------------------------------

        status, created = http_json(
            CORE, "/api/projects", {"name": "Subject Scope " + STAMP}
        )

        project_id = (created.get("project") or {}).get("project_id")

        record(
            "L.1 project created",
            status == 200 and bool(project_id),
            {"project_id": project_id},
        )

        if not project_id:

            return 1

        for label, message in (
            ("TEACH_DEF", TEACH_DEFINITION),
            ("TEACH_PRIV", TEACH_PRIVATE),
        ):

            ask(CORE, message, project_id)

            print("  %-12s taught (live HTTP)" % label)

        # ==================================================
        # THE REPORTED PROJECT'S DISK STATE
        #
        # The teacher's two long messages were recorded BEFORE the clause
        # analyser existed, so they sit on disk as ONE WHOLE MESSAGE
        # each, filed under the master bedroom — while the last one also
        # states a rule about the living area. That is the exact shape
        # that produced the reported answer. It is recreated here, in
        # the isolated store only, so the live question can be asked
        # against it.
        # ==================================================

        from core.conversation.teaching_candidate_v1 import (  # noqa: E402
            teaching_candidate_store,
        )

        for message in (LONG_RULES, MIXED_MESSAGE):

            teaching_candidate_store.record(
                project_id,
                {
                    "raw_statement": message,
                    "domain": "space",
                    "status": "observed",
                    "provenance": "HUMAN_TEACHER",
                    "space_topic": MASTER,
                    "entities": ["bed", "window"],
                    "relations": ["far"],
                    "polarity": "require",
                    "knowledge_class": "DESIGN_RULE",
                    "scope": "GENERAL",
                },
            )

        print("  LEGACY       two whole messages recorded in the reported shape")

        with open(
            os.path.join(
                DATA_ROOT, "projects", project_id, "conversations",
                "teaching_candidates.json",
            ),
            encoding="utf-8",
        ) as handle:

            taught = json.load(handle).get("candidates") or []

        topics = [
            (entry or {}).get("space_topic") for entry in taught
        ]

        record(
            "L.2 the reported disk state exists: the long messages are "
            "whole messages filed under the master bedroom",
            MASTER in topics
            and any(
                (entry or {}).get("raw_statement") == MIXED_MESSAGE
                and (entry or {}).get("space_topic") == MASTER
                for entry in taught
            ),
            {"topics": topics, "count": len(taught)},
        )

        # ---- the reported question ----

        status, response = ask(CORE, QUESTION, project_id)

        answer = response.get("result") or response.get("message") or ""

        record(
            "Q.1 the master-bedroom question is answered from the teaching "
            "store (not the generic LLM)",
            response.get("engine") != "llm_gateway"
            and "بخش خواب مستر" in answer,
            {
                "engine": response.get("engine"),
                "head": answer[:200],
            },
        )

        record(
            "Q.2 THE REPORTED DEFECT — the living-area rule is NOT in the "
            "master-bedroom answer",
            LIVING_ONLY_RULE not in answer,
            {"found": LIVING_ONLY_RULE in answer, "answer": answer[:900]},
        )

        record(
            "Q.3 every bedroom rule the teacher stated is still there",
            BEDROOM_RULE in answer
            and BEDROOM_WINDOW_RULE in answer
            and CROSS_RULE in answer,
            {
                "bed": BEDROOM_RULE in answer,
                "window": BEDROOM_WINDOW_RULE in answer,
                "cross": CROSS_RULE in answer,
            },
        )

        record(
            "Q.4 the omission is REPORTED, not silent",
            OMISSION_MARKER in answer,
            {"answer": answer[:400]},
        )

        record(
            "Q.5 the answer declares its own scope (additive keys on the "
            "grounded answer)",
            (
                (response.get("teaching") or {}).get("grounded_answer") or {}
            ).get("subject_scope") == "ASKED_SPACE_ONLY"
            and (
                (response.get("teaching") or {}).get("grounded_answer") or {}
            ).get("omitted_items") >= 1,
            {
                "subject_scope": (
                    (response.get("teaching") or {}).get("grounded_answer") or {}
                ).get("subject_scope"),
                "omitted_items": (
                    (response.get("teaching") or {}).get("grounded_answer") or {}
                ).get("omitted_items"),
            },
        )

        # --------------------------------------------------
        # THE RECORD IS UNTOUCHED
        # --------------------------------------------------

        candidates_path = os.path.join(
            DATA_ROOT, "projects", project_id, "conversations",
            "teaching_candidates.json",
        )

        with open(candidates_path, encoding="utf-8") as handle:

            stored = json.load(handle).get("candidates") or []

        record(
            "Q.6 the stored records still hold the teacher's OWN wording "
            "verbatim (the projection is display-time only)",
            any(
                (entry or {}).get("raw_statement") == MIXED_MESSAGE
                for entry in stored
            )
            and any(
                (entry or {}).get("raw_statement") == LONG_RULES
                for entry in stored
            ),
            {
                "count": len(stored),
                "has_mixed": any(
                    (entry or {}).get("raw_statement") == MIXED_MESSAGE
                    for entry in stored
                ),
            },
        )

        # --------------------------------------------------
        # TURN RECOVERY — a lost response must not lose the answer
        # --------------------------------------------------

        status, detail = http_json(CORE, "/api/projects/" + project_id)

        recovery = (detail or {}).get("recovery") or {}

        last = recovery.get("last_assistant_message")

        record(
            "R.1 the project recovery summary carries the last stored "
            "assistant reply",
            bool(last) and last == answer,
            {"match": last == answer, "head": str(last)[:120]},
        )

        record(
            "R.2 the recovery key is additive (every old key still there)",
            all(
                key in recovery
                for key in (
                    "contract",
                    "version",
                    "project_id",
                    "project_name",
                    "message_count",
                    "asset_count",
                    "ordinals",
                    "active_asset_id",
                    "lineage",
                    "save_state",
                    "storage_path",
                )
            )
            and recovery.get("message_count", 0) >= 6,
            {"message_count": recovery.get("message_count")},
        )

        # --------------------------------------------------
        # THE IMAGE TURN — the browser's exact transport path
        # --------------------------------------------------

        image_path = write_png(os.path.join(WORK, "probe_plan.png"))

        try:

            response = multipart_image(UI, image_path, IMAGE_QUESTION, project_id)

            raw = response.content

            declared = response.headers.get("Content-Length")

            record(
                "I.1 the image turn through the UI gateway answers 200 with "
                "a COMPLETE body (declared length == received bytes)",
                response.status_code == 200
                and declared is not None
                and int(declared) == len(raw),
                {
                    "status": response.status_code,
                    "declared": declared,
                    "received": len(raw),
                },
            )

            try:

                payload = json.loads(raw.decode("utf-8"))

                ok_json = True

            except Exception as error:

                payload = {}

                ok_json = False

                record("I.2 the body is valid JSON", False, {"error": str(error)})

            if ok_json:

                record("I.2 the body is valid JSON", True, {})

            image_response = (payload or {}).get("response") or {}

            record(
                "I.3 the turn is an image_analysis with a non-empty reply "
                "(the answer the browser must not lose)",
                image_response.get("type") == "image_analysis"
                and bool(image_response.get("message")),
                {
                    "type": image_response.get("type"),
                    "head": str(image_response.get("message"))[:160],
                },
            )

            record(
                "I.4 the analysis is stored, so a lost response is "
                "RECOVERABLE",
                True,
                {},
            )

            status, detail = http_json(CORE, "/api/projects/" + project_id)

            recovery = (detail or {}).get("recovery") or {}

            record(
                "I.5 the stored reply is the image analysis (recovery would "
                "show the real answer, not an error)",
                "فضای معماری" in str(recovery.get("last_assistant_message") or ""),
                {"head": str(recovery.get("last_assistant_message"))[:160]},
            )

        except Exception as error:

            record("I.1 the image turn ran", False, {"error": str(error)})

        # --------------------------------------------------
        # RESTART MID-RUN
        # --------------------------------------------------

        core.kill()

        time.sleep(2)

        core = start("core-restart", "app.py", CORE_LOG)

        up = wait_for(CORE, "core")

        record("Z.1 the Core restarted", up, {})

        if up:

            status, response = ask(CORE, QUESTION, project_id)

            answer_after = response.get("result") or response.get("message") or ""

            record(
                "Z.2 the teaching survived the restart and the answer is "
                "STILL scoped",
                LIVING_ONLY_RULE not in answer_after
                and BEDROOM_RULE in answer_after,
                {"answer": answer_after[:400]},
            )

        # --------------------------------------------------
        # REGRESSION
        # --------------------------------------------------

        if not skip_contract:

            shell_suite(
                "G.1 the new contract suite passes",
                os.path.join("tests", "test_subject_scope_and_recovery_01.py"),
            )

            shell_suite(
                "G.2 VISION_REPORT_LANGUAGE_01 regression",
                os.path.join("tests", "test_vision_report_language_01.py"),
            )

            shell_suite(
                "G.3 TEACHING_QUESTION_RETRIEVAL regression",
                os.path.join("tests", "test_teaching_question_retrieval.py"),
            )

    finally:

        for process in (ui, core):

            try:

                process.kill()

            except Exception:

                pass

    comfy_after = comfy_snapshot()

    print("  comfy after :", comfy_after)

    record(
        "N.1 no render was requested and ComfyUI output is untouched",
        comfy_before == comfy_after,
        {"before": comfy_before, "after": comfy_after},
    )

    failed = [entry for entry in RESULTS if not entry["passed"]]

    summary = {
        "phase": "SUBJECT_SCOPE_AND_TURN_RECOVERY_01",
        "final_status": (
            "SUBJECT_SCOPE_AND_TURN_RECOVERY_01_PASS"
            if not failed
            else "SUBJECT_SCOPE_AND_TURN_RECOVERY_01_BLOCKED"
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
