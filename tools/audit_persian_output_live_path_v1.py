"""PERSIAN_OUTPUT_ORTHOGRAPHY_V1 — LIVE response-path validation.

Runs the REAL wired path (LLMGateway + PromptEngine + ResponseGuard +
persian_output_orthography) for the malformed-context user turns that
were measured to make llama3 ECHO the malformed spelling, plus the clean
'output quality' turns from the brief.

Reports, per turn:
    USER            the exact user text
    RAW             the LLM reply BEFORE orthography normalisation
    FINAL           the reply AFTER orthography normalisation
    CHANGES         the applied corrections
    VERDICT         PASS when FINAL contains no malformed form

Malformed forms under test (must NEVER appear in FINAL):
    «حیات خلوت»  (should be «حیاط خلوت»)
    «زخیره»      (should be «ذخیره»)

This tool does NOT touch STT, dictation, routing or any frozen surface.
"""

from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# the response path prints a lot; keep this run's stdout clean
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":

    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )


from core.llm.llm_gateway import LLMGateway                      # noqa: E402
from core.prompt_engine import PromptEngine                      # noqa: E402
from core.chat.response_guard import ResponseGuard               # noqa: E402
from core.chat.persian_output_orthography_v1 import (            # noqa: E402
    persian_output_orthography,
)


BAD_FORMS = ("حیات خلوت", "زخیره")

# (a) the measured ECHO trigger turns + (b) the brief's quality turns
TURNS = [
    "این رو یادت باشه آشپزخانه بهتر کنار حیات خلوت باشه",
    "پس خونه بهتر کنار حیات خلوت باشه",
    "بی خیال فعلا زخیره نکنه",
    "خودت رو معرفی کن",
    "بیا درباره معماری حرف بزنیم",
    "آشپزخانه چه ارتباطی با حیاط خلوت دارد؟",
    "فعلاً چیزی ذخیره نکن.",
]


def main() -> int:

    gateway = LLMGateway()
    engine = PromptEngine()
    guard = ResponseGuard()

    failures = []
    rows = []

    for user_text in TURNS:

        prompt = engine.build(user_text, {})

        # LLMGateway.generate() returns the plain reply string (or None).
        raw = str(gateway.generate(prompt) or "")

        corrected = guard.correct(
            user_text, raw, expected_language="persian"
        )

        guarded = str(corrected.get("response", raw))

        ortho = persian_output_orthography.normalize(guarded)

        final = ortho["text"]

        hits_raw = [b for b in BAD_FORMS if b in raw]
        hits_final = [b for b in BAD_FORMS if b in final]

        verdict = "PASS" if not hits_final else "FAIL"

        if hits_final:

            failures.append((user_text, hits_final))

        rows.append(
            {
                "user": user_text,
                "raw": raw.strip(),
                "final": final.strip(),
                "changes": ortho.get("changes") or [],
                "hits_raw": hits_raw,
                "hits_final": hits_final,
                "verdict": verdict,
            }
        )

    # ---- report (ASCII markers so the shell capture is reliable) ----
    for i, row in enumerate(rows, 1):

        print("=" * 72)
        print(f"TURN {i}")
        print("USER   >>>", row["user"])
        print("RAW    >>>", row["raw"].replace("\n", " "))
        print("FINAL  >>>", row["final"].replace("\n", " "))
        print("CHANGES>>>", row["changes"])
        print("HITS_RAW >>>", row["hits_raw"])
        print("HITS_FINAL >>>", row["hits_final"])
        print("VERDICT>>>", row["verdict"])

    print("=" * 72)
    print("TOTAL_TURNS >>>", len(rows))
    print("TOTAL_FAILURES >>>", len(failures))
    print("OVERALL >>>", "PASS" if not failures else "FAIL")

    return 0 if not failures else 1


if __name__ == "__main__":

    raise SystemExit(main())
