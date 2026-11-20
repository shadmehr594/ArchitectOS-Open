# ==========================================================
# PHASE 10 — SPACE TYPES + ADJACENCY INTELLIGENCE ACCEPTANCE RUNNER
#
# Runs the REQUIRED Phase 10 acceptance tests (A-H) against the LIVE
# runtime:
#
#   UI-style HTTP -> Core API (app.py) -> /api/conversation/curriculum/*
#                                     -> ChatArchitect.handle
#
# HARD CONSTRAINTS
#   - NO render, NO ComfyUI, NO geometry, NO CAD, NO BIM, NO IFC.
#     The Core API starts with ARCHITECTOS_COMFY_PORT=9 and an isolated
#     project data root; the ComfyUI output directory is asserted
#     unchanged and the isolated root is scanned for artefacts.
#
# Usage:
#   .venv/Scripts/python.exe tools/run_space_adjacency_10_acceptance.py
#   .venv/Scripts/python.exe tools/run_space_adjacency_10_acceptance.py --fast
# ==========================================================


import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request


ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


CORE_API = "http://127.0.0.1:5000"

REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_10_report.json"
)

LOG_PATH = os.path.join(
    ROOT, "logs", "runtime", "acceptance_10_core.log"
)

WORK_DIR = os.path.join(
    ROOT,
    ".pytest_tmp",
    "space_adjacency_10_" + time.strftime("%Y%m%d_%H%M%S"),
)

DATA_ROOT = os.path.join(WORK_DIR, "project_data")

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT


PHASE10_TESTS = os.path.join(
    ROOT, "tests", "test_space_adjacency_10.py"
)

PHASE09_TESTS = os.path.join(
    ROOT, "tests", "test_architectural_learning_bridge_09.py"
)

PHASE08_TESTS = os.path.join(
    ROOT, "tests", "test_teaching_foundation_08.py"
)

PHASE09_ACCEPTANCE = os.path.join(
    ROOT, "tools", "run_architectural_learning_bridge_09_acceptance.py"
)

CHAT_LANGUAGE_TESTS = os.path.join(
    ROOT, "tests", "test_chat_language_02.py"
)

CHAT_CORE_TESTS = os.path.join(
    ROOT, "tests", "test_chat_core_only.py"
)

# The Voice 07 regression is run ONCE, at THIS level. It is deliberately
# NOT nested through Phase 09 -> Phase 08 -> Voice 07 (four process
# levels), which starves the real CPU Whisper STT step of resources.
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
            json.dumps(detail, ensure_ascii=False, default=str)[:520],
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
    env["ARCHITECTOS_CORE_API_PORT"] = str(port)
    env["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT

    env["ARCHITECTOS_COMFY_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_COMFY_PORT"] = "9"

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    if not os.path.isfile(python):

        python = sys.executable

    handle = open(LOG_PATH + log_suffix, "ab")

    handle.write(b"\n\n===== acceptance_10 core start =====\n")

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


def curriculum_query(text, language=None):

    return http_json(
        CORE_API,
        "/api/conversation/curriculum/query",
        {"text": text, "language": language},
        timeout=10800,
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    fast = "--fast" in sys.argv

    report = {
        "phase": "PHASE_10_SPACE_TYPES_ADJACENCY_INTELLIGENCE",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "comfy_blocked_by_construction": True,
        "comfy_port": 9,
        "real_renders": 0,
        "image_generations": 0,
        "geometry_outputs": 0,
        "cad_outputs": 0,
        "bim_outputs": 0,
        "ifc_outputs": 0,
        "bubble_diagram_started_by_phase_10": False,
        "bubble_diagram_layer_present_after_phase_11": True,
        "layout_generation_started": False,
        "rplan_integrated": False,
        "data_root": DATA_ROOT,
        "tests": [],
    }

    # A per-run work directory is used, so there is never a bulk delete of
    # a previous run's tree (which can trip environment safety guards).
    os.makedirs(DATA_ROOT, exist_ok=True)

    # ==================================================
    # SECTION 0 — AUDIT + STATIC CHECKS
    # ==================================================

    print("\n" + "=" * 70)
    print("  SECTION 0 — AUDIT + STATIC + CONTRACT CHECKS")
    print("=" * 70)

    from core.curriculum.space_types_v1 import space_types

    from core.curriculum.adjacency_model_v1 import adjacency_model

    from core.curriculum.privacy_logic_v1 import privacy_logic

    from core.curriculum.space_curriculum_v1 import space_curriculum

    from core.conversation.knowledge_read_bridge_v1 import (
        knowledge_read_bridge,
    )

    from core.conversation.teaching_candidate_v1 import (
        ALLOWED_STATUSES,
        PERMANENT_LEARNING_IMPLEMENTED,
    )

    from core.conversation.knowledge_promotion_bridge_v1 import (
        PROMOTION_IMPLEMENTED,
    )

    # ---- 10A: the audit is real — the corpus is REUSED ----
    read_report = knowledge_read_bridge.read_report()

    space_report = space_types.report()

    record(
        "0.1 existing corpus reused through the Phase 09 read bridge",
        read_report["read_only"] is True
        and read_report["writes_performed"] == 0
        and (space_report["by_origin"] or {}).get("SPACE_SPECS", 0) >= 40
        and (space_report["by_origin"] or {}).get("ONTOLOGY", 0) >= 40,
        {"origins": space_report["by_origin"]},
    )

    record(
        "0.2 space model has all six curriculum categories",
        len(space_report["by_category"]) == 6
        and all(
            space_report["by_category"].get(c, 0) > 0
            for c in (
                "PUBLIC", "SEMI_PUBLIC", "PRIVATE", "SERVICE",
                "CIRCULATION", "EXTERNAL",
            )
        ),
        space_report["by_category"],
    )

    adjacency_report = adjacency_model.report()

    record(
        "0.3 adjacency model is graded (not boolean)",
        adjacency_report["boolean_relations"] is False
        and len(adjacency_report["by_relation_type"]) >= 4
        and adjacency_report["relation_count"] >= 50,
        adjacency_report["by_relation_type"],
    )

    record(
        "0.4 privacy logic online with three bands",
        privacy_logic.report()["band_basis"] == "curriculum_category"
        and privacy_logic.report()["controlled_access_spaces"] > 0,
        privacy_logic.report()["spaces_by_band"],
    )

    record(
        "0.5 space curriculum exposes 5 space aspects",
        space_curriculum.report()["aspect_count"] == 5
        and space_curriculum.report()["candidate_only"] is True,
        space_curriculum.report()["aspects"],
    )

    # ---- scope: no layout / RPLAN / floor plan / geometry layer ----
    #
    # RELAXED TWICE (relax + add, never delete):
    #   * Phase 11 legitimately added the bubble-diagram / zone layer,
    #     so "bubble" left this list;
    #   * Phase 12 legitimately added the FLOOR PROGRAM layer, so
    #     "floor_program" leaves it too.
    # "floorplan" (a floor PLAN) stays forbidden; "floor_program" (a
    # semantic program) does not. 0.6b proves the new layers stayed
    # semantic.
    forbidden_modules = (
        "adjacency_matrix", "rplan", "layout_generation",
        "floorplan", "floor_plan", "geometry", "cad", "bim", "ifc",
        "render",
    )

    curriculum_dir = os.path.join(ROOT, "core", "curriculum")

    hits = [
        name for name in os.listdir(curriculum_dir)
        if name.endswith(".py")
        and any(t in name.lower() for t in forbidden_modules)
    ]

    record(
        "0.6 no layout / RPLAN / floor plan / geometry layer exists",
        not hits,
        {"hits": hits},
    )

    from core.curriculum.bubble_diagram_v1 import (
        bubble_diagram_builder,
    )

    from core.curriculum.floor_program_v1 import (
        floor_program_reasoning,
    )

    semantic = bubble_diagram_builder.report()

    semantic_diagram = bubble_diagram_builder.build(
        "\u062e\u0627\u0646\u0647 \u06f3 \u062e\u0648\u0627\u0628\u0647",
        language="fa",
    )

    semantic_program = floor_program_reasoning.reason(
        "\u062e\u0627\u0646\u0647 \u06f3 \u062e\u0648\u0627\u0628\u0647",
        "fa",
    )

    record(
        "0.6b Phase 11 + 12 layers are semantic only (no geometry, "
        "no render)",
        semantic["contains_geometry"] is False
        and semantic["contains_coordinates"] is False
        and semantic_diagram["semantic_only"] is True
        and semantic_diagram["render_requested"] is False
        and semantic_diagram["comfy_invoked"] is False
        and semantic_program["semantic_only"] is True
        and semantic_program["contains_geometry"] is False
        and semantic_program["contains_coordinates"] is False
        and semantic_program["contains_walls"] is False
        and semantic_program["contains_openings"] is False
        and semantic_program["render_requested"] is False,
        {
            "diagram_geometry": semantic_diagram["contains_geometry"],
            "program_geometry": semantic_program["contains_geometry"],
        },
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

    # ---- contract suites ----
    print("\n  running contract suites ...")

    for label, path in (
        ("0.8 Phase 10 contract suite green", PHASE10_TESTS),
        ("0.9 Phase 09 contract suite still green", PHASE09_TESTS),
        ("0.10 Phase 08 contract suite still green", PHASE08_TESTS),
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

        report["final_status"] = "SPACE_ADJACENCY_10_BLOCKED"

        with open(REPORT_PATH, "w", encoding="utf-8") as handle:

            json.dump(report, handle, ensure_ascii=False, indent=2)

        return 1

    record("1.0 Core API online", True, {"pid": process.pid})

    status, curriculum_status = http_json(
        CORE_API, "/api/conversation/curriculum/status"
    )

    record(
        "1.1 curriculum surface online over HTTP",
        status == 200
        and ((curriculum_status or {}).get("space_types") or {}).get(
            "space_count", 0
        ) >= 80
        and ((curriculum_status or {}).get("render_requested")) is False,
        {"status": status},
    )

    persian_project, _ = create_project("Phase10 Curriculum Persian")

    english_project, _ = create_project("Phase10 Curriculum English")

    isolation_a, _ = create_project("Phase10 Isolation A")

    isolation_b, _ = create_project("Phase10 Isolation B")

    record(
        "1.2 acceptance projects created",
        all([persian_project, english_project, isolation_a, isolation_b]),
        {"persian": persian_project, "english": english_project},
    )

    # ==================================================
    # A — SPACE CLASSIFICATION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST A — SPACE CLASSIFICATION")
    print("=" * 70)

    status, payload = curriculum_query(
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 "
        "\u0641\u0636\u0627\u06cc \u062e\u0635\u0648\u0635\u06cc \u0627\u0633\u062a"
    )

    result = (payload or {}).get("result") or {}

    record(
        "A.1 space classification works (Persian)",
        status == 200
        and result.get("query_type") == "SPACE_CLASSIFICATION"
        and result.get("verdict") == "CORRECT"
        and result.get("actual_category") == "PRIVATE",
        {"query_type": result.get("query_type"),
         "verdict": result.get("verdict"),
         "category": result.get("actual_category")},
    )

    record(
        "A.2 the answer is grounded in the space registry",
        bool(result.get("answer"))
        and result.get("space_id") == "BEDROOM_DOUBLE",
        {"answer": result.get("answer"), "space": result.get("space_id")},
    )

    # a deliberately WRONG claim must be refused
    status, payload = curriculum_query(
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 "
        "\u0641\u0636\u0627\u06cc \u062e\u0635\u0648\u0635\u06cc \u0627\u0633\u062a"
    )

    wrong = (payload or {}).get("result") or {}

    record(
        "A.3 a wrong classification is corrected, not agreed with",
        wrong.get("verdict") == "INCORRECT"
        and wrong.get("actual_category") == "SEMI_PUBLIC",
        {"verdict": wrong.get("verdict"),
         "actual": wrong.get("actual_category")},
    )

    # ==================================================
    # B — ADJACENCY REASONING
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST B — ADJACENCY REASONING")
    print("=" * 70)

    status, payload = curriculum_query(
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u06a9\u0646\u0627\u0631 "
        "\u0646\u0634\u06cc\u0645\u0646 \u0645\u0646\u0627\u0633\u0628 \u0627\u0633\u062a"
    )

    result = (payload or {}).get("result") or {}

    record(
        "B.1 positive adjacency reasoning works",
        status == 200
        and result.get("query_type") == "POSITIVE_RELATION"
        and result.get("verdict") == "ACCEPTABLE"
        and result.get("relation_type") == "NORMAL_CONNECTION",
        {"query_type": result.get("query_type"),
         "verdict": result.get("verdict"),
         "relation": result.get("relation_type")},
    )

    record(
        "B.2 the verdict carries a reason and provenance",
        bool(result.get("reason")) and bool(result.get("provenance")),
        {"reason": result.get("reason"),
         "provenance": result.get("provenance")},
    )

    # kitchen <-> dining is STRONG
    status, payload = curriculum_query(
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u06a9\u0646\u0627\u0631 "
        "\u063a\u0630\u0627\u062e\u0648\u0631\u06cc \u0645\u0646\u0627\u0633\u0628 \u0627\u0633\u062a"
    )

    strong = (payload or {}).get("result") or {}

    record(
        "B.3 kitchen <-> dining is a STRONG connection",
        strong.get("relation_type") == "STRONG_CONNECTION"
        and strong.get("verdict") == "ACCEPTABLE",
        {"relation": strong.get("relation_type")},
    )

    # ==================================================
    # C — NEGATIVE RELATIONSHIP
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST C — NEGATIVE RELATIONSHIP")
    print("=" * 70)

    status, payload = curriculum_query(
        "\u0648\u0631\u0648\u062f\u06cc \u0645\u0633\u062a\u0642\u06cc\u0645 \u0628\u0647 "
        "\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0645\u0646\u0627\u0633\u0628 \u0646\u06cc\u0633\u062a"
    )

    result = (payload or {}).get("result") or {}

    record(
        "C.1 negative relationship reasoning works",
        status == 200
        and result.get("query_type") == "NEGATIVE_RELATION"
        and result.get("verdict") == "CONFIRMED"
        and result.get("relation_type") == "AVOID_CONNECTION",
        {"query_type": result.get("query_type"),
         "verdict": result.get("verdict"),
         "relation": result.get("relation_type")},
    )

    record(
        "C.2 separation is required and privacy bands conflict",
        (result.get("separation") or {}).get("required") is True
        and result.get("privacy_relation") == "CONFLICT",
        {"separation": result.get("separation"),
         "privacy": result.get("privacy_relation")},
    )

    # bathroom -> living is FORBIDDEN
    status, payload = curriculum_query(
        "\u062d\u0645\u0627\u0645 \u0645\u0633\u062a\u0642\u06cc\u0645 \u0628\u0647 "
        "\u0646\u0634\u06cc\u0645\u0646 \u0645\u0646\u0627\u0633\u0628 \u0646\u06cc\u0633\u062a"
    )

    forbidden = (payload or {}).get("result") or {}

    record(
        "C.3 bathroom -> living room is FORBIDDEN",
        forbidden.get("relation_type") == "FORBIDDEN_CONNECTION"
        and forbidden.get("verdict") == "CONFIRMED",
        {"relation": forbidden.get("relation_type")},
    )

    # ==================================================
    # D — PERSIAN LANGUAGE
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST D — PERSIAN LANGUAGE")
    print("=" * 70)

    persian_cases = [
        ("\u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0641\u0636\u0627\u06cc \u062e\u0635\u0648\u0635\u06cc \u0627\u0633\u062a",
         "SPACE_CLASSIFICATION", "CORRECT"),
        ("\u0646\u0634\u06cc\u0645\u0646 \u0641\u0636\u0627\u06cc \u0639\u0645\u0648\u0645\u06cc \u0627\u0633\u062a",
         "SPACE_CLASSIFICATION", "CORRECT"),
        ("\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u06a9\u0646\u0627\u0631 \u0646\u0634\u06cc\u0645\u0646 \u0645\u0646\u0627\u0633\u0628 \u0627\u0633\u062a",
         "POSITIVE_RELATION", "ACCEPTABLE"),
        ("\u0648\u0631\u0648\u062f\u06cc \u0645\u0633\u062a\u0642\u06cc\u0645 \u0628\u0647 \u0627\u062a\u0627\u0642 \u062e\u0648\u0627\u0628 \u0645\u0646\u0627\u0633\u0628 \u0646\u06cc\u0633\u062a",
         "NEGATIVE_RELATION", "CONFIRMED"),
    ]

    failures = []

    for text, query_type, verdict in persian_cases:

        status, payload = curriculum_query(text)

        result = (payload or {}).get("result") or {}

        if (
            result.get("query_type") != query_type
            or result.get("verdict") != verdict
        ):

            failures.append(
                {"text": text, "query": result.get("query_type"),
                 "verdict": result.get("verdict")}
            )

    record(
        "D.1 Persian language works across all query types",
        not failures,
        failures,
    )

    # ==================================================
    # E — ENGLISH LANGUAGE
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST E — ENGLISH LANGUAGE")
    print("=" * 70)

    english_cases = [
        ("Bedroom is a private space", "SPACE_CLASSIFICATION", "CORRECT"),
        ("Kitchen next to the living room is appropriate",
         "POSITIVE_RELATION", "ACCEPTABLE"),
        ("The entrance should not open directly to the bedroom",
         "NEGATIVE_RELATION", "CONFIRMED"),
        ("Bathroom should not open directly to the living room",
         "NEGATIVE_RELATION", "CONFIRMED"),
    ]

    failures = []

    for text, query_type, verdict in english_cases:

        status, payload = curriculum_query(text)

        result = (payload or {}).get("result") or {}

        if (
            result.get("query_type") != query_type
            or result.get("verdict") != verdict
        ):

            failures.append(
                {"text": text, "query": result.get("query_type"),
                 "verdict": result.get("verdict")}
            )

    record(
        "E.1 English language works across all query types",
        not failures,
        failures,
    )

    # ==================================================
    # PART 4 — TEACHING COMPATIBILITY
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST T — TEACHING COMPATIBILITY (PART 4)")
    print("=" * 70)

    status, turn = chat(
        persian_project,
        "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645 \u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 "
        "\u0631\u0627 \u0628\u0647 \u062a\u0648 \u06cc\u0627\u062f \u0628\u062f\u0647\u0645",
    )

    response = (turn or {}).get("response") or {}

    teaching = (response or {}).get("teaching") or {}

    elicitation = teaching.get("elicitation") or {}

    text = str((response or {}).get("result") or "")

    record(
        "T.1 teaching a space asks which aspect (5 space aspects)",
        ((response or {}).get("turn_semantics") or {}).get("turn_kind")
        == "OFFER_TO_TEACH"
        and teaching.get("aspect_set") == "space"
        and len(elicitation.get("aspects") or []) == 5
        and "\u06a9\u062f\u0627\u0645 \u0628\u062e\u0634" in text,
        {"aspect_set": teaching.get("aspect_set"),
         "aspects": len(elicitation.get("aspects") or []),
         "text": text[:120]},
    )

    record(
        "T.2 the question names the space the user offered",
        "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647" in text,
        {"text": text[:120]},
    )

    record(
        "T.3 no candidate, no learning, never routed to EXECUTE",
        teaching.get("candidate") is None
        and teaching.get("routed_to_execute") is False
        and (response or {}).get("capability") != "EXECUTE",
        {"capability": (response or {}).get("capability")},
    )

    status, turn_en = chat(
        english_project, "I want to teach you about the bedroom"
    )

    response_en = (turn_en or {}).get("response") or {}

    teaching_en = (response_en or {}).get("teaching") or {}

    record(
        "T.4 English space teaching offer uses the space aspects",
        teaching_en.get("aspect_set") == "space"
        and len((teaching_en.get("elicitation") or {}).get("aspects")
                or []) == 5,
        {"aspect_set": teaching_en.get("aspect_set")},
    )

    # ==================================================
    # F — PROJECT ISOLATION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST F — PROJECT ISOLATION")
    print("=" * 70)

    chat(
        isolation_a,
        "\u0628\u0627\u0645 \u0628\u0627\u06cc\u062f \u0634\u06cc\u0628 "
        "\u0645\u0646\u0627\u0633\u0628 \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f",
    )

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
        "F.1 project A candidates never appear in project B",
        bool(list_a)
        and not (ids_a & ids_b)
        and all(c.get("project_id") == isolation_a for c in list_a)
        and all(c.get("project_id") == isolation_b for c in list_b),
        {"a": len(list_a), "b": len(list_b),
         "overlap": list(ids_a & ids_b)},
    )

    status, guard = http_json(
        CORE_API,
        "/api/conversation/knowledge/storage-guard?project_id="
        + persian_project,
    )

    guard_result = (guard or {}).get("result") or {}

    record(
        "F.2 teaching storage stays project-scoped, global memory clean",
        guard_result.get("global_memory_clean") is True
        and guard_result.get("teaching_storage_is_project_scoped") is True,
        {"clean": guard_result.get("global_memory_clean")},
    )

    # ==================================================
    # G — NO LEARNED KNOWLEDGE
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST G — NO LEARNED KNOWLEDGE CREATED AUTOMATICALLY")
    print("=" * 70)

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
        "G.1 learned_count is 0 in every project",
        learned_total == 0,
        {"learned_total": learned_total},
    )

    record(
        "G.2 every candidate status is a candidate status",
        not forbidden_found,
        {"forbidden": forbidden_found[:3]},
    )

    # the curriculum surfaces must not have written anything
    status, sources_after = http_json(
        CORE_API, "/api/conversation/knowledge/sources"
    )

    record(
        "G.3 the corpus was not written by the curriculum layer",
        ((sources_after or {}).get("result") or {}).get(
            "writes_performed"
        ) == 0
        and ((sources_after or {}).get("result") or {}).get(
            "read_only"
        ) is True,
        None,
    )

    status, promo = http_json(
        CORE_API, "/api/conversation/knowledge/promotion/status"
    )

    record(
        "G.4 promotion is still not implemented",
        ((promo or {}).get("result") or {}).get(
            "promotion_implemented"
        ) is False
        and ((promo or {}).get("result") or {}).get(
            "direct_candidate_to_knowledge_path"
        ) is False,
        None,
    )

    # ==================================================
    # PART 2 / 3 SURFACES OVER HTTP
    # ==================================================

    print("\n" + "=" * 70)
    print("  SURFACE CHECKS — SPACES / RELATIONS / PRIVACY")
    print("=" * 70)

    status, spaces = http_json(
        CORE_API, "/api/conversation/curriculum/spaces?category=PRIVATE"
    )

    record(
        "S.1 private spaces are queryable by category",
        status == 200 and (spaces or {}).get("count", 0) > 0,
        {"count": (spaces or {}).get("count")},
    )

    status, relations = http_json(
        CORE_API,
        "/api/conversation/curriculum/relations?relation_type="
        "FORBIDDEN_CONNECTION",
    )

    record(
        "S.2 forbidden relations are queryable",
        status == 200 and (relations or {}).get("count", 0) > 0,
        {"count": (relations or {}).get("count")},
    )

    status, privacy = http_json(
        CORE_API,
        "/api/conversation/curriculum/privacy?source="
        "%D8%A7%D8%AA%D8%A7%D9%82%20%D8%AE%D9%88%D8%A7%D8%A8&target="
        "%D9%88%D8%B1%D9%88%D8%AF%DB%8C",
    )

    evaluation = (privacy or {}).get("evaluation") or {}

    record(
        "S.3 privacy evaluation is served (bedroom / entrance)",
        status == 200
        and evaluation.get("relation_type") == "AVOID_CONNECTION"
        and (evaluation.get("separation") or {}).get("required") is True,
        {"relation": evaluation.get("relation_type")},
    )

    stop_core(process)

    # ==================================================
    # H — ZERO RENDER / COMFY / GEOMETRY / CAD / BIM / IFC
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST H — ZERO RENDER / COMFY / GEOMETRY / CAD / BIM / IFC")
    print("=" * 70)

    after_comfy = comfy_output_snapshot()

    record(
        "H.1 ComfyUI output directory unchanged",
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
        "H.2 no ComfyUI invocation (port 9)",
        not comfy_reachable or before_comfy == after_comfy,
        {"comfy_reachable": comfy_reachable},
    )

    scan = artifact_scan(DATA_ROOT)

    report["artifact_scan"] = scan

    report["geometry_outputs"] = scan["geometry_files"]

    record(
        "H.3 ZERO geometry / CAD / BIM / IFC artefacts produced",
        scan["geometry_files"] == 0,
        scan,
    )

    record(
        "H.4 ZERO render / image artefacts produced",
        scan["image_files"] == 0 and report["real_renders"] == 0,
        {"image_files": scan["image_files"]},
    )

    # ==================================================
    # REGRESSIONS — PHASES 01-09
    # ==================================================

    print("\n" + "=" * 70)
    print("  REGRESSION — PHASES 01-09")
    print("=" * 70)

    # Phase 09 acceptance is ALWAYS run in fast mode here: its nested
    # Voice 07 regression is executed once, at this level, just below.
    completed = subprocess.run(
        [sys.executable, PHASE09_ACCEPTANCE, "--fast"],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=10800,
    )

    report["phase09_regression"] = {
        "returncode": completed.returncode,
        "fast_mode": True,
        "tail": (completed.stdout or "")[-1200:],
    }

    record(
        "R.1 Phase 09 acceptance still green",
        completed.returncode == 0,
        {"returncode": completed.returncode,
         "tail": (completed.stdout or "")[-400:]},
    )

    # ---- Voice 07 regression, one level deep ----
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

    report["space_type_report"] = space_report

    report["adjacency_report"] = adjacency_report

    report["final_status"] = (
        "SPACE_ADJACENCY_10_PASS"
        if not failed
        else "SPACE_ADJACENCY_10_BLOCKED"
    )

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:

        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("  PHASE 10 ACCEPTANCE SUMMARY")
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
        "  %d/%d PASS  |  renders: %d  |  geometry: %d  |  spaces: %d"
        "  |  relations: %d"
        % (
            report["passed"],
            report["total"],
            report["real_renders"],
            report["geometry_outputs"],
            space_report["space_count"],
            adjacency_report["relation_count"],
        )
    )

    print("  FINAL STATUS:", report["final_status"])

    print("  REPORT:", REPORT_PATH)

    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
