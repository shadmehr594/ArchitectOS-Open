# ==========================================================
# ArchitectOS Image Mode Routing Contract — Direct Acceptance
#
# No ComfyUI jobs. No image model calls. This validates the native
# classifier, no-attachment router guard, and completed-turn API contract.
# ==========================================================

import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from core.intent_router import intent_router
from core.vision.image_intent_v1 import (
    INTENT_ANALYZE,
    INTENT_EDIT,
    INTENT_UPLOAD_ONLY,
    MODE_CHAT,
    MODE_IMAGE_ANALYSIS,
    MODE_IMAGE_EDIT,
    MODE_IMAGE_UPLOAD,
    MODE_TEXT_TO_IMAGE,
    build_mode_contract,
    classify_image_intent,
)


PASS = []


def ok(label):
    PASS.append(label)
    print("[PASS] " + label)


def attached_contract(intent, output):
    return build_mode_contract(
        {"type": output, "vision": {"intent": intent}},
        has_image=True,
    )


def main():
    # A1 / A9: explicit analysis stays analysis and never renders.
    intent = classify_image_intent(
        "این تصویر را فقط تحلیل کن. هیچ طراحی یا تغییری انجام نده."
    )
    assert intent["intent"] == INTENT_ANALYZE, intent
    contract = attached_contract(intent["intent"], "image_analysis")
    assert contract["mode"] == MODE_IMAGE_ANALYSIS and not contract["render"], contract
    ok("A1/A9 attachment analysis -> IMAGE_ANALYSIS, render=false")

    # A2: reported production failure case: edit outranks reference phrase.
    intent = classify_image_intent(
        "این تصویر خام ساختمان را به نمای نئوکلاسیک تبدیل کن. "
        "هندسه حفظ شود. رندر تولید کن."
    )
    assert intent["intent"] == INTENT_EDIT, intent
    contract = attached_contract(intent["intent"], "image_render")
    assert contract["mode"] == MODE_IMAGE_EDIT and contract["render"], contract
    ok("A2 Persian transform -> IMAGE_EDIT, render=true")

    # A3: image question remains non-render analysis.
    intent = classify_image_intent("این تصویر چه فضای معماری را نشان می‌دهد؟")
    assert intent["intent"] == INTENT_ANALYZE, intent
    contract = attached_contract(intent["intent"], "image_analysis")
    assert contract["mode"] == MODE_IMAGE_ANALYSIS and not contract["render"], contract
    ok("A3 attachment question -> IMAGE_ANALYSIS, render=false")

    # A4 / A5: colloquial and facade-style edits are explicit edits.
    for phrase in (
        "این عکس رو ویرایش کن",
        "این تصویر را به نمای کلاسیک تغییر بده",
    ):
        intent = classify_image_intent(phrase)
        assert intent["intent"] == INTENT_EDIT, (phrase, intent)
    ok("A4/A5 Persian image edits -> IMAGE_EDIT")

    # A6: an actual generation action is still text-to-image.
    route = intent_router.route("یک تصویر از یک خانه مدرن بساز")
    assert route == {"intent": "image", "mode": "generate"}, route
    contract = build_mode_contract({"type": "image_render"}, has_image=False)
    assert contract["mode"] == MODE_TEXT_TO_IMAGE and contract["render"], contract
    ok("A6 text generation -> TEXT_TO_IMAGE, render=true")

    # A7: the word تصویر alone no longer promotes a question to generation.
    route = intent_router.route("این تصویر چه فضای معماری را نشان می‌دهد؟")
    assert route == {"intent": "chat", "mode": "conversation"}, route
    contract = build_mode_contract({"type": "chat"}, has_image=False)
    assert contract["mode"] == MODE_CHAT and not contract["render"], contract
    ok("A7 text-only visual question -> CHAT, render=false")

    # A8: an attachment without instructions is an upload, not an edit.
    intent = classify_image_intent("")
    assert intent["intent"] == INTENT_UPLOAD_ONLY, intent
    contract = attached_contract(intent["intent"], "image_upload")
    assert contract["mode"] == MODE_IMAGE_UPLOAD and not contract["render"], contract
    ok("A8 attachment only -> IMAGE_UPLOAD, render=false")

    # A10: established valid img2img phrasing keeps edit precedence.
    intent = classify_image_intent("همین رندر رو شب کن")
    assert intent["intent"] == INTENT_EDIT, intent
    ok("A10 existing img2img wording remains IMAGE_EDIT")

    contract = attached_contract(INTENT_EDIT, "image_render")
    assert set(("mode", "intent", "input", "output", "render")) <= set(contract), contract
    assert contract["contract"] == "ImageModeRoutingV1", contract
    ok("routing contract exposes mode/intent/input/output/render")

    ui_path = os.path.join(ROOT, "ui", "static", "app.js")
    with open(ui_path, encoding="utf-8") as handle:
        ui_source = handle.read()
    assert 'operation: file ? "Image-to-Image" : "Text-to-Image"' not in ui_source
    assert "payload.routing" in ui_source and "routing.mode" in ui_source
    ok("UI consumes backend routing contract, not attachment label")

    print("RESULT: IMAGE_MODE_ROUTING_CONTRACT_PASS (%d checks)" % len(PASS))


if __name__ == "__main__":
    main()
