# ==========================================================
# ArchitectOS Vision Analysis Store v1
#
# VISION_REPORT_LANGUAGE_01
#
# The LAST architectural image interpretation of a project, kept so the
# teacher can ask for it again in another language.
#
# WHY THIS EXISTS
#
# The user analysed a photo (answered in English, by mistake), then
# asked "میشه تحلیل عکستو فارسی برام بگي". Nothing in the project held
# the interpretation any more, so the request could only be answered by
# the generic LLM — which invented a discussion of "عکستو فارسی" as if
# it were an architectural element. Persisting the last interpretation
# is what makes a language switch a real, honest re-render.
#
# Project-scoped, additive, tiny. It stores ONLY the read-only
# interpretation contract plus the text that produced it. No image
# bytes, no geometry, no render, no learning.
# ==========================================================


from __future__ import annotations


import os
import time


from core.project.project_workspace_v1 import (
    project_workspace,
    atomic_write_json,
    read_json,
)


CONTRACT = "VisionAnalysisStoreV1"
VERSION = "1.0"


# The interpretation keys this store is allowed to carry. Anything else
# in the payload is dropped rather than persisted blindly.
CARRIED_KEYS = (
    "contract",
    "version",
    "space_type",
    "confidence",
    "observed_elements",
    "architectural_interpretation",
    "spatial_relations",
    "possible_function",
    "unknowns",
    "limitations",
    "geometry_authoritative",
)


class VisionAnalysisStoreV1:

    CONTRACT = CONTRACT
    VERSION = VERSION

    FILE = "vision_analysis.json"

    def __init__(self):

        print(
            "VISION ANALYSIS STORE v1.0 ONLINE "
            "(the last image interpretation, per project)"
        )

    def path(self, project_id):

        """Storage path. Never creates a folder on a READ."""

        if not project_id:

            return None

        return os.path.join(
            project_workspace.project_dir(project_id),
            "conversations",
            self.FILE,
        )

    def save(self, project_id, interpretation, source_text=None,
             image_id=None):

        """Persist the last interpretation. Returns True on success."""

        if not project_id or not isinstance(interpretation, dict):

            return False

        path = self.path(project_id)

        if not path:

            return False

        try:

            if not project_workspace.exists(project_id):

                return False

            payload = {

                "contract": CONTRACT,
                "version": VERSION,

                "project_id": project_id,

                "image_id": image_id,

                "source_text": str(source_text or ""),

                "saved_at": time.time(),

                "interpretation": {
                    key: interpretation.get(key)
                    for key in CARRIED_KEYS
                    if key in interpretation
                },
            }

            os.makedirs(os.path.dirname(path), exist_ok=True)

            atomic_write_json(path, payload)

            return True

        except Exception as error:

            print(
                "VISION ANALYSIS STORE SAVE ERROR:",
                type(error).__name__,
                error,
            )

            return False

    def load(self, project_id):

        """The last interpretation dict, or None."""

        path = self.path(project_id)

        if not path:

            return None

        try:

            payload = read_json(path, default=None)

        except Exception:

            return None

        if not isinstance(payload, dict):

            return None

        interpretation = payload.get("interpretation")

        if not isinstance(interpretation, dict):

            return None

        return interpretation

    def source_text(self, project_id):

        path = self.path(project_id)

        if not path:

            return None

        try:

            payload = read_json(path, default=None)

        except Exception:

            return None

        if not isinstance(payload, dict):

            return None

        return payload.get("source_text") or None


vision_analysis_store = VisionAnalysisStoreV1()
