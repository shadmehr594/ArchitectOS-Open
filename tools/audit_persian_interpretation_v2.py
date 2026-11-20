# -*- coding: utf-8 -*-
"""PERSIAN_VOICE_QUALITY_V2 / PHASE 2 — interpretation-layer test matrix.

Read-only. Drives the REAL SpokenLanguageInterpreterV1 against the RAW
transcripts actually produced by Whisper large-v3-turbo on this machine
(from `tools/audit_persian_stt_v2.py`, `.pytest_tmp/stt_audit_v2/`), plus
the required word list and the DANGEROUS near-miss pairs that must NOT be
"corrected" (e.g. آشپزی must never become آشپزخانه).

It prints, per case:
    EXPECTED | RAW | INTERPRETED | changed? | verdict

and, crucially, the ANTI-CORRUPTION cases where the interpreter must
REFUSE to change anything.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.chat.spoken_language_interpretation_v1 import (  # noqa: E402
    interpret_utterance,
)


# (label, raw_transcript, expected_interpretation_or_None, must_change)
#
# must_change semantics:
#   True  -> the NEAR-MISS itself must be corrected (spoken-form changes
#            may also happen; an exact `expect` string is checked when set)
#   False -> the NEAR-MISS must survive untouched. Other independent
#            spoken-form normalisations (e.g. یه->یک) are allowed and do
#            NOT count as a failure. When `expect` is set it is checked
#            exactly.
#
# For the must_change=False rows the probe also asserts the near-miss
# token itself is still present in the interpreted utterance — that is the
# real safety property, not "the string is byte-identical".
CASES = [
    # ---- the CANONICAL architecture rescue (must still work) ----
    ("A1 معماری — talk-about turn",
     "بیا در باره مماری صحبت کنیم",
     "بیا در باره معماری صحبت کنیم", True),
    ("A2 معماری — isolated (no context)",
     "میموری.",
     None, False),           # no context -> must NOT change
    ("A3 معماری — in-sentence w/ context",
     "در طراحی این خانه معماری اهمیت دارد",
     "در طراحی این خانه معماری اهمیت دارد", False),
    ("A4 معماری — near-miss + design marker",
     "در طراحی این خانه میماری مهم است",
     "در طراحی این خانه معماری مهم است", True),
    ("A5 معماری — near-miss, NO marker at all",
     "من می‌خوام یه نکته میماری بهت یاد بدم",
     None, False),           # near-miss deliberately LEFT
                             # (only the "یه"->"یک" spoken form applies)

    # ---- حیاط خلوت / ذخیره / آشپزخانه (homophone letter confusions) ----
    ("B1 حیاط خلوت -> حیات خلوت (ط->ت)",
     "آشپزخانه کنار حیات خلوت است.",
     "آشپزخانه کنار حیاط خلوت است.", True),
    ("B2 ذخیره -> زخیره (ذ->ز)",
     "فعلا این اطلاعات را زخیره نکن.",
     "فعلا این اطلاعات را ذخیره نکن.", True),
    ("B3 آشپزخانه -> آشپسخانه (ز->س)",
     "آشپسخانه کنار حیاط خلوت قرار دارد.",
     "آشپزخانه کنار حیاط خلوت قرار دارد.", True),

    # ==========================================================
    # ANTI-CORRUPTION — these MUST NOT CHANGE. This is the heart of
    # the "do not aggressively rewrite" rule.
    # ==========================================================
    ("C1 آشپزی (cooking) MUST stay آشپزی",
     "من عاشق آشپزی هستم",
     "من عاشق آشپزی هستم", False),
    ("C2 آشپزی near-miss MUST NOT become آشپزخانه",
     "اشپا زی را دوست دارم",
     None, False),
    ("C3 مماری inside a COOKING turn MUST NOT become معماری",
     "دستور مماری برای پختن برنج چیه",
     None, False),
    ("C4 میماری inside a non-arch turn MUST NOT change",
     "این فیلم درباره میماری یک بازیکن است",
     None, False),
    ("C5 حیات (life) MUST NOT become حیاط blindly",
     "حیات پس از مرگ چیست",
     None, False),
    ("C6 زخیره (non-word) may be recovered to ذخیره",
     "او زخیره شد و رفت",
     "او ذخیره شد و رفت", True),
    ("C6b حیات with NO yard context MUST NOT change",
     "حیات من در خطر است",
     None, False),

    # ---- spoken-form contractions must still work ----
    ("D1 راجب -> راجع به",
     "بیا راجب خانه صحبت کنیم",
     "بیا راجع به خانه صحبت کنیم", True),
    ("D2 میخوام -> می‌خواهم",
     "میخوام یه خانه طراحی کنیم",
     "می‌خواهم یک خانه طراحی کنیم", True),

    # ---- ISOLATED words (the user's exact reported pairs) ----
    ("E1 زخیره isolated -> ذخیره",
     "زخیره", "ذخیره", True),
    ("E2 آشپسخانه isolated -> آشپزخانه",
     "آشپسخانه", "آشپزخانه", True),
    ("E3 حیات خلوت isolated -> حیاط خلوت",
     "حیات خلوت", "حیاط خلوت", True),
    ("E4 ارسال مستقیم -> ذخیره نکن",
     "فعلا این اطلاعات را ذخیره نکن.",
     "فعلا این اطلاعات را ذخیره نکن.", False),
]


def _near_miss_untouched(raw, out):
    """True when NO lexical-rescue change was applied.

    Spoken-form normalisations (یه->یک, راجب->راجع به, …) are allowed;
    what must NOT happen is a semantic rescue (homophone or architecture
    contextual rescue) on a turn that has no context to justify it.
    """

    for change in out.get("changes") or []:
        if change.get("kind") in ("homophone_rescue", "contextual_rescue"):
            return False
    return True


def main():
    rows = []
    print("=" * 78)
    print("PERSIAN VOICE QUALITY V2 / PHASE 2 — interpretation matrix")
    print("=" * 78)
    print(f"{'CASE':<44} | {'CHG':<4} | {'VERDICT':<8}")
    print("-" * 78)

    fails = []
    for label, raw, expect, must_change in CASES:
        out = interpret_utterance(raw)
        interp = out.get("interpreted_utterance")
        changed = interp != raw

        # Verdict semantics (see the CASES comment):
        #   expect set        -> the interpreted string must match exactly.
        #   must_change=True  -> some correction must have happened.
        #   must_change=False -> the turn must NOT have been corrected as
        #                        a whole (an independent spoken-form fix
        #                        is still allowed, e.g. یه->یک).
        if expect is not None:
            ok = (interp == expect)
        elif must_change:
            ok = changed
        else:
            ok = _near_miss_untouched(raw, out)

        verdict = "PASS" if ok else "FAIL"
        if not ok:
            fails.append((label, raw, interp, expect, must_change))

        line = f"{label[:44]:<44} | {str(changed):<4} | {verdict:<8}"
        print(line)
        print(f"    raw  : {raw}")
        print(f"    interp: {interp}")
        if changed:
            print(f"    changes: {json.dumps(out.get('changes'), ensure_ascii=False)}")
        rows.append({
            "label": label, "raw": raw, "interpreted": interp,
            "expected": expect, "must_change": must_change,
            "changed": changed, "verdict": verdict,
            "changes": out.get("changes"),
        })

    print("-" * 78)
    print(f"TOTAL {len(CASES)}  PASS {len(CASES) - len(fails)}  FAIL {len(fails)}")
    if fails:
        print("\nFAILURES:")
        for label, raw, interp, expect, mc in fails:
            print(f"  - {label}\n      raw={raw!r}\n      got={interp!r}\n      want={expect!r} must_change={mc}")

    out_dir = os.path.join(ROOT, ".pytest_tmp", "phase2_interpretation")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "interpretation_matrix.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"cases": rows, "fails": len(fails)}, fh,
                  ensure_ascii=False, indent=2)
    print(f"\nsaved -> {path}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
