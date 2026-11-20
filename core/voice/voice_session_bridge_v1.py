# ==========================================================
# ArchitectOS Voice Session Bridge v1
#
# VOICE_07 — 07C SAME CHAT PIPELINE / 07F PERSISTENCE
#
# Product principle
#   Voice is an OPTIONAL INPUT/OUTPUT MODALITY.
#   It is NOT a separate assistant, memory, session or intent
#   pipeline. Text chat remains primary and canonical.
#
# This bridge therefore:
#   - uses the ONE ChatArchitect instance owned by app.py
#   - uses session_id = project_id (the Phase 06 canonical session)
#   - reuses the existing strategy controller, language path, intent
#     router, image registry, vision path and conversation store
#   - records the turn with input_type = "voice"
#
# It does NOT create a second assistant and does NOT keep its own
# history.
# ==========================================================


from __future__ import annotations


import os
import time


from config import runtime_config as RC

from core.chat.session_registry_v1 import session_registry

from core.render.render_strategy_controller_v1 import resolve_strategy

from core.voice.voice_capability_v1 import audit as audit_voice

from core.voice.voice_stt_whisper_v1 import transcribe as stt_transcribe

# SPOKEN_LANGUAGE_INTERPRETATION_V1 — lightweight, deterministic normaliser
# for casual speech / obvious STT noise. It keeps the raw transcript and adds
# a separate interpreted utterance for UNDERSTANDING. It is NOT a router.
from core.chat.spoken_language_interpretation_v1 import (
    interpret_utterance,
)


CONTRACT = "VoiceSessionBridgeV1"
VERSION = "1.0"


AUDIO_DIR_NAME = "voice"


class VoiceSessionBridge:

    VERSION = VERSION

    def __init__(self, chat, response_adapter, project_session,
                 project_workspace):

        self.chat = chat
        self.response_adapter = response_adapter
        self.project_session = project_session
        self.project_workspace = project_workspace

        print("🎙️ VOICE SESSION BRIDGE v1 ONLINE -> canonical ChatArchitect")

    # ======================================================
    # AUDIO STORAGE  (project-scoped, collision-safe)
    # ======================================================

    def store_audio(self, project_id, file_storage, extension=".webm"):

        """Keep the raw recording.

        Project-scoped when a project is open. When no project is open
        the recording still needs to exist so transcription can run, so
        it goes to a dedicated non-project voice inbox instead. It is
        never silently dropped.
        """

        if file_storage is None:

            return None

        try:

            if project_id:

                folder = self.project_workspace.subdir(
                    project_id, "documents"
                )

            else:

                folder = os.path.join(
                    RC.PROJECT_DATA_ROOT, "voice_inbox"
                )

                os.makedirs(folder, exist_ok=True)

        except Exception:

            return None

        import uuid

        name = "voice_%03d_%s%s" % (
            int(time.time()) % 1000,
            uuid.uuid4().hex[:6],
            extension,
        )

        target = os.path.join(folder, name)

        try:

            file_storage.save(target)

        except Exception:

            return None

        return {
            "path": target,
            "filename": name,
            "size_bytes": (
                os.path.getsize(target) if os.path.isfile(target) else 0
            ),
            "project_scoped": bool(project_id),
        }

    # ======================================================
    # TRANSCRIBE ONLY
    # ======================================================

    def transcribe(self, audio_path, language="auto"):

        started = time.time()

        result = stt_transcribe(audio_path, language=language)

        result["bridge_seconds"] = round(time.time() - started, 3)

        return result

    # ======================================================
    # CANONICAL TURN
    # ======================================================

    def run_turn(
        self,
        transcript,
        project_id=None,
        mode=None,
        quality=None,
        seed_mode=None,
        seed_value=None,
        voice_meta=None,
        language="auto",
    ):

        """Feed a transcript into the SAME ChatArchitect path as text."""

        if not transcript or not str(transcript).strip():

            return {
                "status": "error",
                "error": "empty_transcript",
                "message": "I did not catch that. Please try again.",
            }

        transcript = str(transcript)

        # ---- project + session (identical to the text path) ----
        if project_id:

            if self.project_session.current_project_id() != project_id:

                opened = self.project_session.open(project_id)

                if not opened:

                    return {
                        "status": "error",
                        "error": "project_not_found",
                        "project_id": project_id,
                    }

            session_id = project_id

        else:

            session_id = None

        # ---- the SAME strategy controller ----
        strategy = resolve_strategy(
            user_text=transcript,
            requested_mode=mode,
            requested_profile=quality,
            seed_mode=seed_mode,
            seed_value=seed_value,
        )

        if strategy.get("blocked"):

            return {
                "status": "error",
                "error": strategy.get("blocked_reason"),
                "message": strategy.get("message"),
            }

        # ==================================================
        # SPOKEN_LANGUAGE_INTERPRETATION_V1
        #
        # A VOICE turn is transcribed by Whisper and would otherwise be fed
        # to the chat path verbatim, so obvious casual-speech / STT noise
        # ("راجب مماری") could be lost. The interpreter produces a SEPARATE
        # `interpreted_utterance` used for UNDERSTANDING while the RAW
        # transcript is preserved verbatim (recorded + echoed back).
        #
        # It is NOT a router, it changes NO routing, it never invents
        # content and it changes nothing when the meaning is not obvious.
        # ==================================================

        utterance = transcript

        interpretation = None

        try:

            interpretation = interpret_utterance(
                transcript, language=language
            )

            candidate = (interpretation or {}).get(
                "interpreted_utterance"
            )

            if candidate and interpretation.get("changes"):

                utterance = candidate

        except Exception as _interpret_error:

            print(
                "SPOKEN LANGUAGE INTERPRETATION ERROR:",
                _interpret_error
            )

            interpretation = None

        _voice_meta = dict(voice_meta or {})

        _voice_meta["raw_transcript"] = transcript

        _voice_meta["interpreted_utterance"] = utterance

        _voice_meta["spoken_language_interpretation"] = (
            interpretation or {}
        )

        # ---- record the user turn as a VOICE turn ----
        if session_id:

            bundle = session_registry.resolve(session_id)

            state = bundle.get("conversation_state")

            if state is not None:

                state.add_message(
                    "user",
                    utterance,
                    [{
                        "kind": "voice",
                        "input_type": "voice",
                        "display_name": (voice_meta or {}).get("filename"),
                        **_voice_meta,
                    }],
                )

        # ---- the SAME ChatArchitect.handle ----
        started = time.time()

        try:

            result = self.chat.handle(

                utterance,

                context={

                    "session_id": session_id,

                    "preset": None,

                    "seed": strategy.get("seed"),

                    "preserve_level": None,

                    "render_profile": strategy.get("render_profile"),

                    "mode": strategy.get("resolved_mode"),

                    # Voice turns carry their provenance so the frozen
                    # text path can ignore it.
                    "input_type": "voice",

                    # PHASE 08E — the STT language is passed as a
                    # LOWEST-TRUST hint only. It must never be the
                    # authority for the reply language (07D proved
                    # Persian STT can be wrong on this machine).
                    "stt_language": language,

                    # SPOKEN_LANGUAGE_INTERPRETATION_V1 — the raw
                    # transcript as the audio actually decoded it, kept
                    # separate from the interpreted utterance that was
                    # handed to the chat path.
                    "raw_transcript": transcript,

                    "interpreted_utterance": utterance,

                    "voice_meta": _voice_meta,
                },
            )

        except Exception as error:

            return {
                "status": "error",
                "error": "chat_failed",
                "message": type(error).__name__ + ": " + str(error),
            }

        chat_seconds = round(time.time() - started, 3)

        try:

            formatted = self.response_adapter.adapt(result)

        except Exception as error:

            return {
                "status": "error",
                "error": "response_adapter_failed",
                "message": str(error),
            }

        # ---- record the assistant turn ----
        response_type = str((formatted or {}).get("type") or "")

        if session_id and "render" not in response_type:

            state = session_registry.resolve(session_id).get(
                "conversation_state"
            )

            if state is not None:

                text = (
                    (formatted or {}).get("result")
                    or (formatted or {}).get("message")
                    or ""
                )

                if text:

                    state.add_message("assistant", str(text))

        # ---- autosave (same project session) ----
        save_state = None

        if project_id:

            save_state = self.project_session.autosave(
                project_id,
                reason="user_message",
            )

        return {

            "status": "success",

            "input_type": "voice",

            # HUMAN_VOICE_CONVERSATION_V1 — RAW transcript is preserved
            # verbatim (what STT actually decoded). `transcript` keeps its
            # historic meaning. The interpreted utterance is exposed
            # SEPARATELY so a caller can always see both, and never gets a
            # silently-rewritten transcript in place of the raw one.
            "transcript": transcript,

            "raw_transcript": transcript,

            "interpreted_utterance": utterance,

            "response": formatted,

            "response_type": response_type,

            "output_type": (
                "text"
                if "render" not in response_type
                else "render"
            ),

            "strategy": {
                "requested_mode": strategy.get("requested_mode"),
                "resolved_mode": strategy.get("resolved_mode"),
                "routing_source": strategy.get("routing_source"),
                "render_profile": strategy.get("render_profile"),
                "seed_mode": strategy.get("seed_mode"),
                "seed": strategy.get("seed"),
                "mutates_node_graph": False,
            },

            "project_id": project_id,
            "session_id": session_id,

            "save_state": save_state,

            "timing": {
                "chat_seconds": chat_seconds,
            },

            "voice_meta": _voice_meta,
        }

    # ======================================================
    # DRY-RUN ROUTING  (no execution)
    #
    # Used by acceptance test F: prove the voice path produces the
    # correct intent/routing metadata for an image-generation request
    # WITHOUT letting ComfyUI execute. It consults the REAL intent
    # router and the REAL strategy controller, then stops.
    # ======================================================

    def dry_run_routing(self, transcript, mode=None, quality=None):

        from core.intent_router import intent_router as canonical_router

        routed = None

        try:

            routed = canonical_router.route(str(transcript or ""))

        except Exception as error:

            routed = {"error": type(error).__name__ + ": " + str(error)}

        strategy = resolve_strategy(
            user_text=transcript,
            requested_mode=mode,
            requested_profile=quality,
        )

        return {

            "status": "success",

            "dry_run": True,
            "executed": False,
            "comfy_invoked": False,

            "transcript": transcript,

            "routing": routed,

            "strategy": {
                "requested_mode": strategy.get("requested_mode"),
                "resolved_mode": strategy.get("resolved_mode"),
                "routing_source": strategy.get("routing_source"),
                "render_profile": strategy.get("render_profile"),
                "seed_mode": strategy.get("seed_mode"),
                "mutates_node_graph": False,
            },
        }

    # ======================================================
    # VOICE SETTINGS  (stored with the project UI state)
    # ======================================================

    DEFAULT_SETTINGS = {
        "voice_reply": "auto",
        "tts_voice": "auto",
        "stt_language": "auto",
        "mic_input": "default",
    }

    def settings(self, project_id=None):

        stored = {}

        if project_id:

            manifest = self.project_workspace.load(project_id) or {}

            stored = (manifest.get("ui") or {}).get("voice") or {}

        merged = dict(self.DEFAULT_SETTINGS)

        merged.update(stored)

        return merged

    def save_settings(self, project_id, settings):

        if not project_id:

            return None

        manifest = self.project_workspace.load(project_id)

        if not manifest:

            return None

        ui = dict(manifest.get("ui") or {})

        voice = dict(ui.get("voice") or {})

        for key in ("voice_reply", "tts_voice", "stt_language", "mic_input"):

            if key in (settings or {}):

                voice[key] = settings[key]

        ui["voice"] = voice

        self.project_workspace.update_fields(project_id, {"ui": ui})

        self.project_session.autosave(project_id, reason="mode_change")

        return self.settings(project_id)

    # ======================================================
    # STATUS
    # ======================================================

    def status(self, project_id=None):

        capability = audit_voice()

        return {

            "contract": CONTRACT,
            "version": VERSION,

            "voice": capability["capabilities"],

            "limitations": capability["limitations"],

            "environment": {
                "interpreter": capability["environment"]["interpreter"],
                "model": capability["environment"]["model"],
            },

            "settings": self.settings(project_id),

            "project_id": project_id,

            "canonical": {
                "same_chat_architect": True,
                "session_is_project": True,
                "separate_voice_assistant": False,
                "separate_voice_memory": False,
            },
        }
