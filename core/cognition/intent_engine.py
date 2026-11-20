# ==========================================================
# ArchitectOS Intent Engine v71.2
# Unified Intent Decision Layer
#
# Chat / Image / Design / Design Update Classification
#
# FIX:
# - Chat priority before generic design
# - Avoid routing general questions to GOD_CORE design
# - Preserve architecture image routing
# - General question detector fixed scope
# - UTF-8 stdout compatibility
# ==========================================================


import sys

import re


try:
    sys.stdout.reconfigure(
        encoding="utf-8"
    )
except Exception:
    pass



from core.cognition.intent_result import IntentResult


# ==========================================================
# CHAT_CODE_REQUEST_ROUTING_FIX_V1
#
# A programming / code request must NEVER be classified as an architectural
# design request. Recognition is deliberately NARROW: the turn must carry an
# explicit programming signal (a language, source code, a script, a code-file
# extension, syntax checking or code execution). Generic Persian prose such as
# "بساز" ("make") alone is NOT a programming signal.
# ==========================================================

_PROGRAMMING_SIGNAL_WORDS = (
    "python",
    "پایتون",
    "source code",
    "سورس",
    "اسکریپت",
    "script",
    "برنامه‌نویسی",
    "برنامه نویسی",
    "کدنویسی",
    "کد نویسی",
    "نحوی",
    "syntax",
    "دیباگ",
    "debug",
    "باگ",
    "bug",
    "ترمینال",
    "terminal",
    "کامند",
    "command",
    "traceback",
    "exception",
    "استثنا",
)

_PROGRAMMING_FILE_EXTENSIONS = (
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".cc", ".c",
    ".cs", ".go", ".rs", ".rb", ".php", ".sh", ".bash", ".html", ".css",
    ".sql", ".json", ".yaml", ".yml",
)

# Creation of an actual code FILE (not merely writing code in the chat).
_CODE_FILE_CREATE_ACTIONS = (
    "بساز", "بسازید", "ایجاد کن", "ایجاد کنید", "ذخیره کن", "ذخیره کنید",
    "درست کن", "درست کنید", "بسازه",
)

# Execution of code.
_CODE_EXEC_ACTIONS = (
    "اجرا کن", "اجرا کنید", "اجرا شود", "اجراش کن", "اجراش کنید",
    "ران کن", "ران کنید", "run it", "run the", "execute",
)

# Syntax checking of code.
_CODE_SYNTAX_ACTIONS = (
    "خطای نحوی", "خطاهای نحوی", "بررسی نحوی", "syntax error",
    "syntax check", "syntax checking",
)

# "کد" must not match "کدام" / "کدوم" (Persian "which").
_CODE_WORD_RE = re.compile(r"کد(?!\s*[اا])")


# ==========================================================
# CHAT_APP_CREATION_ROUTING_V1 — general desktop-app requests
#
# A normal user asks for an application, not for "source code". Requiring the
# literal words "Python" / "کد" / "برنامه‌نویسی" meant a request such as
# "یک ماشین‌حساب گرافیکی بساز" was never recognised as programming at all, so it
# fell through to ordinary chat and the chat model answered that it could not
# build anything.
#
# This detector is deliberately about SHAPE, not about one product: an
# application noun plus a creation verb. It is not calculator-specific and
# carries no generated source.
#
# Architectural requests must never be captured: a request that names an
# architectural object stays on the design path even when it also contains
# "برنامه" or "پنجره".
# ==========================================================

_APP_OBJECT_WORDS = (
    "برنامه", "اپلیکیشن", "اپلیکیشن", "نرم‌افزار", "نرم افزار", "نرم‌افزاری",
    "ماشین‌حساب", "ماشین حساب", "بازی", "ابزار", "داشبورد", "ویجت",
    "gui", "app", "application", "desktop", "widget", "calculator", "game",
)

_APP_CREATE_VERBS = (
    "بساز", "بسازید", "بسازه", "ایجاد کن", "ایجاد کنید", "درست کن",
    "درست کنید", "بنویس", "تولید کن", "تولید کنید",
    "build", "create", "make", "develop", "write",
)

# If any of these appear, the turn belongs to architecture, not to app building.
_ARCHITECTURAL_OBJECT_WORDS = (
    "ساختمان", "معماری", "نقشه", "پلان", "نما", "طبقه", "مسکونی", "تجاری",
    "حیاط", "اتاق", "سازه", "سایت پروژه", "متری", "پارکینگ", "بیم",
)


def app_creation_request(text):
    """True when the turn asks for a desktop application to be created.

    Shape-based and product-agnostic: an application noun plus a creation verb,
    with an architectural-object guard so design requests are never captured.
    """
    if not isinstance(text, str) or not text.strip():
        return False

    lowered = text.lower()

    if any(word in lowered for word in _ARCHITECTURAL_OBJECT_WORDS):
        return False

    has_object = any(word in lowered for word in _APP_OBJECT_WORDS)
    has_verb = any(word in lowered for word in _APP_CREATE_VERBS)

    return has_object and has_verb



# ==========================================================
# CHAT_CODING_CONDITIONAL_FALLBACK_FIX_V1
#
# A file-creation request may carry an EXPLICIT conditional fallback. Only a
# fallback that asks for the code to be WRITTEN IN THE CHAT turns the turn into
# an ordinary code-writing chat; a fallback that merely asks to "declare the
# limitation" or "don't fake the result" stays a hard capability request.
# ==========================================================

_FALLBACK_CONDITION_RE = re.compile(
    r"اگر[^.؟!\n]{0,60}?"
    r"(نداری|ندارید|نمی‌توانی|نمیتوانی|نمی‌تونی|نتوانستی|نتونستی|"
    r"نمی‌شه|نمیشه|ممکن نیست|امکان ندارد|امکان نداره|"
    r"امکان‌پذیر نیست|امکان پذیر نیست|نمی‌توانید|نمیتوانید)"
)

_FALLBACK_CONDITION_WORDS = (
    "در غیر این صورت",
    "در غیراین‌صورت",
    "وگرنه",
    "وإلا",
    "if you can't",
    "if you cannot",
    "if that's not possible",
    "if not possible",
    "if it's not possible",
    "otherwise",
)

# Positive "write the code in the chat" signals.
_CODE_IN_CHAT_REFS = ("چت", "chat", "همین‌جا", "همینجا", "اینجا")
_CODE_WRITE_VERBS = ("بنویس", "بنویسید", "بده", "write", "ارائه بده")

# A NEGATED chat reference must not be read as a fallback permission
# (e.g. "فقط کد را در چت نمایش نده").
_CODE_IN_CHAT_NEGATIONS = (
    "ننویس", "ننویسید", "نمایش نده", "نمایش ندهید", "ارائه نده", "ارائه ندهید",
    "ندهد", "don't write", "do not write", "don't show",
)


def _explicit_chat_fallback(text):
    """True when the turn EXPLICITLY permits writing the code in the chat if a
    real file cannot be produced."""

    lowered = text.lower()

    has_condition = bool(
        _FALLBACK_CONDITION_RE.search(text)
    ) or any(
        word in lowered for word in _FALLBACK_CONDITION_WORDS
    )

    if not has_condition:

        return False

    if any(neg in lowered for neg in _CODE_IN_CHAT_NEGATIONS):

        return False

    chat_ref = any(ref in lowered for ref in _CODE_IN_CHAT_REFS)

    write_verb = any(verb in lowered for verb in _CODE_WRITE_VERBS)

    return chat_ref and write_verb


def _has_programming_signal(text):
    """True when the turn explicitly concerns programming / source code."""

    lowered = text.lower()

    if any(ext in lowered for ext in _PROGRAMMING_FILE_EXTENSIONS):

        return True

    if any(word in lowered for word in _PROGRAMMING_SIGNAL_WORDS):

        return True

    if _CODE_WORD_RE.search(text):

        return True

    # CHAT_APP_CREATION_ROUTING_V1 — an ordinary "build me an app" turn is a
    # programming turn even when it never says "code" or "Python".
    if app_creation_request(text):

        return True

    return False


def _programming_request_kind(text):
    """Classify a programming turn.

    Returns:
        "code_file" — asks to create/execute/syntax-check an ACTUAL code file
                      (ArchitectOS has no verified tool for this).
        "code_chat" — ordinary "write/show/explain code in the chat" request.
        None        — not a programming request.
    """

    if not _has_programming_signal(text):

        return None

    lowered = text.lower()

    file_action = (

        # a real file must be produced
        (
            "فایل" in text
            and any(action in text for action in _CODE_FILE_CREATE_ACTIONS)
        )

        # a named file with a code extension ("calculator.py")
        or any(ext in lowered for ext in _PROGRAMMING_FILE_EXTENSIONS)

        # execution
        or any(action in text for action in _CODE_EXEC_ACTIONS)

        # syntax checking
        or any(action in text for action in _CODE_SYNTAX_ACTIONS)

    )

    # CHAT_CODING_CONDITIONAL_FALLBACK_FIX_V1 — if the user explicitly permits
    # writing the code in the CHAT when a real file cannot be produced, honour
    # that fallback and route to code-writing chat instead of the hard
    # capability response.
    if file_action and _explicit_chat_fallback(text):

        return "code_chat"

    return "code_file" if file_action else "code_chat"





class IntentEngine:


    VERSION = "71.2"



    def __init__(self):

        print(
            "Intent Engine v71.2 ACTIVE"
        )



    # ======================================================
    # CHAT DETECTOR
    # ======================================================

    def is_chat_message(
        self,
        text
    ):

        words = [

            "سلام",
            "درود",
            "hello",
            "hi",
            "hey",

            "خوبی",
            "چطوری",
            "چه خبر",

            "ممنون",
            "مرسی",

            "اسمت",
            "نامت",
            "کی هستی",

            "who are you",
            "how are you"

        ]


        return any(

            w in text

            for w in words

        )



    # ======================================================
    # ANALYZE
    # ======================================================

    def analyze(
        self,
        normalized_data
    ):


        if isinstance(
            normalized_data,
            dict
        ):

            text = (

                normalized_data.get(
                    "normalized"
                )

                or

                normalized_data.get(
                    "text"
                )

                or

                ""

            )

        else:

            text = str(
                normalized_data
            )



        text = (

            text

            .lower()

            .strip()

        )


        # ==================================================
        # PROJECT EXPORT DETECTOR
        # ==================================================

        export_words = [

            "export",
            "export project",
            "export file",
            "dwg",
            "dxf",
            "ifc",
            "rvt",
            "cad",
            "خروجی",
            "اکسپورت",
            "تبدیل فایل"

        ]


        if any(

            x in text

            for x in export_words

        ):


            return IntentResult(

                intent="project_export",

                confidence=0.95,

                source="export_rule"

            )



        # ==================================================
        # 1 - CHAT PRIORITY
        # ==================================================

        if self.is_chat_message(
            text
        ):


            return IntentResult(

                intent="chat",

                confidence=0.95,

                source="chat_rule"

            )



        # ==================================================
        # 1.5 - GENERAL QUESTION CHAT
        # ==================================================

        general_chat_words = [

            "چرا",
            "چگونه",
            "چطور",
            "چیست",
            "چی هست",
            "توضیح بده",
            "معنی",
            "فرق",
            "آیا",
            "به نظر",

            "what",
            "why",
            "how",
            "explain",
            "difference"

        ]



        # CODER-03 — a turn that carries an explicit programming signal is a
        # CODING turn, even when it also contains a generic question word
        # ("… کد کامل … را بنویس و توضیح بده …"). The narrow programming
        # signal list below decides; a purely general question has none and is
        # unaffected.
        if (

            any(

                x in text

                for x in general_chat_words

            )

            and not _has_programming_signal(text)

        ):


            return IntentResult(

                intent="chat",

                confidence=0.85,

                source="general_chat_rule"

            )


        # ==================================================
        # PROJECT EXPORT
        # ==================================================

        export_words = [

            "export",
            "export this project",
            "export project",

            "dwg",
            "dxf",
            "ifc",

            "خروجی",
            "اکسپورت",
            "صادر کن",
            "تبدیل به dwg",
            "تبدیل به dxf"

        ]


        if any(

            x in text

            for x in export_words

        ):


            return IntentResult(

                intent="project_export",

                confidence=0.95,

                source="export_rule"

            )



        # ==================================================
        # 1.9 - PROGRAMMING / CODE REQUEST (CHAT_CODE_REQUEST_ROUTING_FIX_V1)
        #
        # Placed BEFORE image and design so a programming request can never
        # fall into the architectural design pipeline. "code_chat" keeps
        # ordinary "write code in the chat" turns on the chat route (the LLM
        # still writes the code); "code_file" marks a request to create or run
        # an actual code file, which ArchitectOS cannot do.
        # ==================================================

        code_kind = _programming_request_kind(text)

        if code_kind == "code_file":

            return IntentResult(

                intent="code_request",

                confidence=0.9,

                source="code_file_rule"

            )

        if code_kind == "code_chat":

            # CODER-03 — the signal is PRESERVED (not folded into "chat") so
            # the routing boundary can send this turn to the coding model.
            return IntentResult(

                intent="code_chat",

                confidence=0.85,

                source="code_chat_rule"

            )


        # ==================================================
        # 2 - IMAGE GENERATION
        # ==================================================

        image_words = [

            "render",
            "image",
            "draw",
            "generate image",

            "رندر",
            "رندر کن",

            "تصویر",
            "تصویر کن",

            "visual",
            "visualization",

            "سه بعدی",
            "3d"

        ]



        if any(

            x in text

            for x in image_words

        ):


            return IntentResult(

                intent="image_generation",

                confidence=0.95,

                source="image_rule"

            )


        # ==================================================
        # EXPORT REQUEST
        # ==================================================

        export_words = [

            "export",
            "export this",
            "export project",

            "dwg",
            "dxf",
            "ifc",
            "revit",
            "rvt",
            "cad",

            "خروجی",
            "اکسپورت",
            "صدور فایل",
            "تبدیل به dwg",
            "تبدیل به dxf",
            "فایل اتوکد",
            "اتوکد"

        ]


        if any(

            x in text

            for x in export_words

        ):

            return IntentResult(

                intent="export_request",

                confidence=0.95,

                source="export_rule"

            )



        # ==================================================
        # 3 - DESIGN UPDATE
        # ==================================================

        update_words = [

            "اضافه کن",
            "به آن اضافه",
            "تغییر بده",
            "اصلاح کن",
            "ویرایش کن",

            "مدرن کن",
            "مدرن‌تر کن",

            "بهبود بده",
            "ارتقا بده",

            "بزرگتر کن",
            "کوچکتر کن",

            "add",
            "change",
            "modify",
            "update"

        ]



        update_targets = [

            "نما",
            "نمای",
            "facade",

            "اتاق",
            "room",
            "bedroom",

            "استخر",
            "pool",

            "garden",
            "باغ",
            "محوطه"

        ]



        has_action = any(

            x in text

            for x in update_words

        )


        has_target = any(

            x in text

            for x in update_targets

        )



        if (

            has_action

            and

            has_target

        ):


            return IntentResult(

                intent="design_update",

                confidence=0.95,

                source="design_update_rule"

            )



        # ==================================================
        # 4 - ARCHITECTURE TYPES
        # ==================================================

        if any(

            x in text

            for x in [

                "ویلا",
                "villa"

            ]

        ):


            return IntentResult(

                intent="villa_design",

                confidence=0.95,

                source="villa_rule"

            )



        if any(

            x in text

            for x in [

                "آپارتمان",
                "apartment"

            ]

        ):


            return IntentResult(

                intent="apartment_design",

                confidence=0.95,

                source="apartment_rule"

            )



        if any(

            x in text

            for x in [

                "برج",
                "tower",
                "highrise"

            ]

        ):


            return IntentResult(

                intent="highrise_design",

                confidence=0.95,

                source="tower_rule"

            )



        # ==================================================
        # 5 - GENERAL DESIGN
        # ==================================================

        # CHAT_CODE_REQUEST_ROUTING_FIX_V1 — explicit architectural phrases
        # are unambiguous design requests.
        strong_design_phrases = [

            "طراحی کن",
            "طراحی کن یک",
            "طراحی یک",

            "پلان معماری",
            "پلان خانه",

            "طراحی ساختمان",
            "طراحی ویلا"

        ]



        if any(

            x in text

            for x in strong_design_phrases

        ):


            return IntentResult(

                intent="design_request",

                confidence=0.9,

                source="design_rule"

            )



        # Generic Persian action verbs ("بساز", "ایجاد کن", …) are ordinary
        # prose: they mean "make" in any domain. They indicate a design request
        # ONLY when the SAME turn carries an architectural object. Otherwise a
        # programming/file request such as "calculator.py بساز" must not enter
        # the design pipeline. Genuine commands ("یک ساختمان بساز",
        # "پلان ساختمان ایجاد کن") still match through their architectural noun.
        generic_design_verbs = [

            "بساز",
            "بسازید",
            "ایجاد کن",
            "ایجاد کنید",
            "تولید کن",
            "تولید کنید"

        ]


        architecture_nouns = [

            "ساختمان",
            "ویلا",
            "خانه",
            "پلان",
            "معماری",
            "برج",
            "آپارتمان",
            "اتاق",
            "طبقه",
            "نقشه",
            "بنا",
            "مجتمع",
            "محوطه",
            "نما",

            "building",
            "house",
            "villa",
            "plan",
            "architecture",
            "tower",
            "apartment",
            "floor",
            "room",
            "facade"

        ]



        if (

            any(

                verb in text

                for verb in generic_design_verbs

            )

            and

            any(

                noun in text

                for noun in architecture_nouns

            )

        ):


            return IntentResult(

                intent="design_request",

                confidence=0.9,

                source="design_rule"

            )



        # ==================================================
        # 6 - MEMORY
        # ==================================================

        memory_words = [

            "یادت",
            "یادته",

            "remember",

            "memory",

            "history"

        ]



        if any(

            x in text

            for x in memory_words

        ):


            return IntentResult(

                intent="memory",

                confidence=0.9,

                source="memory_rule"

            )



        # ==================================================
        # 7 - FALLBACK CHAT
        # ==================================================

        return IntentResult(

            intent="chat",

            confidence=0.5,

            source="fallback"

        )



    # ======================================================
    # OPTIONAL CHAT CHECK
    # ======================================================

    def force_chat_check(
        self,
        text
    ):

        return self.is_chat_message(
            text
        )





# ==========================================================
# SINGLETON
# ==========================================================


intent_engine = IntentEngine()