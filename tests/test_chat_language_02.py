# ==========================================================
# ArchitectOS CHAT_LANGUAGE_02 — Contract Tests
#
# A. Persian normal chat
# B. English normal chat
# C. mixed Persian / English chat
# D. Persian architectural render request
# E. English architectural render request
# F. architectural terminology preservation
# G. two independent sessions (no context leakage)
# H. response-language mismatch correction
# I. render handoff: compiled English prompt reaches RenderRuntime
# J. RUNTIME_FOUNDATION_01 regression
#
# NO REAL IMAGE GENERATION IS PERFORMED.
# ==========================================================


import importlib.util
import os
import sys
import types


ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if ROOT not in sys.path:

    sys.path.insert(
        0,
        ROOT
    )


from core.cognition.persian_normalizer import persian_normalizer

from core.cognition.architectural_terminology_v1 import (
    normalize_architectural_terms,
    augment_compiled_prompt,
)

from core.prompt_intelligence.persian_architectural_understanding import (
    persian_architectural_understanding,
)

from core.prompt_intelligence.architectural_prompt_compiler_v1 import (
    architectural_prompt_compiler,
)

from core.prompt_intelligence.render_prompt_resolver_v1 import (
    resolve_render_prompt,
)

from core.chat.response_guard import ResponseGuard

from core.chat.session_registry_v1 import (
    session_registry,
    DEFAULT_SESSION_KEY,
)

from core.chat.chat_architect import ChatArchitect

from core.render.render_runtime import RenderRuntime

from core.render.comfy_http_runtime import ComfyHTTPRuntime



PASS = []



def ok(label):

    PASS.append(label)

    print("  [ OK ] " + label)



def has_persian(text):

    return any(
        "\u0600" <= ch <= "\u06FF"
        for ch in str(text or "")
    )



# ==========================================================
# CANONICAL LANGUAGE PATH HELPER
#
# Mirrors the exact sequence ChatArchitect.handle() performs:
#   normalize -> interpret -> compile -> terminology augment
# ==========================================================

def canonical_language_path(text):

    request = persian_normalizer.normalize(
        text
    )

    understanding = persian_architectural_understanding.interpret(
        request
    )

    compiled = architectural_prompt_compiler.compile(
        understanding
    )

    terminology = normalize_architectural_terms(
        request["normalized_text"]
    )

    compiled_render_prompt = augment_compiled_prompt(
        (compiled or {}).get("positive_prompt", ""),
        terminology
    )

    return {

        "original": request["raw_text"],
        "normalized": request["normalized_text"],
        "detected_language": request["detected_language"],
        "understanding": understanding,
        "compiled": compiled,
        "terminology": terminology,
        "compiled_render_prompt": compiled_render_prompt,

    }



# ==========================================================
# FAKE LLM (deterministic, no provider call)
# ==========================================================

class FakeLLM:

    def __init__(self, reply="ok", correction=None, raise_on_correct=False):

        self.reply = reply
        self.correction = correction
        self.raise_on_correct = raise_on_correct
        self.calls = []


    def generate(self, user, use_context=False):

        self.calls.append(user)

        if "REPLY TO REWRITE" in str(user):

            if self.raise_on_correct:

                raise RuntimeError("corrector boom")

            return self.correction

        return self.reply



# ==========================================================
# SHARED CHAT ARCHITECT (built once)
# ==========================================================

_CHAT = None


def chat_architect():

    global _CHAT

    if _CHAT is None:

        _CHAT = ChatArchitect(
            types.SimpleNamespace()
        )

    return _CHAT



# ==========================================================
# A / B / C — NORMAL CHAT IN EACH LANGUAGE
# ==========================================================

def _run_chat(text, session_id, fake_reply):

    chat = chat_architect()

    original_llm = chat.llm

    chat.llm = FakeLLM(reply=fake_reply)

    try:

        return chat.handle(
            text,
            context={"session_id": session_id}
        )

    finally:

        chat.llm = original_llm



def test_persian_normal_chat():

    print("\n[A] Persian normal chat")

    result = _run_chat(
        "سلام، حالت چطوره؟",
        "test_A",
        "سلام! من آماده‌ام به شما در طراحی معماری کمک کنم."
    )

    assert result.get("type") == "chat", result.get("type")

    trace = result.get("render_handoff") or {}

    assert trace.get("detected_language") == "fa", trace.get("detected_language")

    # original user request must survive untouched
    assert trace.get("original_user_prompt") == "سلام، حالت چطوره؟"

    assert result["language"]["input_language"] == "persian"

    assert result["language"]["output_language"] == "persian"

    ok("Persian chat: language fa, original text preserved, no mismatch")


def test_english_normal_chat():

    print("\n[B] English normal chat")

    result = _run_chat(
        "hello, how are you?",
        "test_B",
        "Hello! I am ready to help with your architectural design."
    )

    assert result.get("type") == "chat", result.get("type")

    trace = result.get("render_handoff") or {}

    assert trace.get("detected_language") == "en", trace.get("detected_language")

    assert trace.get("original_user_prompt") == "hello, how are you?"

    assert result["language"]["input_language"] == "english"

    assert result["language"]["output_language"] == "english"

    ok("English chat: language en, original text preserved, no mismatch")


def test_mixed_chat():

    print("\n[C] Mixed Persian / English chat")

    mixed = "سلام، این villa رو ببین"

    result = _run_chat(
        mixed,
        "test_C",
        "سلام! ویلا را دیدم، بگویید چه تغییری لازم است."
    )

    assert result.get("type") == "chat", result.get("type")

    trace = result.get("render_handoff") or {}

    assert trace.get("detected_language") == "mixed", trace.get("detected_language")

    assert trace.get("original_user_prompt") == mixed

    # mixed input keeps a sensible conversational language (no forced switch)
    assert result["language"]["guard_status"] == "validated", result["language"]

    ok("Mixed chat: language mixed, sensible language preserved")


# ==========================================================
# D / E — ARCHITECTURAL RENDER REQUESTS
# ==========================================================

def test_persian_render_request():

    print("\n[D] Persian architectural render request")

    result = canonical_language_path(
        "یک رندر واقع گرایانه از نمای جنوبی ویلا با متریال شیشه و نور غروب بساز"
    )

    assert result["detected_language"] == "fa"

    assert result["compiled"].get("status") == "COMPILED"

    compiled = result["compiled_render_prompt"]

    assert compiled, "no compiled render prompt produced"

    assert not has_persian(compiled), (
        "compiled render prompt still contains Persian: " + compiled
    )

    assert "glass" in compiled.lower()

    ok("Persian render request -> deterministic English compiled prompt")


def test_english_render_request():

    print("\n[E] English architectural render request")

    result = canonical_language_path(
        "render a realistic south facade of a villa with glass material at sunset"
    )

    assert result["detected_language"] == "en"

    compiled = result["compiled_render_prompt"]

    assert compiled

    assert not has_persian(compiled)

    ok("English render request -> English compiled prompt")


# ==========================================================
# F — ARCHITECTURAL TERMINOLOGY PRESERVATION
# ==========================================================

REQUIRED_FAMILIES = {

    "facade": ("نمای جنوبی", "south facade"),

    "material": ("متریال شیشه", "glass"),

    "light": ("نور غروب", "sunset lighting"),

    "style": ("سبک مدرن", "modern style"),

    "camera": ("زاویه دوربین پایین", "camera angle"),

    "space": ("فضای داخلی", "interior space"),

}


def test_terminology_preservation():

    print("\n[F] Architectural terminology preservation")

    for family, (persian_text, expected_en) in REQUIRED_FAMILIES.items():

        terminology = normalize_architectural_terms(
            persian_text
        )

        assert family in terminology["families"], (
            family + " not detected in " + persian_text
        )

        prompt = augment_compiled_prompt(
            "",
            terminology
        )

        assert expected_en in prompt, (
            expected_en + " missing for " + persian_text + " -> " + prompt
        )

        print(
            "     "
            + family.ljust(9)
            + persian_text.ljust(22)
            + "-> "
            + prompt
        )

    ok(
        str(len(REQUIRED_FAMILIES))
        + " required terminology families preserved"
    )


def test_terminology_does_not_invent():

    print("\n[F2] Terminology layer does not invent concepts")

    terminology = normalize_architectural_terms(
        "سلام، حالت چطوره؟"
    )

    assert terminology["families"] == [], terminology["families"]

    assert augment_compiled_prompt("", terminology) == ""

    ok("non-architectural text produces no terminology prompt")


# ==========================================================
# G — SESSION ISOLATION
# ==========================================================

def test_session_isolation():

    print("\n[G] Two independent sessions - no context leakage")

    chat = chat_architect()

    bundle_a = session_registry.begin("client_A")

    chat.state.update({"last_prompt": "PROMPT_FROM_A"})

    assert chat.state.get().get("last_prompt") == "PROMPT_FROM_A"

    context_a = chat._architectural_context_store()

    context_a.apply_turn(
        understanding={"scope": "facade", "contract": "test"},
        raw_text="A",
        normalized_text="A"
    )

    bundle_b = session_registry.begin("client_B")

    assert chat.state.get().get("last_prompt") is None, (
        "session B saw session A conversation state"
    )

    context_b = chat._architectural_context_store()

    assert context_b.get() == {}, (
        "session B saw session A architectural context"
    )

    assert context_a is not context_b

    assert bundle_a["conversation_state"] is not bundle_b["conversation_state"]

    # image handler must follow the same session
    assert chat.image_handler.state is chat.state

    # returning to A restores A's state, still isolated
    session_registry.begin("client_A")

    assert chat.state.get().get("last_prompt") == "PROMPT_FROM_A"

    assert chat._architectural_context_store().get() != {}

    ok("independent sessions isolated (state + architectural context)")

    session_registry.end()


def test_default_session_backward_compatible():

    print("\n[G2] No session id -> legacy global state (unchanged)")

    bundle = session_registry.begin(None)

    assert bundle["session_id"] == DEFAULT_SESSION_KEY

    assert bundle["isolated"] is False

    from core.chat.conversation_state import conversation_state

    assert bundle["conversation_state"] is conversation_state

    ok("default session still resolves to the legacy global singleton")

    session_registry.end()


# ==========================================================
# H — RESPONSE LANGUAGE MISMATCH CORRECTION
# ==========================================================

def test_guard_corrects_mismatch():

    print("\n[H] Response-language mismatch correction (bounded)")

    guard = ResponseGuard()

    persian_user = "سلام، حالت چطوره؟"

    english_reply = "Hello! I am fine and ready to help."

    persian_reply = "سلام! خوبم و آماده کمک هستم."

    # ---- mismatch detected ----
    check = guard.validate(persian_user, english_reply)

    assert check["valid"] is False

    # ---- one bounded correction succeeds ----
    result = guard.correct(
        persian_user,
        english_reply,
        corrector=lambda u, r, c: persian_reply
    )

    assert result["corrected"] is True, result

    assert result["status"] == "corrected"

    assert result["response"] == persian_reply

    ok("mismatch corrected by ONE bounded correction call")

    # ---- corrector fails -> deterministic fallback, original kept ----
    failed = guard.correct(
        persian_user,
        english_reply,
        corrector=lambda u, r, c: None
    )

    assert failed["corrected"] is False

    assert failed["status"] == "language_mismatch_uncorrected"

    assert failed["response"] == english_reply

    ok("failed correction falls back without retry, original preserved")

    # ---- corrector raises -> no crash, no retry ----
    raised = guard.correct(
        persian_user,
        english_reply,
        corrector=lambda u, r, c: (_ for _ in ()).throw(RuntimeError("x"))
    )

    assert raised["status"] == "language_mismatch_uncorrected"

    assert raised["fallback"] == "corrector_error"

    ok("corrector exception handled without retry loop")

    # ---- no corrector at all ----
    none_result = guard.correct(persian_user, english_reply)

    assert none_result["status"] == "language_mismatch_uncorrected"

    ok("no corrector -> truthful uncorrected status")


def test_guard_correction_single_attempt():

    print("\n[H2] Correction is a single attempt (no retry loop)")

    guard = ResponseGuard()

    calls = []


    def counting_corrector(user, response, check):

        calls.append(1)

        return "Still English, no good."


    result = guard.correct(
        "سلام",
        "Hello there.",
        corrector=counting_corrector
    )

    assert len(calls) == 1, "correction was retried: " + str(len(calls))

    assert result["corrected"] is False

    assert result["status"] == "language_mismatch_uncorrected"

    ok("exactly one correction attempt, never retried")


def test_chat_path_uses_bounded_correction():

    print("\n[H3] Canonical chat path applies bounded correction")

    chat = chat_architect()

    original_llm = chat.llm

    chat.llm = FakeLLM(
        reply="Hello! I am fine.",
        correction="سلام! خوبم."
    )

    try:

        correction = chat._canonical_chat_reply(
            "prompt",
            "سلام، حالت چطوره؟"
        )

    finally:

        chat.llm = original_llm


    assert correction["corrected"] is True, correction

    assert correction["response"] == "سلام! خوبم."

    ok("chat path corrected a Persian request answered in English")


# ==========================================================
# I — RENDER HANDOFF
# ==========================================================

def test_compiled_prompt_reaches_render_runtime():

    print("\n[I] Compiled English prompt reaches RenderRuntime")

    language = canonical_language_path(
        "یک رندر واقع گرایانه از نمای جنوبی ویلا با متریال شیشه و نور غروب بساز"
    )

    compiled = language["compiled_render_prompt"]

    assert compiled

    runtime = RenderRuntime()

    # dead endpoint: NO real generation is possible
    dead = ComfyHTTPRuntime(endpoint="http://127.0.0.1:9")

    runtime.executor.comfy = dead

    runtime.result_bridge.comfy = dead

    builder_prompt = (
        "modern villa architectural visualization, "
        "architectural photography, 35mm lens, 8k ultra realistic"
    )

    runtime.render(
        "chat_language_02_test",
        {
            "prompt": builder_prompt,
            "original_prompt": language["original"],
            "compiled_render_prompt": compiled,
            "architectural_intent": {"building_type": "villa"},
            "mode": "text2img",
        },
        "flux",
        None
    )

    received = runtime.last_render_request

    # 1. the compiled prompt is what the runtime actually received
    assert received["compiled_render_prompt"] == compiled, (
        "compiled prompt did not reach RenderRuntime"
    )

    # 2. it was CONSUMED (not merely present)
    assert received["compiled_consumed"] is True, received

    assert received["prompt_source"] == "compiled_authoritative", received

    # 3. the final prompt used is the compiled one (authoritative content)
    final_prompt = received["resolved_prompt"]

    assert compiled in final_prompt, final_prompt

    assert not has_persian(final_prompt)

    # 4. existing quality presets were preserved, not dropped
    assert "8k ultra realistic" in final_prompt, final_prompt

    ok("compiled English prompt consumed by RenderRuntime (authoritative)")

    ok("builder quality preset tail preserved")

    return runtime, language


def test_resolver_rules():

    print("\n[I2] Resolver determinism + backward compatibility")

    # no compiled prompt -> previous behaviour byte for byte
    only_builder = resolve_render_prompt(
        compiled_prompt=None,
        builder_prompt="builder only prompt"
    )

    assert only_builder["prompt"] == "builder only prompt"

    assert only_builder["source"] == "builder_only"

    assert only_builder["compiled_consumed"] is False

    # compiled only
    only_compiled = resolve_render_prompt(
        compiled_prompt="compiled english prompt",
        builder_prompt=""
    )

    assert only_compiled["prompt"] == "compiled english prompt"

    assert only_compiled["source"] == "compiled_only"

    # dedupe: builder segment already in compiled is not repeated
    merged = resolve_render_prompt(
        compiled_prompt="photorealistic render, south facade",
        builder_prompt="photorealistic render, 35mm lens"
    )

    assert merged["prompt"].count("photorealistic render") == 1, merged["prompt"]

    assert "35mm lens" in merged["prompt"]

    ok("resolver: no compiled -> unchanged; compiled -> authoritative + deduped tail")


def test_render_request_plumbing():

    print("\n[I3] handle() passes the compiled prompt into the render handler")

    chat = chat_architect()

    recorded = {}

    original = chat.image_handler.handle_image_generate


    def recorder(text, **kwargs):

        recorded["text"] = text

        recorded["compiled_render_prompt"] = kwargs.get("compiled_render_prompt")

        recorded["architectural_intent"] = kwargs.get("architectural_intent")

        return {"type": "image", "status": "recorded_no_render"}


    chat.image_handler.handle_image_generate = recorder

    try:

        result = chat.handle(
            "یک رندر واقع گرایانه از نمای جنوبی ویلا با متریال شیشه بساز",
            context={"session_id": "test_I3"}
        )

    finally:

        chat.image_handler.handle_image_generate = original


    assert recorded.get("text"), "render handler not reached"

    compiled = recorded.get("compiled_render_prompt")

    assert compiled, "compiled_render_prompt was not passed to the render handler"

    assert not has_persian(compiled), compiled

    trace = result.get("render_handoff") or {}

    assert trace.get("original_user_prompt") == (
        "یک رندر واقع گرایانه از نمای جنوبی ویلا با متریال شیشه بساز"
    )

    assert trace.get("compiled_render_prompt") == compiled

    assert trace.get("compiled_prompt_source") != "none"

    ok("handle() -> image handler carries the compiled English prompt")

    ok("render handoff trace records original + normalized + compiled")


# ==========================================================
# J — RUNTIME_FOUNDATION_01 REGRESSION
# ==========================================================

def test_runtime_foundation_01_regression():

    print("\n[J] RUNTIME_FOUNDATION_01 regression")

    path = os.path.join(
        ROOT,
        "tests",
        "test_runtime_foundation_01.py"
    )

    spec = importlib.util.spec_from_file_location(
        "runtime_foundation_01",
        path
    )

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    code = module.run_all()

    assert code == 0, "RUNTIME_FOUNDATION_01 regression failed"

    ok("RUNTIME_FOUNDATION_01 suite still passes")


# ==========================================================
# EXAMPLE TRACE
# ==========================================================

def print_example_trace():

    print("\n" + "=" * 62)
    print("  EXAMPLE TRACE — PERSIAN RENDER REQUEST")
    print("=" * 62)

    language = canonical_language_path(
        "یک رندر واقع گرایانه از نمای جنوبی ویلا با متریال شیشه و نور غروب بساز"
    )

    runtime = RenderRuntime()

    dead = ComfyHTTPRuntime(endpoint="http://127.0.0.1:9")

    runtime.executor.comfy = dead

    runtime.result_bridge.comfy = dead

    runtime.render(
        "trace_demo",
        {
            "prompt": "modern villa architectural visualization, 35mm lens, 8k ultra realistic",
            "original_prompt": language["original"],
            "compiled_render_prompt": language["compiled_render_prompt"],
            "architectural_intent": {"building_type": "villa"},
            "mode": "text2img",
        },
        "flux",
        None
    )

    received = runtime.last_render_request

    print("\n  ORIGINAL")
    print("   ", language["original"])

    print("\n  NORMALIZED")
    print("   ", language["normalized"])

    print("\n  COMPILED_ENGLISH")
    print("   ", language["compiled_render_prompt"])

    print("\n  RENDER_RUNTIME_RECEIVED (payload prompt)")
    print("   ", received["received_prompt"])

    print("\n  RENDER_RUNTIME_FINAL_PROMPT (used)")
    print("   ", received["resolved_prompt"])

    print("\n  PROMPT SOURCE:", received["prompt_source"])

    print("=" * 62)



# ==========================================================
# RUNNER
# ==========================================================

def run_all():

    print("=" * 62)
    print("  ARCHITECTOS CHAT_LANGUAGE_02 — TESTS")
    print("=" * 62)

    test_persian_normal_chat()

    test_english_normal_chat()

    test_mixed_chat()

    test_persian_render_request()

    test_english_render_request()

    test_terminology_preservation()

    test_terminology_does_not_invent()

    test_session_isolation()

    test_default_session_backward_compatible()

    test_guard_corrects_mismatch()

    test_guard_correction_single_attempt()

    test_chat_path_uses_bounded_correction()

    test_compiled_prompt_reaches_render_runtime()

    test_resolver_rules()

    test_render_request_plumbing()

    test_runtime_foundation_01_regression()

    print_example_trace()

    print("\n" + "=" * 62)
    print("  " + str(len(PASS)) + " CHECKS PASSED")
    print("  RESULT: CHAT_LANGUAGE_02_TESTS_PASS")
    print("=" * 62)

    return 0



if __name__ == "__main__":

    sys.exit(
        run_all()
    )
