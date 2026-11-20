# -*- coding: utf-8 -*-
"""HUMAN_CONVERSATION_NATURALNESS_V1 — live acceptance probe.

Drives the REAL ChatArchitect.handle() path for the brief's test set and
prints the actual generated Persian / English responses.

Read-only: it uses an isolated project data root, makes no design, never
renders and never calls ComfyUI.
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"<repo-root>"

os.environ.setdefault(
    "ARCHITECTOS_PROJECT_DATA_ROOT",
    os.path.join(ROOT, ".pytest_tmp", "naturalness_v1_data"),
)
# render-stop guard: every ComfyUI submit must fail fast and truthfully
os.environ.setdefault("ARCHITECTOS_COMFY_PORT", "9")

sys.path.insert(0, ROOT)

from core.chat.chat_architect import ChatArchitect  # noqa: E402
from core.app_boot import AppBoot  # noqa: E402

PERSIAN = [
    "سلام خوبی؟",
    "بیا یکم حرف بزنیم.",
    "بیا یک کمی راجع به آشپزی و غذا درست کردن صحبت کنیم.",
    "بیا یکم راجع به معماری با هم صحبت کنیم.",
    "به نظرت معماری مدرن چه جذابیتی داره؟",
]

ENGLISH = [
    "Hello, how are you?",
    "Let's just chat for a bit.",
    "Let's talk about architecture.",
    "Let's talk about cooking.",
]

# the brief's reported defect example, verbatim
REPORTED = [
    "سلام خوبی بیایی یکمی راجب معماری با هم دیگه صحبت کنم",
]


def run_one(chat, text, session_id):
    try:
        r = chat.handle(text, {"session_id": session_id})
    except Exception as e:  # noqa: BLE001
        return {"result": f"<ERROR: {e!r}>", "domain": None, "engine": None}

    result = r.get("result") or r.get("message") or ""
    domain = None
    if isinstance(r.get("conversation_domain"), dict):
        domain = r["conversation_domain"].get("domain")
    return {
        "result": result,
        "domain": domain,
        "engine": r.get("engine"),
    }


def main():

    chat = ChatArchitect(AppBoot().get_brain())

    groups = [
        ("PERSIAN", PERSIAN, "fa"),
        ("ENGLISH", ENGLISH, "en"),
        ("REPORTED-DEFECT", REPORTED, "fa"),
    ]

    out = []

    for label, items, prefix in groups:

        out.append("")
        out.append("=" * 70)
        out.append(f"  {label}")
        out.append("=" * 70)

        for i, text in enumerate(items):

            session_id = f"naturalness_{prefix}_{i}"

            r = run_one(chat, text, session_id)

            out.append("")
            out.append(f"USER  : {text}")
            out.append(f"DOMAIN: {r['domain']}   ENGINE: {r['engine']}")
            out.append(f"BOT   : {r['result']}")

    text_out = "\n".join(out)
    print(text_out)

    with open(
        os.path.join(ROOT, ".pytest_tmp", "naturalness_v1_live.txt"),
        "w",
        encoding="utf-8",
    ) as fh:
        fh.write(text_out)


if __name__ == "__main__":
    main()
