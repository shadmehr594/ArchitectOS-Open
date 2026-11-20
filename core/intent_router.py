# ==========================================================
# ArchitectOS Intent Router Bridge v69.4
# Unified Intent Routing Layer
#
# Compatible:
# Intent Engine v71
# Chat Runtime v26+
# Core Platform v26
# ==========================================================


from core.cognition.intent_engine import (
    intent_engine,
    _has_programming_signal,
)


import re as _re


# ==========================================================
# T2I_I2I_CHAT_TO_IMAGE_EXECUTION_V1 — GENERAL CREATION VOCABULARY
#
# The image-generation gate used to require explicit render / image
# vocabulary ("رندر", "تصویر", "image", "3d", …). A user who simply asks
# for something to be MADE ("یک مکعب سفید ساده بساز" / "Generate a simple
# white cube.") carried no such word, so the turn fell through to ordinary
# chat and was never rendered. These are the general creation verbs, in
# both supported languages.
#
# They are deliberately NOT added to the strong image-signal list, because
# that list is evaluated BEFORE the intent engine and a bare creation verb
# would then hijack a genuine architectural design request
# ("یک ساختمان بساز" -> design). They are applied only as a FALLBACK, when
# the intent engine itself could not classify the turn.
# ==========================================================

GENERIC_CREATION_VERBS = (
    # Persian
    "بساز", "بسازید", "بسازه", "بسازی",
    "درست کن", "درست کنید",
    "ایجاد کن", "ایجاد کنید",
    "تولید کن", "تولید کنید",
    "بکش", "بکشید",
    "رسم کن", "رسم کنید",
    # English (matched on word boundaries)
    "make", "create", "generate", "draw", "produce",
    "paint", "sketch", "illustrate",
)


# English verbs are matched with \b so that "make" cannot match inside
# "makeup", "maker", "creates", etc.
_ENGLISH_CREATION_VERBS = tuple(
    v for v in GENERIC_CREATION_VERBS if v.isascii()
)

_PERSIAN_CREATION_VERBS = tuple(
    v for v in GENERIC_CREATION_VERBS if not v.isascii()
)


# Non-visual artefacts. "یک متن بساز" / "create a report" is a writing
# request, not an image request; a creation verb alone must not turn it
# into a render.
NON_VISUAL_ARTIFACT_NOUNS = (
    "متن", "فایل", "جدول", "گزارش", "ایمیل", "مقاله", "کد",
    "برنامه", "اسکریپت", "سند", "جمله", "مثال", "سوال", "سؤال",
    "لیست", "محاسبه", "فرمول", "پاورپوینت", "اکسل", "املا",
    "text", "file", "table", "report", "email", "article",
    "code", "script", "document", "sentence", "example",
    "question", "list", "formula", "calculation", "essay",
    "summary", "resume", "letter",
)


# Architectural / design nouns. The intent engine already resolves these
# to a design intent; this guard additionally stops a pending image
# request from capturing an architectural answer such as "۳ طبقه".
ARCHITECTURAL_DESIGN_NOUNS = (
    "ساختمان", "ویلا", "پلان", "طبقه", "واحد", "آپارتمان", "برج",
    "مجتمع", "پارکینگ", "نما", "نقشه", "خانه", "اتاق", "سایت",
    "building", "villa", "plan", "floor", "storey", "story",
    "apartment", "tower", "parking", "facade", "house", "room",
    "site", "plot",
)


# Concrete visual subjects accepted by the generic creation fallback.  A bare
# creation verb is not enough: "make it iterative" is a conversational/code
# continuation, while "make a white cube" names a visual result.  Explicit UI
# modes and the normal image/render vocabulary remain authoritative elsewhere.
VISUAL_CREATION_NOUNS = (
    "تصویر", "عکس", "رندر", "پوستر", "لوگو", "نقاشی", "طرح", "مکعب",
    "کره", "آیکن", "کاراکتر", "منظره", "محصول",
    "image", "picture", "render", "poster", "logo", "painting",
    "illustration", "drawing", "cube", "sphere", "icon", "character",
    "landscape", "product", "object",
)


CODER_FOLLOWUP_SIGNALS = (
    "iterative", "recursive", "recursion", "loop", "function", "method",
    "algorithm", "return value", "base case", "complexity",
    "تکراری", "بازگشتی", "حلقه", "تابع", "الگوریتم", "پیچیدگی",
)


# Specification tokens: what an answer to "which dimensions / colour /
# material?" looks like. At least one must be present for a turn to be
# treated as the completion of a pending image request.
SPECIFICATION_UNITS = (
    "سانتی‌متر", "سانتیمتر", "سانتی متر", "سانتی", "میلی‌متر",
    "میلیمتر", "میلی متر", "میلی", "متر", "کیلومتر",
    "cm", "mm", "km", "inch", "inches", "foot", "feet", "meter",
    "meters", "metre", "metres", "centimeter", "centimetre",
)

_SPECIFICATION_UNITS_LATIN = tuple(
    u for u in SPECIFICATION_UNITS if u.isascii()
)

SPECIFICATION_QUALITIES = (
    # colour
    "سفید", "سیاه", "مشکی", "قرمز", "آبی", "سبز", "زرد", "نارنجی",
    "بنفش", "صورتی", "خاکستری", "طوسی", "نقره", "طلایی", "قهوه‌ای",
    "کرم", "فیروزه‌ای", "برنزی",
    "white", "black", "red", "blue", "green", "yellow", "orange",
    "purple", "pink", "gray", "grey", "silver", "gold", "golden",
    "brown", "beige", "turquoise", "bronze",
    # material
    "چوب", "چوبی", "فلز", "فلزی", "آهن", "شیشه", "بتن", "سنگ",
    "آجری", "آجر", "پلاستیک", "برنج", "مس", "فولاد", "سرامیک",
    "wood", "wooden", "metal", "metallic", "iron", "glass",
    "concrete", "stone", "brick", "plastic", "steel", "ceramic",
    "marble", "granite",
)


# A pending image request survives this many subsequent turns. Beyond it,
# the request is considered abandoned and is not allowed to capture an
# unrelated later turn.
PENDING_IMAGE_MAX_AGE_TURNS = 6

# A specification answer is a short completion ("5*5*5 سانتیمتر"), never a
# paragraph.
PENDING_IMAGE_MAX_ANSWER_CHARS = 60


def _has_generic_creation_verb(text):
    lowered = str(text or "").lower()

    if any(v in lowered for v in _PERSIAN_CREATION_VERBS):

        return True

    if _ENGLISH_CREATION_VERBS:

        pattern = r"\b(" + "|".join(
            _re.escape(v) for v in _ENGLISH_CREATION_VERBS
        ) + r")(s|es|d|ed|ing)?\b"

        if _re.search(pattern, lowered):

            return True

    return False


def _has_non_visual_artifact_noun(text):

    lowered = str(text or "").lower()

    return any(n in lowered for n in NON_VISUAL_ARTIFACT_NOUNS)


def _has_architectural_design_noun(text):

    lowered = str(text or "").lower()

    return any(n in lowered for n in ARCHITECTURAL_DESIGN_NOUNS)


def _has_visual_creation_subject(text):

    lowered = str(text or "").lower()

    return any(noun in lowered for noun in VISUAL_CREATION_NOUNS)


def _is_coder_followup(text, conversation_state):
    """Continue the already selected coder role for a narrow code follow-up.

    The previous route is explicit session evidence.  This avoids guessing a
    code domain from words such as "make" while still handling the measured
    "make it iterative instead of recursive" turn after a render.
    """

    if not isinstance(conversation_state, dict):

        return False

    if conversation_state.get("last_model_role") != "coder":

        return False

    lowered = str(text or "").lower()

    return any(signal in lowered for signal in CODER_FOLLOWUP_SIGNALS)


def _has_specification_token(text):

    lowered = str(text or "").lower()

    if _re.search(r"\d", lowered):

        return True

    if any(u in lowered for u in SPECIFICATION_UNITS):

        return True

    if _SPECIFICATION_UNITS_LATIN:

        pattern = r"\b(" + "|".join(
            _re.escape(u) for u in _SPECIFICATION_UNITS_LATIN
        ) + r")\b"

        if _re.search(pattern, lowered):

            return True

    return any(q in lowered for q in SPECIFICATION_QUALITIES)



# ----------------------------------------------------------
# Shared predicates for the pending image-generation session.
# The router and the image handler MUST agree on what counts as
# "the answer that completes the previous request", so the rule
# lives here once.
# ----------------------------------------------------------

_QUESTION_MARKERS = (
    "?", "؟", "چیه", "چیست", "چی هست", "کدام", "چطور", "چرا",
    "what", "which", "why", "how",
)


def is_pending_image_answer(text):
    """True when `text` is a specification answer that completes a pending
    image-generation request (dimensions / colour / material)."""

    raw = str(text or "")

    if not raw.strip():

        return False

    if len(raw) > PENDING_IMAGE_MAX_ANSWER_CHARS:

        return False

    lowered = raw.lower()

    if any(m in lowered for m in _QUESTION_MARKERS):

        return False

    if _has_generic_creation_verb(raw):

        return False

    if _has_non_visual_artifact_noun(raw):

        return False

    if _has_architectural_design_noun(raw):

        return False

    return _has_specification_token(raw)


def merge_pending_image_prompt(pending, text):
    """Merge a specification answer into the pending request. Returns the
    merged prompt, or None when there is nothing to merge."""

    if not isinstance(pending, dict):

        return None

    base = str(pending.get("prompt") or "").strip()

    if not base:

        return None

    answer = str(text or "").strip()

    if not answer or answer in base:

        return base

    return base + " " + answer


class IntentRouter:


    VERSION = "69.4"



    def __init__(self):

        print(
            "🧠 Intent Router Bridge v69.4 ONLINE"
        )



    # ======================================================
    # ROUTE
    # ======================================================

    def route(
        self,
        text,
        image=None,
        context=None
    ):


        text = (
            text
            or
            ""
        ).strip()


        # ==================================================
        # LAST RENDER CONTINUATION CHECK v1
        #
        # Detect:
        # "همین رندر"
        # "همین تصویر"
        # "اضافه کن"
        #
        # Route to image edit
        # using previous render asset
        # ==================================================

        conversation_state = (
            context.get(
                "conversation_state",
                {}
            )
            if context
            else {}
        )


        last_render_asset = (
            conversation_state.get(
                "last_render_asset"
            )
        )


        # ==================================================
        # PRODUCT_INTEGRATION_V1 — VALIDATED MANUAL MODE
        # ==================================================
        # The API strategy controller has already validated this value.  A
        # manual mode is therefore authoritative at the routing boundary; auto
        # mode still uses the existing intent logic below.

        requested_mode = str(
            (context or {}).get("mode") or ""
        ).strip().lower()

        routing_source = str(
            (context or {}).get("routing_source") or ""
        ).strip().lower()

        manual_mode = requested_mode if routing_source == "manual" else ""

        if manual_mode == "text_to_image":

            return {
                "intent": "image",
                "mode": "generate",
                "source": "validated_manual_mode",
            }

        if manual_mode == "image_to_image":

            if (context or {}).get("dual_image_pair"):

                return {
                    "intent": "image",
                    "mode": "generate",
                    "source": "validated_manual_dual_image_mode",
                }

            if image or last_render_asset or conversation_state.get("last_image_asset"):

                return {
                    "intent": "image",
                    "mode": "edit",
                    "source": "validated_manual_mode",
                }

            return {
                "intent": "image",
                "mode": "waiting_for_upload",
                "type": "image_edit",
                "status": "waiting_for_upload",
                "message": "لطفاً تصویر هدف را برای ویرایش ارسال کنید.",
                "source": "validated_manual_mode",
            }

        if manual_mode == "chat":

            return {
                "intent": "chat",
                "mode": "conversation",
                "source": "validated_manual_mode",
            }


        if _is_coder_followup(text, conversation_state):

            return {
                "intent": "chat",
                "mode": "conversation",
                "model_role": "coder",
                "source": "coder_conversation_continuation",
            }


        conversation_intent = (
            (context or {}).get("conversation_intent")
            if isinstance((context or {}).get("conversation_intent"), dict)
            else {}
        )

        edit_delta = (
            (context or {}).get("image_edit_delta")
            if isinstance((context or {}).get("image_edit_delta"), dict)
            else {}
        )

        has_structured_edit_delta = bool(
            edit_delta.get("edit_class")
            and edit_delta.get("edit_class") != "generic_edit"
        )

        # A structured architectural appearance delta against an existing
        # render is an edit, even when the user does not repeat "this render".
        # This is the measured second-turn form: "make the brick colour a bit
        # lighter; preserve style/form/floors/windows".
        if (
            last_render_asset
            and has_structured_edit_delta
            and (
                conversation_intent.get("is_architecture")
                or conversation_state.get("last_route_intent") == "image"
            )
            and not _has_programming_signal(text)
        ):

            return {
                "intent": "image",
                "mode": "edit",
                "source": "structured_last_render_edit",
            }


        # ==================================================
        # T2I_I2I_CHAT_TO_IMAGE_EXECUTION_V1
        # PENDING IMAGE-GENERATION CONTINUATION GATE
        #
        # A previous turn asked the user for a missing specification
        # ("به ابعاد آن نیاز دارم"). The user's answer ("5*5*5 سانتیمتر")
        # carries no creation verb and no image vocabulary, so without this
        # gate it was routed as ordinary chat and the original request was
        # lost.
        #
        # The gate is deliberately narrow. The turn is treated as the
        # completion of the pending request ONLY when ALL of these hold:
        #   * a pending image-generation request exists and is not stale;
        #   * the turn is short and is not itself a question;
        #   * it carries no new creation verb (that would be a NEW request);
        #   * it carries no non-visual artefact noun;
        #   * it carries no architectural design noun (so an architectural
        #     answer such as "۳ طبقه" is never captured);
        #   * it carries at least one specification token (number / unit /
        #     colour / material).
        #
        # Nothing here is object-specific: any object, in either language,
        # continues the same way.
        # ==================================================

        pending_generate = conversation_state.get(
            "pending_image_generate"
        )

        if (
            isinstance(pending_generate, dict)
            and pending_generate.get("prompt")
            and not _has_programming_signal(text)
        ):

            _age = (
                int(conversation_state.get("turn_index", 0) or 0)
                - int(pending_generate.get("created_turn", 0) or 0)
            )

            if 0 <= _age <= PENDING_IMAGE_MAX_AGE_TURNS:

                if is_pending_image_answer(text):

                    print(
                        "🖼️ PENDING IMAGE GENERATION CONTINUATION DETECTED"
                    )

                    return {

                        "intent":
                            "image",

                        "mode":
                            "generate",

                        "continuation":
                            True,

                        "source":
                            "pending_image_generate"

                    }


        # ==================================================
        # V4.3A — M7 SAME-SUBJECT APPEARANCE CONTINUATION
        #
        # MEASURED DEFECT (V4.3 §5.2): the natural multi-variant phrasing never
        # reached the edit path.
        #
        #   "same tower, sunset"              -> design / create
        #   "Render the same tower at sunset" -> image / generate, with the
        #                                        NEW IMAGE REQUEST reset below
        #                                        discarding `last_render_asset`
        #
        # Both throw away the source image, so massing, camera and openings
        # cannot be preserved. A same-subject reference PLUS a classified
        # appearance delta is an EDIT of the existing render — and only when a
        # source image actually exists, so a request without one is never
        # forced into the edit path.
        # ==================================================

        _source_available = bool(
            image
            or last_render_asset
            or conversation_state.get("last_image_asset")
        )

        if _source_available and not _has_programming_signal(text):

            try:

                from core.prompt_intelligence.image_edit_delta_v1 import (
                    is_same_subject_appearance_request,
                )

                _same_subject_appearance = (
                    is_same_subject_appearance_request(text)
                )

            except Exception:

                _same_subject_appearance = False

            if _same_subject_appearance:

                print(
                    "🖼️ SAME-SUBJECT APPEARANCE CONTINUATION DETECTED"
                )

                return {
                    "intent": "image",
                    "mode": "edit",
                    "source": "same_subject_appearance_variation",
                }


        # ==================================================
        # NEW INDEPENDENT IMAGE REQUEST RESET
        # ==================================================

        new_image_request_words = [

            "draw",
            "generate",
            "create",
            "render",
            "رندر کن",
            "بساز",
            "طراحی کن"

        ]


        is_new_image_request = any(

            w in text.lower()

            for w in new_image_request_words

        )


        if is_new_image_request:


            print(
                "🆕 NEW IMAGE REQUEST - IGNORE OLD RENDER STATE"
            )


            last_render_asset = None


        continuation_words = [

            "همین رندر",
            "همین تصویر",
            "همین عکس",
            "روی همین",
            "در همین",
            "اضافه کن",
            "تغییر بده",
            "ویرایش کن",
            "اصلاح کن",
            "کم کن",
            "حذف کن"

        ]


        is_continuation = any(

            word in text.lower()

            for word in continuation_words

        )


        if (
            last_render_asset
            and
            is_continuation
            and not _has_programming_signal(text)
            and (
                conversation_intent.get("is_architecture")
                or has_structured_edit_delta
            )
        ):

            print(
                "🖼️ LAST RENDER CONTINUATION DETECTED"
            )


            return {

                "intent":
                    "image",


                "mode":
                    "edit",


                "source":
                    "last_render_asset"

            }
    



        # ==================================================
        # IMAGE EDIT WAITING GATE
        # ==================================================

        if (
            image is None
            and self.is_image_edit_request(text)
        ):

            print(
                "🖼️ IMAGE EDIT REQUEST WITHOUT IMAGE - WAITING"
            )


            return {

                "intent":
                    "image",

                "mode":
                    "waiting_for_upload",

                "type":
                    "image_edit",

                "status":
                    "waiting_for_upload",

                "message":
                    "لطفاً عکس ساختمان را ارسال کنید تا ویرایش روی همان تصویر انجام شود."

            }


        # A visual-reference question without an attached image is ordinary
        # chat.  The word "image" / "تصویر" must not alone turn it into a
        # generation request through the downstream intent engine.
        question_markers = (
            "?", "؟", "چیه", "چیست", "چی هست", "چه ",
            "کدام", "چطور", "توضیح", "تحلیل", "بررسی",
            "what", "which", "describe", "explain", "analyze",
        )

        generation_actions = (
            "بساز", "ایجاد کن", "تولید کن", "رندر کن",
            "generate", "create", "render",
        )

        # CODER-03 — a turn with an explicit programming signal is a CODING
        # turn, even when it also contains a generic question word
        # ("… کد کامل … را بنویس و توضیح بده …"). It must fall through to the
        # engine so the coding signal is preserved; a purely general question
        # has no programming signal and is unaffected.
        if (
            image is None
            and any(marker in text.lower() for marker in question_markers)
            and not any(action in text.lower() for action in generation_actions)
            and not _has_programming_signal(text)
        ):

            return {
                "intent": "chat",
                "mode": "conversation",
            }



        # ==================================================
        # IMAGE GENERATION PRIORITY OVERRIDE v1
        #
        # CHAT-02E — a word that is ALSO ordinary Persian prose must never on
        # its own turn a turn into an image operation. «واقعی» ("real", as in
        # «رمان معمایی واقعی» = "a real mystery novel") is in the weak list:
        # it only counts when an unambiguous image/render signal is present in
        # the same turn, or when the turn actually carries an image. A
        # legitimate image request («یک رندر واقع‌گرایانه بساز») still matches
        # through its strong word («رندر»).
        # ==================================================

        image_generate_words = [

            # strong — unambiguous image / render vocabulary
            "رندر",

            "render",

            "سه بعدی",

            "3d",

            "visual",

            "visualization",

            "archviz",

            "تصویر",

            "عکس",

            "ایمیج",

            "image"

        ]

        # weak — everyday words that may ALSO describe an image
        weak_image_words = [

            "واقع‌گرایانه",

            "واقعی",

            "واقع گرایانه"

        ]



        has_strong_image_signal = any(

            word in text.lower()

            for word in image_generate_words

        )


        has_weak_image_signal = any(

            word in text.lower()

            for word in weak_image_words

        )


        if has_strong_image_signal or (has_weak_image_signal and image):


            print(
                "🖼️ IMAGE GENERATION OVERRIDE"
            )



            conversation_state = (

                context.get(
                    "conversation_state",
                    {}
                )

                if context

                else {}

            )



            last_render_asset = (

                conversation_state.get(
                    "last_render_asset"
                )

            )



            is_followup = self._is_followup(

                text,

                conversation_state

            )



            if (

                last_render_asset

                and

                is_followup

            ):


                print(
                    "🖼️ IMAGE EDIT MODE DETECTED"
                )


                return {

                    "intent":
                        "image",

                    "mode":
                        "edit"

                }



            return {

                "intent":
                    "image",

                "mode":
                    "generate"

            }





        # ==================================================
        # IMAGE EDIT PRIORITY
        # ==================================================

        if image:


            edit_words = [

                "edit",

                "modify",

                "change",

                "facade",

                "نما",

                "تغییر",

                "اصلاح",

                "مدرن"

            ]



            if any(

                w in text.lower()

                for w in edit_words

            ):


                return {


                    "intent":

                        "image",


                    "mode":

                        "edit"


                }





        # ==================================================
        # INTENT ENGINE
        # ==================================================

        try:


            result = intent_engine.analyze(

                text

            )



            if hasattr(

                result,

                "intent"

            ):


                intent = result.intent



            elif isinstance(

                result,

                dict

            ):


                intent = result.get(

                    "intent"

                )



            else:


                intent = None





            # ----------------------------------------------
            # NORMALIZATION
            # ----------------------------------------------


            if intent == "image_generation":


                return {


                    "intent":

                        "image",


                    "mode":

                        "generate"


                }





            if intent == "design_update":


                return {


                    "intent":

                        "design",


                    "mode":

                        "update"


                }





            # CHAT_CODE_REQUEST_ROUTING_FIX_V1 — a request to create or run an
            # actual code file is NOT an architectural design. It is routed to
            # a dedicated capability boundary that answers truthfully instead
            # of entering the design / BIM pipeline.
            if intent == "code_request":


                return {


                    "intent":

                        "code",


                    "mode":

                        "capability"


                }



            if intent in [


                "villa_design",

                "apartment_design",

                "highrise_design",

                "design_request"

            ]:


                return {


                    "intent":

                        "design",


                    "mode":

                        "create",


                    "design_type":

                        intent


                }





            if intent == "memory":


                return {


                    "intent":

                        "memory",


                    "mode":

                        "recall"


                }




            # CODER-03 — a confirmed code-writing chat turn keeps the CHAT
            # route (it is still ordinary conversation) but asks the chat
            # branch to answer with the dedicated coding model. Every other
            # turn is unchanged.
            if intent == "code_chat":


                return {


                    "intent":

                        "chat",


                    "mode":

                        "conversation",


                    "model_role":

                        "coder"


                }


            # ==================================================
            # T2I_I2I_CHAT_TO_IMAGE_EXECUTION_V1
            # GENERIC CREATION-VERB IMAGE FALLBACK
            #
            # The engine resolved this turn to ordinary chat. If the turn is
            # nevertheless a creation request ("یک مکعب سفید ساده بساز" /
            # "Generate a simple white cube.") it is a text-to-image request
            # and must be rendered.
            #
            # This is a FALLBACK, never an override:
            #   * it runs only after the engine returned `chat`, so every
            #     design / code / memory / export intent the engine already
            #     recognises is untouched ("یک ساختمان بساز" stays design);
            #   * it never fires on a question ("مکعب چیست؟");
            #   * it never fires on a non-visual artefact request
            #     ("یک متن بساز", "create a report");
            #   * it never fires when an image is already attached (that
            #     turn belongs to the upload / analyse / edit paths).
            # ==================================================

            if (
                image is None
                and _has_generic_creation_verb(text)
                and not _has_non_visual_artifact_noun(text)
                and _has_visual_creation_subject(text)
            ):

                print(
                    "🖼️ GENERIC CREATION REQUEST -> IMAGE GENERATE"
                )

                return {

                    "intent":
                        "image",

                    "mode":
                        "generate",

                    "source":
                        "generic_creation_verb"

                }






            return {


                "intent":

                    "chat",


                "mode":

                    "conversation"

            }





        except Exception as e:


            print(

                "INTENT ROUTER ERROR:",

                e

            )


            return {


                "intent":

                    "chat",


                "mode":

                    "conversation"

            }





    # ======================================================
    # FOLLOW UP DETECTOR
    # ======================================================

    def _is_followup(

        self,

        text,

        conversation_state

    ):


        if not text:

            return False



        words = [

            "اضافه کن",

            "تغییر بده",

            "ویرایش کن",

            "اصلاح کن",

            "هم اضافه کن",

            "modify",

            "change",

            "add"

        ]



        text = text.lower()



        return any(

            word in text

            for word in words

        )





    # ======================================================
    # IMAGE EDIT REQUEST DETECTOR
    # ======================================================

    def is_image_edit_request(

        self,

        text,

        has_image=False

    ):


        if not text:

            return False



        # CHAT-02E — strong edit vocabulary. These name an image/edit action
        # explicitly, so they stand on their own.
        #
        # R2_AUTO_IMAGE_INTENT_SAFETY_V1 — the deictic «این ساختمان» was in
        # this list, so a sentence that merely NAMED the subject counted as a
        # modification command. In Auto mode that sent a descriptive question
        # («این ساختمان چند طبقه دارد؟») to a real img2img render.
        #
        # A reference is not a verb. Deictic turns are still edits through the
        # EXISTING deictic path (an object anchor plus an appearance noun) and
        # through the imperative vocabulary below; only the bare reference
        # stopped standing alone.
        keywords = [


            "عکس خام",

            "عکس میفرستم",

            "عکس می‌فرستم",

            "آپلود",

            "ویرایش",

            "ویرایش کن",

            "بدون تغییر فرم",

            "روی این عکس",

            "preserve",

            "edit",

            "img2img"

        ]


        # CHAT-02E — everyday phrases that only describe an EDIT when an image
        # is actually attached. «بدون تغییر» alone is ordinary prose ("without
        # changing the subject") and must not open the image-edit gate.
        contextual_keywords = [


            "بدون تغییر",

            "اصلاح کن",

            "اضافه کن"

        ]


        text = text.lower()


        if any(

            item.lower() in text

            for item in keywords

        ):

            return True


        if has_image and any(

            item.lower() in text

            for item in contextual_keywords

        ):

            return True


        return False





# singleton

intent_router = IntentRouter()
