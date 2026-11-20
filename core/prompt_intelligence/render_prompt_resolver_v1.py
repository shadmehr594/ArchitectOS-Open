# ==========================================================
# ArchitectOS Render Prompt Resolver v1
#
# CHAT_LANGUAGE_02
#
# Single deterministic decision point that answers:
#   "what exact prompt string does the render path send?"
#
# Problem it fixes
#   The compiled architectural English prompt (2D-3) was produced,
#   stored in session context, and then IGNORED: RenderRuntime's
#   internal PromptBuilder rebuilds the final prompt purely from
#   architectural_intent and discards any incoming prompt string.
#   Result: "compiled prompt exists only in context".
#
# Resolution rule
#   compiled architectural prompt = AUTHORITATIVE for content
#   builder prompt                = PRESERVED as quality/style tail
#
#   The builder tail (lens, lighting rig, "8k ultra realistic", ...)
#   is an existing render preset and must not be dropped, so it is
#   appended deterministically with de-duplication.
#
# Fully deterministic. No provider calls.
# ==========================================================


CONTRACT = "RenderPromptResolutionV1"
VERSION = "1.0"



def _as_text(value):
    """Normalize a prompt-ish value into a clean single-line string."""

    if value is None:

        return ""

    if isinstance(value, dict):

        for key in (
            "positive_prompt",
            "description",
            "prompt",
        ):

            candidate = value.get(key)

            if candidate:

                return _as_text(candidate)

        return ""

    if isinstance(value, (list, tuple)):

        return ", ".join(
            part
            for part in (
                _as_text(item) for item in value
            )
            if part
        )

    return " ".join(
        str(value).split()
    )



def _segments(text):
    """Split a prompt into ordered, de-duplicated, trimmed segments."""

    parts = []

    for chunk in str(text or "").replace("\n", ",").split(","):

        cleaned = chunk.strip().strip(".").strip()

        if not cleaned:

            continue

        if cleaned.lower() in [
            p.lower() for p in parts
        ]:

            continue

        parts.append(cleaned)

    return parts



def _split_segments(text):
    """Split a prompt into ordered, de-duplicated, trimmed segments."""

    parts = []

    for chunk in str(text or "").replace("\n", ",").split(","):

        cleaned = chunk.strip().strip(".").strip()

        if not cleaned:

            continue

        if cleaned.lower() in [
            p.lower() for p in parts
        ]:

            continue

        parts.append(cleaned)

    return parts



# Backwards-compatible alias (previous private name).
_segments = _split_segments



def filter_tail_segments(text, conflict_terms):
    """Remove only conflicting generic filler segments.

    TEXT_TO_IMAGE_COMFY_03B
    Applied to the GENERIC builder tail only - never to the compiled
    architectural prompt and never to the preset's own tail.

    Returns (kept_segments, removed_records).
    """

    kept = []

    removed = []

    terms = [
        str(term).lower()
        for term in (conflict_terms or ())
        if str(term).strip()
    ]


    for segment in _split_segments(text):

        lowered = segment.lower()

        matched = None

        for term in terms:

            if term in lowered:

                matched = term

                break


        if matched:

            removed.append({
                "segment": segment,
                "matched": matched,
            })

            continue

        kept.append(segment)


    return kept, removed


# ==========================================================
# RENDER_INSTRUCTION_HANDOFF_V1 — bounded constraint block
# ==========================================================

def _instruction_sentences(text):
    """Whole sentences only; the boundary is ". " and nothing else."""

    parts = []

    for chunk in str(text or "").strip().split(". "):

        chunk = chunk.strip()

        if not chunk:
            continue

        if not chunk.endswith("."):
            chunk += "."

        parts.append(chunk)

    return parts


def _instruction_block(instruction, compiled, max_chars):
    """(block, truncated) — de-duplicated against the compiled prompt.

    A sentence that already exists in the compiled content is dropped, so the
    same constraint is never stated twice. The block is capped at
    `max_chars` on a SENTENCE boundary: a constraint is never cut in half.
    """

    if not isinstance(instruction, dict):

        return "", False

    raw = (
        _as_text(instruction.get("constraint_block"))
        or _as_text(instruction.get("english_instruction"))
    )

    if not raw:

        return "", False

    compiled_lower = (compiled or "").lower()

    kept, total, truncated = [], 0, False

    for sentence in _instruction_sentences(raw):

        if sentence.lower() in compiled_lower:

            continue

        addition = len(sentence) + (1 if kept else 0)

        if total + addition > max_chars:

            truncated = True

            break

        kept.append(sentence)

        total += addition

    return " ".join(kept), truncated


def resolve_render_prompt(
    compiled_prompt=None,
    builder_prompt=None,
    user_text="",
    preset_tail=None,
    preset_name=None,
    conflict_terms=None,
    reinforcement=None,
    architectural_instruction=None,
    # LIVE_HANDOFF_V1 — `build_constraint_block` already bounds the block to
    # CONSTRAINT_BLOCK_BUDGET. This second, independent 1100-char cap then
    # re-truncated the SAME block, so the dual-image semantic role block
    # (1093 chars) consumed the whole allowance and the grounded
    # "Preserve the TARGET BUILDING … exactly as observed" sentence — the only
    # carrier of what vision actually measured — was cut off after the block
    # had already been correctly assembled. The two budgets are now aligned.
    max_instruction_chars=2400,
):
    """Resolve the exact prompt string the render path will use.

    Composition order (deterministic, de-duplicated):

        compiled architectural content   <- AUTHORITATIVE, never filtered
        + preset quality tail            <- preset intent, never filtered
        + preset reinforcement           <- camera/lighting framing
        + generic builder tail           <- filtered against the preset

    A preset makes its own intent authoritative by removing ONLY the
    conflicting generic filler segments. User-requested architectural
    content lives in `compiled_prompt` and is never touched.

    Returns a deterministic contract dict including the required trace:
      preset / removed_conflicting_tail_terms / retained_builder_tail /
      final_prompt
    """

    compiled = _as_text(compiled_prompt)

    builder = _as_text(builder_prompt)

    preset = _as_text(preset_tail)

    reinforce = _as_text(reinforcement)


    # ------------------------------------------------------
    # PRESET-AWARE FILTERING OF THE GENERIC TAIL ONLY
    # ------------------------------------------------------

    builder_kept, builder_removed = filter_tail_segments(
        builder,
        conflict_terms
    )


    # ------------------------------------------------------
    # BUILD THE TAIL IN PRIORITY ORDER
    # ------------------------------------------------------

    tail = []

    tail_lower = set()


    for source in (preset, reinforce, ", ".join(builder_kept)):

        for segment in _split_segments(source):

            low = segment.lower()

            if low in tail_lower:

                continue

            if compiled and low in compiled.lower():

                continue

            tail_lower.add(low)

            tail.append(segment)


    # ======================================================
    # RENDER_INSTRUCTION_HANDOFF_V1
    #
    # The A/B constraint block (geometry shape, target preservation,
    # temporary-object rules, explicit user constraints) belongs BETWEEN the
    # compiled architectural content and the quality tail:
    #
    #   * after compiled, because compiled is the user's own intent and must
    #     never be displaced by a derived constraint;
    #   * before the tail, because the FLUX T5 encoder budget is finite and
    #     truncation must eat the boilerplate tail, never a constraint.
    #
    # When no instruction is supplied this block is a no-op and the prompt is
    # byte-identical to the previous behaviour.
    # ======================================================

    instruction_block, instruction_truncated = _instruction_block(
        architectural_instruction,
        compiled,
        max_instruction_chars,
    )

    tail_text = ", ".join(tail)

    if instruction_block:

        if compiled:

            prompt = compiled.rstrip().rstrip(".") + ". " + instruction_block

        else:

            prompt = instruction_block

        if tail_text:

            prompt = prompt + ", " + tail_text

    elif compiled:

        prompt = compiled + (", " + tail_text if tail_text else "")

    else:

        prompt = tail_text


    if compiled:

        source_label = (
            "compiled_authoritative"
            if tail
            else "compiled_only"
        )

    elif preset:

        source_label = "preset_only"

    else:

        source_label = "builder_only"


    return {

        "contract": CONTRACT,
        "version": VERSION,

        # ---- required trace (TEXT_TO_IMAGE_COMFY_03B) ----
        "preset": preset_name,

        "removed_conflicting_tail_terms": [
            record["matched"] for record in builder_removed
        ],

        "removed_conflicting_tail_segments": builder_removed,

        "retained_builder_tail": builder_kept,

        "final_prompt": prompt,

        # ---- composition detail ----
        "prompt": prompt,

        "compiled_prompt": compiled,
        "preset_tail": preset,
        "preset_reinforcement": reinforce,
        "builder_prompt": builder,

        "source": source_label,

        "compiled_consumed": bool(compiled),

        "preserved_tail_segments": tail,

        "tail_filtered": bool(builder_removed),

        # ---- RENDER_INSTRUCTION_HANDOFF_V1 ----
        # The block that was actually placed in the prompt, its size, and
        # whether the budget cut it. Logged so the effective prompt can be
        # audited without re-deriving it.
        "instruction_block": instruction_block,
        "instruction_chars": len(instruction_block),
        "instruction_truncated": instruction_truncated,
        "instruction_applied": bool(instruction_block),

    }
