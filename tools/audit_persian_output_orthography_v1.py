# -*- coding: utf-8 -*-
"""PERSIAN_OUTPUT_ORTHOGRAPHY_V1 — contrast tests (Part A).

Proves the response-side safety net:
  * fixes the measured malformed forms
  * NEVER corrupts the legitimate word حیات
  * is not a global replacement dictionary
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.chat.persian_output_orthography_v1 import (  # noqa: E402
    normalize_response_orthography,
)

# (input, expected)
CASES = [
    # ---- must FIX ----
    ("آشپزخانه کنار حیات خلوت قرار دارد.", "آشپزخانه کنار حیاط خلوت قرار دارد."),
    ("حیات خلوت", "حیاط خلوت"),
    ("پس خونه بهتر کنار حیات خلوت باشه", "پس خونه بهتر کنار حیاط خلوت باشه"),
    ("فعلا این اطلاعات را زخیره نکن", "فعلا این اطلاعات را ذخیره نکن"),
    ("زخیره", "ذخیره"),

    # ---- must PRESERVE (the heart of the safety contract) ----
    ("حیات انسان ارزشمند است.", "حیات انسان ارزشمند است."),
    ("حیات وحش این منطقه متنوع است.", "حیات وحش این منطقه متنوع است."),
    ("حیات پس از مرگ چیست؟", "حیات پس از مرگ چیست؟"),
    ("مفهوم حیات در زیست‌شناسی", "مفهوم حیات در زیست‌شناسی"),
    ("حیات", "حیات"),
    ("حیاط خلوت خانه کوچک است.", "حیاط خلوت خانه کوچک است."),
    ("اطلاعات را ذخیره کن.", "اطلاعات را ذخیره کن."),

    # ---- Arabic codepoint unification (presentation only) ----
    ("معمارى ايرانی", "معماری ایرانی"),
]

fails = 0
print("=" * 74)
print("PART A — Persian output orthography contrast tests")
print("=" * 74)
for src, want in CASES:
    out = normalize_response_orthography(src)
    got = out["text"]
    ok = got == want
    if not ok:
        fails += 1
    flag = "FIX " if out["changed"] else "KEEP"
    print(f"[{'PASS' if ok else 'FAIL'}] ({flag}) {src!r}")
    if out["changed"]:
        print(f"          -> {got!r}")
        print(f"          changes: {out['changes']}")
    if not ok:
        print(f"          WANT {want!r}")

# Explicitly assert the bare word حیات is untouched anywhere
assert normalize_response_orthography("حیات انسان")["text"] == "حیات انسان"
assert normalize_response_orthography("حیات وحش")["text"] == "حیات وحش"
print("\n[PASS] bare «حیات» preserved in حیات انسان / حیات وحش")

print("\n" + "=" * 74)
print(f"RESULT: {'ALL PASS' if fails == 0 else str(fails) + ' FAIL'} ({len(CASES)} cases)")
sys.exit(1 if fails else 0)
