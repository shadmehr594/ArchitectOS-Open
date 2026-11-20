# ==========================================================
# ARCHITECTURAL_KNOWLEDGE_STRUCTURER_V1 — LIVE ACCEPTANCE
#
# Proves, on a THROW-AWAY Core (spare port, isolated data root,
# render-stop guard), that:
#
#   * the teacher's recorded statements become an architectural
#     structure for the space, in the shape the brief pins
#   * the structure is attached to the grounded answer (read-only
#     integration point, after retrieval and before the answer)
#   * nothing is learned, promoted, stored, rendered or modified
#   * the earlier phases still pass
#
# Usage:
#   .venv/Scripts/python.exe tools/run_architectural_knowledge_structurer_01_acceptance.py
#
# Add --skip-contract to skip the suites (fast path).
# ==========================================================

import io
import json
import os
import re
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

PORT = 5093

CORE = "http://127.0.0.1:%d" % PORT

WORK = os.path.join(ROOT, ".pytest_tmp", "knowledge_structurer_01_" + STAMP)

DATA_ROOT = os.path.join(WORK, "project_data")

os.makedirs(DATA_ROOT, exist_ok=True)

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

LOG_PATH = os.path.join(WORK, "core.log")

REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_architectural_knowledge_structurer_01_report.json"
)

MASTER = "MASTER_BEDROOM_SLEEPING"

# ---- the teacher's own session, verbatim ----

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

CLOSET_MESSAGE = (
    "برای اون اتاق کلوزت و حموم با یه سرویس فرنگی در نظر گرفت"
)

SMALL_AREA_MESSAGE = (
    "اگه زیربنای خونه کم بود همون تخت دونفره با یه کمد دیواری کمد "
    "کافیه دیگه بستگی به جا داره شاید کلوزت هم بشه بزاری"
)

QUESTION = "راجب اتاق خواب مستر چی می‌دونی؟"

LIVING_ONLY_RULE = "نشیمن هم باید پنجره داشته باشه"


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


def core_env():

    env = os.environ.copy()

    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = env["NO_PROXY"]
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT
    env["ARCHITECTOS_CORE_API_PORT"] = str(PORT)
    env["ARCHITECTOS_CORE_API_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_CORE_API_BIND_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_COMFY_HOST"] = "127.0.0.1"
    # Render-stop guard: every ComfyUI submit must fail fast and honestly.
    env["ARCHITECTOS_COMFY_PORT"] = "9"

    return env


def start_core(label):

    handle = open(LOG_PATH, "ab")

    handle.write(
        ("\n\n===== %s start @ %s =====\n" % (label, STAMP)).encode("utf-8")
    )

    handle.flush()

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    return subprocess.Popen(
        [python, "-u", "app.py"],
        cwd=ROOT,
        env=core_env(),
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )


def wait_for_core(timeout=10800):

    started = time.time()

    while time.time() - started < timeout:

        status, _ = http_json(CORE, "/health", timeout=5)

        if status == 200:

            return True

        time.sleep(1)

    return False


def ask(message, project_id):

    status, payload = http_json(
        CORE, "/api/chat", {"text": message, "project_id": project_id}
    )

    response = (payload or {}).get("response") or {}

    grounded = (response.get("teaching") or {}).get("grounded_answer") or {}

    return status, response, grounded


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

    lines = [line for line in text.splitlines() if "PASS" in line or "FAIL" in line]

    record(
        name,
        finished.returncode == 0 and "FAIL" not in text,
        {"summary": (lines[-1] if lines else "")[-200:], "rc": finished.returncode},
    )


# ==========================================================

def main():

    skip_contract = "--skip-contract" in sys.argv

    comfy_before = comfy_snapshot()

    print("\n" + "=" * 76)
    print("ARCHITECTURAL_KNOWLEDGE_STRUCTURER_V1 — LIVE ACCEPTANCE")
    print("  core=%s" % CORE)
    print("  data root=%s" % DATA_ROOT)
    print("=" * 76)

    print("  comfy before:", comfy_before)

    core = start_core("core")

    if not wait_for_core():

        record("X.1 fresh Core came up on the spare port", False, {"port": PORT})

        core.kill()

        return 1

    record("X.1 fresh Core came up on the spare port", True, {"port": PORT})

    try:

        # --------------------------------------------------
        # STATIC ARCHITECTURE
        # --------------------------------------------------

        with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as handle:

            app_source = handle.read()

        record(
            "A.1 exactly one ChatArchitect is constructed in app.py",
            app_source.count("ChatArchitect(") == 1,
            {"count": app_source.count("ChatArchitect(")},
        )

        module_path = os.path.join(
            ROOT, "core", "knowledge", "architectural_knowledge_structurer_v1.py"
        )

        with open(module_path, encoding="utf-8") as handle:

            module_source = handle.read()

        forbidden = [
            token for token in (
                "\nclass ",
                ".record(",
                ".promote(",
                "requests.",
                "llm_gateway",
                "import comfy",
                "app.run",
            )
            if token in module_source
        ]

        record(
            "A.2 the structurer defines no class and contains no write, "
            "promotion, network or render call",
            not forbidden,
            {"forbidden": forbidden},
        )

        # --------------------------------------------------
        # LIVE: THE TEACHER'S SESSION
        # --------------------------------------------------

        status, created = http_json(
            CORE, "/api/projects", {"name": "Knowledge Structurer " + STAMP}
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

            ask(message, project_id)

            print("  %-12s taught (live HTTP)" % label)

        # The two long messages sit on disk as WHOLE MESSAGES (recorded
        # before the clause analyser) — the reported project's shape.
        from core.conversation.teaching_candidate_v1 import (  # noqa: E402
            teaching_candidate_store,
        )

        for message in (LONG_RULES, MIXED_MESSAGE, CLOSET_MESSAGE, SMALL_AREA_MESSAGE):

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
                    "candidate_id": "tc_acc_%d" % len(message),
                    "confidence": 0.9,
                },
            )

        print("  LEGACY       the teacher's long messages recorded as whole messages")

        candidates_path = os.path.join(
            DATA_ROOT, "projects", project_id, "conversations",
            "teaching_candidates.json",
        )

        with open(candidates_path, encoding="utf-8") as handle:

            before_store = json.dumps(
                json.load(handle), ensure_ascii=False, sort_keys=True
            )

        # --------------------------------------------------
        # THE QUESTION
        # --------------------------------------------------

        status, response, grounded = ask(QUESTION, project_id)

        structure = grounded.get("architectural_knowledge") or {}

        answer = grounded.get("result") or response.get("message") or ""

        print("  engine=%s" % response.get("engine"))

        record(
            "S.1 the answer is still grounded in the teaching store (not "
            "the generic LLM)",
            response.get("engine") != "llm_gateway"
            and "بخش خواب مستر" in answer,
            {"engine": response.get("engine"), "head": answer[:200]},
        )

        record(
            "S.2 the structure is attached at the read-only integration "
            "point and declares its contract",
            structure.get("contract") == "ArchitecturalKnowledgeStructureV1"
            and structure.get("space_id") == MASTER,
            {
                "contract": structure.get("contract"),
                "space_id": structure.get("space_id"),
            },
        )

        contract_keys = (
            "space_id", "space_category", "definition", "users",
            "primary_goals", "privacy_level", "required_elements",
            "optional_elements", "spatial_relations", "design_rules",
            "size_dependency", "uncertainties", "provenance",
        )

        missing = [key for key in contract_keys if key not in structure]

        record(
            "S.3 every contract key the brief pins is present",
            not missing,
            {"missing": missing},
        )

        record(
            "S.4 users / category / privacy come from the teacher and the "
            "frozen corpus",
            "parents" in (structure.get("users") or [])
            and structure.get("space_category") == "private"
            and structure.get("privacy_level") == "private"
            and structure.get("provenance") == "HUMAN_TEACHER",
            {
                "users": structure.get("users"),
                "category": structure.get("space_category"),
            },
        )

        rules = [rule.get("rule") for rule in structure.get("design_rules") or []]

        record(
            "S.5 the teacher's rules are structured (privacy + placement + "
            "public-zone separation)",
            "avoid_direct_view_to_bed_from_entry" in rules
            and "bed_away_from_window" in rules
            and "keep_away_from_public_zones" in rules,
            {"rules": rules},
        )

        record(
            "S.6 the elements and the area dependency are structured",
            "window" in (structure.get("required_elements") or [])
            and bool(structure.get("optional_elements"))
            and any(
                entry.get("condition") == "small_area"
                for entry in structure.get("size_dependency") or []
            ),
            {
                "required": structure.get("required_elements"),
                "optional": structure.get("optional_elements"),
                "size_dependency": structure.get("size_dependency"),
            },
        )

        record(
            "S.7 the living-area rule does NOT enter the master-bedroom "
            "structure (subject scope holds)",
            LIVING_ONLY_RULE not in answer
            and LIVING_ONLY_RULE not in json.dumps(structure, ensure_ascii=False),
            {"answer": answer[:300]},
        )

        record(
            "S.8 the answer uses the brief's answer style and reports what "
            "is NOT yet a definitive rule",
            "بر اساس آموزش‌های دریافت‌شده" in answer
            and "مواردی که هنوز" in answer
            and "None" not in answer,
            {"answer": answer[-500:]},
        )

        teacher_items = [
            item for item in structure.get("items") or []
            if item.get("provenance") == "HUMAN_TEACHER"
        ]

        corpus_items = [
            item for item in structure.get("items") or []
            if item.get("provenance") == "CORPUS"
        ]

        record(
            "S.9 every structured item carries its provenance, and every "
            "TEACHER item keeps its source candidate and status",
            bool(teacher_items)
            and all(
                item.get("candidate_id") and item.get("status")
                for item in teacher_items
            )
            and all(
                item.get("value")
                for item in (structure.get("items") or [])
            ),
            {
                "teacher_items": len(teacher_items),
                "corpus_items": len(corpus_items),
                "total": len(structure.get("items") or []),
            },
        )

        record(
            "S.10 the layer is read-only: no learning, no promotion, no "
            "curriculum / memory / corpus change, no LLM, no render",
            structure.get("learned_anything") is False
            and structure.get("permanent_learning_implemented") is False
            and structure.get("promoted") is False
            and structure.get("curriculum_modified") is False
            and structure.get("architecture_rules_modified") is False
            and structure.get("teaching_memory_modified") is False
            and structure.get("llm_used") is False
            and structure.get("network_used") is False
            and structure.get("render_requested") is False
            and structure.get("comfy_invoked") is False,
            {"learned": structure.get("learned_anything")},
        )

        with open(candidates_path, encoding="utf-8") as handle:

            after_store = json.dumps(
                json.load(handle), ensure_ascii=False, sort_keys=True
            )

        record(
            "S.11 the teaching store is byte-identical before and after "
            "(the structure is never written back)",
            before_store == after_store,
            {
                "before_bytes": len(before_store),
                "after_bytes": len(after_store),
            },
        )

        # --------------------------------------------------
        # RESTART MID-RUN
        # --------------------------------------------------

        core.kill()

        time.sleep(2)

        core = start_core("core-restart")

        up = wait_for_core()

        record("Z.1 the Core restarted", up, {})

        if up:

            _status, _response, grounded_after = ask(QUESTION, project_id)

            structure_after = grounded_after.get("architectural_knowledge") or {}

            record(
                "Z.2 the structure is reproducible after a restart (same "
                "rules, same users, still scoped)",
                structure_after.get("space_id") == MASTER
                and "parents" in (structure_after.get("users") or [])
                and [
                    rule.get("rule")
                    for rule in structure_after.get("design_rules") or []
                ] == rules,
                {"rules_after": structure_after.get("design_rules")},
            )

        # --------------------------------------------------
        # REGRESSION
        # --------------------------------------------------

        if not skip_contract:

            shell_suite(
                "G.1 the structurer contract suite passes",
                os.path.join("tests", "test_architectural_knowledge_structurer_v1.py"),
            )

            shell_suite(
                "G.2 SUBJECT_SCOPE_AND_TURN_RECOVERY_01 regression",
                os.path.join("tests", "test_subject_scope_and_recovery_01.py"),
            )

            shell_suite(
                "G.3 VISION_REPORT_LANGUAGE_01 regression",
                os.path.join("tests", "test_vision_report_language_01.py"),
            )

            shell_suite(
                "G.4 TEACHING_QUESTION_RETRIEVAL regression",
                os.path.join("tests", "test_teaching_question_retrieval.py"),
            )

    finally:

        try:

            core.kill()

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
        "phase": "ARCHITECTURAL_KNOWLEDGE_STRUCTURER_V1",
        "final_status": (
            "ARCHITECTURAL_KNOWLEDGE_STRUCTURER_V1_PASS"
            if not failed
            else "ARCHITECTURAL_KNOWLEDGE_STRUCTURER_V1_BLOCKED"
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
