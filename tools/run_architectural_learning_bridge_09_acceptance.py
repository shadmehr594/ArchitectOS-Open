# ==========================================================
# PHASE 09 — ARCHITECTURAL LEARNING BRIDGE ACCEPTANCE RUNNER
#
# Runs the REQUIRED Phase 09 acceptance tests (A-I) against the LIVE
# runtime:
#
#   UI-style HTTP -> Core API (app.py) -> ChatArchitect.handle
#                                    -> /api/conversation/*
#
# HARD CONSTRAINTS
#   - NO render, NO ComfyUI, NO geometry, NO BIM, NO IFC.
#     The Core API starts with ARCHITECTOS_COMFY_PORT=9 and an isolated
#     project data root; the ComfyUI output directory is asserted
#     unchanged and the isolated root is scanned for geometry/BIM/IFC
#     artefacts (must be zero).
#
# Usage:
#   .venv/Scripts/python.exe tools/run_architectural_learning_bridge_09_acceptance.py
#   .venv/Scripts/python.exe tools/run_architectural_learning_bridge_09_acceptance.py --fast
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
    ROOT, "tools", "acceptance_09_report.json"
)

LOG_PATH = os.path.join(
    ROOT, "logs", "runtime", "acceptance_09_core.log"
)

WORK_DIR = os.path.join(
    ROOT,
    ".pytest_tmp",
    "learning_bridge_09_" + time.strftime("%Y%m%d_%H%M%S"),
)

DATA_ROOT = os.path.join(WORK_DIR, "project_data")

# Isolate acceptance storage from real user projects.
os.environ["ARCHITECTOS_PROJECT_DATA_ROOT"] = DATA_ROOT


PHASE08_ACCEPTANCE = os.path.join(
    ROOT, "tools", "run_teaching_foundation_08_acceptance.py"
)

PHASE08_TESTS = os.path.join(
    ROOT, "tests", "test_teaching_foundation_08.py"
)

PHASE09_TESTS = os.path.join(
    ROOT, "tests", "test_architectural_learning_bridge_09.py"
)

CHAT_LANGUAGE_TESTS = os.path.join(
    ROOT, "tests", "test_chat_language_02.py"
)

CHAT_CORE_TESTS = os.path.join(
    ROOT, "tests", "test_chat_core_only.py"
)


COMFY_OUTPUT_DIR = os.path.join("C:", os.sep, "ComfyUI-Zluda", "output")

try:

    from config import runtime_config as RC

    COMFY_OUTPUT_DIR = RC.COMFYUI_OUTPUT_DIR

except Exception:

    pass


# Artefact extensions that must NEVER appear for Phase 09.
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

    # RENDER-STOP GUARD: ComfyUI is unreachable by construction.
    env["ARCHITECTOS_COMFY_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_COMFY_PORT"] = "9"

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    if not os.path.isfile(python):

        python = sys.executable

    handle = open(LOG_PATH + log_suffix, "ab")

    handle.write(b"\n\n===== acceptance_09 core start =====\n")

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

    """Count geometry / BIM / IFC / render artefacts under a root."""

    geometry = []

    images = []

    if not os.path.isdir(root):

        return {
            "root": root,
            "exists": False,
            "geometry_files": 0,
            "image_files": 0,
            "samples": [],
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


def turn_kind_of(turn):

    response = (turn or {}).get("response") or {}

    return ((response or {}).get("turn_semantics") or {}).get("turn_kind")


def response_text(turn):

    response = (turn or {}).get("response") or {}

    if not isinstance(response, dict):

        return ""

    return str(
        response.get("result")
        or response.get("message")
        or turn.get("result")
        or ""
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    fast = "--fast" in sys.argv

    report = {
        "phase": "PHASE_09_ARCHITECTURAL_LEARNING_BRIDGE",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "comfy_blocked_by_construction": True,
        "comfy_port": 9,
        "real_renders": 0,
        "image_generations": 0,
        "geometry_outputs": 0,
        "bim_outputs": 0,
        "ifc_outputs": 0,
        "curriculum_started": False,
        "data_root": DATA_ROOT,
        "tests": [],
    }

    # A per-run work directory is used, so there is never a bulk delete of
    # a previous run's tree (which can trip environment safety guards when
    # this runner is nested inside a later phase's acceptance).
    os.makedirs(DATA_ROOT, exist_ok=True)

    # ==================================================
    # 0. STATIC / CONTRACT CHECKS
    # ==================================================

    print("\n" + "=" * 70)
    print("  SECTION 0 — STATIC + CONTRACT CHECKS")
    print("=" * 70)

    from core.conversation.turn_semantics_v1 import (
        TURN_OFFER_TO_TEACH,
        TEACHING_INTENT,
    )

    from core.conversation.teaching_candidate_v1 import (
        ALLOWED_STATUSES,
        FORBIDDEN_STATUSES,
        PERMANENT_LEARNING_IMPLEMENTED,
    )

    from core.conversation.knowledge_promotion_bridge_v1 import (
        PROMOTION_IMPLEMENTED,
    )

    # ---- exactly one assistant ----
    with open(os.path.join(ROOT, "app.py"), "r",
              encoding="utf-8", errors="replace") as handle:

        app_text = handle.read()

    record(
        "0.1 exactly ONE ChatArchitect in the Core API",
        app_text.count("ChatArchitect(") == 1,
        {"count": app_text.count("ChatArchitect(")},
    )

    # ---- no curriculum started ----
    forbidden_modules = (
        "curriculum", "lesson", "exercise", "bubble_diagram",
        "adjacency_matrix", "rplan", "layout_generation",
    )

    conversation_dir = os.path.join(ROOT, "core", "conversation")

    curriculum_hits = [
        name for name in os.listdir(conversation_dir)
        if name.endswith(".py")
        and any(t in name.lower() for t in forbidden_modules)
    ]

    record(
        "0.2 curriculum NOT started (no curriculum module added)",
        not curriculum_hits,
        {"hits": curriculum_hits},
    )

    record(
        "0.3 teaching intent vocabulary present",
        TURN_OFFER_TO_TEACH == "OFFER_TO_TEACH"
        and TEACHING_INTENT == TURN_OFFER_TO_TEACH,
        {"kind": TURN_OFFER_TO_TEACH},
    )

    record(
        "0.4 promotion NOT implemented, statuses closed",
        PROMOTION_IMPLEMENTED is False
        and PERMANENT_LEARNING_IMPLEMENTED is False
        and set(ALLOWED_STATUSES) == {
            "observed", "needs_confirmation", "rejected"
        }
        and all(s not in ALLOWED_STATUSES for s in FORBIDDEN_STATUSES),
        {"allowed": list(ALLOWED_STATUSES)},
    )

    # ---- contract suites ----
    print("\n  running contract suites ...")

    completed = subprocess.run(
        [sys.executable, PHASE09_TESTS],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=10800,
    )

    record(
        "0.5 Phase 09 contract suite green",
        completed.returncode == 0,
        {"returncode": completed.returncode,
         "tail": (completed.stdout or "")[-400:]},
    )

    completed = subprocess.run(
        [sys.executable, PHASE08_TESTS],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=10800,
    )

    record(
        "0.6 Phase 08 contract suite still green",
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

        report["final_status"] = "ARCHITECTURAL_LEARNING_BRIDGE_09_BLOCKED"

        with open(REPORT_PATH, "w", encoding="utf-8") as handle:

            json.dump(report, handle, ensure_ascii=False, indent=2)

        return 1

    record("1.0 Core API online", True, {"pid": process.pid})

    persian_project, _ = create_project("Phase09 Learning Persian")

    english_project, _ = create_project("Phase09 Learning English")

    isolation_a, _ = create_project("Phase09 Isolation A")

    isolation_b, _ = create_project("Phase09 Isolation B")

    record(
        "1.1 acceptance projects created",
        all([persian_project, english_project, isolation_a, isolation_b]),
        {"persian": persian_project, "english": english_project},
    )

    http_json(
        CORE_API,
        "/api/conversation/language",
        {"project_id": english_project, "language": "en"},
        timeout=10800,
    )

    # ==================================================
    # A — TEACHING INTENT
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST A — TEACHING INTENT (\"می خواهم راه پله را یاد بدهم\")")
    print("=" * 70)

    status, turn = chat(
        persian_project,
        "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645 \u0631\u0627\u0647 \u067e\u0644\u0647 \u0631\u0627 \u06cc\u0627\u062f \u0628\u062f\u0647\u0645",
    )

    response = (turn or {}).get("response") or {}

    semantics = (response or {}).get("turn_semantics") or {}

    teaching = (response or {}).get("teaching") or {}

    elicitation = teaching.get("elicitation") or {}

    text = response_text(turn)

    record(
        "A.1 teaching offer classified as TEACHING_INTENT",
        semantics.get("turn_kind") == "OFFER_TO_TEACH"
        and semantics.get("is_teaching_intent") is True,
        {"turn_kind": semantics.get("turn_kind"),
         "is_teaching_intent": semantics.get("is_teaching_intent")},
    )

    record(
        "A.2 teaching intent NEVER routed to EXECUTE",
        semantics.get("is_action_request") is False
        and (response or {}).get("capability") != "EXECUTE"
        and teaching.get("routed_to_execute") is False,
        {"capability": (response or {}).get("capability")},
    )

    record(
        "A.3 elicitation asks which aspect (topic-aware aspect set)",
        len(elicitation.get("aspects") or []) in (5, 6)
        and "\u06a9\u062f\u0627\u0645 \u0628\u062e\u0634" in text
        and bool(teaching.get("aspect_set")),
        {"aspects": len(elicitation.get("aspects") or []),
         "aspect_set": teaching.get("aspect_set"),
         "text": text[:150]},
    )

    record(
        "A.4 teaching intent created NO candidate",
        teaching.get("candidate") is None
        and semantics.get("may_produce_candidate") is False,
        {"candidate": teaching.get("candidate")},
    )

    # ---- English teaching offer ----
    status, turn_en = chat(
        english_project, "I want to teach you about staircases"
    )

    record(
        "A.5 English teaching offer classified as TEACHING_INTENT",
        turn_kind_of(turn_en) == "OFFER_TO_TEACH",
        {"turn_kind": turn_kind_of(turn_en)},
    )

    # ---- PHASE 10 compatibility: the GENERIC aspect set is still used
    # for a teaching offer that is NOT about a known architectural space.
    # Phase 10 made the aspect set topic-aware, so this is the check that
    # guarantees the Phase 09 generic behaviour was not lost.
    status, turn_generic = chat(
        persian_project,
        "\u0645\u06cc \u062e\u0648\u0627\u0647\u0645 \u0628\u0647 \u062a\u0648 "
        "\u062f\u0631\u0628\u0627\u0631\u0647 \u0636\u0648\u0627\u0628\u0637 "
        "\u06cc\u0627\u062f \u0628\u062f\u0647\u0645",
    )

    generic_teaching = (
        ((turn_generic or {}).get("response") or {}).get("teaching") or {}
    )

    generic_elicitation = generic_teaching.get("elicitation") or {}

    record(
        "A.6 non-space teaching offer still uses the generic 6 aspects",
        turn_kind_of(turn_generic) == "OFFER_TO_TEACH"
        and generic_teaching.get("aspect_set") == "generic"
        and len(generic_elicitation.get("aspects") or []) == 6,
        {"turn_kind": turn_kind_of(turn_generic),
         "aspect_set": generic_teaching.get("aspect_set"),
         "aspects": len(generic_elicitation.get("aspects") or [])},
    )

    # ==================================================
    # B — QUESTION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST B — QUESTION (\"راه پله چیست؟\")")
    print("=" * 70)

    status, turn = chat(
        persian_project,
        "\u0631\u0627\u0647 \u067e\u0644\u0647 \u0686\u06cc\u0633\u062a\u061f",
    )

    response = (turn or {}).get("response") or {}

    record(
        "B.1 question classified as QUESTION",
        turn_kind_of(turn) == "QUESTION",
        {"turn_kind": turn_kind_of(turn)},
    )

    record(
        "B.2 question produced NO candidate and NO render",
        ((response or {}).get("teaching") or {}) == {}
        and ((response or {}).get("turn_semantics") or {}).get(
            "may_produce_candidate"
        ) is False,
        None,
    )

    # ==================================================
    # C — TEACHING STATEMENT (copular definition)
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST C — TEACHING STATEMENT (\"راه پله ارتباط بین طبقات است\")")
    print("=" * 70)

    status, turn = chat(
        persian_project,
        "\u0631\u0627\u0647 \u067e\u0644\u0647 \u0627\u0631\u062a\u0628\u0627\u0637 \u0628\u06cc\u0646 \u0637\u0628\u0642\u0627\u062a \u0627\u0633\u062a",
    )

    response = (turn or {}).get("response") or {}

    teaching = (response or {}).get("teaching") or {}

    candidate_c = teaching.get("candidate") or {}

    record(
        "C.1 copular teaching statement classified as TEACHING_STATEMENT",
        turn_kind_of(turn) == "TEACHING_STATEMENT",
        {"turn_kind": turn_kind_of(turn)},
    )

    record(
        "C.2 statement stored as a CANDIDATE only",
        candidate_c.get("status") in ALLOWED_STATUSES
        and candidate_c.get("is_learned_knowledge") is False,
        {"status": candidate_c.get("status")},
    )

    # ==================================================
    # D — TEACHING STATEMENT (Persian ب-noun)
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST D — TEACHING STATEMENT (\"بام باید شیب مناسب داشته باشد\")")
    print("=" * 70)

    status, turn = chat(
        persian_project,
        "\u0628\u0627\u0645 \u0628\u0627\u06cc\u062f \u0634\u06cc\u0628 \u0645\u0646\u0627\u0633\u0628 \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f",
    )

    response = (turn or {}).get("response") or {}

    teaching = (response or {}).get("teaching") or {}

    candidate_d = teaching.get("candidate") or {}

    record(
        "D.1 ب-noun statement classified as TEACHING_STATEMENT",
        turn_kind_of(turn) == "TEACHING_STATEMENT",
        {"turn_kind": turn_kind_of(turn)},
    )

    record(
        "D.2 NOT classified as INSTRUCTION (no false imperative)",
        turn_kind_of(turn) != "INSTRUCTION"
        and ((response or {}).get("turn_semantics") or {}).get(
            "is_action_request"
        ) is False,
        None,
    )

    # ==================================================
    # E — EXTENDED CANDIDATE CONTRACT
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST E — CANDIDATE TAXONOMY FIELDS")
    print("=" * 70)

    status, payload = http_json(
        CORE_API,
        "/api/conversation/candidates?project_id=" + persian_project,
    )

    candidates = (payload or {}).get("candidates") or []

    required_fields = (
        "knowledge_class", "scope", "domain", "provenance",
        "confidence", "confidence_kind", "status",
    )

    missing = sorted(
        {
            field
            for candidate in candidates
            for field in required_fields
            if field not in candidate
        }
    )

    record(
        "E.1 candidates carry knowledge_class/scope/domain/provenance",
        bool(candidates) and not missing,
        {"missing": missing, "count": len(candidates)},
    )

    classes = sorted(
        {c.get("knowledge_class") for c in candidates}
    )

    scopes = sorted({c.get("scope") for c in candidates})

    provenances = sorted({c.get("provenance") for c in candidates})

    # RELAXED (curriculum foundation fix): the knowledge-class vocabulary
    # GREW — DEFINITION was added as its own class. A hardcoded tuple is
    # now wrong, so this becomes a SUBSET check against the live
    # vocabulary PLUS an assertion that every ORIGINAL Phase 09 value is
    # still present. Growth is allowed; deletion is not.
    from core.conversation.teaching_meaning_v1 import (
        ALL_KNOWLEDGE_CLASSES,
        ALL_SCOPES,
        ALL_PROVENANCES,
    )

    phase09_classes = {
        "ARCHITECTURAL_FACT", "DESIGN_RULE", "PATTERN",
        "PREFERENCE", "PROJECT_DECISION", "OBSERVATION", "UNKNOWN",
    }

    record(
        "E.2 taxonomy values come from the closed vocabularies",
        phase09_classes <= set(ALL_KNOWLEDGE_CLASSES)
        and all(
            c.get("knowledge_class") in ALL_KNOWLEDGE_CLASSES
            and c.get("scope") in ALL_SCOPES
            and c.get("provenance") in ALL_PROVENANCES
            and c.get("confidence_kind") == "learning_state"
            for c in candidates
        ),
        {"classes": classes, "scopes": scopes,
         "provenances": provenances},
    )

    record(
        "E.3 taxonomy actually distinguishes categories",
        len(classes) >= 2,
        {"classes": classes},
    )

    # ==================================================
    # F — CANNOT BECOME LEARNED KNOWLEDGE
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST F — CANDIDATE CANNOT BECOME LEARNED KNOWLEDGE")
    print("=" * 70)

    record(
        "F.1 learned_count is 0",
        int((payload or {}).get("learned_count") or 0) == 0,
        {"learned_count": (payload or {}).get("learned_count")},
    )

    record(
        "F.2 every status is a candidate status",
        all(
            c.get("status") in ALLOWED_STATUSES for c in candidates
        ),
        {"statuses": sorted({c.get("status") for c in candidates})},
    )

    # promotion attempt over HTTP
    if candidates:

        status, promo = http_json(
            CORE_API,
            "/api/conversation/knowledge/promotion/request",
            {
                "project_id": persian_project,
                "candidate_id": candidates[0].get("candidate_id"),
                "target_registry":
                    "human_architectural_learning_registry_v1",
            },
        )

        promo_result = (promo or {}).get("result") or {}

        promo_request = promo_result.get("request") or {}

        record(
            "F.3 promotion request recorded but NOT executed",
            promo_result.get("promotion_implemented") is False
            and promo_result.get("knowledge_registry_written") is False
            and promo_request.get("promoted") is False
            and promo_request.get("stage") == "awaiting_explicit_approval",
            {"stage": promo_request.get("stage"),
             "promoted": promo_request.get("promoted")},
        )

        # the registry must be byte-identical after the request
        status, sources = http_json(
            CORE_API, "/api/conversation/knowledge/sources"
        )

        registry_entry = next(
            (
                s for s in
                ((sources or {}).get("result") or {}).get("sources", [])
                if s.get("id") == "human_learning_registry"
            ),
            None,
        )

        record(
            "F.4 knowledge registry untouched by the request",
            registry_entry is not None
            and registry_entry.get("sha256") == REGISTRY_SHA256_BEFORE,
            {
                "before": REGISTRY_SHA256_BEFORE,
                "after": (registry_entry or {}).get("sha256"),
            },
        )

    status, promo_status = http_json(
        CORE_API,
        "/api/conversation/knowledge/promotion/status?project_id="
        + persian_project,
    )

    promo_state = (promo_status or {}).get("result") or {}

    record(
        "F.5 promotion / approval not implemented, no direct path",
        promo_state.get("promotion_implemented") is False
        and promo_state.get("approval_implemented") is False
        and promo_state.get("direct_candidate_to_knowledge_path") is False
        and promo_state.get("requests_promoted") == 0,
        promo_state,
    )

    # ==================================================
    # G — PROJECT ISOLATION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST G — PROJECT ISOLATION")
    print("=" * 70)

    chat(
        isolation_a,
        "\u0628\u0627\u0645 \u0628\u0627\u06cc\u062f \u0634\u06cc\u0628 \u0645\u0646\u0627\u0633\u0628 \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f",
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
        "G.1 project A candidates never appear in project B",
        bool(list_a)
        and not (ids_a & ids_b)
        and all(c.get("project_id") == isolation_a for c in list_a)
        and all(c.get("project_id") == isolation_b for c in list_b),
        {"a": len(list_a), "b": len(list_b),
         "overlap": list(ids_a & ids_b)},
    )

    # global memory must be clean
    status, guard = http_json(
        CORE_API,
        "/api/conversation/knowledge/storage-guard?project_id="
        + persian_project,
    )

    guard_result = (guard or {}).get("result") or {}

    record(
        "G.2 teaching storage is project-scoped, global memory clean",
        guard_result.get("global_memory_clean") is True
        and not guard_result.get("leaked_into_global_memory")
        and guard_result.get("teaching_storage_is_project_scoped") is True,
        {
            "clean": guard_result.get("global_memory_clean"),
            "leaked": guard_result.get("leaked_into_global_memory"),
        },
    )

    # ==================================================
    # READ BRIDGE (09-4)
    # ==================================================

    print("\n" + "=" * 70)
    print("  READ BRIDGE + TAXONOMY SURFACE")
    print("=" * 70)

    status, sources = http_json(
        CORE_API, "/api/conversation/knowledge/sources"
    )

    sources_result = (sources or {}).get("result") or {}

    record(
        "R.1 read bridge serves the existing corpus read-only",
        sources_result.get("read_only") is True
        and sources_result.get("writes_performed") == 0
        and sources_result.get("source_count", 0) >= 8
        and all(
            s.get("exists") for s in sources_result.get("sources", [])
        ),
        {
            "sources": sources_result.get("source_count"),
            "writes": sources_result.get("writes_performed"),
        },
    )

    status, patterns = http_json(
        CORE_API, "/api/conversation/knowledge/patterns"
    )

    record(
        "R.2 pattern libraries readable (positive + negative)",
        (patterns or {}).get("positive_count", 0) >= 10
        and (patterns or {}).get("negative_count", 0) >= 5,
        {
            "positive": (patterns or {}).get("positive_count"),
            "negative": (patterns or {}).get("negative_count"),
        },
    )

    status, spaces = http_json(
        CORE_API, "/api/conversation/knowledge/spaces"
    )

    record(
        "R.3 space ontology readable with zones",
        (spaces or {}).get("count", 0) >= 20
        and len((spaces or {}).get("zones") or []) >= 5,
        {
            "count": (spaces or {}).get("count"),
            "zones": (spaces or {}).get("zones"),
        },
    )

    status, taxonomy = http_json(
        CORE_API, "/api/conversation/knowledge/taxonomy"
    )

    record(
        "R.4 taxonomy surface exposes closed vocabularies",
        # RELAXED: `>= 7` instead of `== 7`, plus a subset check that
        # every original Phase 09 class is still exposed. The curriculum
        # foundation fix added DEFINITION, so the count legitimately grew.
        len((taxonomy or {}).get("knowledge_classes") or []) >= 7
        and phase09_classes <= set(
            (taxonomy or {}).get("knowledge_classes") or []
        )
        and len((taxonomy or {}).get("scopes") or []) == 2
        and len((taxonomy or {}).get("provenances") or []) == 3
        and (taxonomy or {}).get("promotion_implemented") is False,
        {"classes": (taxonomy or {}).get("knowledge_classes")},
    )

    # ==================================================
    # TEACH-BACK still honest
    # ==================================================

    status, turn = chat(
        persian_project,
        "\u0686\u06cc \u0627\u0632 \u062d\u0631\u0641 \u0645\u0646 \u0641\u0647\u0645\u06cc\u062f\u06cc\u061f",
    )

    teaching = ((turn or {}).get("response") or {}).get("teaching") or {}

    teach_back = teaching.get("teach_back") or {}

    record(
        "T.1 teach-back still refuses to claim learning",
        teach_back.get("learned_anything") is False
        and teach_back.get("permanent_learning_implemented") is False
        and teach_back.get("candidates_considered", 0) >= 1,
        {"considered": teach_back.get("candidates_considered")},
    )

    record(
        "T.2 teach-back shows the learning taxonomy",
        any(
            s.get("knowledge_class") and s.get("scope")
            for s in (teach_back.get("statements") or [])
        ),
        {"statements": len(teach_back.get("statements") or [])},
    )

    stop_core(process)

    # ==================================================
    # H — EXISTING PHASES 01-08 REGRESSION
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST H — EXISTING PHASES 01-08 REGRESSION")
    print("=" * 70)

    phase08_args = [sys.executable, PHASE08_ACCEPTANCE]

    if fast:

        phase08_args.append("--skip-voice07")

    completed = subprocess.run(
        phase08_args,
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=5400,
    )

    report["phase08_regression"] = {
        "returncode": completed.returncode,
        "fast_mode": fast,
        "tail": (completed.stdout or "")[-1200:],
    }

    record(
        "H.1 Phase 08 acceptance still green",
        completed.returncode == 0,
        {"returncode": completed.returncode,
         "tail": (completed.stdout or "")[-400:]},
    )

    for label, path in (
        ("H.2 CHAT_LANGUAGE_02 regression", CHAT_LANGUAGE_TESTS),
        ("H.3 chat core regression", CHAT_CORE_TESTS),
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
    # I — ZERO RENDER / COMFY / GEOMETRY / BIM / IFC
    # ==================================================

    print("\n" + "=" * 70)
    print("  TEST I — ZERO RENDER / COMFY / GEOMETRY / BIM / IFC")
    print("=" * 70)

    after_comfy = comfy_output_snapshot()

    record(
        "I.1 ComfyUI output directory unchanged",
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
        "I.2 no ComfyUI invocation (port 9)",
        not comfy_reachable or before_comfy == after_comfy,
        {"comfy_reachable": comfy_reachable},
    )

    scan = artifact_scan(DATA_ROOT)

    report["artifact_scan"] = scan

    report["geometry_outputs"] = scan["geometry_files"]

    record(
        "I.3 ZERO geometry / BIM / IFC artefacts produced",
        scan["geometry_files"] == 0,
        scan,
    )

    record(
        "I.4 ZERO render / image artefacts produced",
        scan["image_files"] == 0 and report["real_renders"] == 0,
        {"image_files": scan["image_files"]},
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

    report["final_status"] = (
        "ARCHITECTURAL_LEARNING_BRIDGE_09_PASS"
        if not failed
        else "ARCHITECTURAL_LEARNING_BRIDGE_09_BLOCKED"
    )

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:

        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("  PHASE 09 ACCEPTANCE SUMMARY")
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
        "  %d/%d PASS  |  renders: %d  |  images: %d  |  geometry: %d"
        % (
            report["passed"],
            report["total"],
            report["real_renders"],
            report["image_generations"],
            report["geometry_outputs"],
        )
    )

    print("  FINAL STATUS:", report["final_status"])

    print("  REPORT:", REPORT_PATH)

    print("=" * 70 + "\n")

    return 0 if not failed else 1


# ==========================================================
# REGISTRY INTEGRITY BASELINE
#
# Captured at import time (before the Core API starts) so test F.4 can
# prove the knowledge registry is byte-identical after a promotion
# request.
# ==========================================================

def _registry_sha256():

    import hashlib

    path = os.path.join(
        ROOT,
        "core", "architecture", "knowledge",
        "human_architectural_learning_registry_v1.json",
    )

    try:

        with open(path, "rb") as handle:

            return hashlib.sha256(handle.read()).hexdigest()

    except Exception:

        return None


REGISTRY_SHA256_BEFORE = _registry_sha256()


if __name__ == "__main__":

    sys.exit(main())
