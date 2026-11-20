# ==========================================================
# ArchitectOS IMAGE_TO_IMAGE_05 — OFFLINE PROMPT PIPELINE DIAGNOSTIC
#
# Reproduces, WITHOUT any render, the exact prompt composition the
# img2img edit path performs for a set of user edits:
#
#   user text
#     -> edit delta compiler        (IMAGE_TO_IMAGE_05)
#     -> terminology extraction     (CHAT_LANGUAGE_02)
#     -> compiled render prompt
#     -> resolve_render_prompt      (compiled authoritative + builder tail)
#     -> final prompt that would reach Comfy node 206
#
# Usage:
#   python tools/diag_05_prompt_pipeline.py
# ==========================================================


import os
import sys


ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


from core.cognition.architectural_terminology_v1 import (
    normalize_architectural_terms,
    augment_compiled_prompt,
)

from core.prompt_intelligence.image_edit_delta_v1 import (
    compile_edit_delta,
    is_classified,
)

from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)

from core.prompt_intelligence.image_edit_prompt_builder import (
    ImageEditPromptBuilder,
)


CASES = (
    "همینو شب کن",
    "همینو روز کن",
    "رندر قبلی رو سنگ روشن کن",
)


# A representative architectural intent for an existing exterior edit.
INTENT = {
    "request_type": "facade_material_edit",
    "building_type": "existing building",
    "style": "traditional",
    "materials": ["wood"],
    "preserve_geometry": True,
    "mode": "img2img",
    "camera": "same as original image",
    "normalized_prompt": "",
}


def main():

    builder = ImageEditPromptBuilder()

    for text in CASES:

        print("=" * 74)
        print("  EDIT:", text)
        print("=" * 74)

        delta = compile_edit_delta(text)

        print("  edit_class         :", delta["edit_class"])
        print("  material           :", delta["material"],
              "| tone", delta["material_tone"])
        print("  time_of_day        :", delta["time_of_day"])
        print("  conflict_terms     :", delta["conflict_terms"])

        terminology = normalize_architectural_terms(text)

        print("  terminology terms  :", terminology["canonical_terms"])

        if is_classified(delta):

            compiled = delta["prompt"]

            conflict = tuple(delta["conflict_terms"])

            print("  compiled source    : edit_delta (authoritative)")

        else:

            compiled = augment_compiled_prompt(
                "", terminology
            )

            conflict = ()

            print("  compiled source    : terminology fallback")

        intent = dict(INTENT)

        intent["normalized_prompt"] = text

        builder_prompt = builder.build(intent)

        resolution = resolve_render_prompt(
            compiled_prompt=compiled,
            builder_prompt=builder_prompt,
            user_text=text,
            preset_tail="",
            preset_name=None,
            conflict_terms=conflict,
            reinforcement="",
        )

        final = resolution.get("final_prompt") or ""

        low = final.lower()

        print("  prompt source      :", resolution.get("source"))
        print("  removed conflicts  :",
              resolution.get("removed_conflicting_tail_terms"))
        print("  FINAL PROMPT LEN   :", len(final))
        print("  contains night     :", "night" in low)
        print("  contains 'natural lighting':", "natural lighting" in low)
        print("  contains 'light natural stone':",
              "light natural stone" in low)
        print("  contains 'material with wood':", "material with wood" in low)
        print("  DELTA SECTION      :", final[:300])
        print()

    return 0


if __name__ == "__main__":

    sys.exit(main())
