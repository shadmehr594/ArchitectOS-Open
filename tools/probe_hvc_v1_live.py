# -*- coding: utf-8 -*-
"""HUMAN_VOICE_CONVERSATION_V1 — live conversational + interpretation probe.

Drives the REAL ChatArchitect path for the brief's Persian/English test set
and the real spoken-language interpretation layer, printing the ACTUAL
generated responses.

Read-only: isolated data root, no design, no render, no ComfyUI.
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"<repo-root>"

os.environ.setdefault(
    "ARCHITECTOS_PROJECT_DATA_ROOT",
    os.path.join(ROOT, ".pytest_tmp", "hvc_v1_data"),
)

sys.path.insert(0, ROOT)

from core.chat.chat_architect import ChatArchitect  # noqa: E402
from core.app_boot import AppBoot  # noqa: E402
from core.chat.spoken_language_interpretation_v1 import (  # noqa: E402
    interpret_utterance,
)

PERSIAN = [
    "سلام خوبی؟",
    "سلام، خوبی، چیکار می‌کنی؟",
    "بیا یکم حرف بزنیم.",
    "بیا یکمی راجب معماری با هم صحبت کنیم.",
    "ببین یه ایده دارم ولی هنوز دقیق نمی‌دونم چی می‌خوام.",
    "نه نه، منظورم این نبود.",
    "بیخیال اون، بیا درباره آشپزی حرف بزنیم.",
    "من یه کم تند حرف می‌زنم، می‌تونی متوجه بشی؟",
]

ENGLISH = [
    "Hey, how are you?",
    "Let's just talk for a bit.",
    "I have an idea but I'm not sure how to explain it yet.",
    "No, that's not what I meant.",
    "Let's forget that and talk about something else.",
    "Let's talk about architecture.",
]

IMPERFECT_STT = [
    "بیا یکمی راجب مماری صحبت کنیم",
    "سلام میخوایم یک کمی در مورد مماری حرف بذاریم",
    "مماری",
    "راجب چیز دیگه صحبت کنیم",
]


def run(chat, text, sid):
    try:
        r = chat.handle(text, {"session_id": sid})
    except Exception as e:  # noqa: BLE001
        return f"<ERROR {e!r}>"
    return r.get("result") or r.get("message") or str(r)


def main():

    chat = ChatArchitect(AppBoot().get_brain())
    out = []

    for label, items, pref in (
        ("PERSIAN CONVERSATION", PERSIAN, "fa"),
        ("ENGLISH CONVERSATION", ENGLISH, "en"),
    ):
        out.append("")
        out.append("=" * 74)
        out.append(f"  {label}")
        out.append("=" * 74)
        for i, t in enumerate(items):
            out.append("")
            out.append(f"USER : {t}")
            out.append(f"BOT  : {run(chat, t, f'{pref}_{i}')}")

    out.append("")
    out.append("=" * 74)
    out.append("  SPOKEN-LANGUAGE INTERPRETATION (raw preserved)")
    out.append("=" * 74)
    for t in IMPERFECT_STT:
        r = interpret_utterance(t)
        out.append("")
        out.append(f"raw_transcript        : {r['raw_transcript']}")
        out.append(f"interpreted_utterance : {r['interpreted_utterance']}")
        out.append(f"changes               : "
                   f"{[(c['from'], c['to']) for c in r['changes']] or 'none'}")

    text = "\n".join(out)
    print(text)

    with open(
        os.path.join(ROOT, ".pytest_tmp", "hvc_v1_live.txt"),
        "w", encoding="utf-8",
    ) as fh:
        fh.write(text)


if __name__ == "__main__":
    main()
