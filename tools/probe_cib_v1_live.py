# -*- coding: utf-8 -*-
"""CONVERSATION_INTENT_BOUNDARY_V1 — live validation probe.

Drives the REAL ChatArchitect path for the brief's full test matrix and
prints, per turn:

    USER TEXT | CLASSIFIER OUTPUT | FINAL ROUTE | ACTUAL RESPONSE

Read-only: isolated data root, no design, no render, no ComfyUI.
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"<repo-root>"

os.environ.setdefault(
    "ARCHITECTOS_PROJECT_DATA_ROOT",
    os.path.join(ROOT, ".pytest_tmp", "cib_v1_data"),
)

sys.path.insert(0, ROOT)

from core.chat.chat_architect import ChatArchitect  # noqa: E402
from core.app_boot import AppBoot  # noqa: E402
from core.chat.conversation_intent_boundary_v1 import (  # noqa: E402
    classify_conversation_intent,
)


GENERAL = [
    "سلام خوبی؟",
    "خودت رو معرفی کن",
    "اسمت چیه؟",
    "تو چه کارهایی می تونی انجام بدی؟",
    "بیا یکم حرف بزنیم",
    "بیا درباره آشپزی حرف بزنیم",
    "نه، منظورم این نبود",
    "بیخیال اون موضوع",
    "Hello, how are you?",
    "Introduce yourself.",
]

ARCHITECTURE = [
    "بیا درباره معماری حرف بزنیم",
    "معماری مدرن رو دوست داری؟",
    "پلان باز چه مزایایی داره؟",
    "نور طبیعی توی طراحی خونه چقدر مهمه؟",
    "به نظرت آشپزخونه جزیره ای خوبه؟",
    "Let's talk about architecture.",
    "What are the benefits of an open floor plan?",
]

TEACHING = [
    "می‌خوام یه نکته معماری بهت یاد بدم",
    "این قانون رو یاد بگیر",
    "این رو به دانشت اضافه کن",
    "یادت باشه در طراحی من آشپزخانه باید کنار حیاط خلوت باشه",
    "می‌خوام این اصل رو برای طراحی‌های بعدی حفظ کنی",
    "I'm going to teach you a design rule.",
    "Remember this rule for future designs.",
]

BOUNDARY = [
    "به نظرم آشپزخونه باید نزدیک ناهارخوری باشه",
    "آشپزخونه بهتره نور طبیعی داشته باشه",
    "این رو قبول ندارم",
    "اصلاحش کن",
    "معماری رو بهم یاد بده",
    "من بهت معماری یاد میدم",
]

SEQUENCE_A = [
    "بیا درباره معماری حرف بزنیم",
    "راستی خودت رو معرفی کن",
    "خب برگردیم به معماری",
]

SEQUENCE_B = [
    "می‌خوام یه قانون طراحی بهت یاد بدم",
    "بیخیال، فعلاً ذخیره نکن",
    "بیا درباره غذا حرف بزنیم",
]


def run(chat, text, sid):
    try:
        r = chat.handle(text, {"session_id": sid})
    except Exception as e:  # noqa: BLE001
        return {"__error__": repr(e)}
    return r or {}


def main():

    chat = ChatArchitect(AppBoot().get_brain())

    out = []

    def emit(line=""):
        out.append(line)
        print(line)

    for label, items in (
        ("GENERAL_CONVERSATION", GENERAL),
        ("ARCHITECTURE_CONVERSATION", ARCHITECTURE),
        ("TEACHING", TEACHING),
        ("BOUNDARY / ADVERSARIAL", BOUNDARY),
    ):

        emit("")
        emit("=" * 100)
        emit("  " + label)
        emit("=" * 100)

        for i, t in enumerate(items):

            r = run(chat, t, "cib_%s_%d" % (label[:4], i))

            cib = r.get("conversation_intent") or {}

            cib_intent = cib.get("intent")

            # direct classifier output (independent of the runtime gate)
            cls = classify_conversation_intent(t)

            tch = r.get("teaching")
            tch_action = (
                tch.get("action") if isinstance(tch, dict) else None
            )

            tk = (r.get("turn_semantics") or {}).get("turn_kind")

            route = (
                "TEACHING_FLOW" if tch_action
                else (tk or "CHAT")
            )

            resp = r.get("result") or r.get("message") or str(r)

            emit("")
            emit("USER      : " + t)
            emit("CLASSIFIER: " + str(cls.get("intent"))
                 + "  (conf " + str(cls.get("confidence")) + ")")
            emit("RUNTIME   : " + str(cib_intent)
                 + "  (conf " + str(cib.get("confidence")) + ")")
            emit("TURN_KIND : " + str(tk))
            emit("ROUTE     : " + str(route)
                 + (" | teaching.action=" + str(tch_action)
                    if tch_action else ""))
            emit("RESPONSE  : " + str(resp)[:300].replace("\n", " "))

    emit("")
    emit("=" * 100)
    emit("  CONTEXT TRANSITION — SEQUENCE A (architecture -> self -> architecture)")
    emit("=" * 100)

    for i, t in enumerate(SEQUENCE_A):
        r = run(chat, t, "cib_seq_a")
        cib = r.get("conversation_intent") or {}
        emit("  %-38s -> %s" % (t[:38], cib.get("intent")))

    emit("")
    emit("=" * 100)
    emit("  CONTEXT TRANSITION — SEQUENCE B (teaching -> cancel -> general)")
    emit("=" * 100)

    for i, t in enumerate(SEQUENCE_B):
        r = run(chat, t, "cib_seq_b")
        cib = r.get("conversation_intent") or {}
        tch = r.get("teaching")
        ta = tch.get("action") if isinstance(tch, dict) else None
        emit("  %-38s -> %-26s %s"
             % (t[:38], cib.get("intent"), ta or ""))

    text = "\n".join(out)

    with open(
        os.path.join(ROOT, ".pytest_tmp", "cib_v1_live.txt"),
        "w", encoding="utf-8",
    ) as fh:
        fh.write(text)


if __name__ == "__main__":
    main()
