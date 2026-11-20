# -*- coding: utf-8 -*-
"""PERSIAN_OUTPUT_ORTHOGRAPHY_V1 — Part A root-cause experiment (READ-ONLY).

Determines the TRUE source of malformed Persian in ArchitectOS responses:

  Q1: Does llama3 generate malformed spelling (حیات خلوت / زخیره) on its
      OWN, from a clean Persian request with NO malformed context?
  Q2: Does it ECHO malformed words that arrive in the context/user turn?
  Q3: Does adding an explicit Persian ORTHOGRAPHY RULE to the prompt
      reduce the errors?

Uses the REAL LLM (llama3 via ollama) and the REAL ProductionPromptEngine.
No files are modified by this script.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.llm.llm_gateway import LLMGateway  # noqa: E402
from core.prompt_engine import PromptEngine  # noqa: E402


MALFORMED_MARKERS = ["حیات خلوت", "زخیره", "آشپسخوره", "آشفزخانه", "آشپسخانه",
                     "تراحی", "مماری", "میماری", "نمو", "هلان"]

# The clean Persian requests to probe (no malformed input at all).
CLEAN_PROBES = [
    "آشپزخانه چه ارتباطی با حیاط خلوت دارد؟",
    "در معماری، حیاط خلوت چه نقشی دارد؟",
    "فعلاً چیزی ذخیره نکن.",
    "بیا درباره معماری حرف بزنیم",
]

# A probe whose CONTEXT contains the malformed form (echo test).
ECHO_PROBE = "پس خونه بهتر کنار حیاط خلوت باشه"


def malformed_hits(text):
    t = str(text or "")
    return [m for m in MALFORMED_MARKERS if m in t]


def run(engine, llm, user, context=None, label=""):
    prompt = engine.build(user, context)
    out = llm.generate(prompt)
    hits = malformed_hits(out)
    print(f"\n--- {label} ---")
    print(f"USER : {user}")
    print(f"REPLY: {str(out)[:200]}")
    print(f"MALFORMED HITS: {hits if hits else 'NONE'}")
    return out, hits


def main():
    engine = PromptEngine()
    llm = LLMGateway()

    total_bad = 0
    print("=" * 78)
    print("PART A — ORTHOGRAPHY ROOT-CAUSE EXPERIMENT (real llama3, no changes)")
    print("=" * 78)

    print("\n########## TEST GROUP 1: CURRENT PROMPT, CLEAN INPUT ##########")
    for p in CLEAN_PROBES:
        _, hits = run(engine, llm, p, label="current prompt / clean input")
        total_bad += len(hits)

    print("\n########## TEST GROUP 2: CURRENT PROMPT, MALFORMED CONTEXT (echo) ##########")
    _, hits = run(engine, llm, ECHO_PROBE, label="current prompt / echo probe")
    total_bad += len(hits)

    print("\n" + "=" * 78)
    print(f"TOTAL malformed hits under CURRENT prompt: {total_bad}")
    print("=" * 78)
    print("\nNOTE: Run again after the prompt is improved to compare.")


if __name__ == "__main__":
    main()
