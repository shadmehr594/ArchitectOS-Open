# ==========================================================
# ArchitectOS Conversation Language v1
#
# PHASE 08E — PERSIAN-FIRST INTERACTION
#
# Language preference is resolved from the CANONICAL PROJECT /
# CONVERSATION STATE, never from STT alone.
#
# Why: VOICE_07D proved that Persian STT on this machine can be
# unreliable (`auto` picked `pt`/`is`, and the model substitutes words).
# A speech-recognition guess must therefore NEVER be the authority for
# the reply language.
#
# Resolution priority
#   1. explicit request parameter        (highest, caller intent)
#   2. stored canonical project language (persisted, may be locked)
#   3. script of the TYPED text          (typed Persian is reliable)
#   4. STT detected language             (LOWEST TRUST — voice only)
#   5. default "en"
#
# Typed Persian is therefore fully testable without any STT.
# ==========================================================


from __future__ import annotations


import time


from core.project.project_workspace_v1 import project_workspace

from core.conversation.turn_semantics_v1 import script_of


CONTRACT = "ConversationLanguageV1"
VERSION = "1.0"


LANGUAGE_FA = "fa"
LANGUAGE_EN = "en"

SUPPORTED = (LANGUAGE_FA, LANGUAGE_EN)


MANIFEST_KEY = "conversation_language"


def is_persian(language):

    return str(language or "").lower().startswith("fa")


def is_english(language):

    return str(language or "").lower().startswith("en")


def normalize_language(value):

    text = str(value or "").strip().lower()

    if not text or text in ("auto", "unknown", "none"):

        return None

    if text.startswith("fa") or text.startswith("per"):

        return LANGUAGE_FA

    if text.startswith("en"):

        return LANGUAGE_EN

    return None


# ----------------------------------------------------------
# PROJECT-CANONICAL PREFERENCE
# ----------------------------------------------------------

def project_language(project_id):

    if not project_id:

        return None

    manifest = project_workspace.load(project_id) or {}

    stored = manifest.get(MANIFEST_KEY)

    if isinstance(stored, dict):

        return normalize_language(stored.get("language"))

    return normalize_language(stored)


def project_language_record(project_id):

    if not project_id:

        return None

    manifest = project_workspace.load(project_id) or {}

    stored = manifest.get(MANIFEST_KEY)

    if isinstance(stored, dict):

        return stored

    if stored:

        return {"language": normalize_language(stored)}

    return None


def set_project_language(project_id, language, source="explicit",
                         locked=True):

    """Persist the canonical project conversation language."""

    if not project_id:

        return None

    normalized = normalize_language(language)

    if not normalized:

        return None

    record = {

        "language": normalized,

        "source": source,

        "locked": bool(locked),

        "updated_at": time.time(),
    }

    project_workspace.update_fields(project_id, {MANIFEST_KEY: record})

    return record


# ----------------------------------------------------------
# RESOLUTION
# ----------------------------------------------------------

def text_script_language(text):

    script = script_of(text)

    if script == "persian":

        return LANGUAGE_FA

    if script == "english":

        return LANGUAGE_EN

    return None


def resolve_conversation_language(
    project_id=None,
    explicit=None,
    text=None,
    stt_language=None,
    input_type="text",
    persist=True,
):

    """Resolve the reply language and record WHY it was chosen."""

    # ---- 1. explicit request parameter ----
    requested = normalize_language(explicit)

    if requested:

        if persist and project_id:

            set_project_language(
                project_id, requested, source="explicit", locked=True
            )

        return _result(
            requested,
            "explicit_request",
            locked=True,
            low_trust=False,
            project_id=project_id,
        )

    # ---- 2. stored canonical project language ----
    record = project_language_record(project_id)

    stored = normalize_language((record or {}).get("language"))

    if stored:

        locked = bool((record or {}).get("locked"))

        # An UNLOCKED auto-detected preference may follow the typed
        # script when the user clearly switches language.  A LOCKED
        # preference (explicitly chosen by the user) never moves.
        script_language = text_script_language(text)

        if (
            not locked
            and script_language
            and script_language != stored
        ):

            if persist and project_id:

                set_project_language(
                    project_id,
                    script_language,
                    source="text_script_switch",
                    locked=False,
                )

            return _result(
                script_language,
                "text_script_switch",
                locked=False,
                low_trust=False,
                project_id=project_id,
            )

        return _result(
            stored,
            "project_conversation_state",
            locked=locked,
            low_trust=False,
            project_id=project_id,
        )

    # ---- 3. script of the typed text ----
    script_language = text_script_language(text)

    if script_language:

        if persist and project_id:

            set_project_language(
                project_id,
                script_language,
                source="text_script",
                locked=False,
            )

        return _result(
            script_language,
            "text_script",
            locked=False,
            low_trust=False,
            project_id=project_id,
        )

    # ---- 4. STT detected language (lowest trust, voice only) ----
    stt = normalize_language(stt_language)

    if stt:

        if persist and project_id:

            set_project_language(
                project_id, stt, source="stt_detected", locked=False
            )

        return _result(
            stt,
            "stt_detected",
            locked=False,
            low_trust=True,
            project_id=project_id,
        )

    # ---- 5. default ----
    return _result(
        LANGUAGE_EN,
        "default",
        locked=False,
        low_trust=False,
        project_id=project_id,
    )


def _result(language, source, locked, low_trust, project_id=None):

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "language": language,
        "source": source,

        "locked": bool(locked),

        # True when the language came from a speech-recognition guess.
        # Such a decision must never be treated as authoritative.
        "low_trust": bool(low_trust),

        "project_id": project_id,

        "persian": language == LANGUAGE_FA,

        "stt_dependent": source == "stt_detected",

        "canonical": source in (
            "explicit_request",
            "project_conversation_state",
            "text_script",
            "text_script_switch",
        ),
    }
