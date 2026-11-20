# ==========================================================
# ArchitectOS Runtime Config v1
# SINGLE SOURCE OF TRUTH for runtime endpoints + paths
#
# RUNTIME_FOUNDATION_01
#
# This module is intentionally dependency-free (stdlib only) so
# that every layer (launcher, core API, UI, render runtime) can
# import it without creating import cycles.
#
# Consumers must NOT hardcode hosts / ports / Comfy paths anymore.
# ==========================================================


import os


# ==========================================================
# REPO ROOT
# ==========================================================

REPO_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)


# ==========================================================
# CORE API  (ArchitectOS gateway -> app.py)
# ==========================================================

CORE_API_HOST = os.environ.get(
    "ARCHITECTOS_CORE_API_HOST",
    "127.0.0.1"
)

CORE_API_PORT = int(
    os.environ.get(
        "ARCHITECTOS_CORE_API_PORT",
        "5000"
    )
)

# Bind address used by app.py itself.
# ArchitectOS-owned writable services are loopback-only by default. A remote
# bind is an explicit deployment choice and does not enable trusted-local
# filesystem authorization.
CORE_API_BIND_HOST = os.environ.get(
    "ARCHITECTOS_CORE_API_BIND_HOST",
    "127.0.0.1"
)

CORE_API_URL = (
    "http://"
    + CORE_API_HOST
    + ":"
    + str(CORE_API_PORT)
)

CORE_API_HEALTH_PATH = "/health"


# ==========================================================
# UI  (ArchitectOS frontend -> ui/app.py)
# ==========================================================

UI_HOST = os.environ.get(
    "ARCHITECTOS_UI_HOST",
    "127.0.0.1"
)

UI_PORT = int(
    os.environ.get(
        "ARCHITECTOS_UI_PORT",
        "3000"
    )
)

UI_BIND_HOST = os.environ.get(
    "ARCHITECTOS_UI_BIND_HOST",
    "127.0.0.1"
)

UI_URL = (
    "http://"
    + UI_HOST
    + ":"
    + str(UI_PORT)
)

UI_STATUS_PATH = "/status"


# ==========================================================
# ComfyUI  (externally managed - detected, never auto-started)
# ==========================================================

COMFYUI_HOST = os.environ.get(
    "ARCHITECTOS_COMFY_HOST",
    "127.0.0.1"
)

COMFYUI_PORT = int(
    os.environ.get(
        "ARCHITECTOS_COMFY_PORT",
        "8188"
    )
)

COMFYUI_URL = (
    "http://"
    + COMFYUI_HOST
    + ":"
    + str(COMFYUI_PORT)
)

COMFYUI_HEALTH_PATH = "/system_stats"

# Canonical ComfyUI installation root (Zluda build).
COMFYUI_ROOT = os.environ.get(
    "ARCHITECTOS_COMFY_ROOT",
    "C:/ComfyUI-Zluda"
)

COMFYUI_INPUT_DIR = (
    COMFYUI_ROOT.rstrip("/")
    + "/input"
)

COMFYUI_OUTPUT_DIR = (
    COMFYUI_ROOT.rstrip("/")
    + "/output"
)


# ==========================================================
# Ollama  (externally managed - detected, never auto-started)
# ==========================================================

OLLAMA_HOST = os.environ.get(
    "ARCHITECTOS_OLLAMA_HOST",
    "127.0.0.1"
)

OLLAMA_PORT = int(
    os.environ.get(
        "ARCHITECTOS_OLLAMA_PORT",
        "11434"
    )
)

OLLAMA_URL = (
    "http://"
    + OLLAMA_HOST
    + ":"
    + str(OLLAMA_PORT)
)

OLLAMA_HEALTH_PATH = "/api/tags"


# ==========================================================
# WORKFLOWS
# ==========================================================

WORKFLOW_DIR = os.path.join(
    REPO_ROOT,
    "core",
    "render",
    "workflows"
)

# Must stay in sync with WorkflowSelector.available_workflows()
REQUIRED_WORKFLOW_FILES = (
    "flux.json",
    "flux_img2img.json",
    # FACADE-04D.2 — role-aware dual-image img2img graph.
    "flux_img2img_dual.json",
    # FACADE-04D.3B-2 — conditioned dual-image graph (explicit opt-in).
    "flux_img2img_dual_conditioned.json",
    # EXISTING_VISUAL_KNOWLEDGE_USO_V1 — USO reference-conditioned
    # text-to-image graph (explicit opt-in via request["uso_reference"]).
    "flux_uso_reference.json",
    "wan_i2v.json",
)

DEFAULT_WORKFLOW_FILE = "flux.json"


# ==========================================================
# RUNTIME LOGGING POLICY  (LOG_ROTATION_FIX_01)
#
# SINGLE SOURCE OF TRUTH for the bounded-log policy.
#
# ROOT CAUSE this fixes: launcher.start_service() used to open
# the service log with a bare open(path, "ab") and never rotate
# or bound it. Combined with the Core API's per-request access
# logging, logs/runtime/core_api.log grew without limit
# (measured ~4.9 MB/min under UI polling -> hundreds of GB/month).
#
# Every writer of a logs/runtime/*.log file MUST honour these
# values. Nothing may open an unbounded append handle again.
# ==========================================================

LOG_DIR = os.path.join(
    REPO_ROOT,
    "logs",
    "runtime"
)

# Rotate a service log once it reaches this many bytes.
LOG_MAX_BYTES = int(
    os.environ.get(
        "ARCHITECTOS_LOG_MAX_BYTES",
        str(32 * 1024 * 1024)
    )
)

# How many rotated generations to keep (<name>.log.1 .. .log.N).
# Total worst case per service = LOG_MAX_BYTES * (LOG_BACKUP_COUNT + 1).
LOG_BACKUP_COUNT = int(
    os.environ.get(
        "ARCHITECTOS_LOG_BACKUP_COUNT",
        "5"
    )
)

# Total worst-case bytes for one service's log family.
LOG_MAX_TOTAL_BYTES = LOG_MAX_BYTES * (LOG_BACKUP_COUNT + 1)


# ==========================================================
# PROJECT WORKSPACE STORAGE  (PROJECT_WORKSPACE_UI_06)
#
# SINGLE SOURCE OF TRUTH for project-scoped storage.
# No module may hardcode a project path.
# ==========================================================

PROJECT_DATA_ROOT = os.environ.get(
    "ARCHITECTOS_PROJECT_DATA_ROOT",
    os.path.join(REPO_ROOT, "data")
)

PROJECTS_ROOT = os.environ.get(
    "ARCHITECTOS_PROJECTS_ROOT",
    os.path.join(PROJECT_DATA_ROOT, "projects")
)

# ==========================================================
# VISUAL REFERENCE LIBRARY  (VISUAL_REFERENCE_UX_V2)
#
# The two reference collections ArchitectOS already owns, plus the
# addressable index built over them. These are the ONLY roots from which a
# reference preview may be served: the browser never supplies a path, only a
# reference id, and the id is resolved through the index.
#
# The historical collection lives OUTSIDE the project on purpose — it is a
# user-owned archive that this system must never move or rewrite.
# ==========================================================

REFERENCE_LIBRARY_ROOT = os.environ.get(
    "ARCHITECTOS_REFERENCE_LIBRARY_ROOT",
    r"D:\ArchitectOS_Visual_References_V1"
)

REFERENCE_CLASSICAL_ROOT = os.environ.get(
    "ARCHITECTOS_REFERENCE_CLASSICAL_ROOT",
    os.path.join(PROJECT_DATA_ROOT, "reference_sets", "classical_facades_20261023")
)

REFERENCE_CLASSICAL_ZIP = os.path.join(
    REPO_ROOT, "ArchitectOS_Classical_Facade_Reference_Pack_20261023.zip"
)

#: The addressable index over both collections. Written by
#: core/vision/visual_reference_index_v1.py and read by the API boundary.
REFERENCE_INDEX_PATH = os.path.join(
    PROJECT_DATA_ROOT, "reference_index", "visual_reference_index_v1.json"
)

#: Preview URL root keys registered with the chat attachment service.
REFERENCE_ROOT_KEYS = {
    "visual_references_v1": "reference_library",
    "classical_facades_20261023": "reference_classical",
}

PROJECT_INDEX_FILE = "index.json"

PROJECT_MANIFEST_FILE = "project.json"

# Sub-folders created inside every project.
PROJECT_SUBDIRS = (
    "conversations",
    "uploads",
    "renders",
    "img2img",
    "documents",
    "exports",
    "thumbnails",
)

# Soft-delete quarantine root (deleted projects are moved here, never
# immediately erased).
PROJECT_TRASH_ROOT = os.path.join(
    PROJECT_DATA_ROOT,
    "trash"
)


def project_root(project_id):
    """Absolute storage folder for one project."""

    return os.path.join(
        PROJECTS_ROOT,
        str(project_id)
    )


# ==========================================================
# HEALTH PROBE TIMEOUTS (seconds)
# ==========================================================

PROBE_TIMEOUT = float(
    os.environ.get(
        "ARCHITECTOS_PROBE_TIMEOUT",
        "3"
    )
)

STARTUP_TIMEOUT = float(
    os.environ.get(
        "ARCHITECTOS_STARTUP_TIMEOUT",
        "45"
    )
)


# ==========================================================
# UPLOAD SIZE POLICY  (UPLOAD_SIZE_LIMIT_01)
#
# The Core API had NO request-size ceiling: a 40 MiB file sent as an "image"
# was accepted, stored and treated as an upload. Werkzeug therefore read the
# whole body before any application check could run.
#
# This is the ONE place the ceiling lives. It bounds a single request body,
# which is what Werkzeug enforces; it is deliberately generous because the
# product legitimately uploads photographs and PDFs. Operators can raise or
# lower it with ARCHITECTOS_MAX_UPLOAD_BYTES.
# ==========================================================

MAX_UPLOAD_BYTES = int(
    os.environ.get(
        "ARCHITECTOS_MAX_UPLOAD_BYTES",
        str(64 * 1024 * 1024)
    )
)


# ==========================================================
# HELPERS
# ==========================================================

def required_comfy_paths():
    """Paths that must exist for render output to be resolvable."""

    return {
        "comfyui_root": COMFYUI_ROOT,
        "comfyui_input": COMFYUI_INPUT_DIR,
        "comfyui_output": COMFYUI_OUTPUT_DIR,
    }


def required_workflow_paths():
    """Absolute paths of the workflow files the selector may request."""

    return {
        name: os.path.join(
            WORKFLOW_DIR,
            name
        )
        for name in REQUIRED_WORKFLOW_FILES
    }


def as_dict():
    """Serializable snapshot of the effective runtime configuration."""

    return {

        "core_api":
            {
                "url": CORE_API_URL,
                "host": CORE_API_HOST,
                "port": CORE_API_PORT,
                "health": CORE_API_HEALTH_PATH,
            },

        "ui":
            {
                "url": UI_URL,
                "host": UI_HOST,
                "port": UI_PORT,
                "status": UI_STATUS_PATH,
            },

        "comfyui":
            {
                "url": COMFYUI_URL,
                "host": COMFYUI_HOST,
                "port": COMFYUI_PORT,
                "health": COMFYUI_HEALTH_PATH,
                "root": COMFYUI_ROOT,
                "input": COMFYUI_INPUT_DIR,
                "output": COMFYUI_OUTPUT_DIR,
            },

        "ollama":
            {
                "url": OLLAMA_URL,
                "host": OLLAMA_HOST,
                "port": OLLAMA_PORT,
                "health": OLLAMA_HEALTH_PATH,
            },

        "workflows":
            {
                "dir": WORKFLOW_DIR,
                "required": list(REQUIRED_WORKFLOW_FILES),
            },

        "projects":
            {
                "data_root": PROJECT_DATA_ROOT,
                "projects_root": PROJECTS_ROOT,
                "trash_root": PROJECT_TRASH_ROOT,
                "index_file": PROJECT_INDEX_FILE,
                "manifest_file": PROJECT_MANIFEST_FILE,
                "subdirs": list(PROJECT_SUBDIRS),
            },

    }


# ==========================================================
# SELF CHECK (manual: python -m config.runtime_config)
# ==========================================================

if __name__ == "__main__":

    import json

    print(
        json.dumps(
            as_dict(),
            indent=4
        )
    )
