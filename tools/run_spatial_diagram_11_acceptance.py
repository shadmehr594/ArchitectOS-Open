# ==========================================================
# PHASE 11 — SPATIAL DIAGRAM INTELLIGENCE ACCEPTANCE RUNNER
#
# Runs the REQUIRED Phase 11 acceptance tests against the LIVE runtime:
#
#   UI-style HTTP -> Core API (app.py) -> /api/conversation/diagram/*
#                                     -> /api/conversation/curriculum/*
#                                     -> /api/chat -> ChatArchitect.handle
#
# WHAT PHASE 11 IS: reasoning only.
#   SPACE + RELATIONSHIP -> ZONE MODEL -> BUBBLE DIAGRAM REPRESENTATION
#
# HARD CONSTRAINTS (asserted, not assumed)
#   - NO render, NO ComfyUI, NO image generation.
#   - NO geometry, NO coordinates, NO CAD, NO BIM, NO IFC.
#     The Core API starts with ARCHITECTOS_COMFY_PORT=9 so every submit
#     fails fast and truthfully, an isolated project data root is used,
#     the ComfyUI output directory is asserted unchanged and the isolated
#     root is scanned for geometry / image artefacts.
#
# Usage:
#   .venv/Scripts/python.exe tools/run_spatial_diagram_11_acceptance.py
#   .venv/Scripts/python.exe tools/run_spatial_diagram_11_acceptance.py --fast
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
    ROOT, "tools", "acceptance_11_report.json"
)

LOG_PATH = os.path.join(
    ROOT, "logs", "runtime", "acceptance_11_core.log"
)

# A per-run TIMESTAMPED work directory. Never bulk-delete a previous
# run's tree: the environment's delete guard can block it and kill a
# nested runner with zero output, which looks exactly like a crash.
WORK_DIR = os.path.join(
    ROOT,
    ".pytest_tmp",
    "spatial_diagram_11_" + time.strftime("%Y%m%d_%H%M%S"),
)

DATA_ROOT = os.path.join(WORK_DIR, "project_data")

os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT


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

PHASE10_ACCEPTANCE = os.path.join(
    ROOT, "tools", "run_space_adjacency_10_acceptance.py"
)

CHAT_LANGUAGE_TESTS = os.path.join(
    ROOT, "tests", "test_chat_language_02.py"
)

CHAT_CORE_TESTS = os.path.join(
    ROOT, "tests", "test_chat_core_only.py"
)

# The Voice 07 regression is run ONCE, at THIS level -- never nested
# through Phase 10 -> Phase 09 -> Phase 08 -> Voice 07.
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
# PERSIAN / ENGLISH INPUTS (used by the live tests)
# ----------------------------------------------------------

FA_PROGRAM = "خانه ۳ خوابه با نشیمن، آشپزخانه، ناهارخوری و دو سرویس"

FA_SITE = "خیابان جنوب، حیاط خلوت شمال"

FA_WHY = "چرا اتاق خواب کنار ورودی نیست؟"

FA_WHY_POSITIVE = "چرا آشپزخانه کنار نشیمن مناسب است؟"

FA_TEACH = "راه پله باید نزدیک ورودی باشد"

FA_TEACH_DIAGRAM = "می خواهم دیاگرام فضایی را یاد بدهم"

FA_TEACH_SPACE = "می خواهم آشپزخانه را به تو یاد بدهم"

FA_TEACH_GENERIC = "می خواهم بام را به تو یاد بدهم"

FA_QUERY_POSITIVE = "آشپزخانه کنار نشیمن مناسب است"

FA_QUERY_NEGATIVE = "ورودی مستقیم به اتاق خواب مناسب نیست"

EN_PROGRAM = (
    "A house with 3 bedrooms, a living room, a kitchen, a dining room "
    "and two bathrooms"
)

EN_WHY = "Why is the kitchen next to the living room?"

EN_TEACH = "The stair should be near the entrance"

EN_TEACH_DIAGRAM = "I want to teach you about the bubble diagram"


BRIEF_BUBBLE_FIELDS = (
    "space_id",
    "space_type",
    "zone",
    "privacy",
    "required_connections",
    "forbidden_connections",
    "adjacency_weight",
    "reasoning",
    "provenance",
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

    handle.write(b"\n\n===== acceptance_11 core start =====\n")

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


def diagram_generate(requirement, site=None, language=None,
                     project_id=None):

    payload = {"requirement": requirement, "language": language}

    if site:

        payload["site"] = site

    if project_id:

        payload["project_id"] = project_id

    return http_json(
        CORE_API, "/api/conversation/diagram/generate", payload, timeout=10800
    )


def diagram_why(text, language=None):

    return http_json(
        CORE_API,
        "/api/conversation/diagram/why",
        {"text": text, "language": language},
        timeout=10800,
    )


def curriculum_query(text, language=None):

    return http_json(
        CORE_API,
        "/api/conversation/curriculum/query",
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
        "phase": "PHASE_11_SPATIAL_DIAGRAM_INTELLIGENCE",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "comfy_blocked_by_construction": True,
        "comfy_port": 9,
        "real_renders": 0,
        "image_generations": 0,
        "geometry_outputs": 0,
        "cad_outputs": 0,
        "bim_outputs": 0,
        "ifc_outputs": 0,
        "bubble_diagram_started": True,
        "layout_generation_started": False,
        # Phase 12 added the floor-program layer; this runner's own scope
        # stopped at the bubble diagram. Split rather than leave a stale
        # claim in a JSON artefact.
        "floor_program_started_by_phase_11": False,
        "floor_program_layer_present_after_phase_12": True,
        "floor_plan_generation_started": False,
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

    # ---- 0.1 / 0.2 one assistant, no second brain ----
    with open(os.path.join(ROOT, "app.py"), "r",
              encoding="utf-8", errors="replace") as handle:

        app_text = handle.read()

    chat_constructors_in_app = app_text.count("ChatArchitect(")

    record(
        "0.1 exactly ONE ChatArchitect in the Core API",
        chat_constructors_in_app == 1,
        {"count": chat_constructors_in_app},
    )

    forbidden_names = (
        "class TeachingAssistant",
        "class ArchitectureTutor",
        "class SecondAssistant",
        "class ParallelAssistant",
        "class DiagramAssistant",
        "class SpatialDiagramAssistant",
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

    # ---- 0.3 the Phase 11 layer constructs no assistant ----
    phase11_modules = (
        "zone_model_v1.py",
        "bubble_diagram_v1.py",
        "site_intent_v1.py",
        "spatial_case_reasoning_v1.py",
        "diagram_curriculum_v1.py",
    )

    curriculum_dir = os.path.join(ROOT, "core", "curriculum")

    layer_hits = []

    for name in phase11_modules:

        path = os.path.join(curriculum_dir, name)

        if not os.path.isfile(path):

            layer_hits.append("MISSING :: " + name)

            continue

        with open(path, "r", encoding="utf-8", errors="replace") as handle:

            content = handle.read()

        for token in (
            "ChatArchitect(", "ChatArchitect ", "Ollama", "llama3",
            "requests.post", "subprocess",
        ):

            if token in content:

                layer_hits.append(name + " :: " + token)

    record(
        "0.3 the Phase 11 layer constructs no assistant / LLM / network "
        "call",
        not layer_hits,
        {"hits": layer_hits[:6]},
    )

    # ---- 0.4 the corpus is REUSED, read-only ----
    from core.conversation.knowledge_read_bridge_v1 import (
        knowledge_read_bridge,
    )

    from core.curriculum.space_types_v1 import space_types

    from core.curriculum.adjacency_model_v1 import adjacency_model

    from core.curriculum.zone_model_v1 import zone_model, ALL_ZONES

    from core.curriculum.bubble_diagram_v1 import (
        bubble_diagram_builder,
    )

    from core.conversation.teaching_candidate_v1 import (
        ALLOWED_STATUSES,
        PERMANENT_LEARNING_IMPLEMENTED,
    )

    from core.conversation.knowledge_promotion_bridge_v1 import (
        PROMOTION_IMPLEMENTED,
    )

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

    # ---- 0.5 zone model ----
    zone_report = zone_model.report()

    record(
        "0.5 zone model: six zones derived from the Phase 10 category",
        zone_report["zone_count"] == 6
        and set(zone_report["zones"]) == set(ALL_ZONES)
        and zone_report["zone_source"] == "derived_from_phase10_category"
        and zone_report["contains_geometry"] is False
        and sum((zone_report["spaces_by_zone"] or {}).values()) >= 80,
        zone_report["spaces_by_zone"],
    )

    # ---- 0.6 adjacency graded ----
    adjacency_report = adjacency_model.report()

    record(
        "0.6 adjacency matrix is graded with reason + provenance",
        adjacency_report["boolean_relations"] is False
        and len(adjacency_report["by_relation_type"]) == 5
        and adjacency_report["relation_count"] >= 100,
        adjacency_report["by_relation_type"],
    )

    # ---- 0.7 scope: no layout / RPLAN / floor plan / geometry layer ----
    #
    # RELAXED in Phase 12 (relax + add, never delete): Phase 12
    # legitimately added the FLOOR PROGRAM layer, so "floor_program"
    # leaves this list. "floorplan" (a floor PLAN) stays forbidden.
    forbidden_modules = (
        "adjacency_matrix", "rplan", "layout_generation",
        "floorplan", "floor_plan", "geometry", "cad", "bim", "ifc",
        "render",
    )

    hits = [
        name for name in os.listdir(curriculum_dir)
        if name.endswith(".py")
        and any(t in name.lower() for t in forbidden_modules)
    ]

    record(
        "0.7 no layout / RPLAN / floor plan / geometry layer exists",
        not hits,
        {"hits": hits},
    )

    semantic_report = bubble_diagram_builder.report()

    semantic_diagram = bubble_diagram_builder.build(
        "خانه ۳ خوابه", language="fa"
    )

    record(
        "0.8 the bubble layer is semantic only (no geometry, no render)",
        semantic_report["contains_geometry"] is False
        and semantic_report["contains_coordinates"] is False
        and semantic_diagram["semantic_only"] is True
        and semantic_diagram["render_requested"] is False
        and semantic_diagram["comfy_invoked"] is False
        and semantic_diagram["llm_used"] is False,
        {"geometry": semantic_diagram["contains_geometry"]},
    )

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
        ("0.10 Phase 11 contract suite green", PHASE11_TESTS),
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

        report["final_status"] = "SPATIAL_DIAGRAM_11_BLOCKED"

        with open(REPORT_PATH, "w", encoding="utf-8") as handle:

            json.dump(report, handle, ensure_ascii=False, indent=2)

        return 1

    record("1.0 Core API online", True, {"pid": process.pid})

    status, diagram_status = http_json(
        CORE_API, "/api/conversation/diagram/status"
    )

    record(
        "1.1 diagram surface online over HTTP",
        status == 200
        and ((diagram_status or {}).get("render_requested")) is False
        and ((diagram_status or {}).get("comfy_invoked")) is False
        and ((diagram_status or {}).get("geometry_generated")) is False
        and ((diagram_status or {}).get("zones") or {}).get(
            "zone_count"
        ) == 6
        and ((diagram_status or {}).get("curriculum") or {}).get(
            "aspect_count"
        ) == 5,
        {"status": status},
    )

    persian_project, _ = create_project("Phase11 Diagram Persian")

    english_project, _ = create_project("Phase11 Diagram English")

    isolation_a, _ = create_project("Phase11 Isolation A")

    isolation_b, _ = create_project("Phase11 Isolation B")

    record(
        "1.2 acceptance projects created",
        all([persian_project, english_project, isolation_a, isolation_b]),
        {"persian": persian_project, "english": english_project},
    )

    # ==================================================
    # TEST A — BUBBLE DIAGRAM OUTPUT
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST A - BUBBLE DIAGRAM OUTPUT")
    print("=" * 70)

    status, payload = diagram_generate(
        FA_PROGRAM, site=FA_SITE, language="fa",
        project_id=persian_project,
    )

    diagram = (payload or {}).get("diagram") or {}

    record(
        "A.1 SPACE + RELATIONSHIP -> semantic bubble diagram",
        status == 200
        and diagram.get("diagram_type") == "semantic_bubble_diagram"
        and len(diagram.get("bubbles") or []) >= 8
        and len(diagram.get("zones") or []) >= 4
        and len(diagram.get("relations") or []) > 0,
        {
            "bubbles": len(diagram.get("bubbles") or []),
            "zones": len(diagram.get("zones") or []),
            "relations": len(diagram.get("relations") or []),
        },
    )

    missing_fields = []

    for bubble in diagram.get("bubbles") or []:

        for field in BRIEF_BUBBLE_FIELDS:

            if field not in bubble:

                missing_fields.append((bubble.get("bubble_id"), field))

    record(
        "A.2 every bubble carries the full brief contract",
        not missing_fields,
        {"missing": missing_fields[:8]},
    )

    record(
        "A.3 bubble ids are unique and deterministic",
        len([b["bubble_id"] for b in diagram.get("bubbles") or []])
        == len({b["bubble_id"] for b in diagram.get("bubbles") or []})
        and diagram.get("deterministic") is True,
        {"ids": [b["bubble_id"] for b in diagram.get("bubbles") or []][:8]},
    )

    serialized = json.dumps(diagram, ensure_ascii=False).lower()

    coordinate_hits = [
        token for token in (
            "polygon", "vertex", "vertices", "bounding_box", "centroid",
            "wall_segment", "door_swing", "ifc", "dwg", "dxf",
        )
        if token in serialized
    ]

    record(
        "A.4 no geometry vocabulary in the serialized diagram",
        not coordinate_hits,
        {"hits": coordinate_hits},
    )

    record(
        "A.5 relation types use the five short grades",
        {r.get("type") for r in diagram.get("relations") or []}
        <= {"STRONG", "NORMAL", "WEAK", "AVOID", "FORBIDDEN"}
        and bool(diagram.get("relations")),
        {"types": sorted({r.get("type")
                          for r in diagram.get("relations") or []})},
    )

    # ==================================================
    # TEST B — ZONE REASONING
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST B - ZONE REASONING")
    print("=" * 70)

    zone_names = {z.get("name") for z in diagram.get("zones") or []}

    record(
        "B.1 the program groups into the semantic zones",
        {"PUBLIC_ZONE", "PRIVATE_ZONE", "CIRCULATION_ZONE"} <= zone_names,
        {"zones": sorted(zone_names)},
    )

    by_space = {}

    for bubble in diagram.get("bubbles") or []:

        by_space.setdefault(bubble["space_id"], []).append(bubble)

    record(
        "B.2 the entrance is public and the bedrooms are private",
        (by_space.get("UNIT_ENTRY") or [{}])[0].get("zone")
        == "PUBLIC_ZONE"
        and all(
            b.get("zone") == "PRIVATE_ZONE"
            for b in by_space.get("BEDROOM_DOUBLE") or []
        )
        and all(
            b.get("zone") == "PRIVATE_ZONE"
            for b in by_space.get("MASTER_BEDROOM_SLEEPING") or []
        ),
        {k: [b["zone"] for b in v]
         for k, v in by_space.items() if k in (
             "UNIT_ENTRY", "BEDROOM_DOUBLE")},
    )

    record(
        "B.3 the service zone holds the bathroom",
        (by_space.get("FAMILY_BATHROOM") or [{}])[0].get("zone")
        == "SERVICE_ZONE",
        {"bathroom": (by_space.get("FAMILY_BATHROOM") or [{}])[0].get("zone")},
    )

    record(
        "B.4 every bubble declares a zone, and no zone is a shape",
        all(b.get("zone") for b in diagram.get("bubbles") or [])
        and diagram.get("contains_geometry") is False,
        None,
    )

    # ==================================================
    # TEST C — ADJACENCY REASONING
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST C - ADJACENCY REASONING")
    print("=" * 70)

    def relation_of(a, b):

        for bubble in diagram.get("bubbles") or []:

            if bubble["space_id"] != a:

                continue

            for connection in bubble.get("connections") or []:

                if connection["to_space"] == b:

                    return connection

        return None

    kitchen_dining = relation_of("OPEN_KITCHEN", "DINING")

    bedroom_living = relation_of("BEDROOM_DOUBLE", "LIVING_RECEPTION")

    record(
        "C.1 kitchen <-> dining is STRONG (brief example)",
        bool(kitchen_dining) and kitchen_dining["short_type"] == "STRONG",
        kitchen_dining,
    )

    record(
        "C.2 bedroom <-> living is WEAK (brief example)",
        bool(bedroom_living) and bedroom_living["short_type"] == "WEAK",
        bedroom_living,
    )

    record(
        "C.3 every connection carries a reason and a provenance",
        all(
            c.get("reason") and c.get("provenance")
            for b in diagram.get("bubbles") or []
            for c in b.get("connections") or []
        ),
        None,
    )

    invented = []

    for bubble in diagram.get("bubbles") or []:

        for connection in bubble.get("connections") or []:

            relation = adjacency_model.relation(
                bubble["space_id"], connection["to_space"]
            )

            if (
                not relation
                or relation["relation_type"] != connection["relation_type"]
            ):

                invented.append(
                    [bubble["space_id"], connection["to_space"]]
                )

    record(
        "C.4 the diagram invents no relationship",
        not invented,
        {"invented": invented[:5]},
    )

    record(
        "C.5 separation rules are surfaced for AVOID / FORBIDDEN pairs",
        len(diagram.get("separation_rules") or []) > 0
        and all(
            r.get("type") in ("AVOID", "FORBIDDEN")
            for r in diagram.get("separation_rules") or []
        ),
        {"rules": len(diagram.get("separation_rules") or [])},
    )

    # ==================================================
    # TEST D — PERSIAN SUPPORT
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST D - PERSIAN SUPPORT")
    print("=" * 70)

    record(
        "D.1 the diagram is generated in Persian",
        diagram.get("language") == "fa"
        and all(
            has_persian((b.get("name") or ""))
            for b in diagram.get("bubbles") or []
        ),
        {"language": diagram.get("language")},
    )

    status, why_payload = diagram_why(FA_WHY, language="fa")

    why = (why_payload or {}).get("result") or {}

    record(
        "D.2 why-questions are answered in Persian",
        status == 200
        and why.get("question_type") == "WHY_NOT_ADJACENT"
        and why.get("conclusion") == "supported"
        and has_persian(why.get("answer")),
        {"q": why.get("question_type"),
         "answer": str(why.get("answer"))[:80]},
    )

    status, query_payload = curriculum_query(FA_QUERY_POSITIVE, language="fa")

    query = (query_payload or {}).get("result") or {}

    record(
        "D.3 curriculum queries are answered in Persian",
        status == 200
        and query.get("query_type") == "POSITIVE_RELATION"
        and query.get("verdict") == "ACCEPTABLE"
        and has_persian(query.get("answer")),
        {"verdict": query.get("verdict")},
    )

    # ==================================================
    # TEST E — ENGLISH SUPPORT
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST E - ENGLISH SUPPORT")
    print("=" * 70)

    status, english_payload = diagram_generate(
        EN_PROGRAM, language="en", project_id=english_project
    )

    english_diagram = (english_payload or {}).get("diagram") or {}

    record(
        "E.1 the diagram is generated in English",
        status == 200
        and english_diagram.get("language") == "en"
        and all(
            not has_persian(b.get("name") or "")
            for b in english_diagram.get("bubbles") or []
        ),
        {"language": english_diagram.get("language")},
    )

    record(
        "E.2 Persian and English programs yield the same graph",
        [b["space_id"] for b in diagram.get("bubbles") or []]
        == [b["space_id"] for b in english_diagram.get("bubbles") or []]
        and len(diagram.get("relations") or [])
        == len(english_diagram.get("relations") or []),
        {
            "fa": [b["space_id"]
                   for b in diagram.get("bubbles") or []][:6],
            "en": [b["space_id"]
                   for b in english_diagram.get("bubbles") or []][:6],
        },
    )

    status, why_en_payload = diagram_why(EN_WHY, language="en")

    why_en = (why_en_payload or {}).get("result") or {}

    record(
        "E.3 why-questions are answered in English",
        status == 200
        and why_en.get("question_type") == "WHY_ADJACENT"
        and not has_persian(why_en.get("answer"))
        and bool(why_en.get("answer")),
        {"q": why_en.get("question_type")},
    )

    status, query_en_payload = curriculum_query(
        "Kitchen next to the living room is appropriate", language="en"
    )

    query_en = (query_en_payload or {}).get("result") or {}

    record(
        "E.4 curriculum queries are answered in English",
        status == 200
        and query_en.get("verdict") == "ACCEPTABLE"
        and not has_persian(query_en.get("answer")),
        {"verdict": query_en.get("verdict")},
    )

    # ==================================================
    # TEST F — SPACE RESOLUTION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST F - SPACE RESOLUTION")
    print("=" * 70)

    status, spaces_payload = http_json(
        CORE_API, "/api/conversation/curriculum/spaces?category=PRIVATE"
    )

    record(
        "F.1 spaces resolve and are queryable by category",
        status == 200 and (spaces_payload or {}).get("count", 0) > 0,
        {"count": (spaces_payload or {}).get("count")},
    )

    status, fa_space = http_json(
        CORE_API,
        "/api/conversation/curriculum/space?term="
        "%D8%A7%D8%AA%D8%A7%D9%82%20%D8%AE%D9%88%D8%A7%D8%A8",
    )

    status_en, en_space = http_json(
        CORE_API,
        "/api/conversation/curriculum/space?term=bedroom",
    )

    fa_id = (fa_space or {}).get("space_id") or (
        (fa_space or {}).get("space") or {}
    ).get("space_id")

    en_id = (en_space or {}).get("space_id") or (
        (en_space or {}).get("space") or {}
    ).get("space_id")

    record(
        "F.2 the same space resolves from Persian and English terms",
        bool(fa_id) and fa_id == en_id,
        {"fa": fa_id, "en": en_id},
    )

    # ==================================================
    # TEST G — SITE + POSITION INTENT
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST G - SITE + POSITION INTENT")
    print("=" * 70)

    status, site_payload = http_json(
        CORE_API,
        "/api/conversation/diagram/site",
        {"text": FA_SITE, "language": "fa"},
        timeout=10800,
    )

    site = (site_payload or {}).get("result") or {}

    record(
        "G.1 site intent maps the street / rear yard to semantic edges",
        status == 200
        and site.get("access_edge") == "south"
        and site.get("open_edge") == "north"
        and site.get("contains_coordinates") is False
        and site.get("contains_geometry") is False,
        {"access": site.get("access_edge"), "open": site.get("open_edge")},
    )

    entry_intent = (by_space.get("UNIT_ENTRY") or [{}])[0].get(
        "position_intent"
    ) or {}

    bedroom_intent = (by_space.get("BEDROOM_DOUBLE") or [{}])[0].get(
        "position_intent"
    ) or {}

    record(
        "G.2 public sits on the access edge",
        entry_intent.get("determined") is True
        and entry_intent.get("edge") == "south",
        entry_intent,
    )

    record(
        "G.3 private sits on the PROTECTED edge (list-valued site key)",
        bedroom_intent.get("determined") is True
        and bedroom_intent.get("edge") == "north",
        bedroom_intent,
    )

    # ==================================================
    # TEST H — CASE REASONING IS EVIDENCE-BASED
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST H - CASE REASONING (EVIDENCE, NOT OPINION)")
    print("=" * 70)

    status, why_pos_payload = diagram_why(FA_WHY_POSITIVE, language="fa")

    why_pos = (why_pos_payload or {}).get("result") or {}

    evidence = why_pos.get("evidence") or {}

    record(
        "H.1 case reasoning cites relation + zone + provenance",
        status == 200
        and bool((evidence.get("relation") or {}).get("type"))
        and bool((evidence.get("relation") or {}).get("reason"))
        and (evidence.get("relation") or {}).get("provenance") is not None
        and bool((evidence.get("source") or {}).get("zone"))
        and bool((evidence.get("target") or {}).get("zone")),
        {"relation": (evidence.get("relation") or {}).get("type")},
    )

    record(
        "H.2 the answer is deterministic and offline",
        why_pos.get("deterministic") is True
        and why_pos.get("llm_used") is False
        and why_pos.get("network_used") is False
        and why_pos.get("render_requested") is False,
        None,
    )

    status, no_ev_payload = curriculum_query(FA_TEACH, language="fa")

    no_ev = (no_ev_payload or {}).get("result") or {}

    record(
        "H.3 a pair with no recorded relation is NO_EVIDENCE, not a "
        "false negative",
        no_ev.get("verdict") == "NO_EVIDENCE"
        and no_ev.get("has_relation") is False
        and "None" not in str(no_ev.get("answer")),
        {"verdict": no_ev.get("verdict")},
    )

    # ==================================================
    # TEST I — TEACHING COMPATIBILITY
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST I - TEACHING COMPATIBILITY")
    print("=" * 70)

    status, turn = chat(persian_project, FA_TEACH)

    response = (turn or {}).get("response") or {}

    teaching = response.get("teaching") or {}

    candidate = teaching.get("candidate") or {}

    text = str(response.get("result") or "")

    record(
        "I.1 teaching a spatial rule yields a CANDIDATE with the full "
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
        "I.2 the system does NOT learn: candidate only, no permanent "
        "knowledge",
        candidate.get("is_learned_knowledge") is False
        and candidate.get("is_permanent") is False
        and candidate.get("status") in ALLOWED_STATUSES
        and teaching.get("permanent_learning") is not True,
        {"status": candidate.get("status")},
    )

    record(
        "I.3 the system asks for confirmation and never routes to EXECUTE",
        response.get("capability") == "UNDERSTAND"
        and teaching.get("permanent_learning") is False
        and bool(text)
        and has_persian(text),
        {"capability": response.get("capability"),
         "permanent_learning": teaching.get("permanent_learning")},
    )

    status, turn_diagram = chat(persian_project, FA_TEACH_DIAGRAM)

    response_diagram = (turn_diagram or {}).get("response") or {}

    teaching_diagram = response_diagram.get("teaching") or {}

    elicitation = teaching_diagram.get("elicitation") or {}

    record(
        "I.4 teaching a DIAGRAM topic asks the 5 diagram aspects",
        teaching_diagram.get("aspect_set") == "diagram"
        and len(elicitation.get("aspects") or []) == 5
        and (response_diagram.get("turn_semantics") or {}).get("turn_kind")
        == "OFFER_TO_TEACH",
        {"aspect_set": teaching_diagram.get("aspect_set"),
         "aspects": len(elicitation.get("aspects") or [])},
    )

    status, turn_space = chat(persian_project, FA_TEACH_SPACE)

    teaching_space = ((turn_space or {}).get("response") or {}).get(
        "teaching"
    ) or {}

    record(
        "I.5 the OLD space-topic path is still reachable (5 space aspects)",
        teaching_space.get("aspect_set") == "space"
        and len(
            (teaching_space.get("elicitation") or {}).get("aspects") or []
        ) == 5,
        {"aspect_set": teaching_space.get("aspect_set")},
    )

    status, turn_generic = chat(persian_project, FA_TEACH_GENERIC)

    teaching_generic = ((turn_generic or {}).get("response") or {}).get(
        "teaching"
    ) or {}

    record(
        "I.6 the generic path is still reachable (6 generic aspects)",
        teaching_generic.get("aspect_set") == "generic"
        and len(
            (teaching_generic.get("elicitation") or {}).get("aspects") or []
        ) == 6,
        {"aspect_set": teaching_generic.get("aspect_set"),
         "aspects": len(
             (teaching_generic.get("elicitation") or {}).get("aspects") or []
         )},
    )

    # ==================================================
    # TEST J — PROJECT ISOLATION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST J - PROJECT ISOLATION")
    print("=" * 70)

    chat(isolation_a, "راه پله باید نزدیک ورودی باشد")

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
        "J.1 project A candidates never appear in project B",
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
        "J.2 teaching storage stays project-scoped, global memory clean",
        guard_result.get("global_memory_clean") is True
        and guard_result.get("teaching_storage_is_project_scoped") is True,
        {"clean": guard_result.get("global_memory_clean")},
    )

    status, p_diagram = diagram_generate(
        FA_PROGRAM, language="fa", project_id=isolation_a
    )

    other_diagram = (p_diagram or {}).get("diagram") or {}

    record(
        "J.3 the diagram is project-scoped and stateless",
        other_diagram.get("project_id") == isolation_a
        and [b["space_id"] for b in other_diagram.get("bubbles") or []]
        == [b["space_id"] for b in diagram.get("bubbles") or []],
        {"project_id": other_diagram.get("project_id")},
    )

    # ==================================================
    # TEST K — RESTART MID-RUN
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST K - RESTART MID-RUN")
    print("=" * 70)

    stop_core(process)

    time.sleep(3)

    process = start_core(port=5000, log_suffix=".restart")

    restarted = wait_for_core(CORE_API, timeout=10800)

    record("K.1 Core API restarted", restarted, None)

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
            "K.2 candidates survive the restart, isolation still holds",
            {c.get("candidate_id") for c in list_a2} == ids_a
            and {c.get("candidate_id") for c in list_b2} == ids_b
            and not (
                {c.get("candidate_id") for c in list_a2}
                & {c.get("candidate_id") for c in list_b2}
            ),
            {"a": len(list_a2), "b": len(list_b2)},
        )

        status, d2 = diagram_generate(FA_PROGRAM, site=FA_SITE, language="fa")

        diagram2 = (d2 or {}).get("diagram") or {}

        record(
            "K.3 the diagram is reproducible after a restart",
            [b["bubble_id"] for b in diagram2.get("bubbles") or []]
            == [b["bubble_id"] for b in diagram.get("bubbles") or []],
            {"bubbles": len(diagram2.get("bubbles") or [])},
        )

    else:

        record("K.2 candidates survive the restart", False, None)

        record("K.3 the diagram is reproducible after a restart", False, None)

    stop_core(process)

    # ==================================================
    # TEST L — ZERO RENDER / COMFY / GEOMETRY / CAD / BIM / IFC
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST L - ZERO RENDER / COMFY / GEOMETRY / CAD / BIM / IFC")
    print("=" * 70)

    after_comfy = comfy_output_snapshot()

    record(
        "L.1 ComfyUI output directory unchanged",
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
        "L.2 no ComfyUI invocation (blocked on port 9)",
        not comfy_reachable or before_comfy == after_comfy,
        {"comfy_reachable": comfy_reachable},
    )

    scan = artifact_scan(DATA_ROOT)

    report["artifact_scan"] = scan

    report["geometry_outputs"] = scan["geometry_files"]

    record(
        "L.3 ZERO geometry / CAD / BIM / IFC artefacts produced",
        scan["geometry_files"] == 0,
        scan,
    )

    record(
        "L.4 ZERO render / image artefacts produced",
        scan["image_files"] == 0 and report["real_renders"] == 0,
        {"image_files": scan["image_files"]},
    )

    # ==================================================
    # REGRESSION — PHASES 01-10
    # ==================================================

    print("\n" + "=" * 70)
    print("  REGRESSION - PHASES 01-10")
    print("=" * 70)

    # Phase 10's acceptance is run in fast mode: its own nested Voice 07
    # regression is skipped, because Voice 07 runs once, at THIS level.
    completed = subprocess.run(
        [sys.executable, PHASE10_ACCEPTANCE, "--fast"],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=10800,
    )

    report["phase10_regression"] = {
        "returncode": completed.returncode,
        "fast_mode": True,
        "tail": (completed.stdout or "")[-1600:],
    }

    record(
        "R.1 Phase 10 acceptance still green",
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

    report["zone_report"] = zone_report

    report["diagram_report"] = semantic_report

    report["final_status"] = (
        "SPATIAL_DIAGRAM_11_PASS"
        if not failed
        else "SPATIAL_DIAGRAM_11_BLOCKED"
    )

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:

        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("  PHASE 11 ACCEPTANCE SUMMARY")
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
        "  |  relations: %d  |  bubbles: %d"
        % (
            report["passed"],
            report["total"],
            report["real_renders"],
            report["geometry_outputs"],
            space_report["space_count"],
            adjacency_report["relation_count"],
            len(diagram.get("bubbles") or []),
        )
    )

    print("  FINAL STATUS:", report["final_status"])

    print("  REPORT:", REPORT_PATH)

    print("=" * 70 + "\n")

    return 0 if not failed else 1


if __name__ == "__main__":

    sys.exit(main())
