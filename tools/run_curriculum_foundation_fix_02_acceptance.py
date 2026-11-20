# ==========================================================
# CURRICULUM_FOUNDATION_FIX_02 — ACCEPTANCE RUNNER
#
# Runs the REQUIRED acceptance tests against the LIVE runtime:
#
#   UI-style HTTP -> Core API (app.py)
#                -> /api/chat                          (teaching)
#                -> /api/conversation/curriculum/sequence
#                -> /api/conversation/knowledge/patterns
#
# WHAT THIS PHASE IS: three foundation fixes only.
#   1. zone assignment teaching support
#   2. a seven-step curriculum sequencer
#   3. a pattern curriculum boundary (residential only; commercial and
#      mixed-use stay BLOCKED)
#
# HARD CONSTRAINTS (asserted, not assumed)
#   - NO lessons, NO curriculum content, NO knowledge promotion.
#   - NO geometry, NO coordinates, NO walls, NO layout, NO CAD, NO DWG,
#     NO BIM, NO IFC, NO RPLAN.
#   - NO render, NO ComfyUI, NO image generation.
#
# Usage:
#   .venv/Scripts/python.exe tools/run_curriculum_foundation_fix_02_acceptance.py
#   .venv/Scripts/python.exe tools/run_curriculum_foundation_fix_02_acceptance.py --fast
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
    ROOT, "tools", "acceptance_curriculum_foundation_fix_02_report.json"
)

LOG_PATH = os.path.join(
    ROOT, "logs", "runtime",
    "acceptance_curriculum_foundation_fix_02_core.log",
)

WORK_DIR = os.path.join(
    ROOT,
    ".pytest_tmp",
    "curriculum_foundation_02_" + time.strftime("%Y%m%d_%H%M%S"),
)

DATA_ROOT = os.path.join(WORK_DIR, "project_data")

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT


FIX02_TESTS = os.path.join(
    ROOT, "tests", "test_curriculum_foundation_fix_02.py"
)

FIX01_TESTS = os.path.join(
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

# The previous phase's runner. It nests Phase 12 -> 11 -> 10 -> 09 -> 08,
# so it is run ONCE, at this level, in fast mode, and Voice 07 is run
# once at the top level rather than at the bottom of that chain.
FIX01_ACCEPTANCE = os.path.join(
    ROOT, "tools", "run_curriculum_foundation_fix_acceptance.py"
)

FIX01_REPORT = os.path.join(
    ROOT, "tools", "acceptance_curriculum_foundation_fix_report.json"
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

# The exact sentence the start audit found unteachable.
BRIEF_ZONE = "ورودی و نشیمن در منطقه عمومی قرار می گیرند"

ZONE_CASES = (
    ("ورودی و نشیمن در منطقه عمومی قرار می گیرند", "PUBLIC_ZONE"),
    ("اتاق خواب در منطقه خصوصی قرار دارد", "PRIVATE_ZONE"),
    ("حمام در منطقه خدماتی واقع شده است", "SERVICE_ZONE"),
    ("نشیمن جزء منطقه نیمه عمومی است", "SEMI_PUBLIC_ZONE"),
    ("راهرو در منطقه گردش قرار می گیرد", "CIRCULATION_ZONE"),
    ("حیاط در منطقه بیرونی قرار دارد", "EXTERNAL_ZONE"),
    ("ورودی در منطقه عمومی است", "PUBLIC_ZONE"),
)

EN_ZONE = "The entry belongs to the public zone"

# A plain descriptive statement must STILL not become a teaching turn.
PLAIN_DESCRIPTIVE = "آشپزخانه سه بخش دارد"

ORIGINAL_FIVE = (
    "space_types",
    "relationships",
    "privacy",
    "zoning",
    "bubble_diagram",
)

ADDED_TWO = ("patterns", "design_reasoning")

FULL_SEQUENCE = ORIGINAL_FIVE + ADDED_TWO


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

    handle.write(b"\n\n===== curriculum foundation 02 core start =====\n")

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


def teach(project_id, text):

    status, payload = chat(project_id, text)

    response = (payload or {}).get("response") or {}

    return (
        status,
        response,
        (response.get("teaching") or {}).get("candidate") or {},
    )


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
        "phase": "CURRICULUM_FOUNDATION_FIX_02",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "comfy_blocked_by_construction": True,
        "comfy_port": 9,
        "real_renders": 0,
        "image_generations": 0,
        "geometry_outputs": 0,
        "layout_outputs": 0,
        "cad_outputs": 0,
        "dwg_outputs": 0,
        "bim_outputs": 0,
        "ifc_outputs": 0,
        "lessons_created": 0,
        "curriculum_content_created": 0,
        "permanent_learning": False,
        "data_root": DATA_ROOT,
        "tests": [],
    }

    os.makedirs(DATA_ROOT, exist_ok=True)

    # ==================================================
    # SECTION 0 — STATIC + CONTRACT CHECKS
    # ==================================================

    print("\n" + "=" * 70)
    print("  SECTION 0 - STATIC + CONTRACT CHECKS")
    print("=" * 70)

    with open(os.path.join(ROOT, "app.py"), "r",
              encoding="utf-8", errors="replace") as handle:

        app_text = handle.read()

    record(
        "0.1 exactly ONE ChatArchitect in the Core API",
        app_text.count("ChatArchitect(") == 1,
        {"count": app_text.count("ChatArchitect(")},
    )

    from core.conversation.teaching_meaning_v1 import (
        ALL_KNOWLEDGE_CLASSES,
    )

    from core.conversation.teaching_candidate_v1 import (
        ALLOWED_STATUSES,
        PERMANENT_LEARNING_IMPLEMENTED,
        TeachingCandidate,
    )

    from core.conversation.knowledge_promotion_bridge_v1 import (
        PROMOTION_IMPLEMENTED,
    )

    from core.curriculum.curriculum_sequencer_v1 import (
        curriculum_sequencer,
        STEP_KEYS,
        LESSONS,
        ALL_STEP_STATUSES,
        FORBIDDEN_STEP_STATUSES,
    )

    from core.curriculum.pattern_curriculum_v1 import (
        pattern_curriculum,
        PATTERNS,
        FAMILY_KEYS,
        PATTERN_TEACHING_ASPECTS,
    )

    record(
        "0.2 the sequencer now carries seven steps",
        len(STEP_KEYS) == 7
        and list(STEP_KEYS) == list(FULL_SEQUENCE)
        and set(ORIGINAL_FIVE) <= set(STEP_KEYS),
        {"steps": list(STEP_KEYS)},
    )

    record(
        "0.3 no lessons exist and the sequencer refuses 'learned'",
        LESSONS == ()
        and curriculum_sequencer.report()["lesson_count"] == 0
        and set(ALL_STEP_STATUSES) == {
            "not_started", "in_progress", "completed"
        }
        and "learned" in FORBIDDEN_STEP_STATUSES,
        None,
    )

    record(
        "0.4 three pattern families; no patterns and no lessons held",
        set(FAMILY_KEYS) == {"residential", "commercial", "mixed_use"}
        and PATTERNS == ()
        and pattern_curriculum.report()["pattern_count"] == 0
        and pattern_curriculum.report()["lesson_count"] == 0
        and len(PATTERN_TEACHING_ASPECTS) == 5,
        None,
    )

    record(
        "0.5 promotion still impossible, statuses closed",
        PROMOTION_IMPLEMENTED is False
        and PERMANENT_LEARNING_IMPLEMENTED is False
        and set(ALLOWED_STATUSES) == {
            "observed", "needs_confirmation", "rejected"
        },
        None,
    )

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
        "0.6 no lesson / layout / floor-plan / geometry layer exists",
        not hits,
        {"hits": hits},
    )

    print("\n  running contract suites ...")

    for label, path in (
        ("0.7 fix-02 contract suite green", FIX02_TESTS),
        ("0.8 fix-01 contract suite still green", FIX01_TESTS),
        ("0.9 Phase 12 contract suite still green", PHASE12_TESTS),
        ("0.10 Phase 11 contract suite still green", PHASE11_TESTS),
        ("0.11 Phase 10 contract suite still green", PHASE10_TESTS),
        ("0.12 Phase 09 contract suite still green", PHASE09_TESTS),
        ("0.13 Phase 08 contract suite still green", PHASE08_TESTS),
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

        report["final_status"] = "CURRICULUM_FOUNDATION_BLOCKED"

        with open(REPORT_PATH, "w", encoding="utf-8") as handle:

            json.dump(report, handle, ensure_ascii=False, indent=2)

        return 1

    record("1.0 Core API online", True, {"pid": process.pid})

    status, sequence_payload = sequence(language="en")

    record(
        "1.1 the sequence surface serves seven steps over HTTP",
        status == 200
        and ((sequence_payload or {}).get("render_requested")) is False
        and ((sequence_payload or {}).get("plan") or {}).get(
            "step_count"
        ) == 7,
        {"status": status},
    )

    status, patterns_payload = http_json(
        CORE_API, "/api/conversation/knowledge/patterns"
    )

    record(
        "1.2 the knowledge surfaces are online",
        status == 200,
        {"status": status},
    )

    persian_project, _ = create_project("Foundation 02 Persian")

    english_project, _ = create_project("Foundation 02 English")

    isolation_a, _ = create_project("Foundation 02 Isolation A")

    isolation_b, _ = create_project("Foundation 02 Isolation B")

    record(
        "1.3 acceptance projects created",
        all([persian_project, english_project, isolation_a, isolation_b]),
        {"persian": persian_project},
    )

    # ==================================================
    # TEST A — ZONE ASSIGNMENT (FIX 1)
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST A - ZONE ASSIGNMENT TEACHING SUPPORT")
    print("=" * 70)

    status, response, candidate = teach(persian_project, BRIEF_ZONE)

    zone = (candidate.get("zone_assignment") or {}).get("zone")

    record(
        "A.1 the brief's zoning statement becomes a teaching candidate",
        status == 200
        and (response.get("turn_semantics") or {}).get("turn_kind")
        == "TEACHING_STATEMENT"
        and candidate.get("knowledge_class") == "ARCHITECTURAL_FACT"
        and zone == "PUBLIC_ZONE",
        {
            "turn_kind": (response.get("turn_semantics") or {}).get(
                "turn_kind"
            ),
            "kc": candidate.get("knowledge_class"),
            "zone": zone,
        },
    )

    record(
        "A.2 the candidate is candidate-only (nothing learned)",
        candidate.get("status") in ALLOWED_STATUSES
        and candidate.get("is_learned_knowledge") is False
        and candidate.get("is_permanent") is False
        and response.get("capability") == "UNDERSTAND",
        {"status": candidate.get("status")},
    )

    failures = []

    for text, expected in ZONE_CASES:

        _status, _response, got = teach(persian_project, text)

        resolved = (got.get("zone_assignment") or {}).get("zone")

        if (
            got.get("knowledge_class") != "ARCHITECTURAL_FACT"
            or resolved != expected
        ):

            failures.append(
                {"expected": expected, "got": resolved,
                 "kc": got.get("knowledge_class")}
            )

    record(
        "A.3 all six zones resolve from a Persian zoning statement",
        not failures,
        failures,
    )

    _status, _response, en_candidate = teach(english_project, EN_ZONE)

    record(
        "A.4 an English zoning statement resolves",
        (en_candidate.get("zone_assignment") or {}).get("zone")
        == "PUBLIC_ZONE",
        {"zone": (en_candidate.get("zone_assignment") or {}).get("zone")},
    )

    _status, plain_response, plain_candidate = teach(
        persian_project, PLAIN_DESCRIPTIVE
    )

    record(
        "A.5 a plain descriptive statement is STILL not a teaching turn",
        (plain_response.get("turn_semantics") or {}).get("turn_kind")
        != "TEACHING_STATEMENT"
        and not plain_candidate,
        {
            "turn_kind": (plain_response.get("turn_semantics") or {}).get(
                "turn_kind"
            )
        },
    )

    # ==================================================
    # TEST B — SEVEN-STEP SEQUENCER (FIX 2)
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST B - SEVEN-STEP CURRICULUM SEQUENCER")
    print("=" * 70)

    status, payload = sequence(language="en")

    plan = (payload or {}).get("plan") or {}

    order = [step.get("key") for step in plan.get("steps") or []]

    record(
        "B.1 the sequence is Space Types -> ... -> Patterns -> "
        "Design Reasoning",
        status == 200 and order == list(FULL_SEQUENCE),
        {"order": order},
    )

    record(
        "B.2 the original five remain unchanged as a prefix",
        order[: len(ORIGINAL_FIVE)] == list(ORIGINAL_FIVE),
        {"order": order},
    )

    record(
        "B.3 only the first step is available at the start",
        plan.get("available_steps") == ["space_types"]
        and plan.get("next_step") == "space_types"
        and plan.get("progress_ratio") == 0.0,
        {"available": plan.get("available_steps")},
    )

    status, stepped = sequence(
        {key: "completed" for key in ORIGINAL_FIVE}, language="en"
    )

    stepped_plan = (stepped or {}).get("plan") or {}

    record(
        "B.4 patterns unlocks only after the bubble diagram",
        stepped_plan.get("available_steps") == ["patterns"]
        and stepped_plan.get("next_step") == "patterns",
        {"available": stepped_plan.get("available_steps")},
    )

    status, done = sequence(
        {key: "completed" for key in FULL_SEQUENCE}, language="en"
    )

    done_plan = (done or {}).get("plan") or {}

    record(
        "B.5 the full seven-step sequence completes",
        status == 200
        and done_plan.get("is_complete") is True
        and done_plan.get("progress_ratio") == 1.0
        and done_plan.get("next_step") is None,
        {"ratio": done_plan.get("progress_ratio")},
    )

    status, out_of_order = sequence(
        {"bubble_diagram": "completed"}, language="en"
    )

    ooo = (out_of_order or {}).get("plan") or {}

    record(
        "B.6 an out-of-order step unlocks nothing downstream",
        ooo.get("available_steps") == ["space_types"]
        and ooo.get("is_complete") is False,
        {"available": ooo.get("available_steps")},
    )

    status, persian_sequence = sequence(language="fa")

    persian_plan = (persian_sequence or {}).get("plan") or {}

    record(
        "B.7 the seven-step sequence is available in Persian",
        status == 200
        and len(persian_plan.get("steps") or []) == 7
        and all(
            has_persian(step.get("label"))
            for step in persian_plan.get("steps") or []
        ),
        None,
    )

    status, invalid = sequence({"patterns": "learned"}, language="en")

    record(
        "B.8 a knowledge-like progress status is refused (HTTP 400)",
        status == 400
        and ((invalid or {}).get("error")) == "invalid_progress",
        {"status": status},
    )

    status, unknown = sequence({"not_a_step": "completed"}, language="en")

    record(
        "B.9 an unknown step is refused (HTTP 400)",
        status == 400
        and ((unknown or {}).get("error")) == "invalid_progress",
        {"status": status},
    )

    # ==================================================
    # TEST C — PATTERN BOUNDARY (FIX 3)
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST C - PATTERN CURRICULUM BOUNDARY")
    print("=" * 70)

    coverage = pattern_curriculum.coverage()

    record(
        "C.1 residential is AVAILABLE; commercial and mixed-use BLOCKED",
        coverage["available_families"] == ["residential"]
        and set(coverage["blocked_families"]) == {
            "commercial", "mixed_use"
        }
        and coverage["partial"] is True,
        {
            "available": coverage["available_families"],
            "blocked": coverage["blocked_families"],
        },
    )

    record(
        "C.2 every blocked family states a reason and has no corpus",
        all(
            family.get("blocked_reason")
            and family.get("pattern_count") == 0
            for family in pattern_curriculum.blocked()
        ),
        [f.get("key") for f in pattern_curriculum.blocked()],
    )

    record(
        "C.3 availability is derived from the read bridge, not hardcoded",
        pattern_curriculum.report()["availability_is_derived"] is True
        and pattern_curriculum.report()["availability_source"]
        == "core/conversation/knowledge_read_bridge_v1.py",
        None,
    )

    status, seq_cov = sequence(language="en")

    patterns_step = [
        step for step in ((seq_cov or {}).get("plan") or {}).get("steps")
        or []
        if step.get("key") == "patterns"
    ]

    step_coverage = (patterns_step[0].get("coverage") or {}) if (
        patterns_step
    ) else {}

    record(
        "C.4 the patterns step carries its coverage boundary over HTTP",
        step_coverage.get("available_families") == ["residential"]
        and set(step_coverage.get("blocked_families") or []) == {
            "commercial", "mixed_use"
        },
        {"available": step_coverage.get("available_families")},
    )

    record(
        "C.5 the pattern boundary holds no patterns and no lessons",
        PATTERNS == ()
        and pattern_curriculum.report()["pattern_count"] == 0
        and pattern_curriculum.report()["lesson_count"] == 0
        and pattern_curriculum.report()["promotion_implemented"] is False,
        None,
    )

    # ==================================================
    # TEST D — NO LESSONS, NOTHING LEARNED
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST D - NO LESSONS, NOTHING LEARNED")
    print("=" * 70)

    record(
        "D.1 no lesson content exists anywhere",
        LESSONS == ()
        and curriculum_sequencer.report()["lesson_count"] == 0
        and pattern_curriculum.report()["lesson_count"] == 0
        and all(
            step.get("has_lesson") is False
            for step in plan.get("steps") or []
        ),
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

        for entry in (payload or {}).get("candidates") or []:

            if entry.get("status") not in ALLOWED_STATUSES:

                forbidden_found.append(entry)

    record(
        "D.2 learned_count is 0 in every project",
        learned_total == 0,
        {"learned_total": learned_total},
    )

    record(
        "D.3 every candidate status is a candidate status",
        not forbidden_found,
        {"forbidden": forbidden_found[:3]},
    )

    status, promo = http_json(
        CORE_API, "/api/conversation/knowledge/promotion/status"
    )

    record(
        "D.4 promotion is still not implemented",
        ((promo or {}).get("result") or {}).get(
            "promotion_implemented"
        ) is False,
        None,
    )

    status, sources_after = http_json(
        CORE_API, "/api/conversation/knowledge/sources"
    )

    record(
        "D.5 the corpus was not written",
        ((sources_after or {}).get("result") or {}).get(
            "writes_performed"
        ) == 0,
        None,
    )

    # ==================================================
    # TEST E — PROJECT ISOLATION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST E - PROJECT ISOLATION")
    print("=" * 70)

    chat(isolation_a, BRIEF_ZONE)

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
        "E.1 project A candidates never appear in project B",
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
        "E.2 teaching storage stays project-scoped, global memory clean",
        guard_result.get("global_memory_clean") is True
        and guard_result.get("teaching_storage_is_project_scoped") is True,
        {"clean": guard_result.get("global_memory_clean")},
    )

    # ==================================================
    # TEST F — RESTART MID-RUN
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST F - RESTART MID-RUN")
    print("=" * 70)

    stop_core(process)

    time.sleep(3)

    process = start_core(port=5000, log_suffix=".restart")

    restarted = wait_for_core(CORE_API, timeout=10800)

    record("F.1 Core API restarted", restarted, None)

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
            "F.2 candidates survive the restart, isolation still holds",
            {c.get("candidate_id") for c in list_a2} == ids_a
            and {c.get("candidate_id") for c in list_b2} == ids_b
            and not (
                {c.get("candidate_id") for c in list_a2}
                & {c.get("candidate_id") for c in list_b2}
            ),
            {"a": len(list_a2), "b": len(list_b2)},
        )

        _status, _response, after = teach(persian_project, BRIEF_ZONE)

        record(
            "F.3 zone classification is identical after a restart",
            after.get("knowledge_class") == "ARCHITECTURAL_FACT"
            and (after.get("zone_assignment") or {}).get("zone")
            == "PUBLIC_ZONE",
            {"zone": (after.get("zone_assignment") or {}).get("zone")},
        )

        status, seq2 = sequence(language="en")

        record(
            "F.4 the seven-step sequence is reproducible after a restart",
            ((seq2 or {}).get("plan") or {}).get("step_count") == 7
            and [
                s.get("key")
                for s in ((seq2 or {}).get("plan") or {}).get("steps") or []
            ] == list(FULL_SEQUENCE),
            None,
        )

    else:

        for label in (
            "F.2 candidates survive the restart, isolation still holds",
            "F.3 zone classification is identical after a restart",
            "F.4 the seven-step sequence is reproducible after a restart",
        ):

            record(label, False, None)

    stop_core(process)

    # ==================================================
    # TEST G — ZERO RENDER / GEOMETRY / LAYOUT / CAD / BIM / IFC
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST G - ZERO RENDER / GEOMETRY / LAYOUT / CAD / BIM / IFC")
    print("=" * 70)

    after_comfy = comfy_output_snapshot()

    record(
        "G.1 ComfyUI output directory unchanged",
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
        "G.2 no ComfyUI invocation (blocked on port 9)",
        not comfy_reachable or before_comfy == after_comfy,
        {"comfy_reachable": comfy_reachable},
    )

    scan = artifact_scan(DATA_ROOT)

    report["artifact_scan"] = scan

    report["geometry_outputs"] = scan["geometry_files"]

    record(
        "G.3 ZERO geometry / layout / CAD / DWG / BIM / IFC artefacts",
        scan["geometry_files"] == 0,
        scan,
    )

    record(
        "G.4 ZERO render / image artefacts produced",
        scan["image_files"] == 0 and report["real_renders"] == 0,
        {"image_files": scan["image_files"]},
    )

    # ==================================================
    # REGRESSION
    # ==================================================

    print("\n" + "=" * 70)
    print("  REGRESSION - PHASES 01-12 + FIX 01")
    print("=" * 70)

    # The previous phase's runner, once, at this level, in fast mode. It
    # nests Phase 12 -> 11 -> 10 -> 09 -> 08, so Voice 07 is run once at
    # THIS level rather than at the bottom of that chain.
    completed = subprocess.run(
        [sys.executable, FIX01_ACCEPTANCE, "--fast"],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=21600,
    )

    report["fix01_regression"] = {
        "returncode": completed.returncode,
        "fast_mode": True,
        "tail": (completed.stdout or "")[-1600:],
    }

    record(
        "R.1 the fix-01 acceptance is still green",
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

        with open(FIX01_REPORT, "r", encoding="utf-8") as handle:

            fix01_report = json.load(handle)

    except Exception:

        fix01_report = {}

    record(
        "R.5 the fix-01 acceptance report still records PASS",
        fix01_report.get("final_status") == "CURRICULUM_FOUNDATION_FIX_PASS"
        and fix01_report.get("failed") == 0,
        {"status": fix01_report.get("final_status")},
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

    report["sequencer_report"] = curriculum_sequencer.report()

    report["pattern_report"] = pattern_curriculum.report()

    report["pattern_coverage"] = coverage

    report["knowledge_classes"] = list(ALL_KNOWLEDGE_CLASSES)

    report["final_status"] = (
        "CURRICULUM_FOUNDATION_READY_FOR_LESSON_01"
        if not failed
        else "CURRICULUM_FOUNDATION_BLOCKED"
    )

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:

        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("  CURRICULUM FOUNDATION FIX 02 — ACCEPTANCE SUMMARY")
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
        "  |  steps: %d  |  pattern families: %d (avail %d / blocked %d)"
        % (
            report["passed"],
            report["total"],
            report["real_renders"],
            report["geometry_outputs"],
            report["lessons_created"],
            len(STEP_KEYS),
            coverage["family_count"],
            coverage["available_count"],
            coverage["blocked_count"],
        )
    )

    print("  FINAL STATUS:", report["final_status"])

    print("  REPORT:", REPORT_PATH)

    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
