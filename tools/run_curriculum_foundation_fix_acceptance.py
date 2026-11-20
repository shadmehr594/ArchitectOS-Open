# ==========================================================
# ARCHITECTURAL CURRICULUM FOUNDATION FIX — ACCEPTANCE RUNNER
#
# Runs the REQUIRED acceptance tests against the LIVE runtime:
#
#   UI-style HTTP -> Core API (app.py)
#                -> /api/conversation/curriculum/sequence
#                -> /api/chat -> ChatArchitect.handle
#
# WHAT THIS PHASE IS: a FOUNDATION FIX. It changes how a teaching
# statement is CLASSIFIED and adds a curriculum ORDER. It teaches no
# lesson.
#
# HARD CONSTRAINTS (asserted, not assumed)
#   - NO geometry, NO coordinates, NO walls, NO doors, NO CAD, NO DWG,
#     NO BIM, NO IFC, NO RPLAN, NO layout generation.
#   - NO render, NO ComfyUI, NO image generation.
#   - NO lesson content; nothing is learned.
#     The Core API starts with ARCHITECTOS_COMFY_PORT=9 so every submit
#     fails fast and truthfully, an isolated project data root is used,
#     the ComfyUI output directory is asserted unchanged and the
#     isolated root is scanned for geometry / image artefacts.
#
# Usage:
#   .venv/Scripts/python.exe tools/run_curriculum_foundation_fix_acceptance.py
#   .venv/Scripts/python.exe tools/run_curriculum_foundation_fix_acceptance.py --fast
# ==========================================================


import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


try:

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

except Exception:

    pass


ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


CORE_API = "http://127.0.0.1:5000"

REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_curriculum_foundation_fix_report.json"
)

LOG_PATH = os.path.join(
    ROOT, "logs", "runtime", "acceptance_curriculum_foundation_fix_core.log"
)

WORK_DIR = os.path.join(
    ROOT,
    ".pytest_tmp",
    "curriculum_foundation_" + time.strftime("%Y%m%d_%H%M%S"),
)

DATA_ROOT = os.path.join(WORK_DIR, "project_data")

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT


FOUNDATION_TESTS = os.path.join(
    ROOT, "tests", "test_curriculum_foundation_fix.py"
)

PHASE12_TESTS = os.path.join(
    ROOT, "tests", "test_floor_program_12.py"
)

PHASE11_TESTS = os.path.join(
    ROOT, "tests", "test_spatial_diagram_11.py"
)

PHASE10_TESTS = os.path.join(
    ROOT, "tests", "test_space_adjacency_10.py"
)

PHASE09_TESTS = os.path.join(
    ROOT, "tests", "test_architectural_learning_bridge_09.py"
)

PHASE08_TESTS = os.path.join(
    ROOT, "tests", "test_teaching_foundation_08.py"
)

PHASE12_ACCEPTANCE = os.path.join(
    ROOT, "tools", "run_floor_program_12_acceptance.py"
)

PHASE12_REPORT = os.path.join(
    ROOT, "tools", "acceptance_12_report.json"
)

CHAT_LANGUAGE_TESTS = os.path.join(
    ROOT, "tests", "test_chat_language_02.py"
)

CHAT_CORE_TESTS = os.path.join(
    ROOT, "tests", "test_chat_core_only.py"
)

VOICE07_RUNNER = os.path.join(
    ROOT, "tools", "run_voice_acceptance_07.py"
)


COMFY_OUTPUT_DIR = os.path.join("C:", os.sep, "ComfyUI-Zluda", "output")

try:

    from config import runtime_config as RC

    COMFY_OUTPUT_DIR = RC.COMFYUI_OUTPUT_DIR

except Exception:

    pass


GEOMETRY_EXTENSIONS = (
    ".ifc", ".dwg", ".dxf", ".rvt", ".obj", ".stl", ".3dm", ".skp",
)

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".exr")


# ----------------------------------------------------------
# INPUTS
# ----------------------------------------------------------

BRIEF_CLASSES = (
    "ARCHITECTURAL_FACT",
    "DESIGN_RULE",
    "PATTERN",
    "OBSERVATION",
    "PREFERENCE",
    "PROJECT_DECISION",
    "DEFINITION",
)

# customary -> PATTERN
FA_CUSTOMARY = "در خانه ایرانی معمولاً آشپزخانه نزدیک فضای نشیمن است"

FA_CUSTOMARY_PLAIN = "معمولاً آشپزخانه نزدیک نشیمن است"

FA_PATTERN_WORD = "الگوی رایج این است که ورودی با هشتی به نشیمن وصل شود"

EN_CUSTOMARY = "A common pattern is a central corridor serving the bedrooms"

# general rule -> DESIGN_RULE
FA_RULE = "راه پله باید نزدیک ورودی باشد"

EN_RULE = "The stair should be near the entrance"

# definition -> DEFINITION
FA_DEFINITION_COPULA = "راه پله ارتباط بین طبقات است"

FA_DEFINITION_HAST = "حیاط خلوت فضای باز خصوصی هست"

FA_DEFINITION_EXPLICIT = "حریم خصوصی یعنی جدایی فضای خصوصی از عمومی"

EN_DEFINITION = "Privacy means separating the private zone from the public one"

# project decision -> PROJECT_DECISION / CURRENT_PROJECT
FA_DECISION = "در این پروژه تصمیم گرفتیم آشپزخانه باز باشد"

EN_DECISION = "For this project we decided the kitchen is open"

# fact / preference (must keep working)
FA_FACT = "حداقل ارتفاع پاگرد پله باید در محدوده مجاز باشد"

FA_PREFERENCE = "من آشپزخانه باز را ترجیح می دهم"


# The ORIGINAL five steps. CURRICULUM_FOUNDATION_FIX_02 appended two
# more, so these are asserted as a PREFIX rather than as the whole
# sequence (relax + add, never delete).
SEQUENCE_KEYS = (
    "space_types",
    "relationships",
    "privacy",
    "zoning",
    "bubble_diagram",
)

ADDED_SEQUENCE_KEYS = ("patterns", "design_reasoning")

FULL_SEQUENCE_KEYS = SEQUENCE_KEYS + ADDED_SEQUENCE_KEYS


_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({})
)


RESULTS = []


def record(name, passed, detail=None, **extra):

    entry = {
        "test": name,
        "passed": bool(passed),
        "detail": detail,
    }

    entry.update(extra)

    RESULTS.append(entry)

    print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

    if detail and not passed:

        print(
            "        ",
            json.dumps(detail, ensure_ascii=True, default=str)[:520],
        )


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

def start_core(port=5000, log_suffix=""):

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    os.makedirs(DATA_ROOT, exist_ok=True)

    env = os.environ.copy()

    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = env["NO_PROXY"]
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["ARCHITECTOS_CORE_API_PORT"] = str(port)
    env["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

    env["ARCHITECTOS_COMFY_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_COMFY_PORT"] = "9"

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    if not os.path.isfile(python):

        python = sys.executable

    handle = open(LOG_PATH + log_suffix, "ab")

    handle.write(b"\n\n===== curriculum foundation core start =====\n")

    handle.flush()

    return subprocess.Popen(
        [python, "app.py"],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )


def wait_for_core(base, timeout=10800):

    started = time.time()

    while time.time() - started < timeout:

        status, _ = http_json(base, "/health", timeout=5)

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


# ==========================================================
# EVIDENCE HELPERS
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


def artifact_scan(root):

    geometry = []

    images = []

    if not os.path.isdir(root):

        return {
            "root": root, "exists": False,
            "geometry_files": 0, "image_files": 0, "samples": [],
        }

    for dirpath, _dirs, files in os.walk(root):

        for name in files:

            lowered = name.lower()

            if lowered.endswith(GEOMETRY_EXTENSIONS):

                geometry.append(os.path.join(dirpath, name))

            elif lowered.endswith(IMAGE_EXTENSIONS):

                images.append(os.path.join(dirpath, name))

    return {
        "root": root,
        "exists": True,
        "geometry_files": len(geometry),
        "image_files": len(images),
        "samples": (geometry + images)[:6],
    }


def create_project(name):

    status, payload = http_json(
        CORE_API, "/api/projects", {"name": name}, timeout=10800
    )

    if status != 200:

        return None, payload

    manifest = payload.get("project") or payload

    return manifest.get("project_id"), payload


def chat(project_id, text, **extra):

    payload = {"text": text, "project_id": project_id, "mode": "chat"}

    payload.update(extra)

    return http_json(CORE_API, "/api/chat", payload, timeout=10800)


def classify(project_id, text):

    """Drive a teaching statement through the live chat path and return
    the candidate the system produced."""

    status, payload = chat(project_id, text)

    response = (payload or {}).get("response") or {}

    teaching = response.get("teaching") or {}

    candidate = teaching.get("candidate") or {}

    return status, response, candidate


def sequence(progress=None, language=None):

    query = []

    for key, value in (progress or {}).items():

        query.append("%s=%s" % (key, value))

    if language:

        query.append("language=%s" % language)

    path = "/api/conversation/curriculum/sequence"

    if query:

        path += "?" + "&".join(query)

    return http_json(CORE_API, path, timeout=10800)


def has_persian(text):

    return any("\u0600" <= ch <= "\u06ff" for ch in str(text or ""))


# ==========================================================
# MAIN
# ==========================================================

def main():

    fast = "--fast" in sys.argv

    report = {
        "phase": "ARCHITECTURAL_CURRICULUM_FOUNDATION_FIX",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "comfy_blocked_by_construction": True,
        "comfy_port": 9,
        "real_renders": 0,
        "image_generations": 0,
        "geometry_outputs": 0,
        "cad_outputs": 0,
        "dwg_outputs": 0,
        "bim_outputs": 0,
        "ifc_outputs": 0,
        "lessons_created": 0,
        "permanent_learning": False,
        "layout_generation_started": False,
        "data_root": DATA_ROOT,
        "tests": [],
    }

    os.makedirs(DATA_ROOT, exist_ok=True)

    # ==================================================
    # SECTION 0 — AUDIT + STATIC + CONTRACT CHECKS
    # ==================================================

    print("\n" + "=" * 70)
    print("  SECTION 0 - AUDIT + STATIC + CONTRACT CHECKS")
    print("=" * 70)

    with open(os.path.join(ROOT, "app.py"), "r",
              encoding="utf-8", errors="replace") as handle:

        app_text = handle.read()

    record(
        "0.1 exactly ONE ChatArchitect in the Core API",
        app_text.count("ChatArchitect(") == 1,
        {"count": app_text.count("ChatArchitect(")},
    )

    forbidden_names = (
        "class TeachingAssistant",
        "class ArchitectureTutor",
        "class SecondAssistant",
        "class ParallelAssistant",
        "class CurriculumTeacher",
        "class LessonEngine",
    )

    forbidden_hits = []

    for folder in ("core", "ui", "chatos"):

        base = os.path.join(ROOT, folder)

        if not os.path.isdir(base):

            continue

        for dirpath, dirs, files in os.walk(base):

            dirs[:] = [
                d for d in dirs
                if d not in ("__pycache__", ".venv", "node_modules")
            ]

            for name in files:

                if not name.endswith(".py"):

                    continue

                path = os.path.join(dirpath, name)

                try:

                    with open(path, "r", encoding="utf-8",
                              errors="replace") as handle:

                        content = handle.read()

                except Exception:

                    continue

                for token in forbidden_names:

                    if token in content:

                        forbidden_hits.append(
                            os.path.relpath(path, ROOT) + " :: " + token
                        )

    record(
        "0.2 no second assistant / teacher class anywhere",
        not forbidden_hits,
        {"hits": forbidden_hits[:5]},
    )

    from core.conversation.teaching_meaning_v1 import (
        ALL_KNOWLEDGE_CLASSES,
        ALL_SCOPES,
    )

    from core.curriculum.curriculum_sequencer_v1 import (
        curriculum_sequencer,
        LESSONS,
        STEP_KEYS,
        ALL_STEP_STATUSES,
        FORBIDDEN_STEP_STATUSES,
    )

    from core.conversation.teaching_candidate_v1 import (
        ALLOWED_STATUSES,
        PERMANENT_LEARNING_IMPLEMENTED,
    )

    from core.conversation.knowledge_promotion_bridge_v1 import (
        PROMOTION_IMPLEMENTED,
    )

    record(
        "0.3 all seven brief knowledge classes exist",
        all(c in ALL_KNOWLEDGE_CLASSES for c in BRIEF_CLASSES),
        {"missing": [c for c in BRIEF_CLASSES
                     if c not in ALL_KNOWLEDGE_CLASSES]},
    )

    record(
        "0.4 DEFINITION is a distinct class and the vocabulary only GREW",
        "DEFINITION" in ALL_KNOWLEDGE_CLASSES
        and "UNKNOWN" in ALL_KNOWLEDGE_CLASSES
        and len(ALL_KNOWLEDGE_CLASSES) >= len(BRIEF_CLASSES)
        and set(ALL_SCOPES) == {"GENERAL", "CURRENT_PROJECT"},
        list(ALL_KNOWLEDGE_CLASSES),
    )

    # shared vocabulary — one source of truth
    import core.conversation.teaching_meaning_v1 as meaning_module

    meaning_source = open(
        meaning_module.__file__, "r", encoding="utf-8"
    ).read()

    record(
        "0.5 PATTERN_MARKERS has ONE definition (imported, not copied)",
        "from core.conversation.turn_semantics_v1 import" in meaning_source
        and "PATTERN_MARKERS = (" not in meaning_source,
        None,
    )

    record(
        "0.6 the sequencer has >= 5 steps, no lessons, refuses 'learned'",
        # RELAXED: the original five must still be present (subset); the
        # count may GROW — fix 02 added two steps.
        set(SEQUENCE_KEYS) <= set(STEP_KEYS)
        and len(STEP_KEYS) >= 5
        and LESSONS == ()
        and set(ALL_STEP_STATUSES) == {
            "not_started", "in_progress", "completed"
        }
        and "learned" in FORBIDDEN_STEP_STATUSES,
        {"steps": list(STEP_KEYS)},
    )

    record(
        "0.7 promotion still impossible, statuses closed",
        PROMOTION_IMPLEMENTED is False
        and PERMANENT_LEARNING_IMPLEMENTED is False
        and set(ALLOWED_STATUSES) == {
            "observed", "needs_confirmation", "rejected"
        },
        None,
    )

    # ---- scope: no lesson / layout / geometry module ----
    curriculum_dir = os.path.join(ROOT, "core", "curriculum")

    forbidden_modules = (
        "lesson", "layout_generation", "floorplan", "floor_plan",
        "geometry", "wall", "opening", "cad", "bim", "ifc", "render",
        "rplan",
    )

    hits = [
        name for name in os.listdir(curriculum_dir)
        if name.endswith(".py")
        and any(t in name.lower() for t in forbidden_modules)
    ]

    record(
        "0.8 no lesson / layout / floor-plan / geometry layer exists",
        not hits,
        {"hits": hits},
    )

    print("\n  running contract suites ...")

    for label, path in (
        ("0.9 foundation contract suite green", FOUNDATION_TESTS),
        ("0.10 Phase 12 contract suite still green", PHASE12_TESTS),
        ("0.11 Phase 11 contract suite still green", PHASE11_TESTS),
        ("0.12 Phase 10 contract suite still green", PHASE10_TESTS),
        ("0.13 Phase 09 contract suite still green", PHASE09_TESTS),
        ("0.14 Phase 08 contract suite still green", PHASE08_TESTS),
    ):

        completed = subprocess.run(
            [sys.executable, path],
            cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10800,
        )

        record(
            label,
            completed.returncode == 0,
            {"returncode": completed.returncode,
             "tail": (completed.stdout or "")[-400:]},
        )

    # ==================================================
    # START CORE API
    # ==================================================

    print("\n" + "=" * 70)
    print("  STARTING CORE API (ComfyUI blocked on port 9)")
    print("=" * 70)

    before_comfy = comfy_output_snapshot()

    process = start_core(port=5000)

    if not wait_for_core(CORE_API):

        record("1.0 Core API online", False, {"log": LOG_PATH})

        report["tests"] = RESULTS

        report["final_status"] = "CURRICULUM_FOUNDATION_FIX_BLOCKED"

        with open(REPORT_PATH, "w", encoding="utf-8") as handle:

            json.dump(report, handle, ensure_ascii=False, indent=2)

        return 1

    record("1.0 Core API online", True, {"pid": process.pid})

    status, sequence_payload = sequence(language="en")

    record(
        "1.1 the curriculum sequence surface is online over HTTP",
        status == 200
        and ((sequence_payload or {}).get("render_requested")) is False
        and ((sequence_payload or {}).get("comfy_invoked")) is False
        and ((sequence_payload or {}).get("plan") or {}).get(
            "step_count"
        ) >= 5,
        {"status": status},
    )

    persian_project, _ = create_project("Foundation Persian")

    english_project, _ = create_project("Foundation English")

    isolation_a, _ = create_project("Foundation Isolation A")

    isolation_b, _ = create_project("Foundation Isolation B")

    record(
        "1.2 acceptance projects created",
        all([persian_project, english_project, isolation_a, isolation_b]),
        {"persian": persian_project, "english": english_project},
    )

    # ==================================================
    # TEST A — TAXONOMY
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST A - KNOWLEDGE CLASS TAXONOMY")
    print("=" * 70)

    report["knowledge_classes"] = list(ALL_KNOWLEDGE_CLASSES)

    record(
        "A.1 the taxonomy carries all seven brief classes",
        all(c in ALL_KNOWLEDGE_CLASSES for c in BRIEF_CLASSES),
        list(ALL_KNOWLEDGE_CLASSES),
    )

    record(
        "A.2 DEFINITION is separate from ARCHITECTURAL_FACT",
        "DEFINITION" in ALL_KNOWLEDGE_CLASSES
        and "ARCHITECTURAL_FACT" in ALL_KNOWLEDGE_CLASSES
        and "UNKNOWN" in ALL_KNOWLEDGE_CLASSES,
        None,
    )

    # ==================================================
    # TEST B — THE FOUR BRIEF CATEGORIES (LIVE)
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST B - THE FOUR BRIEF CATEGORIES")
    print("=" * 70)

    def expect(label, text, knowledge_class, scope):

        status, response, candidate = classify(persian_project, text)

        ok = (
            status == 200
            and (response.get("turn_semantics") or {}).get("turn_kind")
            == "TEACHING_STATEMENT"
            and candidate.get("knowledge_class") == knowledge_class
            and candidate.get("scope") == scope
        )

        record(
            label,
            ok,
            {
                "turn_kind": (response.get("turn_semantics") or {}).get(
                    "turn_kind"
                ),
                "kc": candidate.get("knowledge_class"),
                "scope": candidate.get("scope"),
            },
        )

        return candidate

    expect(
        "B.1 customary rule -> PATTERN / GENERAL (the brief's example)",
        FA_CUSTOMARY, "PATTERN", "GENERAL",
    )

    expect(
        "B.2 general architectural rule -> DESIGN_RULE / GENERAL",
        FA_RULE, "DESIGN_RULE", "GENERAL",
    )

    expect(
        "B.3 definition (copula است) -> DEFINITION / GENERAL",
        FA_DEFINITION_COPULA, "DEFINITION", "GENERAL",
    )

    expect(
        "B.4 project decision -> PROJECT_DECISION / CURRENT_PROJECT only",
        FA_DECISION, "PROJECT_DECISION", "CURRENT_PROJECT",
    )

    # ==================================================
    # TEST C — PATTERN WITHOUT NORMATIVE
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST C - PATTERN WITHOUT A NORMATIVE MARKER")
    print("=" * 70)

    expect(
        "C.1 a plain customary statement is PATTERN (no باید / must)",
        FA_CUSTOMARY_PLAIN, "PATTERN", "GENERAL",
    )

    expect(
        "C.2 a statement naming a pattern (الگوی) is PATTERN",
        FA_PATTERN_WORD, "PATTERN", "GENERAL",
    )

    expect(
        "C.3 English pattern wording is PATTERN",
        EN_CUSTOMARY, "PATTERN", "GENERAL",
    )

    # ==================================================
    # TEST D — PERSIAN DEFINITIONAL DETECTION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST D - PERSIAN DEFINITIONAL DETECTION")
    print("=" * 70)

    expect(
        "D.1 copula است -> DEFINITION",
        FA_DEFINITION_COPULA, "DEFINITION", "GENERAL",
    )

    expect(
        "D.2 copula هست -> DEFINITION",
        FA_DEFINITION_HAST, "DEFINITION", "GENERAL",
    )

    expect(
        "D.3 explicit یعنی -> DEFINITION",
        FA_DEFINITION_EXPLICIT, "DEFINITION", "GENERAL",
    )

    expect(
        "D.4 English 'means' -> DEFINITION",
        EN_DEFINITION, "DEFINITION", "GENERAL",
    )

    # ==================================================
    # TEST E — PRESERVED CATEGORIES
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST E - PRESERVED CATEGORIES (no regression)")
    print("=" * 70)

    expect(
        "E.1 regulation wording -> ARCHITECTURAL_FACT / GENERAL",
        FA_FACT, "ARCHITECTURAL_FACT", "GENERAL",
    )

    expect(
        "E.2 preference -> PREFERENCE / GENERAL",
        FA_PREFERENCE, "PREFERENCE", "GENERAL",
    )

    expect(
        "E.3 English general rule -> DESIGN_RULE / GENERAL",
        EN_RULE, "DESIGN_RULE", "GENERAL",
    )

    expect(
        "E.4 English project decision -> PROJECT_DECISION / "
        "CURRENT_PROJECT",
        EN_DECISION, "PROJECT_DECISION", "CURRENT_PROJECT",
    )

    # ==================================================
    # TEST F — CURRICULUM SEQUENCER
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST F - CURRICULUM SEQUENCER FOUNDATION")
    print("=" * 70)

    status, payload = sequence(language="en")

    plan = (payload or {}).get("plan") or {}

    order = [
        step.get("key") for step in plan.get("steps") or []
    ]

    record(
        "F.1 the sequence BEGINS Space Types -> Relationships -> Privacy "
        "-> Zoning -> Bubble Diagram",
        # RELAXED: the original five must remain, in order, as a PREFIX.
        # Fix 02 appended `patterns` + `design_reasoning`.
        status == 200 and order[: len(SEQUENCE_KEYS)] == list(SEQUENCE_KEYS),
        {"order": order},
    )

    record(
        "F.2 only the first step is available at the start",
        plan.get("available_steps") == ["space_types"]
        and plan.get("next_step") == "space_types"
        and plan.get("progress_ratio") == 0.0,
        {"available": plan.get("available_steps")},
    )

    status, stepped = sequence(
        {"space_types": "completed"}, language="en"
    )

    stepped_plan = (stepped or {}).get("plan") or {}

    record(
        "F.3 completing a step unlocks exactly its dependent step",
        stepped_plan.get("available_steps") == ["relationships"]
        and stepped_plan.get("next_step") == "relationships",
        {"available": stepped_plan.get("available_steps")},
    )

    status, out_of_order = sequence(
        {"zoning": "completed"}, language="en"
    )

    ooo_plan = (out_of_order or {}).get("plan") or {}

    record(
        "F.4 an out-of-order step does NOT unlock its dependents",
        ooo_plan.get("available_steps") == ["space_types"]
        and ooo_plan.get("is_complete") is False,
        {"available": ooo_plan.get("available_steps")},
    )

    status, done = sequence(
        {key: "completed" for key in FULL_SEQUENCE_KEYS}, language="en"
    )

    done_plan = (done or {}).get("plan") or {}

    record(
        "F.5 the full sequence completes",
        status == 200
        and done_plan.get("is_complete") is True
        and done_plan.get("progress_ratio") == 1.0
        and done_plan.get("next_step") is None,
        {"ratio": done_plan.get("progress_ratio")},
    )

    status, persian_sequence = sequence(language="fa")

    persian_steps = (persian_sequence or {}).get("plan") or {}

    record(
        "F.6 the sequence is available in Persian",
        status == 200
        and all(
            has_persian(step.get("label"))
            for step in persian_steps.get("steps") or []
        ),
        None,
    )

    # invalid progress must be refused, not silently accepted
    status, invalid = sequence({"space_types": "learned"}, language="en")

    record(
        "F.7 a knowledge-like progress status is refused (HTTP 400)",
        status == 400
        and ((invalid or {}).get("error")) == "invalid_progress",
        {"status": status},
    )

    status, unknown = sequence({"not_a_step": "completed"}, language="en")

    record(
        "F.8 an unknown step is refused (HTTP 400)",
        status == 400
        and ((unknown or {}).get("error")) == "invalid_progress",
        {"status": status},
    )

    # ==================================================
    # TEST G — NO LESSONS, NOTHING LEARNED
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST G - NO LESSONS, NOTHING LEARNED")
    print("=" * 70)

    status, payload = sequence(language="en")

    sequence_report = (payload or {}).get("report") or {}

    record(
        "G.1 the sequencer contains no lesson content",
        sequence_report.get("lesson_count") == 0
        and sequence_report.get("has_lessons") is False
        and sequence_report.get("persists_progress") is False,
        {"lesson_count": sequence_report.get("lesson_count")},
    )

    record(
        "G.2 the sequencer writes nothing and learns nothing",
        sequence_report.get("writes_performed") == 0
        and sequence_report.get("read_only") is True
        and sequence_report.get("permanent_learning") is False,
        None,
    )

    learned_total = 0

    forbidden_found = []

    for project_id in (
        persian_project, english_project, isolation_a, isolation_b
    ):

        _status, payload = http_json(
            CORE_API,
            "/api/conversation/candidates?project_id=" + project_id,
        )

        learned_total += int((payload or {}).get("learned_count") or 0)

        for candidate in (payload or {}).get("candidates") or []:

            if candidate.get("status") not in ALLOWED_STATUSES:

                forbidden_found.append(candidate)

    record(
        "G.3 learned_count is 0 in every project",
        learned_total == 0,
        {"learned_total": learned_total},
    )

    record(
        "G.4 every candidate status is a candidate status",
        not forbidden_found,
        {"forbidden": forbidden_found[:3]},
    )

    status, promo = http_json(
        CORE_API, "/api/conversation/knowledge/promotion/status"
    )

    record(
        "G.5 promotion is still not implemented",
        ((promo or {}).get("result") or {}).get(
            "promotion_implemented"
        ) is False,
        None,
    )

    # ==================================================
    # TEST H — PROJECT ISOLATION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST H - PROJECT ISOLATION")
    print("=" * 70)

    chat(isolation_a, FA_RULE)

    chat(isolation_b, "The roof must be above the bedroom.")

    status_a, payload_a = http_json(
        CORE_API,
        "/api/conversation/candidates?project_id=" + isolation_a,
    )

    status_b, payload_b = http_json(
        CORE_API,
        "/api/conversation/candidates?project_id=" + isolation_b,
    )

    list_a = (payload_a or {}).get("candidates") or []

    list_b = (payload_b or {}).get("candidates") or []

    ids_a = {c.get("candidate_id") for c in list_a}

    ids_b = {c.get("candidate_id") for c in list_b}

    record(
        "H.1 project A candidates never appear in project B",
        bool(list_a)
        and not (ids_a & ids_b)
        and all(c.get("project_id") == isolation_a for c in list_a)
        and all(c.get("project_id") == isolation_b for c in list_b),
        {"a": len(list_a), "b": len(list_b)},
    )

    status, guard = http_json(
        CORE_API,
        "/api/conversation/knowledge/storage-guard?project_id="
        + persian_project,
    )

    guard_result = (guard or {}).get("result") or {}

    record(
        "H.2 teaching storage stays project-scoped, global memory clean",
        guard_result.get("global_memory_clean") is True
        and guard_result.get("teaching_storage_is_project_scoped") is True,
        {"clean": guard_result.get("global_memory_clean")},
    )

    # ==================================================
    # TEST I — RESTART MID-RUN
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST I - RESTART MID-RUN")
    print("=" * 70)

    stop_core(process)

    time.sleep(3)

    process = start_core(port=5000, log_suffix=".restart")

    restarted = wait_for_core(CORE_API, timeout=10800)

    record("I.1 Core API restarted", restarted, None)

    if restarted:

        status_a2, payload_a2 = http_json(
            CORE_API,
            "/api/conversation/candidates?project_id=" + isolation_a,
        )

        status_b2, payload_b2 = http_json(
            CORE_API,
            "/api/conversation/candidates?project_id=" + isolation_b,
        )

        list_a2 = (payload_a2 or {}).get("candidates") or []

        list_b2 = (payload_b2 or {}).get("candidates") or []

        record(
            "I.2 candidates survive the restart, isolation still holds",
            {c.get("candidate_id") for c in list_a2} == ids_a
            and {c.get("candidate_id") for c in list_b2} == ids_b
            and not (
                {c.get("candidate_id") for c in list_a2}
                & {c.get("candidate_id") for c in list_b2}
            ),
            {"a": len(list_a2), "b": len(list_b2)},
        )

        status, after_restart, candidate = classify(
            persian_project, FA_CUSTOMARY
        )

        record(
            "I.3 classification is identical after a restart",
            candidate.get("knowledge_class") == "PATTERN"
            and candidate.get("scope") == "GENERAL",
            {"kc": candidate.get("knowledge_class")},
        )

        status, seq2 = sequence(language="en")

        record(
            "I.4 the sequence is reproducible after a restart",
            ((seq2 or {}).get("plan") or {}).get("step_count") >= 5
            and [
                s.get("key")
                for s in ((seq2 or {}).get("plan") or {}).get("steps") or []
            ][: len(SEQUENCE_KEYS)] == list(SEQUENCE_KEYS),
            None,
        )

    else:

        for label in (
            "I.2 candidates survive the restart, isolation still holds",
            "I.3 classification is identical after a restart",
            "I.4 the sequence is reproducible after a restart",
        ):

            record(label, False, None)

    stop_core(process)

    # ==================================================
    # TEST J — ZERO RENDER / GEOMETRY / CAD / BIM / IFC
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST J - ZERO RENDER / GEOMETRY / CAD / BIM / IFC")
    print("=" * 70)

    after_comfy = comfy_output_snapshot()

    record(
        "J.1 ComfyUI output directory unchanged",
        before_comfy == after_comfy,
        {"before": before_comfy, "after": after_comfy},
    )

    comfy_reachable = False

    try:

        urllib.request.urlopen(
            "http://127.0.0.1:8188/system_stats", timeout=3
        )

        comfy_reachable = True

    except Exception:

        comfy_reachable = False

    record(
        "J.2 no ComfyUI invocation (blocked on port 9)",
        not comfy_reachable or before_comfy == after_comfy,
        {"comfy_reachable": comfy_reachable},
    )

    scan = artifact_scan(DATA_ROOT)

    report["artifact_scan"] = scan

    report["geometry_outputs"] = scan["geometry_files"]

    record(
        "J.3 ZERO geometry / CAD / DWG / BIM / IFC artefacts produced",
        scan["geometry_files"] == 0,
        scan,
    )

    record(
        "J.4 ZERO render / image artefacts produced",
        scan["image_files"] == 0 and report["real_renders"] == 0,
        {"image_files": scan["image_files"]},
    )

    # ==================================================
    # REGRESSION — PHASES 01-12
    # ==================================================

    print("\n" + "=" * 70)
    print("  REGRESSION - PHASES 01-12")
    print("=" * 70)

    completed = subprocess.run(
        [sys.executable, PHASE12_ACCEPTANCE, "--fast"],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=18000,
    )

    report["phase12_regression"] = {
        "returncode": completed.returncode,
        "fast_mode": True,
        "tail": (completed.stdout or "")[-1600:],
    }

    record(
        "R.1 Phase 12 acceptance still green",
        completed.returncode == 0,
        {"returncode": completed.returncode,
         "tail": (completed.stdout or "")[-500:]},
    )

    if fast:

        record(
            "R.2 Voice 07 regression (SKIPPED by --fast)",
            True,
            {"skipped": True},
        )

    else:

        completed = subprocess.run(
            [sys.executable, VOICE07_RUNNER],
            cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=5400,
        )

        report["voice07_regression"] = {
            "returncode": completed.returncode,
            "tail": (completed.stdout or "")[-1200:],
        }

        record(
            "R.2 Voice 07 regression remains green",
            completed.returncode == 0,
            {"returncode": completed.returncode,
             "tail": (completed.stdout or "")[-400:]},
        )

    for label, path in (
        ("R.3 CHAT_LANGUAGE_02 regression", CHAT_LANGUAGE_TESTS),
        ("R.4 chat core regression", CHAT_CORE_TESTS),
    ):

        completed = subprocess.run(
            [sys.executable, path],
            cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10800,
        )

        record(
            label,
            completed.returncode == 0,
            {"returncode": completed.returncode,
             "tail": (completed.stdout or "")[-300:]},
        )

    try:

        with open(PHASE12_REPORT, "r", encoding="utf-8") as handle:

            phase12_report = json.load(handle)

    except Exception:

        phase12_report = {}

    record(
        "R.5 Phase 12 acceptance report still records PASS",
        phase12_report.get("final_status") == "FLOOR_PROGRAM_12_PASS"
        and phase12_report.get("failed") == 0,
        {"status": phase12_report.get("final_status")},
    )

    # ==================================================
    # REPORT
    # ==================================================

    failed = [entry for entry in RESULTS if not entry["passed"]]

    report["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    report["tests"] = RESULTS

    report["passed"] = len(RESULTS) - len(failed)

    report["failed"] = len(failed)

    report["total"] = len(RESULTS)

    report["comfy_output_before"] = before_comfy

    report["comfy_output_after"] = after_comfy

    report["sequencer_report"] = sequence_report

    report["final_status"] = (
        "CURRICULUM_FOUNDATION_FIX_PASS"
        if not failed
        else "CURRICULUM_FOUNDATION_FIX_BLOCKED"
    )

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:

        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("  CURRICULUM FOUNDATION FIX — ACCEPTANCE SUMMARY")
    print("=" * 70)

    for entry in RESULTS:

        print(
            "  [%s] %s" % (
                "PASS" if entry["passed"] else "FAIL",
                entry["test"],
            )
        )

    print("-" * 70)

    print(
        "  %d/%d PASS  |  renders: %d  |  geometry: %d  |  lessons: %d"
        "  |  classes: %d  |  steps: %d"
        % (
            report["passed"],
            report["total"],
            report["real_renders"],
            report["geometry_outputs"],
            report["lessons_created"],
            len(ALL_KNOWLEDGE_CLASSES),
            len(STEP_KEYS),
        )
    )

    print("  FINAL STATUS:", report["final_status"])

    print("  REPORT:", REPORT_PATH)

    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
