# ==========================================================
# ArchitectOS Response Adapter v3.1
# GOD CORE -> UI/API Response Formatter
# Runtime + Render + Design + Memory + State Contract
# ==========================================================


# ==========================================================
# R4_PHOTO_FAST_PATH_CLOSURE_V1 — ACCEPTED PHOTOMETRIC CONFIRMATION
#
# `build_message()` honoured only `result["result"]` when it was a string and
# otherwise fell through to one generic sentence. The photometric bridge
# therefore reported "درخواست شما پردازش شد." and its own `message` key was
# never shown to the user.
#
# This is ONE exact sentence for ONE exact engine. It says what happened (the
# photograph's colour balance was warmed) and what did NOT happen (no
# architectural component was rebuilt or moved). It deliberately claims no
# physical relighting, no material replacement and no night conversion, and it
# promises nothing about any other photograph.
# ==========================================================

PHOTOMETRIC_WARMTH_CONFIRMATION = (
    "تراز رنگ عکس کمی گرم‌تر شد. "
    "اجزای معماری بازسازی یا جابه‌جا نشدند."
)


# ARCHITECTURAL_PRESERVATION_VISIBLE_HANDOFF_V1 — presentation only.
# The reasoning owner is GeometryAuthorityHandoffV1.  This boundary locates
# its already-built preservation sub-contract, copies it verbatim to a stable
# top-level API field, and renders only values that are actually present.
_PRESERVATION_LABELS_FA = {
    "main_facade_surface_expression": "مصالح و بیان معماری نمای اصلی",
    "main_facade_surface_finish": "پوشش سطح نمای اصلی",
    "building_massing": "حجم ساختمان",
    "floor_count": "تعداد طبقات",
    "structural_grid": "شبکه و قاب سازه‌ای",
    "windows_and_openings": "پنجره‌ها و بازشوهای موجود",
    "balcony_and_terrace_boundaries": "مرز بالکن‌ها و تراس‌ها",
    "ground_floor_open_bays": "دهانه‌های باز طبقه همکف",
    "roof_geometry": "هندسه بام",
    "camera_perspective": "پرسپکتیو دوربین",
    "courtyard": "حیاط",
    "foreground_ground_surfaces": "سطوح زمین پیش‌زمینه",
    "retaining_walls": "دیوارهای حائل",
    "adjacent_buildings": "ساختمان‌های مجاور",
    "neighbouring_architectural_details": "جزئیات معماری مجاور",
    "surrounding_site_layout": "چیدمان محوطه پیرامون",
}

_COMPLETION_LABELS_FA = {
    "complete_windows_within_existing_openings": (
        "نصب پنجره، قاب و شیشه درون بازشوهای موجود"
    ),
    "install_door_within_existing_doorway": (
        "نصب در و قاب درون درگاه موجود"
    ),
    "apply_decorative_column_treatment": (
        "اجرای پوشش، پیلستر یا سرستون روی ستون‌های موجود"
    ),
    "finish_balcony_within_existing_boundaries": (
        "تکمیل بالکن و تراس درون مرزهای موجود"
    ),
    "replace_requested_facade_surface_material": (
        "جایگزینی پوشش سطح نما با متریال درخواستی"
    ),
}


def _architectural_preservation_contract(result):
    """Return the existing V1 contract without deriving or mutating it."""

    if not isinstance(result, dict):
        return None

    direct = result.get("architectural_preservation_intent")
    if isinstance(direct, dict):
        return direct

    decision = result.get("architectural_design_decision")
    if isinstance(decision, dict):
        nested = decision.get("architectural_preservation_intent")
        if isinstance(nested, dict):
            return nested

    intent = result.get("architectural_intent")
    if isinstance(intent, dict):
        decision = intent.get("architectural_design_decision")
        if isinstance(decision, dict):
            nested = decision.get("architectural_preservation_intent")
            if isinstance(nested, dict):
                return nested

    return None


def _preservation_scope_labels(contract, scope):
    scopes = contract.get("scopes") if isinstance(contract, dict) else {}
    values = scopes.get(scope) if isinstance(scopes, dict) else []
    labels = []
    for item in values or []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        value = str(item["id"])
        label = _PRESERVATION_LABELS_FA.get(value, value.replace("_", " "))
        if label not in labels:
            labels.append(label)
    return labels


def _architectural_preservation_summary(contract):
    """Render a concise UI summary; never upgrade capability or evidence."""

    if not isinstance(contract, dict):
        return ""

    target = _preservation_scope_labels(contract, "design_target")
    architecture = _preservation_scope_labels(contract, "protected_architecture")
    context = _preservation_scope_labels(contract, "protected_context")
    requirements = contract.get("material_style_requirements") or {}
    capability = contract.get("preservation_capability") or {}

    lines = ["تصمیم حفاظت معماری:"]
    if target:
        lines.append("هدف طراحی: " + "، ".join(target))
    if architecture:
        lines.append("معماری حفاظت‌شده: " + "، ".join(architecture))
    if context:
        lines.append("بستر حفاظت‌شده: " + "، ".join(context))

    completion = contract.get("architectural_completion") or {}
    completion_labels = []
    for item in completion.get("allowed_operations") or []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        operation_id = str(item["id"])
        label = _COMPLETION_LABELS_FA.get(
            operation_id, operation_id.replace("_", " ")
        )
        if label not in completion_labels:
            completion_labels.append(label)
    if completion_labels:
        lines.append("تکمیل معماری مجاز: " + "، ".join(completion_labels))
        lines.append(
            "مرز تکمیل: فقط داخل هندسهٔ موجود؛ ایجاد، جابه‌جایی یا بزرگ‌کردن "
            "بازشوها و جابه‌جایی سازه مجاز نیست."
        )

    material_parts = []
    style = requirements.get("style")
    material = requirements.get("material")
    if isinstance(style, dict) and style.get("id"):
        material_parts.append(str(style["id"]))
    if isinstance(material, dict) and material.get("id"):
        material_parts.append(str(material["id"]))
    material_parts.extend(str(item) for item in (
        requirements.get("appearance_qualifiers") or []
    ))
    if material_parts:
        lines.append("نیاز متریال/سبک: " + "، ".join(material_parts))

    exclusions = requirements.get("excluded_material_expressions") or []
    if exclusions:
        lines.append(
            "تفسیرهای متریال غیرمجاز: "
            + "، ".join(str(item) for item in exclusions)
        )

    unverified = [
        item for item in (contract.get("evidence_register") or [])
        if isinstance(item, dict)
        and item.get("grounding_category") == "model_reported_but_unverified"
    ]
    if unverified:
        lines.append(
            "شواهد مدل‌گزارش‌شده همچنان UNVERIFIED هستند و هندسهٔ تأییدشده محسوب نمی‌شوند."
        )

    status = capability.get("status")
    if status:
        lines.append("وضعیت قابلیت: " + str(status))
    if status == "PRESERVATION_CAPABILITY_INSUFFICIENT":
        lines.append(
            "جریان dual-conditioned نصب‌شده فقط هدایت نرم هندسی ارائه می‌کند؛ "
            "حفظ دقیق هندسه، پیکسل‌های محوطه یا اجزای محافظت‌شده تضمین نشده است."
        )
        lines.append(
            "این تصمیم به‌تنهایی رندر یا پذیرش R4 را فعال نمی‌کند."
        )

    return "\n".join(lines)


class ResponseAdapter:


    VERSION = "v3.1"



    def __init__(self):

        print(
            "📦 RESPONSE ADAPTER v3.1 ONLINE"
        )



    # ======================================================
    # MAIN ADAPT
    # ======================================================

    def adapt(
        self,
        result
    ):


        if not isinstance(
            result,
            dict
        ):

            return {

                "status": "success",

                "type": "chat",

                "result": result

            }



        response = {


            "status":
                result.get(
                    "status",
                    "success"
                ),


            "type":
                result.get(
                    "type",
                    "chat"
                )

        }


        # ==================================================
        # USER FRIENDLY MESSAGE
        # ==================================================

        response["message"] = self.build_message(result)

        # ARCHITECTURAL_VISION_INTERPRETER_V1 — additive structured output.
        if "architectural_interpretation" in result:
            response["architectural_interpretation"] = result.get(
                "architectural_interpretation"
            )



        # ==================================================
        # ENGINE
        # ==================================================

        if "engine" in result:

            response["engine"] = result.get(
                "engine"
            )



        # ==================================================
        # INTENT
        # ==================================================

        if "intent" in result:

            response["intent"] = result.get(
                "intent"
            )


        # ==================================================
        # CHAT_LANGUAGE_02 — LANGUAGE + RENDER HANDOFF DIAGNOSTICS
        #
        # Additive pass-through so the language decision and the
        # chat -> render handoff remain observable at the API boundary.
        # ==================================================

        for _key in (
            # ARCHITECTURAL REASONING INTEGRATION V8 — retain the truthful
            # execution verdict and its evidence-based decision at the public
            # API boundary.  These are additive diagnostics; the stable text
            # `result`/`message` surfaces below are unchanged.
            "reason",
            "architectural_intent",
            "architectural_design_decision",
            "language",
            "render_handoff",
            # VISION_IMAGE_REGISTRY_04 — image understanding provenance
            "vision",
            # IMAGE_TO_IMAGE_05 — edit preservation + lineage + guard
            "preservation",
            "edit_preservation",
            "parent_image_id",
            "unsupported_edit",
            "render_metadata",
            # IMAGE_TO_IMAGE_05 — prompt / delta authority diagnostics
            "edit_delta",
            "compiled_render_prompt",
            # PHASE 08 — conversational turn semantics + teaching
            # foundation. Additive pass-through only.
            "turn_semantics",
            "teaching",
            "capability",
            "turn_language",
            "render_requested",
            # CORRECTION_LOOP_01 — the classifier's own verdict next to
            # the turn kind the teaching layer acted on.
            "classifier_turn_kind",
            "recovered_turn_kind",
            # CLAUSE_ANALYSIS_01 — every clause of a long message
            "candidates",
            "clause_count",
            # VISION_REPORT_LANGUAGE_01 — an explicit language request
            "language_request",
            # VISION_OBSERVATION_MODE_SEPARATION_V1 — the observation
            # contract at the API boundary, beside `architectural_interpretation`.
            "observation",
            # RENDER_SEMANTIC_FIDELITY_V1 — the English render instruction and
            # its fail-closed verdict, so the gate is observable at the API
            # boundary (contract only; nothing is rendered here).
            "render_instruction",
            "render_fidelity",
            # DUAL_IMAGE_COMPARISON_V1 — the grounded A/B comparison contract.
            "comparison",
            # CODER-05.2 trusted UI-proxy transport metadata. The UI gateway
            # strips this before returning the response to browser JavaScript.
            "code_approval",
        ):

            if _key in result:

                response[_key] = result.get(_key)

        # ARCHITECTURAL_PRESERVATION_VISIBLE_HANDOFF_V1 — the complete
        # machine-readable contract already exists inside the architectural
        # decision. Expose that exact object at a stable response key and add
        # a concise user-facing rendering of it. No route, admission, evidence
        # status or capability value is recomputed here.
        _preservation_contract = _architectural_preservation_contract(result)

        if isinstance(_preservation_contract, dict):

            _preservation_summary = _architectural_preservation_summary(
                _preservation_contract
            )

            response["architectural_preservation_intent"] = (
                _preservation_contract
            )

            response["architectural_preservation_summary"] = (
                _preservation_summary
            )

            if _preservation_summary:

                _existing_message = response.get("message")

                response["message"] = (
                    (str(_existing_message).rstrip() + "\n\n")
                    if isinstance(_existing_message, str)
                    and _existing_message.strip()
                    else ""
                ) + _preservation_summary



        # ==================================================
        # RESULT
        # ==================================================

        if "result" in result:

            response["result"] = result.get(
                "result"
            )

        # The UI renders response.result as text. Preserve that stable
        # surface while exposing the structured contract above.
        #
        # CHAT-02E — `result` is a TEXT surface: ui/static/app.js takes
        # `response.result || response.message` and runs it through
        # `String(...)`, so ANY dict left here is displayed literally as
        # "[object Object]". The earlier guard below only covered two
        # response types, so every other structured turn leaked a dict.
        # The structured value is never lost: it stays on its own keys
        # (`design`, `observation`, `architectural_interpretation`,
        # `bim_result`, ...) and is also kept verbatim under
        # `result_structured`. When there is no human-readable message the
        # surface says so truthfully instead of showing an object.
        if "result" in response and not isinstance(response["result"], str):

            response["result_structured"] = response["result"]

            _message = response.get("message")

            if isinstance(_message, str) and _message.strip():

                response["result"] = _message

            else:

                _language = self.declared_output_language(result)

                if str(_language or "").lower().startswith("fa"):

                    response["result"] = (
                        "⚠️ پاسخی از موتور دریافت شد اما متن قابل نمایشی نداشت."
                    )

                else:

                    response["result"] = (
                        "⚠️ A response was received but it carried no "
                        "displayable text."
                    )



        # ==================================================
        # ARCHITECTURAL INTENT
        # ==================================================

        if "architectural_intent" in result:

            response["architectural_intent"] = (
                result["architectural_intent"]
            )



        # ==================================================
        # DESIGN
        # ==================================================

        if result.get(
            "type"
        ) == "design":


            response["design"] = (
                result.get(
                    "result"
                )
            )


        elif "design" in result:


            response["design"] = (
                result["design"]
            )


        elif "spatial" in result:


            response["design"] = (
                result["spatial"]
            )


        # ==================================================
        # PLAN DRAWING ARTEFACT CONTRACT v1.0
        #
        # Additive only. Surfaces the bridge's rendered,
        # human-readable plan file (when one was produced)
        # without touching any existing response key.
        #
        # The block is deliberately honest: it reports the
        # artefact path plus the fail-closed resolution state,
        # so unresolved rooms stay visible as pending rather
        # than being silently dropped or guessed.
        # ==================================================

        plan_drawing = result.get(
            "plan_drawing"
        )

        if not isinstance(
            plan_drawing,
            dict
        ):

            plan_drawing = (
                result.get(
                    "result",
                    {}
                ).get(
                    "plan_drawing"
                )
                if isinstance(
                    result.get("result"),
                    dict
                )
                else
                None
            )


        if isinstance(
            plan_drawing,
            dict
        ):

            status = plan_drawing.get(
                "status"
            )

            contract = {

                "status":
                    status,

                "type":
                    plan_drawing.get(
                        "type",
                        "plan_drawing"
                    ),

                "version":
                    plan_drawing.get(
                        "version"
                    )

            }

            if status == "ready":

                contract["format"] = (
                    plan_drawing.get("format")
                )

                contract["path"] = (
                    plan_drawing.get("path")
                )

                contract["artefacts"] = (
                    plan_drawing.get(
                        "artefacts",
                        []
                    )
                )

                contract["plan_summary"] = (
                    plan_drawing.get(
                        "plan_summary",
                        {}
                    )
                )

                contract["room_resolution"] = (
                    plan_drawing.get(
                        "room_resolution",
                        {}
                    )
                )

                contract["pending_rooms"] = (
                    plan_drawing.get(
                        "pending_rooms",
                        []
                    )
                )

                contract["withheld_openings"] = (
                    plan_drawing.get(
                        "withheld_openings",
                        {}
                    )
                )

            else:

                contract["reason"] = (
                    plan_drawing.get("reason")
                )

                if "plan_summary" in plan_drawing:

                    contract["plan_summary"] = (
                        plan_drawing.get(
                            "plan_summary",
                            {}
                        )
                    )

                if "pending_rooms" in plan_drawing:

                    contract["pending_rooms"] = (
                        plan_drawing.get(
                            "pending_rooms",
                            []
                        )
                    )


            response["plan_drawing"] = contract


        # ==================================================
        # DESIGN STATE CONTRACT
        # ==================================================


        if result.get(
            "type"
        ) == "design":


            response["project_state"] = (

                result.get(
                    "project_state"
                )

                or

                "WAITING_APPROVAL"

            )


            response["approval_required"] = (

                response["project_state"]

                !=

                "APPROVED"

            )


            response["approval_status"] = (

                result.get(
                    "approval_status"
                )

                or

                False

            )


        # ==================================================
        # BIM / CAD CONTRACT
        # ==================================================

        if "bim" in result:

            response["bim"] = result.get(
                "bim"
            )

        if "bim_result" in result:

            response["bim"] = result.get(
                "bim_result"
            )


        if "file_analysis" in result:

            response["file_analysis"] = result.get(
                "file_analysis"
            )


        if "geometry" in result:

            response["geometry"] = result.get(
                "geometry"
            )


        if "visualization" in result:

            response["visualization"] = result.get(
                "visualization"
            )


        # ==================================================
        # DESIGN PREVIEW
        # ==================================================


        if "design_preview" in result:

            response["preview"] = result.get(
                "design_preview"
            )


        elif "visualization" in result:

            response["preview"] = result.get(
                "visualization"
            )



        # ==================================================
        # RENDER IMAGE
        # ==================================================

        image = self.extract_render_image(
            result
        )


        if image:

            response["image"] = image


        attachments = self.extract_attachments(
            result
        )


        if attachments:

            response["attachments"] = attachments


            if "image" not in response:

                first_image = next(
                    (
                        item
                        for item in attachments
                        if item.get("kind") in ("image", "render")
                    ),
                    None
                )


                if first_image:

                    response["image"] = {
                        "status": first_image.get("status", "ready"),
                        "filename": first_image.get("filename"),
                        "url": first_image.get("url")
                    }



        # ==================================================
        # MEMORY CONTRACT
        # ==================================================

        if "memory_context" in result:


            memory = result.get(
                "memory_context",
                {}
            )


            response["memory"] = {


                "architecture_style":
                    memory.get(
                        "architecture_style"
                    )

            }



        elif "memory" in result:


            response["memory"] = result.get(
                "memory"
            )



        # ==================================================
        # STATE BRIDGE
        # ==================================================

        if "state" in result:

            response["state"] = result.get(
                "state"
            )


        if "project_state" in result:

            response["project_state"] = result.get(
                "project_state"
            )


        if "conversation_state" in result:

            response["conversation_state"] = result.get(
                "conversation_state"
            )



        # ==================================================
        # RENDER METADATA
        # ==================================================

        if (
            result.get("type") == "render"
            or
            result.get("workflow")
            or
            result.get("prompt")
            or
            result.get("render")
        ):

            response["render"] = {

                "engine":
                    result.get("engine"),

                "workflow":
                    result.get("workflow"),

                "prompt":
                    result.get("prompt")

            }



        # ==================================================
        # SUMMARY
        # ==================================================

        response["summary"] = (
            self.build_summary(
                result
            )
        )



        return response





    # ======================================================
    # IMAGE EXTRACTION
    # ======================================================

    def extract_render_image(self, result):

        allowed_types = [
            "render",
            "design",
            "image"
        ]

        if result.get("type") not in [
            "render",
            "design",
            "image",
            "image_render",
            "image_edit",
            "image_upload"
        ]:
            return None


        candidates = [


            result.get(
                "image"
            ),


            result.get(
                "image_asset"
            )

        ]



        render = result.get(
            "render"
        )


        if isinstance(
            render,
            dict
        ):

            candidates.append(
                render.get(
                    "image_asset"
                )
            )



        execution = result.get(
            "execution"
        )


        if isinstance(
            execution,
            dict
        ):


            images = execution.get(
                "images"
            )


            if images:

                candidates.append(
                    images[0]
                )



            nested = execution.get(
                "execution"
            )


            if isinstance(
                nested,
                dict
            ):


                nested_images = nested.get(
                    "images"
                )


                if nested_images:

                    candidates.append(
                        nested_images[0]
                    )



        for item in candidates:


            if item:

                return self.extract_image(
                    item
                )



        return None



    # ======================================================
    # ATTACHMENT CONTRACT
    # ======================================================

    def normalize_attachment(self, attachment):

        if not isinstance(attachment, dict):

            return None


        url = attachment.get("url")


        if not isinstance(url, str) or not url.startswith("/"):

            return None


        allowed = (
            "id",
            "kind",
            "mime_type",
            "filename",
            "display_name",
            "url",
            "thumbnail_url",
            "size_bytes",
            "source",
            "status",
            "metadata"
        )


        return {
            key: attachment.get(key)
            for key in allowed
            if attachment.get(key) is not None
        }


    def extract_attachments(self, result):

        if not isinstance(result, dict):

            return []


        groups = []


        groups.append(result.get("attachments"))


        for key in ("result", "render"):

            nested = result.get(key)


            if isinstance(nested, dict):

                groups.append(nested.get("attachments"))


                image = nested.get("image") or nested.get("image_asset")


                if isinstance(image, dict):

                    groups.append([image.get("attachment")])


        for key in ("image", "image_asset"):

            image = result.get(key)


            if isinstance(image, dict):

                groups.append([image.get("attachment")])


        attachments = []
        seen = set()


        for group in groups:

            if not isinstance(group, list):

                continue


            for item in group:

                normalized = self.normalize_attachment(item)


                if not normalized:

                    continue


                marker = normalized.get("id") or normalized.get("url")


                if marker in seen:

                    continue


                seen.add(marker)
                attachments.append(normalized)


        return attachments





    # ======================================================
    # IMAGE NORMALIZER
    # ======================================================

    def extract_image(
        self,
        image
    ):


        if not isinstance(
            image,
            dict
        ):

            return image



        filename = image.get(
            "filename"
        )



        return {


            "status":
                image.get(
                    "status",
                    "success"
                ),


            "filename":
                filename,


            "url":
                image.get(
                    "url"
                )
                or
                (
                    "/output/"
                    + filename
                    if filename
                    else None
                ),


            "path":
                image.get(
                    "path"
                )

        }



    # CHAT_CODE_REQUEST_ROUTING_FIX_V1 — generic display placeholders that must
    # never, on their own, prove that a design exists.
    _GENERIC_BUILDING_VALUES = (
        "building", "unknown", "n/a", "none", "null", "ساختمان", "نامشخص"
    )

    _GENERIC_STYLE_VALUES = (
        "modern", "unknown", "n/a", "none", "null", "نامشخص"
    )

    def _non_generic(self, value, generic):

        if not isinstance(value, str):

            return False

        cleaned = value.strip().lower()

        if not cleaned:

            return False

        return cleaned not in generic

    def _design_has_real_geometry(self, payload):
        """REAL design artefacts — never the empty scaffold.

        A degenerate design emits the whole pipeline structure with EMPTY
        geometry (`rooms/walls/doors = []`, `bim_elements = []`, `assets = []`).
        That must not count as a created design.
        """

        if not isinstance(payload, dict):

            return False

        sources = [payload, payload.get("result"), payload.get("bim_result")]

        for source in sources:

            if not isinstance(source, dict):

                continue

            for key in ("geometry", "architectural_geometry"):

                geo = source.get(key)

                if not isinstance(geo, dict):

                    continue

                for gkey in (
                    "rooms", "walls", "spaces", "floors",
                    "doors", "windows", "levels", "openings"
                ):

                    value = geo.get(gkey)

                    if isinstance(value, (list, tuple, dict)) and len(value) > 0:

                        return True

            for key in ("spaces", "rooms", "bim_elements", "assets"):

                value = source.get(key)

                if isinstance(value, (list, tuple)) and len(value) > 0:

                    return True

            ifc_model = source.get("ifc_model")

            if isinstance(ifc_model, dict):

                entities = ifc_model.get("entities")

                if isinstance(entities, dict):

                    for value in entities.values():

                        if isinstance(value, (list, tuple)) and len(value) > 0:

                            return True

        return False

    def _design_was_created(self, result, building, style):
        """CHAT-02E + CHAT_CODE_REQUEST_ROUTING_FIX_V1 — real evidence that a
        design artefact exists.

        A design turn is announced as created ONLY when the payload carries
        REAL evidence: an explicit design identifier, non-empty geometry /
        BIM elements / assets, or a building type that is genuinely specific.
        Generic display placeholders (`building_type="building"`,
        `style="modern"`) and the empty geometry scaffold are NEVER evidence,
        so an empty design reports truthfully that nothing was created.
        """

        if not isinstance(result, dict):

            return False

        for key in ("design_id", "plan_id", "compiled_prompt"):

            if result.get(key):

                return True

        if self._design_has_real_geometry(result):

            return True

        if self._non_generic(building, self._GENERIC_BUILDING_VALUES):

            return True

        if self._non_generic(style, self._GENERIC_STYLE_VALUES):

            return True

        return False

    # ======================================================
    # HUMAN MESSAGE
    # ======================================================

    def build_message(self, result):

        # R4_PHOTO_FAST_PATH_CLOSURE_V1 — the accepted non-generative
        # photometric edit has exactly one truthful confirmation. Keyed on the
        # precise engine, so no other response shape can receive it and no
        # generic message changes.
        if (
            isinstance(result, dict)
            and result.get("engine") == "photometric_warmth_adjustment_v1"
        ):

            return PHOTOMETRIC_WARMTH_CONFIRMATION

        response_type = result.get(
            "type",
            "chat"
        )


        if response_type == "design":

            summary = result.get(
                "summary",
                {}
            )

            # CHAT-02E — "building" and "modern" were DISPLAY fallbacks, not
            # evidence: they made an empty design read as a successful one.
            # They are gone; an unknown value is simply unknown.
            style = (
                summary.get("style")
                or
                result.get(
                    "architectural_intent",
                    {}
                ).get(
                    "style"
                )
            )

            building = (

                summary.get(
                    "building_type"
                )

                or

                result.get(
                    "architectural_intent",
                    {}
                ).get(
                    "building_type"
                )

                or

                result.get(
                    "result",
                    {}
                ).get(
                    "metadata",
                    {}
                ).get(
                    "building_type"
                )

            )

            # CHAT-02E — never announce a design that does not exist.
            if not self._design_was_created(result, building, style):

                return (
                    "⚠️ طراحی ایجاد نشد.\n\n"
                    "این درخواست به مسیر طراحی هدایت شد، اما هیچ طراحی معتبری "
                    "تولید یا ذخیره نشد. اگر منظور شما گفت‌وگوی معمولی بود، "
                    "لطفاً دوباره بپرسید."
                )

            details = ""

            if building:

                details += f"نوع ساختمان: {building}\n"

            if style:

                details += f"سبک: {style}\n"

            return (
                "🏠 طراحی معماری آماده شد.\n\n"
                + details
                + "\n✅ طراحی با موفقیت ایجاد و ذخیره شد."
                + self.build_plan_message(result)
            )


        if response_type == "ifc":

            return (
                "🏗️ فایل BIM با موفقیت تحلیل شد."
            )


        if response_type in ("render", "image_render", "image_edit"):

            # T2I_I2I_CHAT_TO_IMAGE_EXECUTION_V1 — the completion message is
            # only truthful when the render ACTUALLY produced an image. A
            # failed or pending execution used to be reported as
            # "رندر آماده شد." with no image behind it.
            _render_status = str(result.get("status") or "")

            if _render_status in ("", "success", "debug"):

                return (
                    "رندر آماده شد."
                )

            _detail = result.get("error") or result.get("reason")

            if _render_status == "completed_no_image":

                return (
                    "رندر کامل نشد: سرویس رندر هیچ تصویر خروجی برنگرداند."
                    + (("\n" + str(_detail)) if _detail else "")
                )

            return (
                "رندر انجام نشد (وضعیت: %s)." % _render_status
                + (("\n" + str(_detail)) if _detail else "")
            )


        if response_type == "image_upload":

            return result.get(
                "message",
                "تصویر دریافت شد."
            )


        if response_type == "image_observation":
            # VISION_OBSERVATION_MODE_SEPARATION_V1 — the observation
            # layer's OWN message. It renders the observation contract and
            # nothing else: no space type, no function, no relations.
            from core.vision.vision_observation_mode_v1 import (
                render_observation,
            )

            observation = result.get("observation") or result.get("result")

            return render_observation(
                observation,
                language=self.declared_output_language(result),
            )


        if response_type == "image_comparison":
            # DUAL_IMAGE_COMPARISON_V1 — the two-image comparison contract.
            # Its text is produced by the comparison projection itself, so the
            # reply is always the evidence that was actually measured.
            comparison = result.get("comparison") or result.get("result") or {}

            if isinstance(comparison, dict):
                from core.vision.dual_image_comparison_v1 import (
                    render_comparison,
                )

                return render_comparison(
                    comparison,
                    language=self.declared_output_language(result),
                )

            if isinstance(result.get("message"), str):
                return result["message"]


        if response_type == "image_analysis":
            interpretation = (
                result.get("architectural_interpretation")
                or result.get("result")
                or {}
            )
            if isinstance(interpretation, dict):
                return self.build_architectural_vision_message(
                    interpretation,
                    # VISION_REPORT_LANGUAGE_01 — the reply must be in the
                    # language the response ITSELF declares. It used to be
                    # hardcoded English while declaring `persian`.
                    language=self.declared_output_language(result),
                )


        if isinstance(
            result.get("result"),
            str
        ):

            return result.get(
                "result"
            )


        return (
            "درخواست شما پردازش شد."
        )




    def declared_output_language(self, result):
        """The output language the response itself declares, or None.

        VISION_REPORT_LANGUAGE_01 — one owner for "what language is this
        reply supposed to be in", so the renderer cannot contradict the
        contract it is rendering.
        """
        language = (result or {}).get("language")

        if isinstance(language, dict):

            return (
                language.get("output_language")
                or language.get("input_language")
            )

        if isinstance(language, str):

            return language

        return None


    def build_architectural_vision_message(self, interpretation, language=None):
        """Render the read-only architectural interpretation contract.

        VISION_REPORT_LANGUAGE_01 — the rendering is now language-aware.
        `language=None` keeps the historical English output exactly.
        """
        from core.vision.vision_report_v1 import render_vision_report

        return render_vision_report(
            interpretation, language or "en"
        )


    # ======================================================
    # PLAN DRAWING MESSAGE v1.0
    #
    # Renders a short, honest description of the plan artefact.
    # Never claims a room was drawn when the bridge reported it
    # pending, and never invents a count, area, or path.
    # ======================================================

    def build_plan_message(self, result):

        plan_drawing = result.get(
            "plan_drawing"
        )

        if not isinstance(
            plan_drawing,
            dict
        ) and isinstance(
            result.get("result"),
            dict
        ):

            plan_drawing = result.get(
                "result",
                {}
            ).get(
                "plan_drawing"
            )


        if not isinstance(
            plan_drawing,
            dict
        ):

            return ""


        status = plan_drawing.get(
            "status"
        )


        if status == "unavailable":

            return (
                "\n\n🚧 نقشه اجرایی در این اجرا تولید نشد."
            )


        if status == "empty":

            return (
                "\n\n🚧 اتاق‌های قطعی‌شده‌ای برای "
                "رسم نقشه وجود ندارد."
            )


        if status != "ready":

            return ""


        resolution = (
            plan_drawing.get(
                "room_resolution",
                {}
            )
            or
            {}
        )

        plan_summary = (
            plan_drawing.get(
                "plan_summary",
                {}
            )
            or
            {}
        )

        drawn = resolution.get(
            "drawn_rooms"
        )

        pending = resolution.get(
            "pending_rooms"
        )

        area = plan_summary.get(
            "resolved_area_m2"
        )

        path = plan_drawing.get(
            "path"
        )


        lines = [
            "\n\n📐 نقشه معماری:"
        ]


        if isinstance(
            drawn,
            int
        ):

            lines.append(
                f"• اتاق‌های رسم‌شده: {drawn}"
            )


        if isinstance(
            area,
            (int, float)
        ) and area:

            lines.append(
                f"• مساحت قطعی‌شده: {area} متر مربع"
            )


        if isinstance(
            pending,
            int
        ) and pending:

            lines.append(
                f"• در انتظار مختصات (رسم نشده): {pending}"
            )


        if path:

            lines.append(
                f"• فایل: {path}"
            )


        return "\n" + "\n".join(
            lines
        )




    # ======================================================
    # SUMMARY
    # ======================================================

    def build_summary(
        self,
        result
    ):


        plan = result.get(
            "plan",
            {}
        )


        intent = result.get(
            "architectural_intent",
            {}
        )



        summary = {


            "building_type":

                plan.get(
                    "building_type"
                )
                or
                intent.get(
                    "building_type"
                ),



            "style":

                plan.get(
                    "style"
                )
                or
                intent.get(
                    "style"
                ),



            "floors":

                plan.get(
                    "floors"
                ),



            "requirements":

                plan.get(
                    "requirements",
                    {}
                ),



            "components":[]

        }



        design = (

            result.get(
                "design"
            )

            or

            result.get(
                "result"
            )

        )



        if isinstance(
            design,
            dict
        ):


            summary["components"] = list(
                design.keys()
            )


        # ==================================================
        # PLAN DRAWING SUMMARY v1.0 (additive)
        # ==================================================

        plan_drawing = result.get(
            "plan_drawing"
        )

        if not isinstance(
            plan_drawing,
            dict
        ) and isinstance(
            result.get("result"),
            dict
        ):

            plan_drawing = result.get(
                "result",
                {}
            ).get(
                "plan_drawing"
            )


        if isinstance(
            plan_drawing,
            dict
        ):

            plan_summary = (
                plan_drawing.get(
                    "plan_summary",
                    {}
                )
                or
                {}
            )

            room_resolution = (
                plan_drawing.get(
                    "room_resolution",
                    {}
                )
                or
                {}
            )

            summary["plan_drawing"] = {

                "status":
                    plan_drawing.get("status"),

                "format":
                    plan_drawing.get("format"),

                "path":
                    plan_drawing.get("path"),

                "drawn_rooms":
                    room_resolution.get(
                        "drawn_rooms"
                    ),

                "pending_rooms":
                    room_resolution.get(
                        "pending_rooms"
                    ),

                "resolved_area_m2":
                    plan_summary.get(
                        "resolved_area_m2"
                    ),

                "floors":
                    plan_summary.get(
                        "floors",
                        []
                    )

            }


        return summary
