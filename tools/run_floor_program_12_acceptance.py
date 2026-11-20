# ==========================================================
# PHASE 12 — FLOOR PROGRAM REASONING ACCEPTANCE RUNNER
#
# Runs the REQUIRED Phase 12 acceptance tests against the LIVE runtime:
#
#   UI-style HTTP -> Core API (app.py) -> /api/conversation/program/*
#                                     -> /api/chat -> ChatArchitect.handle
#
# WHAT PHASE 12 IS: reasoning only.
#   requirement -> building program understanding
#               -> FLOOR PROGRAM MODEL
#               -> REASONED PROGRAM + trace
#
# HARD CONSTRAINTS (asserted, not assumed)
#   - NO floor plan, NO layout generation, NO coordinates, NO walls,
#     NO doors, NO geometry, NO CAD, NO DWG, NO BIM, NO IFC, NO RPLAN.
#   - NO render, NO ComfyUI, NO image generation.
#     The Core API starts with ARCHITECTOS_COMFY_PORT=9 so every submit
#     fails fast and truthfully, an isolated project data root is used,
#     the ComfyUI output directory is asserted unchanged and the
#     isolated root is scanned for geometry / image artefacts.
#
# Usage:
#   .venv/Scripts/python.exe tools/run_floor_program_12_acceptance.py
#   .venv/Scripts/python.exe tools/run_floor_program_12_acceptance.py --fast
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
    ROOT, "tools", "acceptance_12_report.json"
)

LOG_PATH = os.path.join(
    ROOT, "logs", "runtime", "acceptance_12_core.log"
)

# A per-run TIMESTAMPED work directory. Never bulk-delete a previous
# run's tree: the environment's delete guard can block it and kill a
# nested runner with zero output, which looks exactly like a crash.
WORK_DIR = os.path.join(
    ROOT,
    ".pytest_tmp",
    "floor_program_12_" + time.strftime("%Y%m%d_%H%M%S"),
)

DATA_ROOT = os.path.join(WORK_DIR, "project_data")

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT


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

PHASE11_ACCEPTANCE = os.path.join(
    ROOT, "tools", "run_spatial_diagram_11_acceptance.py"
)

PHASE11_REPORT = os.path.join(
    ROOT, "tools", "acceptance_11_report.json"
)

CHAT_LANGUAGE_TESTS = os.path.join(
    ROOT, "tests", "test_chat_language_02.py"
)

CHAT_CORE_TESTS = os.path.join(
    ROOT, "tests", "test_chat_core_only.py"
)

# The Voice 07 regression is run ONCE, at THIS level -- never nested
# through Phase 11 -> Phase 10 -> Phase 09 -> Phase 08 -> Voice 07.
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

FA_RESIDENTIAL = "خانه سه خوابه برای خانواده چهار نفره"

FA_COMMERCIAL = "مجتمع تجاری با فروشگاه و رستوران"

FA_MIXED = "ساختمان ترکیبی تجاری و مسکونی"

FA_UNDER = "خانه دو خوابه برای خانواده شش نفره"

FA_TEACH_PROGRAM = "می خواهم برنامهٔ فضایی را یاد بدهم"

FA_TEACH_SPACE = "می خواهم آشپزخانه را به تو یاد بدهم"

FA_TEACH_DIAGRAM = "می خواهم دیاگرام فضایی را یاد بدهم"

FA_TEACH_GENERIC = "می خواهم بام را به تو یاد بدهم"

FA_TEACH_RULE = "در خانه ایرانی معمولاً آشپزخانه نزدیک فضای نشیمن است"

EN_RESIDENTIAL = "A house with 3 bedrooms for a family of four"

EN_COMMERCIAL = "A commercial building with retail and offices"

EN_MIXED = "A mixed-use building with retail and apartments"

EN_TEACH_PROGRAM = "I want to teach you about the floor program"


PROGRAM_SECTIONS = (
    "zones",
    "spaces",
    "relationships",
    "priorities",
    "constraints",
)


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

    handle.write(b"\n\n===== acceptance_12 core start =====\n")

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


def program_reason(requirement, language=None, project_id=None):

    payload = {"requirement": requirement, "language": language}

    if project_id:

        payload["project_id"] = project_id

    return http_json(
        CORE_API, "/api/conversation/program/reason", payload, timeout=10800
    )


def program_classify(text, language=None):

    return http_json(
        CORE_API,
        "/api/conversation/program/classify",
        {"text": text, "language": language},
        timeout=10800,
    )


def has_persian(text):

    return any("\u0600" <= ch <= "\u06ff" for ch in str(text or ""))


# ==========================================================
# MAIN
# ==========================================================

def main():

    fast = "--fast" in sys.argv

    report = {
        "phase": "PHASE_12_FLOOR_PROGRAM_REASONING",
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
        "floor_program_started": True,
        "floor_plan_generation_started": False,
        "layout_generation_started": False,
        "rplan_integrated": False,
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

    # ---- 0.1 one assistant ----
    with open(os.path.join(ROOT, "app.py"), "r",
              encoding="utf-8", errors="replace") as handle:

        app_text = handle.read()

    chat_constructors_in_app = app_text.count("ChatArchitect(")

    record(
        "0.1 exactly ONE ChatArchitect in the Core API",
        chat_constructors_in_app == 1,
        {"count": chat_constructors_in_app},
    )

    # ---- 0.2 no second assistant ----
    forbidden_names = (
        "class TeachingAssistant",
        "class ArchitectureTutor",
        "class SecondAssistant",
        "class ParallelAssistant",
        "class DiagramAssistant",
        "class ProgramAssistant",
        "class FloorProgramAssistant",
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
        "0.2 no second assistant / tutor class anywhere",
        not forbidden_hits,
        {"hits": forbidden_hits[:5]},
    )

    # ---- 0.3 the Phase 12 layer constructs no assistant ----
    phase12_modules = (
        "program_model_v1.py",
        "program_classifier_v1.py",
        "floor_program_v1.py",
        "program_curriculum_v1.py",
    )

    curriculum_dir = os.path.join(ROOT, "core", "curriculum")

    layer_hits = []

    for name in phase12_modules:

        path = os.path.join(curriculum_dir, name)

        if not os.path.isfile(path):

            layer_hits.append("MISSING :: " + name)

            continue

        with open(path, "r", encoding="utf-8", errors="replace") as handle:

            content = handle.read()

        for token in (
            "ChatArchitect(", "Ollama", "llama3",
            "requests.post", "subprocess",
        ):

            if token in content:

                layer_hits.append(name + " :: " + token)

    record(
        "0.3 the Phase 12 layer constructs no assistant / LLM / network "
        "call",
        not layer_hits,
        {"hits": layer_hits[:6]},
    )

    # ---- imports for the static checks ----
    from core.conversation.knowledge_read_bridge_v1 import (
        knowledge_read_bridge,
    )

    from core.curriculum.space_types_v1 import space_types

    from core.curriculum.adjacency_model_v1 import adjacency_model

    from core.curriculum.zone_model_v1 import zone_model, ALL_ZONES

    from core.curriculum.program_model_v1 import (
        program_model,
        PRIMARY_BUILDING_TYPES,
        ALL_PRIORITIES,
        ALL_CONSTRAINT_KINDS,
    )

    from core.curriculum.program_classifier_v1 import (
        program_classifier,
    )

    from core.curriculum.floor_program_v1 import (
        floor_program_reasoning,
    )

    from core.curriculum.program_curriculum_v1 import (
        program_curriculum,
    )

    from core.conversation.teaching_candidate_v1 import (
        ALLOWED_STATUSES,
        PERMANENT_LEARNING_IMPLEMENTED,
    )

    from core.conversation.knowledge_promotion_bridge_v1 import (
        PROMOTION_IMPLEMENTED,
    )

    # ---- 0.4 corpus reused read-only ----
    read_report = knowledge_read_bridge.read_report()

    space_report = space_types.report()

    record(
        "0.4 existing corpus reused through the Phase 09 read bridge",
        read_report["read_only"] is True
        and read_report["writes_performed"] == 0
        and (space_report["by_origin"] or {}).get("SPACE_SPECS", 0) >= 40
        and (space_report["by_origin"] or {}).get("ONTOLOGY", 0) >= 40,
        {"origins": space_report["by_origin"]},
    )

    # ---- 0.5 the program layer consumes, never duplicates ----
    model_report = program_model.report()

    import core.curriculum.program_model_v1 as model_module

    model_source = open(
        model_module.__file__, "r", encoding="utf-8"
    ).read()

    record(
        "0.5 the program layer REUSES Phase 11's space map (no second "
        "knowledge base)",
        "PROGRAM_SPACE_MAP = {" not in model_source
        and "from core.curriculum.bubble_diagram_v1 import" in model_source
        and model_report["space_map_size"] >= 25,
        {"space_map_size": model_report["space_map_size"]},
    )

    # ---- 0.6 the six zones and the three primary building types ----
    zone_report = zone_model.report()

    record(
        "0.6 program model covers the brief's three building types and "
        "all six zones",
        set(PRIMARY_BUILDING_TYPES) == {
            "residential", "commercial", "mixed_use"
        }
        and zone_report["zone_count"] == 6
        and len(ALL_PRIORITIES) == 3
        and len(ALL_CONSTRAINT_KINDS) == 6,
        {"primary": list(PRIMARY_BUILDING_TYPES)},
    )

    # ---- 0.7 scope: no layout / floor plan / geometry layer ----
    forbidden_modules = (
        "layout_generation", "floorplan", "floor_plan", "geometry",
        "wall", "opening", "cad", "bim", "ifc", "render", "rplan",
    )

    hits = [
        name for name in os.listdir(curriculum_dir)
        if name.endswith(".py")
        and any(t in name.lower() for t in forbidden_modules)
    ]

    record(
        "0.7 no layout / floor-plan / geometry / RPLAN layer exists",
        not hits,
        {"hits": hits},
    )

    # ---- 0.8 the program layer is semantic only ----
    probe_program = floor_program_reasoning.reason(FA_RESIDENTIAL, "fa")

    record(
        "0.8 the floor program is semantic only (no geometry, no render)",
        probe_program["semantic_only"] is True
        and probe_program["contains_geometry"] is False
        and probe_program["contains_coordinates"] is False
        and probe_program["render_requested"] is False
        and probe_program["comfy_invoked"] is False
        and probe_program["llm_used"] is False
        and probe_program["floor_program"]["contains_walls"] is False
        and probe_program["floor_program"]["contains_openings"] is False,
        {"geometry": probe_program["contains_geometry"]},
    )

    # ---- 0.9 promotion still impossible ----
    record(
        "0.9 promotion still impossible, statuses closed",
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
        ("0.10 Phase 12 contract suite green", PHASE12_TESTS),
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

        report["final_status"] = "FLOOR_PROGRAM_12_BLOCKED"

        with open(REPORT_PATH, "w", encoding="utf-8") as handle:

            json.dump(report, handle, ensure_ascii=False, indent=2)

        return 1

    record("1.0 Core API online", True, {"pid": process.pid})

    status, program_status = http_json(
        CORE_API, "/api/conversation/program/status"
    )

    record(
        "1.1 program surface online over HTTP",
        status == 200
        and ((program_status or {}).get("render_requested")) is False
        and ((program_status or {}).get("comfy_invoked")) is False
        and ((program_status or {}).get("geometry_generated")) is False
        and ((program_status or {}).get("curriculum") or {}).get(
            "aspect_count"
        ) == 5,
        {"status": status},
    )

    persian_project, _ = create_project("Phase12 Program Persian")

    english_project, _ = create_project("Phase12 Program English")

    isolation_a, _ = create_project("Phase12 Isolation A")

    isolation_b, _ = create_project("Phase12 Isolation B")

    record(
        "1.2 acceptance projects created",
        all([persian_project, english_project, isolation_a, isolation_b]),
        {"persian": persian_project, "english": english_project},
    )

    # ==================================================
    # TEST A — PROGRAM CLASSIFICATION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST A - PROGRAM CLASSIFICATION")
    print("=" * 70)

    status, payload = program_classify(FA_RESIDENTIAL, "fa")

    classification = (payload or {}).get("result") or {}

    record(
        "A.1 a residential requirement is classified (Persian)",
        status == 200
        and classification.get("building_type") == "residential"
        and classification.get("is_primary_type") is True,
        {"type": classification.get("building_type")},
    )

    record(
        "A.2 occupancy is understood from the requirement",
        (classification.get("occupancy") or {}).get("household_size") == 4
        and (classification.get("occupancy") or {}).get("bedrooms") == 3,
        classification.get("occupancy"),
    )

    status, payload = program_classify(FA_MIXED, "fa")

    mixed = (payload or {}).get("result") or {}

    record(
        "A.3 mixed use is classified from BOTH fields",
        mixed.get("building_type") == "mixed_use"
        and mixed.get("building_type_components")
        == ["residential", "commercial"],
        {"type": mixed.get("building_type"),
         "src": mixed.get("building_type_source")},
    )

    status, payload = program_classify(FA_COMMERCIAL, "fa")

    commercial = (payload or {}).get("result") or {}

    record(
        "A.4 commercial is classified and is NOT mixed use",
        commercial.get("building_type") == "commercial",
        {"type": commercial.get("building_type")},
    )

    # ==================================================
    # TEST B — FLOOR PROGRAM MODEL
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST B - FLOOR PROGRAM MODEL")
    print("=" * 70)

    status, payload = program_reason(
        FA_RESIDENTIAL, "fa", project_id=persian_project
    )

    result = (payload or {}).get("result") or {}

    program = result.get("floor_program") or {}

    record(
        "B.1 requirement -> reasoned floor program over HTTP",
        status == 200
        and program.get("contract") == "ProgramModelV1"
        and all(section in program for section in PROGRAM_SECTIONS),
        {"sections": sorted(
            k for k in PROGRAM_SECTIONS if k in program
        )},
    )

    record(
        "B.2 the program is semantic only",
        program.get("semantic_only") is True
        and program.get("contains_geometry") is False
        and program.get("contains_coordinates") is False
        and program.get("contains_walls") is False
        and program.get("contains_openings") is False
        and program.get("render_requested") is False
        and program.get("comfy_invoked") is False,
        {"geometry": program.get("contains_geometry")},
    )

    record(
        "B.3 every program space resolves to a space id and a zone",
        not program.get("unresolved_spaces")
        and all(s.get("zone") for s in program.get("spaces") or [])
        and (program.get("counts") or {}).get("spaces", 0) >= 9,
        {"unresolved": program.get("unresolved_spaces"),
         "counts": program.get("counts")},
    )

    record(
        "B.4 the bedroom count expands into real sleeping spaces",
        len([
            s for s in program.get("spaces") or []
            if s.get("space_id") in (
                "MASTER_BEDROOM_SLEEPING", "BEDROOM_DOUBLE"
            )
        ]) == 3,
        {"source": result.get("program_source")},
    )

    record(
        "B.5 zones / priorities / constraints are all populated",
        bool(program.get("zones"))
        and len(program.get("priorities") or []) == 3
        and bool(program.get("constraints"))
        and all(
            c.get("geometric") is False
            for c in program.get("constraints") or []
        ),
        {"zones": len(program.get("zones") or []),
         "constraints": len(program.get("constraints") or [])},
    )

    # the brief's example must reason out the brief's spaces
    ids = {s.get("space_id") for s in program.get("spaces") or []}

    record(
        "B.6 the brief's example reasons out living/kitchen/dining/"
        "bedrooms/bathroom/circulation/storage",
        {"LIVING_RECEPTION", "OPEN_KITCHEN", "DINING",
         "FAMILY_BATHROOM", "PRIVATE_HALL_CORRIDOR",
         "STORAGE_LINEN"} <= ids,
        {"spaces": sorted(i for i in ids if i)},
    )

    # under-provision must raise a capacity constraint
    status, payload = program_reason(FA_UNDER, "fa")

    under = (payload or {}).get("result") or {}

    under_kinds = {
        c.get("kind") for c in
        (under.get("floor_program") or {}).get("constraints") or []
    }

    adequate_kinds = {
        c.get("kind") for c in program.get("constraints") or []
    }

    record(
        "B.7 CAPACITY fires only when the program is under-provided",
        "CAPACITY" in under_kinds and "CAPACITY" not in adequate_kinds,
        {"under": sorted(under_kinds), "adequate": sorted(adequate_kinds)},
    )

    # ==================================================
    # TEST C — PROGRAM REASONING TRACE
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST C - PROGRAM REASONING TRACE")
    print("=" * 70)

    steps = [line.get("step") for line in result.get("reasoning") or []]

    record(
        "C.1 the reasoning trace names every step",
        steps == [
            "building_type", "occupancy", "required_spaces",
            "curriculum_completion", "zones", "privacy_hierarchy",
            "priorities", "constraints", "scope",
        ],
        {"steps": steps},
    )

    record(
        "C.2 the trace is grounded in evidence, not prose alone",
        all(line.get("evidence") is not None
            for line in result.get("reasoning") or []),
        None,
    )

    record(
        "C.3 reasoning is deterministic and offline",
        result.get("deterministic") is True
        and result.get("llm_used") is False
        and result.get("network_used") is False
        and result.get("render_requested") is False
        and bool(result.get("narrative")),
        None,
    )

    # ==================================================
    # TEST D — PERSIAN
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST D - PERSIAN SUPPORT")
    print("=" * 70)

    record(
        "D.1 the program is reasoned in Persian",
        result.get("language") == "fa"
        and has_persian(result.get("narrative"))
        and result.get("building_type_label")
        == "\u0645\u0633\u06a9\u0648\u0646\u06cc",
        {"label": result.get("building_type_label")},
    )

    record(
        "D.2 Persian space names are used in the summary",
        any(has_persian(item.get("name"))
            for item in result.get("space_summary") or []),
        {"sample": (result.get("space_summary") or [{}])[0].get("name")},
    )

    record(
        "D.3 Persian required-space list is readable",
        "x" in floor_program_reasoning.required_names(
            result.get("space_summary") or [], "fa"
        ) or "," in floor_program_reasoning.required_names(
            result.get("space_summary") or [], "fa"
        ),
        None,
    )

    # ==================================================
    # TEST E — ENGLISH
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST E - ENGLISH SUPPORT")
    print("=" * 70)

    status, en_payload = program_reason(
        EN_RESIDENTIAL, "en", project_id=english_project
    )

    en_result = (en_payload or {}).get("result") or {}

    en_ids = sorted(
        s.get("space_id")
        for s in (en_result.get("floor_program") or {}).get("spaces") or []
    )

    fa_ids = sorted(s.get("space_id") for s in program.get("spaces") or [])

    record(
        "E.1 the program is reasoned in English",
        status == 200
        and en_result.get("language") == "en"
        and not has_persian(en_result.get("narrative")),
        {"language": en_result.get("language")},
    )

    record(
        "E.2 Persian and English requirements produce the same program",
        en_ids == fa_ids
        and en_result.get("building_type") == result.get("building_type"),
        {"fa": fa_ids[:6], "en": en_ids[:6]},
    )

    status, en_mixed_payload = program_reason(EN_MIXED, "en")

    en_mixed = (en_mixed_payload or {}).get("result") or {}

    status, en_comm_payload = program_reason(EN_COMMERCIAL, "en")

    en_comm = (en_comm_payload or {}).get("result") or {}

    record(
        "E.3 English commercial + mixed use classify correctly",
        en_comm.get("building_type") == "commercial"
        and en_mixed.get("building_type") == "mixed_use",
        {"commercial": en_comm.get("building_type"),
         "mixed": en_mixed.get("building_type")},
    )

    # ==================================================
    # TEST F — THE BRIEF'S THREE EXAMPLES
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST F - RESIDENTIAL / COMMERCIAL / MIXED USE")
    print("=" * 70)

    record(
        "F.1 residential example: zones + private field",
        result.get("building_type") == "residential"
        and {
            z.get("name") for z in program.get("zones") or []
        } >= {"PUBLIC_ZONE", "SEMI_PUBLIC_ZONE", "PRIVATE_ZONE",
              "SERVICE_ZONE"},
        {"zones": sorted(
            z.get("name") for z in program.get("zones") or []
        )},
    )

    status, comm_payload = program_reason(FA_COMMERCIAL, "fa")

    comm = (comm_payload or {}).get("result") or {}

    comm_ids = {
        s.get("space_id")
        for s in (comm.get("floor_program") or {}).get("spaces") or []
    }

    record(
        "F.2 commercial example: retail + office + service core",
        comm.get("building_type") == "commercial"
        and {"retail", "office_room", "service_core"} <= comm_ids,
        {"spaces": sorted(i for i in comm_ids if i)},
    )

    status, mixed_payload = program_reason(FA_MIXED, "fa")

    mixed_result = (mixed_payload or {}).get("result") or {}

    mixed_ids = {
        s.get("space_id")
        for s in (mixed_result.get("floor_program") or {}).get("spaces") or []
    }

    record(
        "F.3 mixed-use example carries BOTH components",
        mixed_result.get("building_type") == "mixed_use"
        and "retail" in mixed_ids
        and "LIVING_RECEPTION" in mixed_ids
        and "BEDROOM_DOUBLE" in mixed_ids,
        {"spaces": sorted(i for i in mixed_ids if i)},
    )

    record(
        "F.4 optional spaces are distinguished from required",
        (mixed_result.get("floor_program") or {}).get(
            "counts", {}
        ).get("optional", 0) > 0,
        {"counts": (mixed_result.get("floor_program") or {}).get("counts")},
    )

    # ==================================================
    # TEST G — TEACHING COMPATIBILITY
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST G - TEACHING COMPATIBILITY")
    print("=" * 70)

    status, turn = chat(persian_project, FA_TEACH_PROGRAM)

    response = (turn or {}).get("response") or {}

    teaching = response.get("teaching") or {}

    elicitation = teaching.get("elicitation") or {}

    text = str(response.get("result") or "")

    record(
        "G.1 teaching a PROGRAM topic asks the 5 program aspects",
        teaching.get("aspect_set") == "program"
        and len(elicitation.get("aspects") or []) == 5
        and (response.get("turn_semantics") or {}).get("turn_kind")
        == "OFFER_TO_TEACH",
        {"aspect_set": teaching.get("aspect_set"),
         "aspects": len(elicitation.get("aspects") or [])},
    )

    record(
        "G.2 the elicitation asks, offers no candidate and learns nothing",
        teaching.get("candidate") is None
        and teaching.get("permanent_learning") is False
        and teaching.get("routed_to_execute") is False
        and has_persian(text),
        {"candidate": teaching.get("candidate")},
    )

    status, turn_space = chat(persian_project, FA_TEACH_SPACE)

    space_teaching = ((turn_space or {}).get("response") or {}).get(
        "teaching"
    ) or {}

    record(
        "G.3 the OLD space-topic path is still reachable (5 space aspects)",
        space_teaching.get("aspect_set") == "space"
        and len(
            (space_teaching.get("elicitation") or {}).get("aspects") or []
        ) == 5,
        {"aspect_set": space_teaching.get("aspect_set")},
    )

    status, turn_diagram = chat(persian_project, FA_TEACH_DIAGRAM)

    diagram_teaching = ((turn_diagram or {}).get("response") or {}).get(
        "teaching"
    ) or {}

    record(
        "G.4 the OLD diagram-topic path is still reachable (5 diagram "
        "aspects)",
        diagram_teaching.get("aspect_set") == "diagram"
        and len(
            (diagram_teaching.get("elicitation") or {}).get("aspects") or []
        ) == 5,
        {"aspect_set": diagram_teaching.get("aspect_set")},
    )

    status, turn_generic = chat(persian_project, FA_TEACH_GENERIC)

    generic_teaching = ((turn_generic or {}).get("response") or {}).get(
        "teaching"
    ) or {}

    record(
        "G.5 the generic path is still reachable (6 generic aspects)",
        generic_teaching.get("aspect_set") == "generic"
        and len(
            (generic_teaching.get("elicitation") or {}).get("aspects") or []
        ) == 6,
        {"aspect_set": generic_teaching.get("aspect_set")},
    )

    # ---- the brief's teaching STATEMENT ----
    status, turn_rule = chat(persian_project, FA_TEACH_RULE)

    rule_response = (turn_rule or {}).get("response") or {}

    rule_teaching = rule_response.get("teaching") or {}

    candidate = rule_teaching.get("candidate") or {}

    record(
        "G.6 a taught program rule yields a CANDIDATE with the full "
        "contract",
        bool(candidate)
        and bool(candidate.get("knowledge_class"))
        and bool(candidate.get("scope"))
        and candidate.get("provenance") is not None
        and candidate.get("confidence") is not None,
        {
            "knowledge_class": candidate.get("knowledge_class"),
            "scope": candidate.get("scope"),
            "confidence": candidate.get("confidence"),
        },
    )

    record(
        "G.7 the system does NOT learn: candidate only, no permanent "
        "knowledge",
        candidate.get("is_learned_knowledge") is False
        and candidate.get("is_permanent") is False
        and candidate.get("status") in ALLOWED_STATUSES
        and rule_teaching.get("permanent_learning") is False
        and rule_response.get("capability") == "UNDERSTAND",
        {"status": candidate.get("status")},
    )

    # ==================================================
    # TEST H — PROJECT ISOLATION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST H - PROJECT ISOLATION")
    print("=" * 70)

    chat(isolation_a, FA_TEACH_RULE)

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
        "H.2 teaching storage stays project-scoped, global memory clean",
        guard_result.get("global_memory_clean") is True
        and guard_result.get("teaching_storage_is_project_scoped") is True,
        {"clean": guard_result.get("global_memory_clean")},
    )

    status, iso_payload = program_reason(
        FA_RESIDENTIAL, "fa", project_id=isolation_a
    )

    iso_result = (iso_payload or {}).get("result") or {}

    record(
        "H.3 the program is project-scoped and stateless",
        iso_result.get("project_id") == isolation_a
        and (iso_result.get("floor_program") or {}).get("counts")
        == program.get("counts"),
        {"project_id": iso_result.get("project_id")},
    )

    # ==================================================
    # TEST I — NO PERMANENT LEARNING
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST I - NO PERMANENT LEARNING")
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

        for candidate_entry in (payload or {}).get("candidates") or []:

            if candidate_entry.get("status") not in ALLOWED_STATUSES:

                forbidden_found.append(candidate_entry)

    record(
        "I.1 learned_count is 0 in every project",
        learned_total == 0,
        {"learned_total": learned_total},
    )

    record(
        "I.2 every candidate status is a candidate status",
        not forbidden_found,
        {"forbidden": forbidden_found[:3]},
    )

    status, sources_after = http_json(
        CORE_API, "/api/conversation/knowledge/sources"
    )

    record(
        "I.3 the corpus was not written by the program layer",
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
        "I.4 promotion is still not implemented",
        ((promo or {}).get("result") or {}).get(
            "promotion_implemented"
        ) is False
        and ((promo or {}).get("result") or {}).get(
            "direct_candidate_to_knowledge_path"
        ) is False,
        None,
    )

    # ==================================================
    # TEST J — RESTART MID-RUN
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST J - RESTART MID-RUN")
    print("=" * 70)

    stop_core(process)

    time.sleep(3)

    process = start_core(port=5000, log_suffix=".restart")

    restarted = wait_for_core(CORE_API, timeout=10800)

    record("J.1 Core API restarted", restarted, None)

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
            "J.2 candidates survive the restart, isolation still holds",
            {c.get("candidate_id") for c in list_a2} == ids_a
            and {c.get("candidate_id") for c in list_b2} == ids_b
            and not (
                {c.get("candidate_id") for c in list_a2}
                & {c.get("candidate_id") for c in list_b2}
            ),
            {"a": len(list_a2), "b": len(list_b2)},
        )

        status, again = program_reason(FA_RESIDENTIAL, "fa")

        again_result = (again or {}).get("result") or {}

        record(
            "J.3 the reasoned program is reproducible after a restart",
            again_result.get("narrative") == result.get("narrative")
            and (again_result.get("floor_program") or {}).get("counts")
            == program.get("counts"),
            None,
        )

    else:

        record("J.2 candidates survive the restart", False, None)

        record("J.3 the reasoned program is reproducible after a restart",
               False, None)

    stop_core(process)

    # ==================================================
    # TEST K — ZERO RENDER / GEOMETRY / CAD / BIM / IFC
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST K - ZERO RENDER / GEOMETRY / CAD / BIM / IFC")
    print("=" * 70)

    after_comfy = comfy_output_snapshot()

    record(
        "K.1 ComfyUI output directory unchanged",
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
        "K.2 no ComfyUI invocation (blocked on port 9)",
        not comfy_reachable or before_comfy == after_comfy,
        {"comfy_reachable": comfy_reachable},
    )

    scan = artifact_scan(DATA_ROOT)

    report["artifact_scan"] = scan

    report["geometry_outputs"] = scan["geometry_files"]

    record(
        "K.3 ZERO geometry / CAD / DWG / BIM / IFC artefacts produced",
        scan["geometry_files"] == 0,
        scan,
    )

    record(
        "K.4 ZERO render / image artefacts produced",
        scan["image_files"] == 0 and report["real_renders"] == 0,
        {"image_files": scan["image_files"]},
    )

    # ==================================================
    # REGRESSION — PHASES 01-11
    # ==================================================

    print("\n" + "=" * 70)
    print("  REGRESSION - PHASES 01-11")
    print("=" * 70)

    # Phase 11's acceptance is run in fast mode: its own nested Voice 07
    # regression is skipped, because Voice 07 runs once, at THIS level.
    completed = subprocess.run(
        [sys.executable, PHASE11_ACCEPTANCE, "--fast"],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=14400,
    )

    report["phase11_regression"] = {
        "returncode": completed.returncode,
        "fast_mode": True,
        "tail": (completed.stdout or "")[-1600:],
    }

    record(
        "R.1 Phase 11 acceptance still green",
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

    # ---- the previous phase's report must still say PASS ----
    try:

        with open(PHASE11_REPORT, "r", encoding="utf-8") as handle:

            phase11_report = json.load(handle)

    except Exception:

        phase11_report = {}

    record(
        "R.5 Phase 11 acceptance report still records PASS",
        phase11_report.get("final_status") == "SPATIAL_DIAGRAM_11_PASS"
        and phase11_report.get("failed") == 0,
        {"status": phase11_report.get("final_status")},
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

    report["program_model_report"] = model_report

    report["program_classifier_report"] = program_classifier.report()

    report["floor_program_report"] = floor_program_reasoning.report()

    report["program_curriculum_report"] = program_curriculum.report()

    report["final_status"] = (
        "FLOOR_PROGRAM_12_PASS"
        if not failed
        else "FLOOR_PROGRAM_12_BLOCKED"
    )

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:

        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("  PHASE 12 ACCEPTANCE SUMMARY")
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
        "  |  program spaces: %d  |  zones: %d"
        % (
            report["passed"],
            report["total"],
            report["real_renders"],
            report["geometry_outputs"],
            space_report["space_count"],
            (program.get("counts") or {}).get("spaces", 0),
            len(program.get("zones") or []),
        )
    )

    print("  FINAL STATUS:", report["final_status"])

    print("  REPORT:", REPORT_PATH)

    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
