# ==========================================================
# ArchitectOS Image Handler v2.7 STABLE FIXED
# Image Generate + Image Edit Routing
#
# Compatible:
# RenderRuntime v7.3
# Intent Router v69.4
# Semantic Intent Engine
# Image Response Adapter v1
#
# Fix:
# - Syntax repair
# - Architectural Intent preservation
# - Continuation state protection
# - Prompt pipeline stability
# - Render context persistence
# - Upload/Edit repair
# ==========================================================


import os
from copy import deepcopy


from core.chat.chat_attachment import chat_attachment_service

# CHAT_LANGUAGE_02 — session scoped conversation state
from core.chat.session_registry_v1 import session_registry


# SOURCE_BOUND_ARCHITECTURAL_CONTINUITY_V1
#
# Registry records already persist through ProjectRegistryBridgeV1.  Keep the
# image-owned payload deliberately small and schema-bound: prompts, histories,
# raw bytes and unrecognised model output never enter this snapshot.
_INTENT_SNAPSHOT_CONTRACT = "ArchitecturalIntentSnapshotV1"
_INTENT_SNAPSHOT_VERSION = "1.0"

_SNAPSHOT_INTENT_FIELDS = (
    "building_type", "style", "materials", "facade", "facade_details",
    "preserve_constraints", "objects", "environment", "lighting",
    "floors", "floor_count", "levels", "roof", "roof_geometry",
    "massing", "building_massing", "silhouette", "building_silhouette",
    "openings", "windows", "doors", "balconies", "balcony_geometry",
    "dimensions", "proportions", "camera", "camera_parameters",
    "perspective", "view",
)

_TRUSTED_FLOOR_SOURCES = {
    "USER_EXPLICIT", "USER_TEXT", "USER_CONFIRMATION",
}

_OBSERVATION_FLOOR_SOURCES = {
    "VISION", "VISION_OBSERVATION", "OBSERVED", "INFERRED", "MODEL",
    "UNCERTAIN_OBSERVATION",
}


def _positive_int(value):

    if value is None or isinstance(value, bool):

        return None

    try:

        parsed = int(value)

        if float(value) == parsed and parsed > 0:

            return parsed

    except (TypeError, ValueError, OverflowError):

        pass

    return None


def _json_safe_copy(value, depth=0):
    """Return a bounded JSON-safe copy, or raise for unsupported values."""

    if depth > 12:

        raise ValueError("snapshot_too_deep")

    if value is None or isinstance(value, (bool, int, float)):

        return value

    if isinstance(value, str):

        if len(value) > 4096:

            raise ValueError("snapshot_string_too_long")

        return value

    if isinstance(value, (list, tuple)):

        if len(value) > 256:

            raise ValueError("snapshot_list_too_long")

        return [_json_safe_copy(item, depth + 1) for item in value]

    if isinstance(value, dict):

        if len(value) > 256:

            raise ValueError("snapshot_object_too_large")

        copied = {}

        for key, item in value.items():

            if not isinstance(key, str) or len(key) > 128:

                raise ValueError("snapshot_invalid_key")

            copied[key] = _json_safe_copy(item, depth + 1)

        return copied

    raise ValueError("snapshot_non_serializable_value")


def _trusted_floor_contract(intent):
    """Return (status, contract, value, observation) without inference."""

    if not isinstance(intent, dict):

        return "absent", None, None, None

    contract = intent.get("floor_count")

    if not isinstance(contract, dict):

        return "absent", None, None, None

    if contract.get("contract") != "FloorCountV1":

        return "invalid", None, None, None

    source = str(contract.get("source") or "").strip().upper()
    value = _positive_int(contract.get("value"))

    if source in _OBSERVATION_FLOOR_SOURCES:

        observation = {
            "contract": "FloorCountObservationV1",
            "value": value,
            "source": contract.get("source"),
        }

        if contract.get("confidence") is not None:

            observation["confidence"] = contract.get("confidence")

        return "observation", None, None, observation

    if source not in _TRUSTED_FLOOR_SOURCES:

        return "unknown", None, None, None

    if value is None:

        return "invalid", None, None, None

    # A trusted contract must agree with any accompanying scalar count.  The
    # generic default levels dictionary is intentionally not authoritative.
    scalar = _positive_int(intent.get("floors"))

    if scalar is not None and scalar != value:

        return "conflict", None, None, None

    safe_contract = _json_safe_copy(contract)

    return "trusted", safe_contract, value, None


def _sanitize_effective_intent(intent, strict=False):
    """Allowlist and validate the intent stored on one image record."""

    if not isinstance(intent, dict):

        return None, "intent_not_object"

    if strict:

        persisted_allowed = set(_SNAPSHOT_INTENT_FIELDS) | {
            "architectural_observations",
        }

        if any(key not in persisted_allowed for key in intent):

            return None, "snapshot_unrecognized_field"

    if intent.get("architectural_conflicts"):

        return None, "snapshot_conflicting_data"

    status, floor_contract, floor_value, observation = (
        _trusted_floor_contract(intent)
    )

    if status in ("invalid", "conflict"):

        return None, "floor_count_" + status

    sanitized = {}

    try:

        for key in _SNAPSHOT_INTENT_FIELDS:

            if key not in intent:

                continue

            if key in ("floors", "floor_count", "levels"):

                continue

            value = intent.get(key)

            if value not in (None, "", [], {}):

                sanitized[key] = _json_safe_copy(value)

        if status == "trusted":

            sanitized["floors"] = floor_value
            sanitized["floor_count"] = floor_contract

            levels = intent.get("levels")

            if isinstance(levels, dict):

                level_count = _positive_int(
                    levels.get("total", levels.get("above_ground"))
                )

                if level_count not in (None, floor_value):

                    return None, "floor_count_conflict"

                sanitized["levels"] = _json_safe_copy(levels)

        if observation:

            sanitized["architectural_observations"] = {
                "floor_count": _json_safe_copy(observation)
            }

        existing_observations = intent.get("architectural_observations")

        if isinstance(existing_observations, dict):

            floor_observation = existing_observations.get("floor_count")

            if isinstance(floor_observation, dict):

                observation_source = str(
                    floor_observation.get("source") or ""
                ).strip().upper()

                if (
                    floor_observation.get("contract")
                        == "FloorCountObservationV1"
                    and observation_source in _OBSERVATION_FLOOR_SOURCES
                ):

                    compact_observation = {
                        "contract": "FloorCountObservationV1",
                        "value": _positive_int(
                            floor_observation.get("value")
                        ),
                        "source": floor_observation.get("source"),
                    }

                    if floor_observation.get("confidence") is not None:

                        compact_observation["confidence"] = (
                            floor_observation.get("confidence")
                        )

                    sanitized["architectural_observations"] = {
                        "floor_count": _json_safe_copy(compact_observation)
                    }

    except (TypeError, ValueError, OverflowError) as error:

        return None, str(error)

    return sanitized, None


# ==========================================================
# UPLOAD_REJECTION_MESSAGE_01
#
# A rejected upload used to return ONLY an error code. The response adapter
# falls back to the default text of the `image_upload` surface, which is
# «تصویر دریافت شد.» — a success-sounding sentence — so the user was told the
# image had been received after it had in fact been refused. The rejection
# now carries its own user-facing reason.
# ==========================================================

_IMAGE_UPLOAD_REJECTION_TEXT = {

    "unsupported_image_format":
        "این فایل به عنوان تصویر پذیرفته نشد: فرمت آن پشتیبانی نمی‌شود. "
        "فرمت‌های پشتیبانی‌شده: JPG، PNG و WebP.",

    "invalid_upload_path":
        "این فایل ذخیره نشد: مسیر آپلود نامعتبر است.",

    "attachment_registration_failed":
        "این فایل ذخیره شد اما به عنوان پیوست قابل استفاده ثبت نشد.",
}


def _image_upload_rejection(code):

    return _IMAGE_UPLOAD_REJECTION_TEXT.get(

        code,

        "این فایل به عنوان تصویر پذیرفته نشد (کد: %s)." % code,
    )



# ==========================================================
# ARCHITECTURAL_VISION_RUNTIME_COMPLETION_V1 — OUTPUT OBSERVATION
#
# The Vision stack (Ollama facade provider -> mapped contract) already
# existed and already worked; `design_constraint_fidelity_v1.observe_output()`
# already wrapped it. What did NOT exist was the runtime call: the handler
# evaluated fidelity with `observed=None` on every turn, so a successful
# render could never be verified and every verdict stayed UNVERIFIED.
#
# This helper is the missing connection. It inspects the ACTUAL produced PNG
# — never the sampler prompt, which is not evidence of what was drawn.
#
# It fails soft: any problem (no image, file missing, ComfyUI cannot release
# VRAM, provider unavailable) returns an observation with `available: False`
# so the caller reports UNVERIFIED. It never invents a count.
# ==========================================================

def _produced_image_path(render_result):
    """Absolute path of the image this render actually wrote."""

    if not isinstance(render_result, dict):
        return None

    try:
        from config import runtime_config as _RC
        output_dir = _RC.COMFYUI_OUTPUT_DIR
    except Exception:  # noqa: BLE001
        return None

    execution = render_result.get("execution") or {}

    for item in execution.get("images") or []:

        if isinstance(item, dict) and item.get("filename"):

            return os.path.join(
                output_dir,
                item.get("subfolder") or "",
                item["filename"],
            )

    return None


# ==========================================================
# T2I_ARCHITECTURAL_FIDELITY_REPORTING_V1 — TRUTHFUL RESULT REPORTING
#
# MEASURED DEFECT (2026-11-03): a text-to-image turn whose prompt said
# "The building has exactly 25 floors." produced a tower of roughly fifteen
# storeys, and the Chat result carried no architectural verdict at all — so a
# technically successful render read as a satisfied architectural constraint.
# The instruction had reached the sampler; the building did not match it.
#
# This report keeps the two facts permanently separate:
#
#   technical_status      — did the render engine produce an image?
#   architectural_status  — was the REQUESTED architecture actually observed?
#
# It only re-shapes the verdict that `design_constraint_fidelity_v1.evaluate()`
# already produced. It adds no detector, no counter and no inference, and it
# never changes control flow: `advisory` is True for every value, the image is
# never discarded, and no retry is triggered.
#
# A missing observation is reported as NOT_VERIFIED. It is NEVER reported as a
# match, and the requested count is never echoed back as an observed one.
# ==========================================================

#: `design_constraint_fidelity_v1` floor status -> reporting status.
_FIDELITY_REPORT_STATUS = {
    "FLOOR_COUNT_VERIFIED": "VERIFIED",
    "FLOOR_COUNT_MISMATCH": "MISMATCH",
    "FLOOR_COUNT_UNVERIFIED": "NOT_VERIFIED",
    "FLOOR_COUNT_NOT_REQUESTED": "NOT_REQUESTED",
}


def _architectural_fidelity_report(fidelity, technical_status, has_image):
    """Re-shape an existing fidelity verdict into a truthful result report.

    ``fidelity`` is the dict returned by
    ``design_constraint_fidelity_v1.evaluate()`` (or None when no evaluation
    was produced). Nothing is inferred: an absent observation yields
    NOT_VERIFIED and ``observed_floors`` stays None.
    """

    report = {
        "contract": "ArchitecturalFidelityReportV1",
        "version": "1.0",
        # ---- technical completion, unchanged -------------------------
        "technical_status": technical_status,
        "image_preserved": bool(has_image),
        # ---- architectural verification, kept separate ---------------
        "architectural_status": "NOT_VERIFIED",
        "floor_status": "NOT_VERIFIED",
        "floor_reason": "no fidelity evaluation was produced for this render",
        "requested_floors": None,
        "observed_floors": None,
        "observation_available": False,
        "observation_source": None,
        "confidence": "NONE",
        "provenance": {},
        "instruction_carried_the_request": None,
        "instruction_is_not_evidence_of_result": True,
        # Advisory only: never a hard failure, never a retry trigger.
        "advisory": True,
    }

    if not isinstance(fidelity, dict):

        return report

    requested = fidelity.get("requested") if isinstance(
        fidelity.get("requested"), dict
    ) else {}

    observed = fidelity.get("observed") if isinstance(
        fidelity.get("observed"), dict
    ) else {}

    floor_status = fidelity.get("floor_status")

    status = _FIDELITY_REPORT_STATUS.get(floor_status, "NOT_VERIFIED")

    # The observed count is carried ONLY when the fidelity layer established
    # it as a grounded total. A lower bound or a visible-level count is not a
    # storey count and must not be published as one.
    observed_floors = observed.get("floors")
    if not isinstance(observed_floors, int) or isinstance(observed_floors, bool):
        observed_floors = None

    available = bool(observed.get("available"))

    consistency = observed.get("floor_consistency") if isinstance(
        observed.get("floor_consistency"), dict
    ) else {}

    count_type = observed.get("floor_count_type")

    if observed_floors is not None and consistency.get("status") == "CONSISTENT":
        confidence = "HIGH"
    elif available:
        confidence = "LOW"
    else:
        confidence = "NONE"

    report.update({
        "architectural_status": status,
        "floor_status": status,
        "floor_reason": fidelity.get("floor_reason"),
        "requested_floors": requested.get("floors"),
        "observed_floors": observed_floors,
        "observation_available": available,
        "observation_source": observed.get("source") if available else None,
        "confidence": confidence,
        "provenance": {
            "source": observed.get("source"),
            "floor_count_type": count_type,
            "floor_consistency": consistency.get("status"),
            "floor_consistency_reason": consistency.get("reason"),
            "view_partial": observed.get("view_partial"),
            "visible_floor_count_lower_bound": observed.get(
                "visible_floor_count_lower_bound"
            ),
            "storey_divisions_legible": observed.get("storey_divisions_legible"),
            "fidelity_contract": fidelity.get("contract"),
            "fidelity_version": fidelity.get("version"),
        },
        "instruction_carried_the_request": fidelity.get(
            "instruction_carried_the_request"
        ),
    })

    return report


def _observe_rendered_output(render_result):
    """Observe the produced render with the EXISTING Vision provider.
    Returns ``{"available", "reason", "contract", "image", "provider",
    "model"}``. ``available`` is False whenever the image could not be
    inspected, which the fidelity layer reports as UNVERIFIED.
    """

    observation = {
        "available": False,
        "reason": None,
        "contract": None,
        "image": None,
        "provider": None,
        "model": None,
    }

    path = _produced_image_path(render_result)

    if not path:
        observation["reason"] = "no_produced_image"
        return observation

    observation["image"] = path

    if not os.path.exists(path):
        observation["reason"] = "produced_image_missing"
        return observation

    # ComfyUI still holds its models after a render; the vision model needs
    # the GPU. The established H1 release fails closed, so a refused release
    # becomes "unobserved", never a guessed verdict.
    try:
        from core.runtime.gpu_handoff_v1 import release_comfyui_for_vision
        release = release_comfyui_for_vision()
        if isinstance(release, dict) and release.get("status") == "blocked":
            observation["reason"] = "comfyui_release_blocked"
            return observation
    except Exception as exc:  # noqa: BLE001
        observation["reason"] = "comfyui_release_failed: %r" % (exc,)
        return observation

    try:
        from core.vision.design_constraint_fidelity_v1 import observe_output
        result = observe_output(path)
    except Exception as exc:  # noqa: BLE001
        observation["reason"] = "observation_failed: %r" % (exc,)
        return observation

    observation["provider"] = result.get("provider")
    observation["model"] = result.get("model")

    contract = result.get("contract")

    if not result.get("available") or not isinstance(contract, dict):
        observation["reason"] = result.get("reason") or "no_usable_observation"
        return observation

    observation["available"] = True
    observation["contract"] = contract
    return observation


class ImageHandler:

    def __init__(
        self,
        render_runtime,
        result_bridge,
        semantic_intent,
        image_bridge,
        image_response,
        writeback,
        state,
        prompt_builder=None
    ):


        self.render_runtime = render_runtime
        self.result_bridge = result_bridge
        self.semantic_intent = semantic_intent
        self.image_bridge = image_bridge
        self.image_response = image_response
        self.writeback = writeback

        # CHAT_LANGUAGE_02: keep the injected state as the fallback and
        # resolve per-request session state through the property below.
        self._state = state

        self.prompt_builder = prompt_builder
        self.attachment_service = chat_attachment_service


        print(
            "🖼️ IMAGE HANDLER v2.7 FIXED ONLINE"
        )


    # ======================================================
    # CHAT_LANGUAGE_02 — SESSION SCOPED STATE
    # ======================================================

    @property
    def state(self):

        return session_registry.current_state(
            self._state
        )


    # ======================================================
    # SOURCE_BOUND_ARCHITECTURAL_CONTINUITY_V1
    # ======================================================

    @staticmethod
    def _current_intent_ownership():

        bundle = session_registry.current() or {}
        session_id = bundle.get("session_id")
        project_id = None

        try:

            from flask import g, has_request_context

            if has_request_context():

                project_id = getattr(g, "project_id", None)

        except Exception:

            project_id = None

        try:

            from core.project.project_registry_bridge_v1 import (
                project_registry_bridge,
            )

            project_id = (
                project_id
                or project_registry_bridge.current_project_id()
            )

        except Exception:

            project_id = None

        # Legacy/non-project sessions still receive a stable ownership key;
        # project sessions use the real project id from the existing bridge.
        return {
            "session_id": session_id,
            "project_id": project_id or session_id,
        }


    def _attach_intent_snapshot(
        self,
        record,
        architectural_intent,
        origin,
        parent_image_id=None,
    ):

        if not isinstance(record, dict):

            return record

        sanitized, error = _sanitize_effective_intent(
            architectural_intent
        )

        if error or not sanitized:

            if error:

                print("⚠️ INTENT SNAPSHOT REJECTED:", error)

            return record

        ownership = self._current_intent_ownership()
        session_id = ownership.get("session_id")

        if (
            not session_id
            or str(record.get("session_id")) != str(session_id)
        ):

            print("⚠️ INTENT SNAPSHOT REJECTED: ownership_mismatch")

            return record

        snapshot = {
            "contract": _INTENT_SNAPSHOT_CONTRACT,
            "version": _INTENT_SNAPSHOT_VERSION,
            "source_image_id": record.get("image_id"),
            "source_session_id": session_id,
            "source_project_id": ownership.get("project_id"),
            "source_type": record.get("source_type"),
            "parent_image_id": parent_image_id,
            "intent": sanitized,
            "provenance": {
                "origin": origin,
                "authority": "effective_architectural_intent",
                "inherited_from_image_id": parent_image_id,
                "vision_promoted": False,
            },
        }

        from core.vision.image_registry_v1 import image_registry

        updated = image_registry.update_record(
            session_id,
            record.get("image_id"),
            {"architectural_intent_snapshot": snapshot},
        )

        return updated or record


    def resolve_source_bound_intent(self, image_record):
        """Resolve a validated snapshot owned by the selected source."""

        ownership = self._current_intent_ownership()

        if not isinstance(image_record, dict):

            return {
                "status": "unknown", "reason": "missing_source_image",
                "intent": {}, **ownership,
            }

        snapshot = image_record.get("architectural_intent_snapshot")

        if snapshot is None:

            return {
                "status": "unknown", "reason": "snapshot_missing",
                "intent": {}, **ownership,
            }

        if (
            not isinstance(snapshot, dict)
            or snapshot.get("contract") != _INTENT_SNAPSHOT_CONTRACT
            or snapshot.get("version") != _INTENT_SNAPSHOT_VERSION
        ):

            return {
                "status": "rejected", "reason": "snapshot_malformed",
                "intent": {}, **ownership,
            }

        allowed_snapshot_fields = {
            "contract", "version", "source_image_id", "source_session_id",
            "source_project_id", "source_type", "parent_image_id", "intent",
            "provenance",
        }

        provenance = snapshot.get("provenance")

        if (
            any(key not in allowed_snapshot_fields for key in snapshot)
            or not isinstance(provenance, dict)
            or provenance.get("vision_promoted") is not False
            or provenance.get("authority") != "effective_architectural_intent"
            or snapshot.get("source_type") != image_record.get("source_type")
            or snapshot.get("parent_image_id")
                != image_record.get("parent_image_id")
        ):

            return {
                "status": "rejected", "reason": "snapshot_malformed",
                "intent": {}, **ownership,
            }

        expected = {
            "source_image_id": image_record.get("image_id"),
            "source_session_id": ownership.get("session_id"),
            "source_project_id": ownership.get("project_id"),
        }

        for key, value in expected.items():

            if str(snapshot.get(key)) != str(value):

                return {
                    "status": "rejected",
                    "reason": "snapshot_ownership_mismatch",
                    "intent": {}, **ownership,
                }

        if str(image_record.get("session_id")) != str(
            ownership.get("session_id")
        ):

            return {
                "status": "rejected",
                "reason": "snapshot_ownership_mismatch",
                "intent": {}, **ownership,
            }

        sanitized, error = _sanitize_effective_intent(
            snapshot.get("intent"),
            strict=True,
        )

        if error:

            return {
                "status": "rejected", "reason": error,
                "intent": {}, **ownership,
            }

        return {
            "status": "trusted",
            "reason": None,
            "intent": sanitized or {},
            "snapshot": deepcopy(snapshot),
            **ownership,
        }


    @staticmethod
    def sanitize_architectural_intent(intent):

        sanitized, error = _sanitize_effective_intent(intent)

        return {
            "status": "trusted" if not error else "rejected",
            "reason": error,
            "intent": sanitized or {},
        }


    # ======================================================
    # VISION_IMAGE_REGISTRY_04 — RENDER AUTO-REGISTRATION
    #
    # A successful render is registered in the session image
    # registry so it can be referenced later without the user
    # saving or re-uploading it.
    # ======================================================

    def _register_render_output(
        self,
        final_render,
        attachments=None,
        architectural_intent=None,
    ):

        from core.vision.image_session_v1 import (
            register_asset as register_session_asset,
        )


        bundle = session_registry.current()

        session_key = (bundle or {}).get("session_id")

        if not session_key:

            return None


        asset = None

        if isinstance(final_render, dict):

            asset = (
                final_render.get("image_asset")
                or final_render.get("image")
            )

        path = asset.get("path") if isinstance(asset, dict) else None


        if not path:

            return None


        # never register a fabricated or missing asset
        if not os.path.isfile(str(path)):

            print(
                "⚠️ RENDER NOT REGISTERED (file missing):",
                path
            )

            return None


        attachment = None

        if isinstance(attachments, (list, tuple)) and attachments:

            attachment = attachments[0]


        record = register_session_asset(

            session_key,

            path=str(path),

            source_type="text_to_image",

            label=(asset or {}).get("filename"),

            asset=asset,

            attachment=attachment,

            make_active=True,

        )

        record = self._attach_intent_snapshot(
            record,
            architectural_intent,
            origin="generated_effective_intent",
        )


        print(
            "🗃️ RENDER REGISTERED:",
            record.get("image_id"),
            "| ordinal",
            record.get("ordinal")
        )


        return record



    # ======================================================
    # IMAGE_TO_IMAGE_05 — DERIVED OUTPUT REGISTRATION
    #
    # An img2img result is registered with source_type
    # "image_to_image" and lineage back to its source image, so the
    # next conversational edit can chain from the derived image.
    # ======================================================

    def _register_derived_output(
        self,
        final_render,
        attachments=None,
        parent_image_id=None,
        architectural_intent=None,
    ):

        from core.vision.image_session_v1 import (
            register_asset as register_session_asset,
        )


        bundle = session_registry.current()

        session_key = (bundle or {}).get("session_id")

        if not session_key:

            return None


        asset = None

        if isinstance(final_render, dict):

            asset = (
                final_render.get("image_asset")
                or final_render.get("image")
            )

        path = asset.get("path") if isinstance(asset, dict) else None


        if not path:

            return None


        if not os.path.isfile(str(path)):

            print(
                "⚠️ DERIVED NOT REGISTERED (file missing):",
                path
            )

            return None


        attachment = None

        if isinstance(attachments, (list, tuple)) and attachments:

            attachment = attachments[0]


        record = register_session_asset(

            session_key,

            path=str(path),

            source_type="image_to_image",

            label=(asset or {}).get("filename"),

            parent_image_id=parent_image_id,

            asset=asset,

            attachment=attachment,

            make_active=True,

        )

        record = self._attach_intent_snapshot(
            record,
            architectural_intent,
            origin="derived_effective_intent",
            parent_image_id=parent_image_id,
        )


        print(
            "🗃️ DERIVED REGISTERED:",
            record.get("image_id"),
            "| ordinal",
            record.get("ordinal"),
            "| parent",
            parent_image_id
        )


        return record



    # ======================================================
    # IMAGE GENERATE
    # ======================================================

    def handle_image_generate(
        self,
        text,
        image=None,
        architectural_intent=None,
        design_state=None,
        compiled_render_prompt=None,
        preset_resolution=None,
        terminology=None,
        render_seed=None,
        image_asset=None,
        image_bindings=None,
        conditioned=False,
        mask_asset=None,
        kontext_edit=False,
        architectural_instruction=None,
        uso_reference=None,
        uso_reference_meta=None,
        verify_render=None,
        r4_preservation_contract=None
    ):


        try:


            if not isinstance(
                architectural_intent,
                dict
            ):

                architectural_intent = {}



            if not isinstance(
                design_state,
                dict
            ):

                design_state = {}



            # ==============================================
            # STATE RECOVERY
            # ==============================================

            current_state = {}


            try:

                current_state = self.state.get()

            except Exception as e:

                print(
                    "STATE READ ERROR:",
                    e
                )



            if not isinstance(
                current_state,
                dict
            ):

                current_state = {}



            # ==============================================
            # T2I_I2I_CHAT_TO_IMAGE_EXECUTION_V1
            # PENDING IMAGE-GENERATION COMPLETION
            #
            # A previous turn asked the user for a missing specification
            # ("به ابعاد آن نیاز دارم"). The user's answer ("5*5*5 سانتیمتر")
            # is a COMPLETION of that request, not a new topic: it is merged
            # with the pending request so the object, the appearance and the
            # dimensions all reach the workflow.
            #
            # The merge predicate is the SAME one the router used to select
            # this route (core.intent_router.is_pending_image_answer), so the
            # routing decision and the prompt can never disagree.
            # ==============================================

            request_text = text

            pending_request = current_state.get(
                "pending_image_generate"
            )

            if isinstance(pending_request, dict) and pending_request.get("prompt"):

                try:

                    from core.intent_router import (
                        is_pending_image_answer,
                        merge_pending_image_prompt,
                    )

                    if is_pending_image_answer(text):

                        merged = merge_pending_image_prompt(
                            pending_request,
                            text
                        )

                        if merged:

                            request_text = merged

                            print(
                                "🖼️ PENDING IMAGE REQUEST COMPLETED"
                            )

                except Exception as e:

                    print(
                        "PENDING IMAGE MERGE ERROR:",
                        e
                    )


            # ==============================================
            # FACADE-04D.3C-2 — DUAL-IMAGE / CONDITIONED PRECEDENCE
            #
            # An EXPLICIT dual-image (role-bound) or conditioned request MUST
            # keep the dual-image rendering path. The legacy edit delegation
            # below would otherwise consume it whenever the prompt carries an
            # edit keyword — the mandated restyle phrase "بازطراحی کن" does —
            # silently discarding IMAGE A, the role/node bindings and the
            # conditioned graph, because handle_image_edit() has no
            # `image_bindings` / `conditioned` parameter to carry them.
            #
            # The precedence is therefore resolved BEFORE the edit detector.
            # The edit detector itself is NOT weakened: a genuine single-image
            # edit (no bindings, not conditioned) still takes the legacy route.
            # ==============================================

            if self._is_dual_image_request(
                image_bindings,
                conditioned
            ):

                contract_error = self._dual_binding_contract_error(
                    image_bindings
                )

                if contract_error:

                    print(
                        "⛔ DUAL-IMAGE ROUTE BLOCKED:",
                        contract_error
                    )

                    return self._dual_route_blocked(
                        contract_error,
                        image_bindings,
                        conditioned
                    )

                print(
                    "🖼️ DUAL-IMAGE ROUTE (edit-keyword delegation skipped)"
                )

            elif self.is_image_edit_request(text):

                print(
                    "🖼️ IMAGE EDIT ROUTE"
                )

                return self.handle_image_edit(
                    text,
                    image,
                    mask_asset=mask_asset,
                    kontext_edit=kontext_edit,
                    verify_render=verify_render,
                )



            # ==============================================
            # CONTINUATION CHECK
            # ==============================================

            normalized_text = str(
                text
            ).lower().strip()



            continuation_words = [

                "تایید شد رندر بگیر",
                "رندر بگیر",
                "render",
                "generate"

            ]



            is_continuation = (

                normalized_text in [

                    x.lower()

                    for x in continuation_words

                ]

            )



            stored_intent = current_state.get(
                "last_architectural_intent"
            )



            if is_continuation:


                print(
                    "🧠 CONTINUATION MODE"
                )


                if isinstance(
                    stored_intent,
                    dict
                ):


                    architectural_intent = stored_intent.copy()


                    print(
                        "🧠 INTENT RESTORED"
                    )



            else:


                new_words = [

                    "طراحی کن",
                    "بساز",
                    "ایجاد کن",
                    "create",
                    "draw",
                    "رندر کن"

                ]



                if any(

                    word in normalized_text

                    for word in new_words

                ):


                    print(
                        "🆕 NEW REQUEST"
                    )


                    architectural_intent = {}



            # ==============================================
            # SEMANTIC INTENT
            # ==============================================

            if architectural_intent:


                intent = architectural_intent.copy()


                print(
                    "🧠 USING EXISTING INTENT"
                )


            else:


                print(
                    "🧠 SEMANTIC EXTRACTION"
                )


                intent = self.semantic_intent.extract(
                    request_text
                )



            if not isinstance(
                intent,
                dict
            ):

                intent = {}



            intent["prompt"] = request_text



            print(
                "🔥 RAW INTENT:",
                intent
            )



            normalized_intent = self.normalize_intent(
                intent,
                floor_constraint=architectural_instruction,
            )



            architectural_intent.update(
                normalized_intent
            )



            print(
                "🔥 ARCH INTENT:",
                architectural_intent
            )
            # ==============================================
            # DESIGN STATE
            # ==============================================

            # Preserve the approved design supplied by ChatArchitect.  State
            # recovery is only a fallback for legacy callers.
            recovered_design_state = self.extract_design_state()
            if not design_state:
                design_state = recovered_design_state


            architectural_intent[

                "design_state"

            ] = design_state



            project_state = {

                "design_state":

                    design_state,


                "previous_intent":

                    architectural_intent

            }



            print(
                "🧠 PROJECT STATE:",
                project_state
            )



            # ==============================================
            # PROMPT BUILDER BRIDGE
            # ==============================================

            if self.prompt_builder:


                prompt_input = {


                    "prompt":

                        request_text,


                    "architectural_intent":

                        architectural_intent,


                    # T2I_PRODUCTION_INTENT_HANDOFF_FIX_V1 — the storey count
                    # the user ACTUALLY stated, taken from the validated
                    # render instruction's constraint contract. PromptBuilder
                    # reads `design["floors"]` (prompt_builder.py:333) and
                    # previously received nothing here, so its default of 1
                    # won and the prompt asserted "single floor building" for
                    # a three-storey request. `floor_count` is `None` when no
                    # count was stated/confirmed, and `None` keeps the
                    # builder's pre-existing default exactly.
                    "floors": (
                        architectural_instruction.get("floor_count")
                        if isinstance(architectural_instruction, dict)
                        else None
                    ),


                    "style":

                        architectural_intent.get(
                            "style",
                            ""
                        ),


                    "materials":

                        architectural_intent.get(
                            "materials",
                            []
                        ),


                    "objects":

                        architectural_intent.get(
                            "objects",
                            []
                        ),


                    "environment":

                        architectural_intent.get(
                            "environment",
                            []
                        )

                }



                try:


                    built_prompt = self.prompt_builder.build(
                        prompt_input
                    )


                    print(
                        "🔥 PROMPT BUILDER:",
                        built_prompt
                    )



                    if isinstance(
                        built_prompt,
                        dict
                    ):


                        architectural_intent[

                            "built_prompt"

                        ] = built_prompt.get(

                            "description",

                            request_text

                        )



                    elif isinstance(
                        built_prompt,
                        str
                    ):


                        architectural_intent[

                            "built_prompt"

                        ] = built_prompt



                except Exception as e:


                    print(
                        "PROMPT BUILDER ERROR:",
                        e
                    )


                    architectural_intent[

                        "built_prompt"

                    ] = request_text



            else:


                print(
                    "⚠️ PROMPT BUILDER NOT CONNECTED"
                )


                architectural_intent[

                    "built_prompt"

                ] = request_text




            final_prompt = architectural_intent.get(

                "built_prompt"

            )



            if not final_prompt:


                final_prompt = architectural_intent.get(

                    "normalized_prompt",

                    request_text

                )



            # ==============================================
            # FINAL RENDER PAYLOAD
            # ==============================================


            render_payload = {


                "prompt":

                    final_prompt,


                "original_prompt":

                    request_text,


                # CHAT_LANGUAGE_02
                # Compiled English architectural prompt (2D-3). Consumed by
                # RenderRuntime as the authoritative content source; the
                # builder prompt above is preserved as the quality tail.
                "compiled_render_prompt":

                    compiled_render_prompt,


                # TEXT_TO_IMAGE_COMFY_03 — resolved preset + terminology
                # (passed through so RenderRuntime does not recompute them)
                "preset_resolution":

                    preset_resolution,

                "terminology":

                    terminology,


                # TEXT_TO_IMAGE_COMFY_03B — optional explicit seed
                # (lets two renders differ ONLY by preset)
                "seed":

                    render_seed,


                "architectural_intent":

                    architectural_intent,


                # RENDER_INSTRUCTION_HANDOFF_V1 — bounded A/B constraint block.
                "architectural_instruction":

                    architectural_instruction,


                # FINAL_CORRECTED_FACADE_GPU_PREFLIGHT_V1 — trusted provenance
                # for the facade-redesign contract. This is the structured
                # OBJECT from `context["r4_preservation_contract"]`, not the
                # rendered text: the image builder must be able to tell a
                # product-issued contract from a user who typed the header
                # into their own request. None for every route without one.
                "r4_preservation_contract":

                    r4_preservation_contract,


                "project_state":

                    project_state,


                "mode":

                    # FACADE-04C — an explicit target image asset turns this
                    # into a real img2img edit, so the workflow selector picks
                    # `flux_img2img.json` and the target image becomes the
                    # latent source. Without an asset the historical mode is
                    # preserved exactly.
                    # FACADE-04D.2 — role-aware bindings alone also force
                    # img2img (the dual-image graph).
                    "img2img" if (image_asset or image_bindings) else architectural_intent.get(

                        "mode",

                        "text2img"

                    )

            }



            print(
                "🔥 FINAL ARCH INTENT BEFORE RUNTIME:",
                architectural_intent
            )



            print(
                "🚨 RENDER PAYLOAD:",
                render_payload
            )



            # ==============================================
            # FACADE-04D.3C-5B.1 — H2 MOVED INTO RenderRuntime.render()
            #
            # H2 (the safe Ollama model release) and the exclusive
            # `gpu_render` lease now run INSIDE RenderRuntime.render(),
            # immediately before the ComfyUI submit. They cannot live here:
            # this handler calls the semantic-intent model first, and
            # RenderRuntime.render() calls it AGAIN for the img2img branch, so
            # an H2 placed here would be undone by this same request reloading
            # qwen3.8:27b before the render. The GPU handoff must cover the
            # whole protected rendering period, not just the handler.
            #
            # A blocked handoff comes back as `status == "gpu_handoff_blocked"`
            # and is refused below, BEFORE the result bridge, in the proven
            # `render_blocked` shape.
            # ==============================================


            # ==============================================
            # RENDER RUNTIME
            # ==============================================

            # VISUAL_REFERENCE_UX_V2 — lineage against the prompt actually
            # built above, so the recorded instruction is the real one.
            if uso_reference:

                try:

                    from core.render import uso_reference_handoff_v1 as _uso_h

                    _uso_meta = uso_reference_meta or {}

                    _uso_reference = dict(uso_reference)

                    _uso_reference["lineage"] = _uso_h.build_lineage(

                        _uso_meta.get("reference") or {},

                        _uso_meta.get("selection") or {},

                        _uso_meta.get("staged") or {},

                        _uso_h.USO_WORKFLOW,

                        render_payload.get("compiled_render_prompt")
                        or render_payload.get("prompt")
                        or text

                    )

                except Exception as _uso_lineage_error:  # noqa: BLE001

                    print(
                        "⚠️ USO LINEAGE UNAVAILABLE:",
                        _uso_lineage_error
                    )

                    _uso_reference = uso_reference

            else:

                _uso_reference = None

            # ==================================================
            # FACADE_FROM_PLAN_V27 — condition on the ACTIVE plan
            #
            # "از همین ساختمان یه رندر از نمای جنوبی بگیر" names a building
            # that already exists as `active_plan_params`. Rendering it as
            # free text produces a facade that disagrees with the plan, so
            # the plan's own South elevation becomes the ControlNet map and
            # its English description becomes the content authority.
            #
            # Only for a pure text-to-image turn: a selected reference or an
            # attached photo is an edit, and the plan is not its subject.
            # ==================================================

            _plan_facade = None

            _plan_facade_mode = None

            _plan_facade_image = None

            if not _uso_reference and not image_asset:

                try:

                    from core.planning.plan_facade_conditioning_v27 import (
                        build_plan_facade_conditioning,
                        trace as _plan_facade_trace,
                    )

                    _plan_facade = build_plan_facade_conditioning(text)

                    if _plan_facade:

                        render_payload["compiled_render_prompt"] = (
                            _plan_facade["prompt_en"]
                        )

                        render_payload["prompt"] = _plan_facade["prompt_en"]

                        _plan_facade_mode = "MODE_1_TXT2IMG_EXACT_FLOORS"

                        _plan_facade_image = _plan_facade["control_image"]

                except Exception as _facade_exc:  # noqa: BLE001

                    print(
                        "⚠️ PLAN FACADE CONDITIONING UNAVAILABLE:",
                        _facade_exc
                    )

                    _plan_facade = None


            render_result = self.render_runtime.render(

                "chat_project",

                render_payload,

                "flux",

                # VISUAL_REFERENCE_UX_V2 — a selected architectural reference
                # is STYLE GUIDANCE, never the img2img source. Passing it as
                # `image_asset` would silently turn a "design a new building"
                # request into an edit of the reference photograph, so the
                # source asset is withheld whenever a reference is selected.
                None
                if _uso_reference
                else image_asset,

                # FACADE-04D.2 — role-aware dual-image binding. IMAGE A is
                # bound to its OWN node; IMAGE B stays bound to node 300.
                # `None` keeps the single-image path byte for byte.
                image_bindings=image_bindings,

                # FACADE-04D.3B-2 — explicit opt-in to the conditioned graph.
                # `False` (every existing caller) keeps the accepted
                # FACADE-04D.2 workflow.
                conditioned=conditioned,

                # KNOWLEDGE_RECOVERY_01 — caller-supplied mask for the
                # GPU-verified Kontext instruction-edit graph. `None` for
                # every existing caller, which leaves selection and the
                # graph untouched. ArchitectOS never derives a mask here.
                mask_asset=mask_asset,

                # KNOWLEDGE_RECOVERY_01 — explicit opt-in to the Kontext
                # instruction-edit workflow.
                kontext_edit=bool(kontext_edit),

                # VISUAL_REFERENCE_UX_V2 — explicit reference selection.
                # None for every existing caller, which leaves the route
                # byte for byte.
                uso_reference=_uso_reference,

                # FACADE_FROM_PLAN_V27 — None for every turn that does not
                # name the active plan's building, which leaves the graph
                # exactly as it was.
                v22_mode=_plan_facade_mode,

                v22_control_image=_plan_facade_image

            )
            

            # ==============================================
            # FACADE-04D.3C-5B.1 — PROTECTED-RENDER FAIL-CLOSED
            #
            # RenderRuntime refuses to submit when the exclusive GPU render
            # lease cannot be taken or when the safe Ollama release fails. The
            # refusal is surfaced in the SAME proven `render_blocked` shape the
            # FACADE-04A / 04D.3C-4 gates use, and the result bridge (which
            # would report a false success) is never reached.
            # ==============================================

            if (
                isinstance(render_result, dict)
                and render_result.get("status") == "gpu_handoff_blocked"
            ):

                _h2 = render_result.get("gpu_handoff_h2")

                print(
                    "⛔ DUAL-IMAGE RENDER BLOCKED: GPU handoff",
                    render_result.get("reason"),
                )

                return {

                    "type":
                        "render_blocked",

                    "engine":
                        "render_runtime",

                    "status":
                        "blocked",

                    "reason":
                        render_result.get("reason"),

                    "gpu_handoff": {
                        "contract": "GpuHandoffV1",
                        "version": "1.0",
                        "h1": None,
                        "h2": _h2,
                    },

                    "image_bindings":
                        image_bindings,

                    "conditioned":
                        bool(conditioned),

                    "message": (
                        "رندر دو‐تصویری متوقف شد: مالکیت انحصاری حافظه "
                        "گرافیکی برای رندر تأمین نشد و آزادسازی ایمن حافظه "
                        "ممکن نشد."
                    )

                }


            # ==============================================
            # VISION_LIGHTING_OUTPUT_VERIFICATION_V2 — EXPLICIT OPT-IN
            #
            # Observing a render costs a local vision inference (135-175 s)
            # plus a ComfyUI release, on top of a render that already takes
            # 160-290 s. That must never be added silently to every render,
            # so the SAME opt-in now covers every route: Krea text-only, USO
            # reference-guided and Kontext edits all reach the observation
            # through this one gate, which does not branch on the route.
            #
            # A turn that does not opt in keeps the honest default: no
            # observation, and the verdict stays UNVERIFIED.
            # ==============================================

            _verify_requested = bool(verify_render)

            # T2I_ARCHITECTURAL_FIDELITY_REPORTING_V1 — the CONTRACT is now
            # computed for every render, not only for opted-in ones. This adds
            # no inference: when the turn did not opt in, `_observation` stays
            # the explicit "observation_not_requested" record below and the
            # verdict is NOT_VERIFIED. The cost is pure dict arithmetic, and it
            # is what lets a plain text-to-image turn say honestly that its
            # architectural constraint was never verified.
            if isinstance(render_result, dict):

                try:

                    from core.vision import design_constraint_fidelity_v1 as _fidelity

                    from core.render.uso_reference_handoff_v1 import (
                        extract_sampler_prompt,
                    )

                    _sampler_text = extract_sampler_prompt(
                        (render_result.get("injected") or {}).get("workflow")
                    ) or render_payload.get("compiled_render_prompt")

                    # The actual generated image, inspected by the existing
                    # Vision provider — ONLY when the turn opted in. Without
                    # the opt-in the contract is still reported, with the
                    # observation explicitly absent, so the verdict stays
                    # UNVERIFIED and no latency is added.
                    if _verify_requested:

                        _observation = _observe_rendered_output(render_result)

                    else:

                        _observation = {
                            "available": False,
                            "reason": "observation_not_requested",
                            "contract": None,
                            "image": None,
                            "provider": None,
                            "model": None,
                        }

                    render_result["design_observation"] = _observation

                    render_result["design_fidelity"] = _fidelity.evaluate(

                        render_payload.get("architectural_intent"),

                        _sampler_text,

                        _observation.get("contract"),

                        requested_text=text

                    )

                except Exception as _fidelity_error:  # noqa: BLE001

                    print(
                        "⚠️ DESIGN FIDELITY UNAVAILABLE:",
                        _fidelity_error
                    )


            print(
                "DEBUG IMAGE HANDLER RENDER RESULT TYPE:",
                type(render_result)
            )

            print(
                "DEBUG IMAGE HANDLER RENDER RESULT KEYS:",
                render_result.keys()
                if isinstance(render_result,dict)
                else None
            )


            print(
                "🔥 RENDER RESULT:",
                render_result
            )



            # ==============================================
            # RESULT BRIDGE
            # ==============================================


            final_render = self.result_bridge.resolve(

                render_result

            )


            # ==============================================
            # RENDER_INTENT_RELIABILITY_V1 — CARRY THE FIDELITY CONTRACT
            #
            # `design_fidelity` is computed above on `render_result`, but
            # `result_bridge.resolve()` builds a NEW dict for asset resolution
            # and does not carry it, so a successful image turn lost the whole
            # requested/executed/observed contract before it could be
            # serialised. The bridge belongs to the frozen render package, so
            # the contract is re-attached HERE — in the owner that computed it
            # — rather than by editing the render layer.
            #
            # Copy only, never re-derive or re-grade: an UNVERIFIED
            # observation stays UNVERIFIED.
            # ==============================================

            if (
                isinstance(final_render, dict)
                and isinstance(render_result, dict)
                and isinstance(render_result.get("design_fidelity"), dict)
                and "design_fidelity" not in final_render
            ):

                final_render["design_fidelity"] = render_result["design_fidelity"]

            if (
                isinstance(final_render, dict)
                and isinstance(render_result, dict)
                and isinstance(render_result.get("design_observation"), dict)
                and "design_observation" not in final_render
            ):

                final_render["design_observation"] = render_result["design_observation"]



            print(
                "🔥 FINAL RENDER:",
                final_render
            )



            ui_image = self.image_response.adapt(

                final_render

            )



            print(
                "🔥 UI IMAGE:",
                ui_image
            )


            attachments = (
                ui_image.get("attachments", [])
                if isinstance(ui_image, dict)
                else []
            )


            # ==============================================
            # VISION_IMAGE_REGISTRY_04 — AUTO-REGISTER RENDER
            #
            # Every successful render enters the session image
            # registry, so the user can refer to it later
            # ("رندر قبلی" / "همین عکس") without saving or
            # re-uploading it.
            # ==============================================

            try:

                self._register_render_output(
                    final_render,
                    attachments,
                    architectural_intent=architectural_intent,
                )

            except Exception as e:

                print(
                    "⚠️ RENDER REGISTRATION ERROR:",
                    e
                )


            if attachments and hasattr(self.state, "add_message"):

                self.state.add_message(
                    "assistant",
                    "رندر آماده شد.",
                    attachments
                )



            # ==============================================
            # STATUS — TRUTHFUL
            #
            # T2I_I2I_CHAT_TO_IMAGE_EXECUTION_V1 — this used to be a constant
            # "success" that was only ever downgraded to "debug". A failed or
            # still-pending ComfyUI execution therefore returned
            # type="image_render" + status="success" with NO image attached,
            # and the UI rendered it as "رندر آماده شد." — a false success.
            #
            # The status is now derived from the ACTUAL result: the bridge
            # status is honoured, and a turn that produced no image can never
            # be reported as a success.
            # ==============================================


            render_status = "success"

            render_error = None



            if isinstance(
                final_render,
                dict
            ):


                status = final_render.get(
                    "status"
                )


                if status == "debug":


                    render_status = "debug"

                elif status and status != "success":

                    render_status = str(status)

                if final_render.get("error"):

                    render_error = str(final_render.get("error"))



            if render_status != "debug" and not attachments:

                if render_status == "success":

                    render_status = "completed_no_image"

                render_error = render_error or "render_output_missing"



            # ==============================================
            # RESPONSE
            # ==============================================


            response = {


                "type":

                    "image_render",


                "engine":

                    "render_runtime",


                "result":

                    ui_image,


                "render":

                    final_render,


                "architectural_intent":

                    architectural_intent,


                "status":

                    render_status,


                "error":

                    render_error,


                # T2I_ARCHITECTURAL_FIDELITY_REPORTING_V1 — technical
                # completion and architectural verification are reported as
                # SEPARATE facts. A successful render whose requested floor
                # count could not be observed is NOT_VERIFIED, never a match;
                # a supported mismatch is reported as MISMATCH without turning
                # the turn into a technical failure. The image is always kept.
                "architectural_fidelity":

                    _architectural_fidelity_report(
                        (render_result or {}).get("design_fidelity")
                        if isinstance(render_result, dict)
                        else None,
                        render_status,
                        bool(attachments),
                    )

            }



            # ==============================================
            # WRITEBACK
            # ==============================================


            self.writeback.store(

                text,

                str(response)

            )



            # ==============================================
            # STATE SAVE
            # ==============================================


            self.state.update({


                "last_architectural_intent":

                    architectural_intent,


                "last_render_context":

                    {


                        "prompt":

                            final_prompt,


                        "architectural_intent":

                            architectural_intent

                    }

            })


            # ==============================================
            # T2I_I2I_CHAT_TO_IMAGE_EXECUTION_V1
            # REMEMBER THE REQUESTED IMAGE
            #
            # The recognised text-to-image request is remembered for the next
            # turn, so a following specification answer ("5*5*5 سانتیمتر")
            # completes it instead of being treated as a new topic. The
            # prompt stored is the one actually rendered, so a completion
            # accumulates (object + appearance + dimensions).
            #
            # Cleared when the user starts a different image request (the
            # stored prompt is replaced), and expired by the router after
            # PENDING_IMAGE_MAX_AGE_TURNS turns.
            # ==============================================

            try:

                self.state.update({

                    "pending_image_generate": {

                        "prompt": (final_prompt or request_text),

                        "source": "chat_image_generate",

                        "created_turn": int(
                            current_state.get("turn_index", 0) or 0
                        ),

                    }

                })

                print(
                    "🖼️ PENDING IMAGE GENERATION REMEMBERED"
                )

            except Exception as e:

                print(
                    "PENDING IMAGE STATE SAVE ERROR:",
                    e
                )



            print(
                "💾 ARCHITECTURAL INTENT SAVED"
            )



            return response



        except Exception as e:


            print(
                "IMAGE GENERATE ERROR:",
                e
            )


            return {


                "type":

                    "image_render",


                "status":

                    "error",


                "error":

                    str(e)

            }





    # ======================================================
    # FACADE-04D.3C-2 — DUAL-IMAGE / CONDITIONED PRECEDENCE
    # ======================================================

    def _is_dual_image_request(
        self,
        image_bindings,
        conditioned
    ):
        """True when the request carries an explicit dual-image contract.

        An explicit role-aware binding (IMAGE A + IMAGE B) OR an explicit
        conditioned opt-in both select the dual-image rendering path. Such a
        request must NEVER be consumed by the legacy single-image edit
        delegation in :meth:`handle_image_generate`.
        """

        return bool(image_bindings) or bool(conditioned)


    def _dual_binding_contract_error(
        self,
        image_bindings
    ):
        """Validate an EXPLICIT dual-image binding; return a reason or None.

        Fail-closed. An explicit binding must name BOTH roles, each with its
        canonical node id and a filename, so IMAGE B can never be swapped off
        node 300 and IMAGE A can never overwrite it. A malformed binding is
        refused here rather than being submitted as an unbound template graph.

        When NO binding is supplied the decision is deliberately left to the
        RenderRuntime conditioned gate, which already refuses a conditioned
        request with ``conditioning_requires_dual_binding`` without ever
        submitting — that accepted behaviour is preserved byte for byte.
        """

        if not image_bindings:

            return None

        if not isinstance(
            image_bindings,
            dict
        ):

            return "dual_image_binding_not_ready"

        from core.render.dual_image_binding_v1 import (
            ROLE_A,
            ROLE_B,
            DUAL_IMAGE_NODE_BINDINGS,
        )

        for role in (ROLE_A, ROLE_B):

            binding = image_bindings.get(role)

            if not isinstance(binding, dict):

                return "dual_image_binding_not_ready"

            if not binding.get("node_id"):

                return "dual_image_binding_not_ready"

            if not binding.get("filename"):

                return "dual_image_binding_not_ready"

        if (
            str(image_bindings[ROLE_A].get("node_id"))
            != DUAL_IMAGE_NODE_BINDINGS[ROLE_A]
            or str(image_bindings[ROLE_B].get("node_id"))
            != DUAL_IMAGE_NODE_BINDINGS[ROLE_B]
        ):

            return "dual_image_binding_not_ready"

        return None


    def _dual_route_blocked(
        self,
        reason,
        image_bindings,
        conditioned
    ):
        """Fail-closed response for an unsatisfiable dual-image contract.

        Never falls back to the legacy single-image edit route and never
        degrades to text-to-image: the request is refused.
        """

        return {

            "type":
                "image_render",

            "engine":
                "render_runtime",

            "status":
                "blocked",

            "reason":
                reason,

            "image_bindings":
                image_bindings,

            "conditioned":
                bool(conditioned)

        }


    # ======================================================
    # DESIGN STATE EXTRACTOR
    # ======================================================


    def extract_design_state(
        self
    ):


        try:


            state = self.state.get()



            if not isinstance(
                state,
                dict
            ):


                return {}



            active_project = state.get(

                "active_project",

                {}

            )



            if not isinstance(
                active_project,
                dict
            ):


                active_project = {}



            design = active_project.get(

                "design",

                {}

            )



            if not isinstance(
                design,
                dict
            ):


                design = {}



            return {


                "project_type":

                    active_project.get(

                        "type",

                        "architectural_project"

                    ),



                "design":

                    design,



                "previous_design":

                    state.get(

                        "previous_design",

                        state.get(

                            "last_design",

                            {}

                        )

                    )

            }



        except Exception as e:


            print(
                "DESIGN STATE ERROR:",
                e
            )


            return {}
    # ======================================================
    # INTENT NORMALIZER
    # ======================================================

    def normalize_intent(
        self,
        intent,
        floor_constraint=None,
    ):


        print(
            "🧠 NORMALIZER INPUT:",
            intent
        )



        if not isinstance(
            intent,
            dict
        ):

            intent = {}



        building = intent.get(
            "building",
            {}
        )



        if not isinstance(
            building,
            dict
        ):

            building = {}



        # FLOOR_COUNT_PROPAGATION_FIX_V1 — preserve an already-extracted
        # numeric storey count; do not parse prose or invent a default here.
        #
        # Precedence is provenance-aware:
        #   1. the published RenderConstraintBlockV1, whose producer admits a
        #      floor only from USER_TEXT / USER_CONFIRMATION;
        #   2. an existing user_explicit FloorCountV1 contract;
        #   3. semantic building.floors;
        #   4. top-level semantic floors as the compatibility fallback.
        #
        # The chosen value remains semantic metadata. This normalizer does
        # not add or upgrade any provenance field.
        def _valid_floor_count(value):

            if value is None or isinstance(value, bool):

                return None

            try:

                parsed = int(value)

                if float(value) == parsed and parsed > 0:

                    return parsed

            except (TypeError, ValueError, OverflowError):

                pass

            return None


        authoritative_floor = None

        if (
            isinstance(floor_constraint, dict)
            and floor_constraint.get("contract") == "RenderConstraintBlockV1"
            and floor_constraint.get("source")
                == "render_instruction.english_instruction"
            and floor_constraint.get("constraint_block")
        ):

            authoritative_floor = _valid_floor_count(
                floor_constraint.get("floor_count")
            )


        explicit_contract_floor = None

        floor_contract = intent.get("floor_count")

        if (
            isinstance(floor_contract, dict)
            and floor_contract.get("contract") == "FloorCountV1"
            and floor_contract.get("source") == "user_explicit"
        ):

            explicit_contract_floor = _valid_floor_count(
                floor_contract.get("value")
            )


        semantic_floor = _valid_floor_count(
            building.get("floors")
        )

        if semantic_floor is None:

            semantic_floor = _valid_floor_count(
                intent.get("floors")
            )


        floors = (
            authoritative_floor
            if authoritative_floor is not None
            else explicit_contract_floor
            if explicit_contract_floor is not None
            else semantic_floor
        )



        prompt = str(

            intent.get(
                "prompt",
                ""
            )

        )



        mode = (

            "img2img"

            if (

                self.is_image_edit_request(
                    prompt
                )

                or

                intent.get(
                    "mode"
                ) == "img2img"

            )

            else

            "text2img"

        )



        materials = intent.get(
            "materials",
            []
        )



        if not isinstance(
            materials,
            list
        ):

            materials = []



        objects = intent.get(
            "objects",
            []
        )



        if not isinstance(
            objects,
            list
        ):

            objects = []



        environment = intent.get(
            "environment",
            []
        )



        if not isinstance(
            environment,
            list
        ):

            environment = []



        normalized = {


            "request_type":

                "edit"

                if mode == "img2img"

                else

                "generate",



            "building_type":

                building.get(

                    "type",

                    intent.get(

                        "building_type",

                        "building"

                    )

                ),



            "style":

                building.get(

                    "style",

                    intent.get(

                        "style",

                        "modern"

                    )

                ),



            "materials":

                materials,


            "facade":

                intent.get(
                    "facade",
                    {}
                ),


            "facade_details":

                intent.get(
                    "facade_details",
                    intent.get("facade", {}).get("details", [])
                    if isinstance(intent.get("facade"), dict)
                    else []
                ),



            "objects":

                objects,



            "site":

                intent.get(

                    "site",

                    []

                ),



            "environment":

                environment,



            "camera":

                (
                    deepcopy(intent.get("camera"))
                    if isinstance(intent.get("camera"), dict)
                    else "architectural visualization"
                ),



            "mood":

                "professional archviz",



            "lighting":

                intent.get(

                    "lighting",

                    {}

                ),



            "preserve_geometry":

                True,



            "mode":

                mode,



            "normalized_prompt":

                prompt

        }


        if floors is not None:

            normalized["floors"] = floors

            # Retain the existing parser-owned contract only when it is the
            # trusted contract that supports this exact value.  This carries
            # provenance; it does not create or upgrade it.
            if (
                explicit_contract_floor == floors
                and isinstance(floor_contract, dict)
            ):

                normalized["floor_count"] = deepcopy(floor_contract)

                levels = intent.get("levels")

                if isinstance(levels, dict):

                    level_count = _valid_floor_count(
                        levels.get("total", levels.get("above_ground"))
                    )

                    if level_count == floors:

                        normalized["levels"] = deepcopy(levels)

        for key in (
            "roof", "roof_geometry", "massing", "building_massing",
            "silhouette", "building_silhouette", "openings", "windows",
            "doors", "balconies", "balcony_geometry", "dimensions",
            "proportions", "camera_parameters", "perspective", "view",
        ):

            value = intent.get(key)

            if value not in (None, "", [], {}):

                normalized[key] = deepcopy(value)


        return normalized





    # ======================================================
    # EDIT INTENT NORMALIZER
    # ======================================================


    def normalize_edit_intent(
        self,
        intent,
        previous_intent=None,
        edit_delta=None
    ):
        """Normalise a conversational edit into the facade-edit contract.

        `previous_intent` is the architectural intent of the turn that
        produced the source image; `edit_delta` is the deterministic
        classification of THIS turn
        (core.prompt_intelligence.image_edit_delta_v1).

        Precedence, highest first:

          1. what this turn states explicitly,
          2. the compiled delta of this turn,
          3. the previous turn's intent (continuity),
          4. the historical defaults.

        Rule 3 is what anchors a second-turn revision: the user says
        "make the brick a little lighter" and the previous style, building
        type and fixed constraints survive.  Rule 2 is what stops that
        continuity from resurrecting a finish the user has just replaced.

        Both parameters are optional, so every pre-existing caller keeps its
        exact behaviour.
        """

        if not isinstance(
            intent,
            dict
        ):

            intent = {}

        if not isinstance(
            previous_intent,
            dict
        ):

            previous_intent = {}

        if not isinstance(
            edit_delta,
            dict
        ):

            edit_delta = {}

        def _present(value):

            return value not in (
                None,
                "",
                [],
                {},
            )

        def _pick(key, fallback):
            """This turn, then the previous turn, then the default."""

            current_value = intent.get(key)

            # These are semantic-parser placeholders, not current explicit
            # corrections.  They must not erase source-bound facts.
            placeholder = (
                (key == "building_type" and current_value == "building")
                or (
                    key == "camera"
                    and current_value == "architectural visualization"
                )
            )

            if _present(current_value) and not placeholder:

                return current_value

            if _present(previous_intent.get(key)):

                return previous_intent.get(key)

            return fallback

        # S3 — the delta classifies THIS turn. A material replacement
        # supersedes both the turn's own wording and the previous finish;
        # its tone modifier ("a little lighter") is expressed by the delta
        # prompt itself, which is the authoritative render instruction.
        delta_material = edit_delta.get(
            "material"
        )

        materials = _pick(
            "materials",
            ["preserve existing facade materials"],
        )

        if delta_material:

            materials = [delta_material]

        # A COLOUR delta must never populate `materials`.
        #
        # `materials` is a MATERIAL-TYPE slot: PromptBuilder appends every
        # entry verbatim as a facade feature, and the material ontology
        # identifies substances (travertine, red_brick), never hues. Writing
        # the requested colour into it turned "make the facade blue" into a
        # material replacement literally called "blue", and discarded the
        # previous finish. That violates both required semantics: a colour
        # change is not a change of material TYPE, and a tone change must
        # preserve the existing material unless the user names another one.
        #
        # The requested colour is already authoritative elsewhere - it is
        # named in the delta prompt (compiled_render_prompt) and carried in
        # edit_delta["color"] - so nothing is lost by leaving `materials` to
        # inherit the previous turn's finish.
        #
        # (The former `elif delta_color: materials = [delta_color]` branch
        # was the defect. A colour is not a material.)

        facade = _pick(
            "facade",
            {}
        )

        merged = dict(intent)

        merged["building_type"] = _pick(
            "building_type",
            "existing building"
        )

        merged["style"] = _pick(
            "style",
            "existing architectural style"
        )

        # KNOWLEDGE_RUNTIME_CONNECTION_V2 — the delta is authoritative for THIS
        # turn's requested style, exactly as `delta_material` is authoritative
        # for this turn's finish. Without it, an explicit style change updated
        # nothing: the derived image kept the PREVIOUS style ("modern"), so the
        # next turn compiled against a stale architectural intent while the
        # user believed the style had changed.
        delta_style = edit_delta.get(
            "style"
        )

        if delta_style:

            merged["style"] = delta_style

        merged["materials"] = materials

        merged["facade"] = facade

        merged["facade_details"] = _pick(
            "facade_details",
            facade.get("details", [])
            if isinstance(facade, dict)
            else []
        )

        merged["preserve_constraints"] = _pick(
            "preserve_constraints",
            []
        )

        merged["objects"] = _pick(
            "objects",
            []
        )

        merged["environment"] = _pick(
            "environment",
            []
        )

        intent = merged


        normalized = {


            "request_type":

                "facade_material_edit",



            "building_type":

                intent.get(

                    "building_type",

                    "existing building"

                ),



            "style":

                intent.get(

                    "style",

                    "existing architectural style"

                ),



            "materials":

                intent.get(

                    "materials",

                    [

                        "preserve existing facade materials"

                    ]

                ),


            "facade":

                intent.get(
                    "facade",
                    {}
                ),


            "facade_details":

                intent.get(
                    "facade_details",
                    intent.get("facade", {}).get("details", [])
                    if isinstance(intent.get("facade"), dict)
                    else []
                ),


            "preserve_constraints":

                intent.get(
                    "preserve_constraints",
                    []
                ),



            "objects":

                intent.get(

                    "objects",

                    []

                ),



            "environment":

                intent.get(

                    "environment",

                    []

                ),



            "preserve_geometry":

                True,



            "mode":

                "img2img",



            "camera":

                _pick("camera", "same as original image"),



            "normalized_prompt":

                intent.get(

                    "prompt",

                    ""

                )

        }

        # Preserve supported structured facts actually present on this image.
        # Current explicit values win; parser defaults do not manufacture
        # architecture.  FloorCountV1 is handled separately because its
        # provenance and internal consistency are authoritative.
        structured_fields = (
            "roof", "roof_geometry", "massing", "building_massing",
            "silhouette", "building_silhouette", "openings", "windows",
            "doors", "balconies", "balcony_geometry", "dimensions",
            "proportions", "camera_parameters", "perspective", "view",
        )

        for key in structured_fields:

            if _present(intent.get(key)):

                normalized[key] = deepcopy(intent.get(key))

            elif _present(previous_intent.get(key)):

                normalized[key] = deepcopy(previous_intent.get(key))

        current_floor = _trusted_floor_contract(intent)
        previous_floor = _trusted_floor_contract(previous_intent)

        chosen_floor = None
        chosen_source = None

        if current_floor[0] == "trusted":

            chosen_floor = current_floor
            chosen_source = intent

        elif current_floor[0] in ("invalid", "conflict"):

            normalized["architectural_conflicts"] = ["floor_count"]

        elif previous_floor[0] == "trusted":

            chosen_floor = previous_floor
            chosen_source = previous_intent

        if chosen_floor:

            normalized["floor_count"] = deepcopy(chosen_floor[1])
            normalized["floors"] = chosen_floor[2]

            levels = chosen_source.get("levels")

            if isinstance(levels, dict):

                level_count = _positive_int(
                    levels.get("total", levels.get("above_ground"))
                )

                if level_count == chosen_floor[2]:

                    normalized["levels"] = deepcopy(levels)

                elif level_count is not None:

                    normalized.pop("floors", None)
                    normalized.pop("floor_count", None)
                    normalized["architectural_conflicts"] = ["floor_count"]

        if current_floor[0] == "observation" and current_floor[3]:

            normalized["architectural_observations"] = {
                "floor_count": deepcopy(current_floor[3])
            }

        return normalized





    # ======================================================
    # IMAGE EDIT DETECTOR
    # ======================================================


    def is_image_edit_request(
        self,
        text
    ):


        if not text:

            return False



        text = str(
            text
        ).lower()



        keywords = [


            # upload / continuation

            "عکس خام",

            "عکس میفرستم",

            "عکس می‌فرستم",

            "آپلود",

            "تصویر دریافت شد",


            # edit commands

            "ویرایش",

            "ویرایش کن",

            "تغییر بده",

            "تغییرش بده",

            "این تصویر",

            "این عکس",

            "روی این عکس",

            "مدرن‌تر کن",

            "مدرن تر کن",

            "مدرنش کن",

            "بهبود بده",

            "بازطراحی کن",

            "بازطراحی",

            "اصلاح کن",


            # english

            "preserve",

            "edit",

            "img2img",

            "modify",

            "change",

            "upgrade"

        ]



        return any(

            key in text

            for key in keywords

        )





    # ======================================================
    # IMAGE UPLOAD TEXT DETECTOR
    # ======================================================


    def is_upload_only_text(
        self,
        text
    ):


        if not text:

            return False



        text = str(
            text
        ).lower()



        words = [


            "عکس",

            "میفرستم",

            "می‌فرستم",

            "آپلود"

        ]



        return any(

            x in text

            for x in words

        )




    # ======================================================
    # IMAGE UPLOAD ONLY HANDLER
    # ======================================================

    def handle_image_upload_only(
        self,
        image
    ):

        try:

            # ==============================================
            # CHAT_UPLOAD_SINGLE_OWNER_V1
            #
            # The request boundary may hand over an ALREADY-STORED image —
            # either a path or the boundary's {"path","attachment"} record —
            # instead of a raw upload handle. Both shapes are already accepted
            # elsewhere in this pipeline (`handle_image_edit`,
            # `_register_session_image`, `resolve_guard_source_identity`), so
            # accepting them here stores the upload exactly ONCE and keeps the
            # transcript record's servable URL intact.
            #
            # A raw upload handle keeps the original behaviour byte for byte.
            # ==============================================

            if isinstance(image, dict):

                _stored_path = image.get("path")

                _stored_attachment = image.get("attachment")

            elif isinstance(image, str):

                _stored_path = image

                _stored_attachment = None

            else:

                _stored_path = None

                _stored_attachment = None


            if _stored_path:

                file_path = _stored_path

                attachment = (
                    _stored_attachment
                    or self.attachment_service.attachment_for_path(
                        _stored_path,
                        root_key="user_media",
                        source="user_upload",
                        kind="image",
                    )
                )

                if not attachment:

                    return {
                        "type": "image_upload",
                        "status": "error",
                        "error": "attachment_registration_failed",
                        "message": _image_upload_rejection(
                            "attachment_registration_failed"
                        ),
                    }

                filename = attachment.get("filename")

            else:

                upload = self.attachment_service.save_upload(
                    image,
                    source="user_upload",
                    kind="image"
                )


                if upload.get("status") != "ready":

                    _rejection = upload.get(
                        "error", "image_upload_failed"
                    )

                    return {
                        "type": "image_upload",
                        "status": "error",
                        "error": _rejection,
                        "message": _image_upload_rejection(_rejection),
                    }


                file_path = upload["path"]
                attachment = self.attachment_service.public_attachment(
                    upload["attachment"]
                )
                filename = attachment["filename"]


            print(
                "📷 IMAGE SAVED:",
                file_path
            )


            asset = self.image_bridge.process_upload(
                "chat_project",
                file_path
            )


            print(
                "🔥 UPLOAD ASSET:",
                asset
            )


            if not isinstance(
                asset,
                dict
            ):

                asset = {
                    "asset": {}
                }


            asset_data = asset.get(
                "asset",
                {}
            )


            self.state.update({

                "last_image_asset":
                    asset_data,

                "waiting_image_edit":
                    True

            })


            # ==============================================
            # CHAT_UPLOAD_SINGLE_OWNER_V1 — NO user record here.
            #
            # The request boundary already recorded this turn (with the
            # validated attachment, URL included) before dispatching. Writing
            # it again here stored ONE user turn TWICE: the project transcript
            # showed two identical image bubbles after a refresh, one of them
            # without a URL and therefore rendered as
            # "attachment unavailable". The boundary is the single owner.
            # ==============================================

            return {

                "type":
                    "image_upload",


                "status":
                    "waiting_for_instruction",


                "message":
                    "تصویر دریافت شد. لطفاً دستور تغییرات را وارد کنید.",


                "asset":
                    {
                        "filename": asset_data.get("filename"),
                        "status": asset_data.get("status", "ready")
                    },

                "image":
                    {
                        "filename":
                            filename,

                        "url":
                            attachment["url"]
                    },

                "attachments":
                    [attachment]

            }



        except Exception as e:


            print(
                "IMAGE UPLOAD ONLY ERROR:",
                e
            )


            return {

                "type":
                    "image_upload",


                "status":
                    "error",


                "error":
                    str(e)

            }





    # ======================================================
    # IMAGE EDIT PIPELINE
    # ======================================================


    def handle_image_edit(
        self,
        text,
        image,
        compiled_render_prompt=None,
        preservation=None,
        seed=None,
        edit_conflict_terms=None,
        render_profile=None,
        parent_image_id=None,
        mask_asset=None,
        kontext_edit=False,
        previous_architectural_intent=None,
        edit_delta=None,
        verify_render=None,
        image_understanding=None,
        r4_preservation_contract=None,
        r4_admission=None,
    ):


        print(
            "✅ IMAGE EDIT START"
        )



        try:


            if not image:


                state = self.state.get()


                if isinstance(
                    state,
                    dict
                ):


                    asset = state.get(

                        "last_image_asset"

                    )


                    if isinstance(
                        asset,
                        dict
                    ):


                        image = asset.get(

                            "path"

                        )



            if not image:


                return {


                    "type":

                        "image_edit",


                    "status":

                        "missing_image"

                }



            if isinstance(
                image,
                dict
            ):


                image_path = image.get(
                    "path"
                )


            elif isinstance(
                image,
                str
            ):


                image_path = image


            else:


                upload = self.attachment_service.save_upload(
                    image,
                    source="user_upload",
                    kind="image"
                )


                if upload.get("status") != "ready":

                    return {
                        "type": "image_edit",
                        "status": "error",
                        "error": upload.get("error", "image_upload_failed")
                    }


                image_path = upload["path"]


                if hasattr(self.state, "add_message"):

                    self.state.add_message(
                        "user",
                        text,
                        [
                            self.attachment_service.public_attachment(
                                upload["attachment"]
                            )
                        ]
                    )



            asset = self.image_bridge.process_upload(

                "chat_project",

                image_path,

                # PROJECT_WORKSPACE_UI_06 — DRAFT/PREVIEW profiles
                # downscale the source into a temporary working copy.
                preview=render_profile,

            )



            asset_data = {}


            if isinstance(
                asset,
                dict
            ):


                asset_data = asset.get(

                    "asset",

                    {}

                )



            # I2I_JPEG_PREVIEW_SAFE_STAGING_V1 — a requested working copy
            # that could not be produced must stop the edit here. Rendering
            # would otherwise send an unexpectedly large (or unknown) source.
            if (
                isinstance(asset_data, dict)
                and asset_data.get("status") == "error"
            ):


                return {


                    "type":

                        "image_edit",


                    "status":

                        "source_staging_failed",


                    "reason":

                        asset_data.get("message"),


                    "preview_reason":

                        asset_data.get("preview_reason")

                }



            self.state.update({

                "last_image_asset":

                    asset_data,


                "waiting_image_edit":

                    True,


                "image_edit_ready":

                    True

            })



            intent = self.semantic_intent.extract(
                text
            )



            if not isinstance(
                intent,
                dict
            ):

                intent = {}



            intent["prompt"] = text

            intent["mode"] = "img2img"



            architectural_intent = self.normalize_edit_intent(
                intent,
                previous_intent=previous_architectural_intent,
                edit_delta=edit_delta,
            )

            # ==================================================
            # ARCHITECTURAL REASONING INTEGRATION V8
            #
            # Reuse the two executable owners that already govern this route:
            # shared facade knowledge and GeometryAuthorityHandoffV1. The
            # additive decision projection makes their combined result depend
            # on the selected image's validated evidence before render
            # dispatch. It never invents masks, coordinates, materials or
            # elements, and MODEL_REPORTED evidence stays UNVERIFIED.
            # ==================================================

            _knowledge_resolver = getattr(
                self.render_runtime,
                "resolve_shared_facade_knowledge",
                None,
            )

            if callable(_knowledge_resolver):
                resolved_facade_knowledge = _knowledge_resolver(
                    architectural_intent
                )
            else:
                # Lightweight recording runtimes used by existing callers do
                # not expose RenderRuntime's convenience method. Reuse its
                # existing route-neutral resolver directly instead of making
                # the new V8 projection a requirement on every runtime fake.
                from core.architecture.knowledge.resolved_facade_knowledge import (
                    SharedFacadeKnowledgeResolverV1,
                )

                resolved_facade_knowledge = (
                    SharedFacadeKnowledgeResolverV1().resolve(
                        architectural_intent
                    )
                )
                architectural_intent["resolved_facade_knowledge"] = (
                    resolved_facade_knowledge
                )
                architectural_intent["facade_knowledge_consumed"] = True

            from core.prompt_intelligence.geometry_authority_handoff_v1 import (
                decision_instruction_block,
                resolve_design_decision,
            )

            # HUMAN TEACHING T1 — accepted human rules are READ from the
            # existing append-only ledger through the existing read bridge.
            # Unconfirmed teaching candidates are never read here, and nothing
            # is promoted on this path.
            if "human_learning_rules" not in architectural_intent:

                try:

                    from core.architecture.knowledge.human_learning_ledger_v1 import (
                        accepted_rules,
                    )

                    architectural_intent["human_learning_rules"] = accepted_rules()

                except Exception as error:

                    print(
                        "⚠️ HUMAN LEARNING LEDGER READ SKIPPED:",
                        error
                    )

                    architectural_intent["human_learning_rules"] = []

            architectural_design_decision = resolve_design_decision(
                user_text=text,
                edit_delta=edit_delta,
                image_understanding=image_understanding,
                resolved_facade_knowledge=resolved_facade_knowledge,
                preserve_geometry=bool(
                    architectural_intent.get("preserve_geometry", True)
                ),
                preserve_constraints=(
                    architectural_intent.get("preserve_constraints") or ()
                ),
                human_learning_rules=(
                    architectural_intent.get("human_learning_rules") or []
                ),
                design_context={
                    "text": text,
                    "image_type": (
                        (image_understanding or {}).get("image_type")
                        if isinstance(image_understanding, dict)
                        else None
                    ),
                },
                # CONCEPTUAL_I2I_LIVE_EVIDENCE_ADMISSION_V1 — this is the
                # structured, server-owned result of ChatArchitect's source,
                # scope, consent and integrity checks.  The decision owner
                # validates the envelope; no visual claim is promoted.
                conceptual_admission=r4_admission,
            )

            architectural_intent["architectural_design_decision"] = (
                architectural_design_decision
            )

            # ARCHITECTURAL DESIGN INSTRUCTION HANDOFF V8.1 — the decision must
            # control the text the existing engine receives. This projection is
            # derived ONLY from the decision above; it re-interprets nothing and
            # adds no second reasoning pass. The block is handed to the EXISTING
            # render constraint seam, which the prompt resolver places after the
            # compiled user intent and before the truncatable quality tail.
            architectural_instruction = decision_instruction_block(
                architectural_design_decision
            )

            _decision_status = architectural_design_decision.get(
                "execution_status"
            )

            _has_current_image_evidence = bool(
                isinstance(image_understanding, dict)
                and image_understanding
            )

            # Older direct ImageHandler callers do not carry the V7.4 image
            # evidence contract. Preserve their established execution path;
            # the live ChatArchitect image-edit route now supplies current
            # evidence and therefore receives the fail-closed V8 decisions.
            # Fixed/editable contradictions remain blocking in either case.
            _decision_blocks = (
                _decision_status == "BLOCKED_CONFLICT"
            ) or (
                _has_current_image_evidence
                and (
                    _decision_status in (
                        "INSUFFICIENT_IMAGE_EVIDENCE",
                        "INSUFFICIENT_SPATIAL_EVIDENCE",
                    )
                    or (
                        _decision_status == "NEEDS_SPATIAL_TARGETING"
                        and not mask_asset
                    )
                )
            )

            if _decision_blocks:

                return {
                    "type": "render_blocked",
                    "engine": "architectural_design_decision",
                    "status": "blocked",
                    "reason": str(_decision_status or "decision_blocked").lower(),
                    "architectural_intent": architectural_intent,
                    "architectural_design_decision": architectural_design_decision,
                    "message": (
                        "The architectural edit was not executed because its "
                        "evidence, spatial targeting, or fixed constraints are "
                        "not sufficient for the existing workflow."
                    ),
                }

            # ======================================================
            # NEOCLASSICAL_FINAL_PROMPT_CONSISTENCY_V1 — PROBLEM D
            #
            # MEASURED: with no `image_understanding`, a facade DESIGN still
            # reached the renderer as `restyle` with
            # `execution_status: READY_FOR_EXISTING_WORKFLOW`, an EMPTY
            # `editable_elements` list and a ZERO-CHARACTER constraint block.
            # The route then rendered the delta prompt alone — no surface
            # assignment, no authorised-addition boundary, no ornament — while
            # reporting READY.
            #
            # A design that requires source-preserving architectural
            # constraints cannot be executed without them. This refuses rather
            # than proceeding silently, and it refuses ONLY a `restyle`: a
            # material replacement, a removal or a lighting edit carries its
            # own instruction and is unaffected, as is text-to-image.
            #
            # SCOPE — the guard applies to the LIVE CHAT ROUTE only, identified
            # by the server-owned `r4_admission` envelope that
            # `ChatArchitect._route_image_edit` always passes and a legacy
            # direct caller never does. The established execution path of those
            # direct callers is preserved unchanged, exactly as the
            # `_has_current_image_evidence` comment above requires.
            #
            # SCOPE 2 — and only to a design that EXPLICITLY requests
            # decorative elements. Those are the requests whose contract is
            # silently lost when the block is empty: the elements are named in
            # the user's words, the block is the only carrier that turns them
            # into relief instructions, and without it they vanish. A plain
            # "restyle to neoclassical" names no element, loses nothing, and
            # keeps its established path.
            # ======================================================
            _decision_operation = (
                (architectural_design_decision.get("requested_operation") or {})
                .get("operation")
            )

            _instruction_block_text = (
                (architectural_instruction or {}).get("constraint_block")
                if isinstance(architectural_instruction, dict)
                else ""
            )

            _requested_ornament = list(
                (
                    architectural_design_decision.get("requested_ornament") or {}
                ).get("elements")
                or []
            )

            _live_chat_route = bool(
                isinstance(r4_admission, dict)
                and r4_admission.get("admitted") is True
            )

            if (
                _live_chat_route
                and _decision_operation == "restyle"
                and _requested_ornament
                and not str(_instruction_block_text or "").strip()
            ):

                print(
                    "⛔ ARCHITECTURAL DESIGN REFUSED: "
                    "constraint block empty (no architectural evidence)"
                )

                return {
                    "type": "render_blocked",
                    "engine": "architectural_design_decision",
                    "status": "blocked",
                    "reason": "architectural_evidence_required",
                    "architectural_intent": architectural_intent,
                    "architectural_design_decision": architectural_design_decision,
                    "capability_gap": {
                        "missing": "source_architectural_evidence",
                        "detail": (
                            "A facade design must carry its architectural "
                            "constraints (protected geometry, surface "
                            "assignment, authorised additions). Without image "
                            "understanding the constraint block is empty, so "
                            "the request is refused instead of being rendered "
                            "as a bare material instruction."
                        ),
                    },
                    "message": (
                        "این طراحی نما نیازمند شواهد معماری تصویر منبع است. "
                        "بدون آن، دستور معماری کامل تولید نمی‌شود و رندر انجام نشد."
                    ),
                }



            payload = {


                "prompt":

                    text,


                "original_prompt":

                    text,


                "architectural_intent":

                    # V4.3D — the prompt builder must know the edit CLASS to
                    # decide whether generic facade-restyle instructions may be
                    # appended. `PromptRouter.build()` rebuilds its dict from
                    # `architectural_intent` only (`{**architectural_intent,
                    # "_user_prompt": …}`), so the classification has to travel
                    # INSIDE it or it is dropped before the builder sees it.
                    # Purely request-scoped: nothing is persisted.
                    (
                        {**architectural_intent, "edit_delta": edit_delta}
                        if isinstance(architectural_intent, dict) and edit_delta
                        else architectural_intent
                    ),


                "asset":

                    asset_data,


                "mode":

                    "img2img",


                # ==============================================
                # IMAGE_TO_IMAGE_05
                #
                # The compiled English prompt becomes authoritative for
                # img2img exactly as it already is for text-to-image.
                # Dimensions are deliberately NOT supplied: the latent
                # comes from the source image.
                # ==============================================
                "compiled_render_prompt":

                    compiled_render_prompt,


                "preservation":

                    preservation,


                "denoise":

                    (preservation or {}).get("denoise"),


                # ==============================================
                # IMAGE_TO_IMAGE_05 — EDIT DELTA AUTHORITY
                #
                # Conflict terms let the render prompt resolver strip
                # the generic builder-tail segments that directly
                # contradict the user's edit delta (for example
                # "natural lighting" on a night edit).
                # ==============================================
                "edit_conflict_terms":

                    list(edit_conflict_terms or ()),


                # ==============================================
                # PROJECT_WORKSPACE_UI_06 — validated render profile
                # (DRAFT / PREVIEW / QUALITY / FINAL). The Render
                # Strategy Controller validated this value; the
                # workflow graph is never mutated.
                # ==============================================
                "render_profile":

                    render_profile,


                # V8.1 — bounded design-decision constraint block. `None` when
                # the decision authorises nothing, which keeps every legacy
                # payload's final prompt unchanged.
                "architectural_instruction":

                    (architectural_instruction or None),


                # FINAL_CORRECTED_FACADE_GPU_PREFLIGHT_V1 — trusted provenance
                # for the facade-redesign contract. See handle_image_generate.
                "r4_preservation_contract":

                    r4_preservation_contract,


                "seed":

                    seed

            }



            print(
                "🔥 IMG2IMG PAYLOAD:",
                payload
            )



            result = self.render_runtime.render(

                "chat_project",

                payload,

                "flux",

                asset_data,

                # KNOWLEDGE_RECOVERY_01 — the conversational EDIT path is the
                # one that carries a caller-supplied mask and the Kontext
                # opt-in. `None` / `False` for every existing caller keeps
                # selection and the graph untouched.
                mask_asset=mask_asset,

                kontext_edit=bool(kontext_edit)

            )


            # ==============================================
            # VISION_STOREY_DISAMBIGUATION_V3 — EDIT OUTPUT
            #
            # The V2 observer gate covered handle_image_generate(), but the
            # established conversational I2I/Kontext route terminates here.
            # Honour the same explicit opt-in, observe the ACTUAL executor
            # output PNG, and keep requested/executed/observed facts separate.
            # No source/output preservation claim is made: that requires the
            # existing dual-image comparison capability, not one output image.
            # ==============================================

            if isinstance(result, dict) and bool(verify_render):

                try:

                    from core.vision import design_constraint_fidelity_v1 as _fidelity

                    _observation = _observe_rendered_output(result)

                    result["design_observation"] = _observation

                    result["design_fidelity"] = _fidelity.evaluate(
                        architectural_intent,
                        compiled_render_prompt or text,
                        _observation.get("contract"),
                        requested_text=text,
                    )

                except Exception as _fidelity_error:  # noqa: BLE001

                    print(
                        "⚠️ EDIT DESIGN FIDELITY UNAVAILABLE:",
                        _fidelity_error,
                    )



            final_render = self.result_bridge.resolve(
                result
            )


            # The result bridge constructs a new response object. Preserve the
            # two already-evaluated contracts verbatim; never re-grade them.
            if isinstance(final_render, dict) and isinstance(result, dict):

                for _verification_key in (
                    "design_observation",
                    "design_fidelity",
                ):

                    if (
                        isinstance(result.get(_verification_key), dict)
                        and _verification_key not in final_render
                    ):

                        final_render[_verification_key] = result[_verification_key]


            if isinstance(final_render, dict):

                final_render["architectural_design_decision"] = (
                    architectural_design_decision
                )

                rendered_asset = final_render.get(
                    "image_asset",
                    final_render.get(
                        "image",
                        {}
                    )
                )


                self.state.update({

                    "last_render_asset":

                        rendered_asset,

                    "last_architectural_intent":

                        architectural_intent

                })


                print(
                    "💾 LAST RENDER ASSET SAVED:",
                    rendered_asset
                )



            ui_image = self.image_response.adapt(
                final_render
            )


            attachments = (
                ui_image.get("attachments", [])
                if isinstance(ui_image, dict)
                else []
            )


            # ==============================================
            # IMAGE_TO_IMAGE_05 — DERIVED IMAGE REGISTRATION
            #
            # The edit result enters the session registry with lineage
            # back to its source, and becomes the LATEST image so the
            # next conversational edit chains from the derived image
            # instead of the original upload.
            # ==============================================

            derived_record = None

            try:

                derived_record = self._register_derived_output(
                    final_render,
                    attachments=attachments,
                    parent_image_id=parent_image_id,
                    architectural_intent=architectural_intent,
                )

            except Exception as e:

                print(
                    "⚠️ DERIVED REGISTRATION ERROR:",
                    e
                )


            if isinstance(final_render, dict):

                _chain_asset = final_render.get(
                    "image_asset",
                    final_render.get("image", {})
                )

                if (
                    isinstance(_chain_asset, dict)
                    and _chain_asset.get("path")
                ):

                    self.state.update({

                        "last_image_asset":

                            _chain_asset

                    })

                    print(
                        "🔗 CHAIN SOURCE UPDATED:",
                        _chain_asset.get("path")
                    )


            if attachments and hasattr(self.state, "add_message"):

                self.state.add_message(
                    "assistant",
                    "رندر آماده شد.",
                    attachments
                )


            # IMAGE_TO_IMAGE_05 — truthful top-level status.
            # Prefer the RenderRuntime derived status: it distinguishes
            # submit_error / execution_error / timeout / completed_no_image,
            # whereas the result bridge collapses failures to
            # "completed_no_image".
            render_status = None

            if isinstance(result, dict) and result.get("status"):

                render_status = result.get("status")

            elif isinstance(final_render, dict):

                render_status = final_render.get("status")

            else:

                render_status = "invalid_render_result"


            return {


                "type":

                    "image_render",


                "engine":

                    "render_runtime",


                # IMAGE_TO_IMAGE_05 — truthful top-level status
                "status":

                    render_status,


                "result":

                    ui_image,


                "render":

                    {
                        "status": render_status,
                        "bridge_status": (
                            final_render.get("status")
                            if isinstance(final_render, dict)
                            else None
                        ),
                        "engine": final_render.get("engine"),
                        "workflow": final_render.get("workflow"),
                        "prompt_id": final_render.get("prompt_id")
                    }
                    if isinstance(final_render, dict)
                    else {"status": "invalid_render_result"},


                "preservation":

                    preservation,


                "parent_image_id":

                    parent_image_id,


                "source_bound_image_id":

                    (
                        derived_record.get("image_id")
                        if isinstance(derived_record, dict)
                        else None
                    ),


                "source_bound_session_id":

                    (
                        derived_record.get("session_id")
                        if isinstance(derived_record, dict)
                        else None
                    ),


                "source_bound_project_id":

                    self._current_intent_ownership().get("project_id"),


                "architectural_intent":

                    architectural_intent,


                "attachments":

                    attachments

            }



        except Exception as e:


            print(
                "IMAGE EDIT ERROR:",
                e
            )


            return {


                "type":

                    "image_render",


                "status":

                    "error",


                "error":

                    str(e)

            }
