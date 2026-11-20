# ==========================================================
# ArchitectOS Response Guard v5
# LLM Output Enforcement Layer
# Language Consistency + Validation
# Safe Output Preservation
# ==========================================================


class ResponseGuard:

    VERSION = "v5"


    def __init__(self):

        print(
            "🛡️ RESPONSE GUARD v5 ONLINE"
        )


    # ======================================================
    # LANGUAGE DETECTION
    # ======================================================

    def detect_language(
        self,
        text
    ):

        if not text:
            return "unknown"


        persian = 0
        english = 0


        for char in str(text):

            if "\u0600" <= char <= "\u06FF":
                persian += 1

            elif char.isalpha():
                english += 1


        if persian > english:
            return "persian"


        if english > persian:
            return "english"


        return "unknown"



    # ======================================================
    # MIXED LANGUAGE
    # ======================================================

    def is_mixed(
        self,
        text
    ):

        if not text:
            return False


        has_persian = False
        has_english = False


        for char in str(text):

            if "\u0600" <= char <= "\u06FF":
                has_persian = True

            elif char.isalpha():
                has_english = True


        return has_persian and has_english



    # ======================================================
    # SAFE CLEAN
    # ======================================================

    def clean_text(
        self,
        text
    ):

        if not text:
            return text


        result = str(text)


        # فقط فاصله‌های اضافی
        while "  " in result:

            result = result.replace(
                "  ",
                " "
            )


        return result.strip()



    # ======================================================
    # REPAIR
    # ======================================================

    def repair(
        self,
        user,
        response
    ):

        # اگر خروجی ساختاری است دست نزن
        if isinstance(response, dict):

            return response


        return self.clean_text(
            response
        )



    # ======================================================
    # VALIDATE
    # ======================================================

    def validate(
        self,
        user,
        response,
        expected_language=None
    ):

        # PHASE 08E — PERSIAN-FIRST
        # When the canonical project/conversation language is known, the
        # reply is validated against THAT language instead of the raw
        # script of this one message.  With expected_language=None the
        # behaviour is byte-identical to before.
        user_lang = expected_language or self.detect_language(
            user
        )


        response_lang = self.detect_language(
            response
        )


        mixed = self.is_mixed(
            response
        )


        valid = True


        # Persian input
        if user_lang == "persian":

            if response_lang == "english" and not mixed:

                valid = False


        # English input
        elif user_lang == "english":

            if response_lang == "persian" and not mixed:

                valid = False


        return {

            "valid": valid,

            "input_language": user_lang,

            "output_language": response_lang,

            "mixed": mixed,

            "expected_language": expected_language,

            "language_source": (
                "canonical_project_state"
                if expected_language
                else "message_script"
            )

        }



    # ======================================================
    # ENFORCE
    # ======================================================

    def enforce(
        self,
        user,
        response
    ):


        repaired = self.repair(
            user,
            response
        )


        check = self.validate(
            user,
            repaired
        )


        if not check["valid"]:

            print(
                "⚠️ RESPONSE GUARD LANGUAGE WARNING:",
                check
            )


        return repaired



    # ======================================================
    # PROCESS
    # ======================================================

    def process(
        self,
        user,
        response
    ):


        result = self.enforce(
            user,
            response
        )


        check = self.validate(
            user,
            result
        )


        print(
            "⚠️ RESPONSE GUARD VALIDATION:",
            check
        )


        return result



    # ======================================================
    # APPLY CONTRACT
    # ======================================================

    def apply(
        self,
        user,
        response
    ):


        repaired = self.process(
            user,
            response
        )


        check = self.validate(
            user,
            repaired
        )


        return {


            "response":
                repaired,


            "input_language":
                check["input_language"],


            "output_language":
                check["output_language"],


            "status":

                "validated"

                if check["valid"]

                else "language_mismatch"

        }



    # ======================================================
    # BOUNDED CORRECTION  (CHAT_LANGUAGE_02)
    #
    # detect + correct, not detect + warn.
    #
    # Exactly ONE correction attempt. No retry loop, ever.
    # The correction is supplied by the caller (bounded LLM call)
    # so this module stays provider-free and testable.
    # ======================================================

    def correct(
        self,
        user,
        response,
        corrector=None,
        expected_language=None
    ):

        check = self.validate(
            user,
            response,
            expected_language=expected_language
        )


        # already consistent -> nothing to do
        if check["valid"]:

            return {

                "response":
                    response,

                "corrected":
                    False,

                "validation":
                    check,

                "status":
                    "validated"

            }


        # no corrector available -> bounded deterministic fallback:
        # keep the original text, report the mismatch truthfully.
        if corrector is None:

            return {

                "response":
                    response,

                "corrected":
                    False,

                "validation":
                    check,

                "status":
                    "language_mismatch_uncorrected",

                "fallback":
                    "no_corrector"

            }


        try:

            candidate = corrector(
                user,
                response,
                check
            )

        except Exception as e:

            return {

                "response":
                    response,

                "corrected":
                    False,

                "validation":
                    check,

                "status":
                    "language_mismatch_uncorrected",

                "fallback":
                    "corrector_error",

                "error":
                    str(e)

            }


        if not candidate:

            return {

                "response":
                    response,

                "corrected":
                    False,

                "validation":
                    check,

                "status":
                    "language_mismatch_uncorrected",

                "fallback":
                    "empty_correction"

            }


        candidate = self.repair(
            user,
            candidate
        )


        recheck = self.validate(
            user,
            candidate,
            expected_language=expected_language
        )


        # Single attempt only: accept the correction only if it
        # actually resolved the mismatch, otherwise keep the original.
        if not recheck["valid"]:

            return {

                "response":
                    response,

                "corrected":
                    False,

                "validation":
                    check,

                "status":
                    "language_mismatch_uncorrected",

                "fallback":
                    "correction_still_invalid",

                "attempted_validation":
                    recheck

            }


        return {

            "response":
                candidate,

            "corrected":
                True,

            "validation":
                recheck,

            "status":
                "corrected"

        }




# ==========================================================
# SINGLETON
# ==========================================================

response_guard = ResponseGuard()