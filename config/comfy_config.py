# ==========================================================
# ArchitectOS Comfy Config (compat shim)
#
# RUNTIME_FOUNDATION_01
#
# This module used to hold its own hardcoded values, including a
# STALE ComfyUI path ("C:/ComfyUI/output/") and a STALE workflow
# path ("workflows/comfy/flux.json") that does not exist.
#
# It is now a thin, backward-compatible re-export of the single
# runtime config source (config/runtime_config.py).
#
# Public names COMFY_URL / WORKFLOW_PATH / OUTPUT_DIR are preserved
# so no existing importer breaks.
# ==========================================================


import os


from config.runtime_config import (

    COMFYUI_URL,

    COMFYUI_OUTPUT_DIR,

    WORKFLOW_DIR,

    DEFAULT_WORKFLOW_FILE,

)


# ----------------------------------------------------------
# PRESERVED PUBLIC INTERFACE
# ----------------------------------------------------------

# ComfyUI HTTP endpoint.
COMFY_URL = COMFYUI_URL


# Workflow JSON used by default.
# Previously pointed at the non-existent "workflows/comfy/flux.json".
WORKFLOW_PATH = os.path.join(
    WORKFLOW_DIR,
    DEFAULT_WORKFLOW_FILE
)


# ComfyUI output directory.
# Previously pointed at the non-existent "C:/ComfyUI/output/".
# Trailing separator preserved for callers that concatenate directly.
OUTPUT_DIR = COMFYUI_OUTPUT_DIR.rstrip("/") + "/"


# ----------------------------------------------------------
# EXTRA (additive, non-breaking)
# ----------------------------------------------------------

COMFY_ROOT = os.environ.get(
    "ARCHITECTOS_COMFY_ROOT",
    "C:/ComfyUI-Zluda"
)

COMFY_INPUT_DIR = os.path.join(
    COMFY_ROOT,
    "input"
)
