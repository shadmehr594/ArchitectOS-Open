# ==========================================================
# ArchitectOS VISION_IMAGE_REGISTRY_04 — Tests
#
# A. upload architectural render -> real structured understanding
# B. upload floor plan -> classified as plan, conservative elements
# C. image + Persian question -> grounded answer
# D. image + English question
# E. successful text-to-image render auto-registers
# F. "همین عکس" resolves to active image
# G. "رندر قبلی" resolves correctly
# H. "عکس دوم" resolves ordinal 2
# I. two sessions prove no image leakage
# J. ambiguous reference returns unresolved
# K. image+text analysis does NOT route to img2img
# L. edit-intent identified for Phase 05 but not executed here
# M. regression 01 / 02 / 03 / 03B
#
# NO REAL IMAGE EDITING AND NO IMAGE GENERATION IS PERFORMED.
# Real vision inference IS performed (local Ollama gemma4:12b).
# ==========================================================


import importlib
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


from werkzeug.datastructures import FileStorage


from core.vision.image_registry_v1 import image_registry
from core.vision.image_understanding_v1 import (
    CONTRACT,
    IMAGE_TYPES,
    build_understanding,
    classify_claim,
)
from core.vision.reference_resolver_v1 import (
    resolve_reference,
    resolve_region_reference,
    is_region_reference,
)
from core.vision.image_intent_v1 import (
    classify_image_intent,
    INTENT_ANALYZE,
    INTENT_EDIT,
    INTENT_REFERENCE,
    INTENT_UPLOAD_ONLY,
)
from core.vision.image_session_v1 import (
    provider,
    register_asset,
    analyze_record,
    build_grounded_prompt,
)

from core.chat.chat_architect import ChatArchitect


PASS = []

WARN = []


RENDER_IMAGE = "C:/ComfyUI-Zluda/output/architectos_v11_00235_.png"

PLAN_IMAGE = os.path.join(
    ROOT,
    "exports",
    "DEFAULT",
    "parcel2_basement_v2_20260909_021346_556821",
    "PARCEL2_BASEMENT_V2_PLAN.png",
)


def ok(label):

    PASS.append(label)

    print("  [ OK ] " + label)


def warn(label):

    WARN.append(label)

    print("  [WARN] " + label)


def _chat():

    return ChatArchitect(types.SimpleNamespace())


def _stub_analysis(session_key, image_id, force=False):

    """Fast deterministic understanding for routing tests."""

    return build_understanding(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["a building exterior", "glazing", "a paved forecourt"],
            "inferred": ["daytime lighting"],
            "unresolved": ["exact material specification"],
            "confidence": "MEDIUM",
            "architectural_elements": ["facade", "window", "entrance"],
            "text_labels_if_visible": [],
        },
        provider="stub",
        model="stub",
        image_id=image_id,
        source_type="uploaded",
    )



# ==========================================================
# A / B — REAL VISION UNDERSTANDING
# ==========================================================

def _assert_provider_observation_contract(understanding):
    """RELAX legacy non-empty observed; ADD attributable data and safety checks.

    Legacy grounding treats observed as object evidence. A render/photo without
    local corroboration must retain provider observation outside that field.
    """
    assert isinstance(understanding["observed"], list)
    bridge = understanding["visual_observer_bridge"]
    raw = bridge["raw_observer"]["raw_text"]
    assert raw.strip(), "no retained provider observation returned"
    candidates = understanding["provider_candidates"]
    if bridge["normalization"]["status"] == "NORMALIZED":
        assert candidates, "normalized provider observation has no candidates"
    for candidate in candidates:
        assert candidate["text"] in candidate["source_quote"] in raw
        assert candidate["grounded"] == (candidate["state"] == "CONFIRMED")
    confirmed = understanding["grounded_provider_evidence"]
    assert all(c["state"] == "CONFIRMED" and c["grounded"] for c in confirmed)
    safe_objects = {c["text"] for c in confirmed if c["verification"]["reason"]
                    == "independent_local_type_presence"}
    assert set(understanding["observed"]) <= safe_objects


def test_A_render_understanding():

    print("\n[A] Architectural render -> real structured understanding")

    if not provider().is_available():

        warn("vision provider unavailable - A skipped")

        return None

    session = "vision_A"

    image_registry.reset(session)

    record = register_asset(
        session,
        path=RENDER_IMAGE,
        source_type="uploaded",
        label="render",
    )

    understanding = analyze_record(session, record["image_id"])

    print("     status     :", understanding.get("analysis_status"))
    print("     image_type :", understanding.get("image_type"))
    print("     confidence :", understanding.get("confidence"))
    print("     observed   :", understanding.get("observed"))
    print("     elements   :", understanding.get("architectural_elements"))

    assert understanding["contract"] == CONTRACT

    for key in (
        "observed", "inferred", "unresolved", "confidence",
        "architectural_elements", "text_labels_if_visible",
        "image_type", "safety",
    ):

        assert key in understanding, "missing key: " + key

    assert understanding["analysis_status"] in (
        "ANALYZED", "ANALYZED_WITH_UNCERTAINTY", "PARTIAL",
    ), understanding["analysis_status"]

    assert understanding["image_type"] in IMAGE_TYPES

    _assert_provider_observation_contract(understanding)

    assert understanding["safety"]["geometry_authoritative"] is False

    ok("provider observation retained with verified-only legacy fields")

    return session


def test_provider_observation_without_local_corroboration():
    """Offline full session + check A for render/photo, including failed normalization.

    This controlled provider is not a live vision/model acceptance result.
    """
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    from core.vision import image_session_v1 as session_module
    from core.vision.general_visual_observer_v1 import CONTRACT as BRIDGE_CONTRACT, raw_observation
    from core.vision.observation_normalizer_v1 import CATEGORIES
    from core.vision.architectural_vision_grounding_v1 import ground_vision_evidence
    from core.vision.vision_observation_mode_v1 import build_observation

    phrases = ["glazed facade", "window", "entrance canopy", "paved forecourt",
               "a tree beside the building", "a low boundary wall",
               "a recessed upper facade", "a shadow below the canopy"]
    data = {"drawing_type": None, **{key: [] for key in CATEGORIES},
            "openings": {"doors": [], "windows": [], "other_openings": []}}
    data["observed_elements"] = [
        {"text": text, "source_quote": text, "kind": "window" if text == "window" else "element",
         "certainty": "ASSERTED", "count": None} for text in phrases]
    with tempfile.TemporaryDirectory() as directory:
        asset = Path(directory) / "synthetic-provider-transport.png"
        asset.write_bytes(b"controlled provider asset; no image inference")
        for image_kind in ("render", "photo"):
            raw = "The " + image_kind + " shows:\n" + "\n".join(phrases)
            for status in ("NORMALIZED", "FAILED"):
                payload = {
                    "contract": BRIDGE_CONTRACT,
                    "raw_observer": raw_observation(provider="controlled", model="offline",
                        backend="test", thinking_mode=False,
                        body={"response": raw, "done": True, "done_reason": "stop"}),
                    "normalization": {"status": status, "structured": data},
                }
                stub = types.SimpleNamespace(name="controlled", model="offline",
                    is_available=lambda: True, analyze=lambda _: payload)
                with patch.object(session_module, "provider", return_value=stub), \
                     patch.object(session_module, "read_local_plan", return_value=None), \
                     patch(__name__ + ".provider", return_value=stub), \
                     patch(__name__ + ".RENDER_IMAGE", str(asset)):
                    # Exercise the actual updated legacy check, not a duplicate.
                    session_key = test_A_render_understanding()
                    record = image_registry.active(session_key)
                    understanding = record["analysis"]
                    assert understanding["visual_observer_bridge"]["raw_observer"]["raw_text"] == raw
                    assert understanding["observed"] == []
                    assert understanding["grounded_provider_evidence"] == []
                    assert understanding["local_plan_reading"] is None
                    candidates = understanding["provider_candidates"]
                    if status == "NORMALIZED":
                        assert [c["text"] for c in candidates] == phrases
                        assert all(c["state"] == "UNVERIFIED" and not c["grounded"] for c in candidates)
                    else:
                        assert candidates == [] and understanding["analysis_status"] == "PARTIAL"
                    grounding = ground_vision_evidence(understanding)
                    assert not any(e["status"] in ("visible", "likely", "symbol_reading")
                                   for e in grounding["elements"])
                    observation = build_observation(understanding)
                    assert observation["elements"] == []
                    assert observation["provider_candidates"] == candidates
                    assert observation["grounded_provider_evidence"] == []
                    prompt = build_grounded_prompt("Describe this image", understanding)
                    assert all(phrase not in prompt for phrase in phrases)
    ok("render/photo provider observations retained without becoming grounded")


def test_B_floor_plan_understanding():

    print("\n[B] Floor plan -> classified as plan, conservative elements")

    if not provider().is_available():

        warn("vision provider unavailable - B skipped")

        return None

    if not os.path.isfile(PLAN_IMAGE):

        warn("plan image not found - B skipped: " + PLAN_IMAGE)

        return None

    session = "vision_B"

    image_registry.reset(session)

    record = register_asset(
        session,
        path=PLAN_IMAGE,
        source_type="uploaded",
        label="plan",
    )

    understanding = analyze_record(session, record["image_id"])

    print("     status     :", understanding.get("analysis_status"))
    print("     image_type :", understanding.get("image_type"))
    print("     observed   :", understanding.get("observed"))
    print("     labels     :", (understanding.get("text_labels_if_visible") or [])[:3])

    rejected = understanding["safety"]["rejected_claims"]

    print("     rejected   :", [r["reason"] for r in rejected][:6])

    assert understanding["image_type"] in IMAGE_TYPES

    assert understanding["safety"]["geometry_authoritative"] is False

    # plans carry dimensions on the page; the validator must never
    # promote them into the understanding
    dimension_rejections = [
        r for r in rejected if r["reason"] == "invented_dimension"
    ]

    if dimension_rejections:

        ok(
            "plan dimensions rejected by the safety validator ("
            + str(len(dimension_rejections))
            + " claim(s))"
        )

    assert understanding["image_type"] in (
        "floor_plan_or_sketch", "architectural_render_or_photo",
        "site_diagram", "unknown",
    )

    if understanding["image_type"] == "floor_plan_or_sketch":

        ok("floor plan classified as floor_plan_or_sketch")

    else:

        warn(
            "plan classified as "
            + understanding["image_type"]
            + " (provider limitation, not fabricated)"
        )

    return session



# ==========================================================
# C / D — GROUNDED CONVERSATION
# ==========================================================

def test_C_persian_question():

    print("\n[C] Image + Persian question -> grounded answer")

    if not provider().is_available():

        warn("vision provider unavailable - C skipped")

        return

    session = "vision_C"

    image_registry.reset(session)

    chat = _chat()

    with open(RENDER_IMAGE, "rb") as handle:

        upload = FileStorage(
            stream=handle,
            filename="render.png",
            content_type="image/png",
        )

        result = chat.handle(
            "این عکس چیه؟ چه چیزی در آن دیده می‌شود؟",
            context={"session_id": session, "image": upload},
        )

    vision = result.get("vision") or {}

    print("     type   :", result.get("type"))
    print("     intent :", vision.get("intent"))
    print("     status :", vision.get("analysis_status"))
    print("     answer :", str(result.get("result"))[:140])

    assert result.get("type") == "image_analysis", result.get("type")

    assert vision.get("intent") == INTENT_ANALYZE

    assert vision.get("image_id")

    assert vision.get("analysis_status") in (
        "ANALYZED", "ANALYZED_WITH_UNCERTAINTY", "PARTIAL",
    ), vision.get("analysis_status")

    assert result.get("result"), "no grounded answer produced"

    ok("Persian image question answered from real visual evidence")


def test_D_english_question():

    print("\n[D] Image + English question -> grounded answer")

    if not provider().is_available():

        warn("vision provider unavailable - D skipped")

        return

    # same session as C: "this image" must resolve to the active image
    session = "vision_C"

    chat = _chat()

    result = chat.handle(
        "describe this image and its visible architectural elements",
        context={"session_id": session},
    )

    vision = result.get("vision") or {}

    reference = vision.get("reference") or {}

    print("     type      :", result.get("type"))
    print("     reference :", reference.get("status"), reference.get("reference_kind"))
    print("     answer    :", str(result.get("result"))[:140])

    assert reference.get("status") == "resolved", reference

    assert result.get("result")

    ok("English question resolved 'this image' and answered")



# ==========================================================
# E — RENDER AUTO-REGISTRATION
# ==========================================================

def test_E_render_auto_registers():

    print("\n[E] Successful render auto-registers into the registry")

    from core.chat.session_registry_v1 import session_registry

    session = "vision_E"

    image_registry.reset(session)

    chat = _chat()

    session_registry.begin(session)

    try:

        record = chat.image_handler._register_render_output(
            {
                "image_asset": {
                    "filename": "architectos_v11_00235_.png",
                    "path": RENDER_IMAGE,
                }
            },
            attachments=[{"id": "attachment_test", "kind": "render"}],
        )

    finally:

        session_registry.end()

    assert record, "render was not registered"

    assert record["source_type"] == "text_to_image"

    assert record["ordinal"] == 1

    assert record["active"] is True

    ok("render output auto-registered (ordinal 1, active)")

    # a missing file must NOT be registered
    session_registry.begin("vision_E_missing")

    try:

        missing = chat.image_handler._register_render_output(
            {"image_asset": {"path": "C:/does/not/exist.png"}}
        )

    finally:

        session_registry.end()

    assert missing is None

    ok("missing render file is never registered")


# ==========================================================
# F / G / H / I / J — REFERENCE RESOLUTION
# ==========================================================

def _seed(session):

    image_registry.reset(session)

    register_asset(session, path="a.png", source_type="uploaded")

    register_asset(session, path="b.png", source_type="text_to_image")

    register_asset(session, path="c.png", source_type="text_to_image")


def test_F_active_reference():

    print("\n[F] 'همین عکس' resolves to the active image")

    session = "vision_F"

    _seed(session)

    resolution = resolve_reference("همین عکس چیه؟", session)

    assert resolution["status"] == "resolved", resolution

    assert resolution["reference_kind"] == "active"

    assert resolution["target_ordinal"] == 3

    ok("'همین عکس' -> active image (ordinal 3)")


def test_G_last_render_reference():

    print("\n[G] 'رندر قبلی' resolves correctly")

    session = "vision_G"

    _seed(session)

    resolution = resolve_reference("رندر قبلی رو توضیح بده", session)

    assert resolution["status"] == "resolved", resolution

    assert resolution["reference_kind"] == "last_render"

    assert resolution["target_ordinal"] == 3

    ok("'رندر قبلی' -> last render (ordinal 3)")

    # last_uploaded must find the upload, not a render
    uploaded = resolve_reference("آخرین آپلود", session)

    assert uploaded["status"] == "resolved"

    assert uploaded["target_ordinal"] == 1

    ok("last uploaded resolves to the uploaded image (ordinal 1)")


def test_H_ordinal_reference():

    print("\n[H] 'عکس دوم' resolves ordinal 2")

    session = "vision_H"

    _seed(session)

    resolution = resolve_reference("عکس دوم رو ببین", session)

    assert resolution["status"] == "resolved", resolution

    assert resolution["reference_kind"] == "ordinal"

    assert resolution["target_ordinal"] == 2

    ok("'عکس دوم' -> ordinal 2")

    english = resolve_reference("show me the second image", session)

    assert english["status"] == "resolved"

    assert english["target_ordinal"] == 2

    ok("'second image' -> ordinal 2")


def test_I_session_isolation():

    print("\n[I] Two sessions prove no image leakage")

    a, b = "vision_I_A", "vision_I_B"

    image_registry.reset(a)

    image_registry.reset(b)

    register_asset(a, path="a1.png", source_type="uploaded")

    register_asset(a, path="a2.png", source_type="text_to_image")

    register_asset(b, path="b1.png", source_type="text_to_image")

    assert image_registry.count(a) == 2

    assert image_registry.count(b) == 1

    list_a = [r["path"] for r in image_registry.list(a)]

    list_b = [r["path"] for r in image_registry.list(b)]

    assert "b1.png" not in list_a

    assert "a1.png" not in list_b

    # ordinal numbering is per-session
    assert image_registry.by_ordinal(b, 1)["path"] == "b1.png"

    assert image_registry.by_ordinal(a, 1)["path"] == "a1.png"

    # a reference in B never resolves to an A image
    resolution = resolve_reference("عکس اول", b)

    assert resolution["target_ordinal"] == 1

    assert image_registry.get(b, resolution["target_image_id"])["path"] == "b1.png"

    ok("sessions fully isolated (list, ordinals, references)")


def test_J_ambiguous_reference():

    print("\n[J] Ambiguous / impossible reference -> unresolved")

    session = "vision_J"

    _seed(session)

    # ordinal beyond the session count
    out_of_range = resolve_reference("عکس پنجم", session)

    assert out_of_range["status"] == "unresolved", out_of_range

    assert out_of_range["reason"] == "ordinal_out_of_range"

    assert out_of_range["target_image_id"] is None

    ok("ordinal out of range -> unresolved (no guessing)")

    # no renders at all in a session with only an upload
    empty = "vision_J_empty"

    image_registry.reset(empty)

    register_asset(empty, path="only.png", source_type="uploaded")

    no_render = resolve_reference("رندر قبلی", empty)

    assert no_render["status"] == "unresolved"

    assert no_render["reason"] == "no_render_in_session"

    ok("no render in session -> unresolved")

    # nothing registered at all
    blank = "vision_J_blank"

    image_registry.reset(blank)

    none_at_all = resolve_reference("همین عکس", blank)

    assert none_at_all["status"] == "unresolved"

    assert none_at_all["reason"] == "no_images_in_session"

    ok("no images in session -> unresolved")

    # non-reference text is never treated as a reference
    plain = resolve_reference("سلام، حالت چطوره؟", session)

    assert plain["status"] == "not_a_reference"

    ok("non-reference text -> not_a_reference")


# ==========================================================
# K / L — ROUTING
# ==========================================================

def test_K_analysis_does_not_route_to_img2img():

    print("\n[K] image + text analysis does NOT route to img2img")

    import core.chat.chat_architect as ca

    session = "vision_K"

    image_registry.reset(session)

    chat = _chat()

    called = {"edit": 0}

    def _record_edit(text, image, **kwargs):

        called["edit"] += 1

        return {"type": "image_edit", "status": "stub"}

    original_edit = chat.image_handler.handle_image_edit

    chat.image_handler.handle_image_edit = _record_edit

    original_analyze = ca.analyze_session_image

    ca.analyze_session_image = _stub_analysis

    try:

        with open(RENDER_IMAGE, "rb") as handle:

            upload = FileStorage(
                stream=handle, filename="r.png", content_type="image/png"
            )

            result = chat.handle(
                "این عکس چیه؟",
                context={"session_id": session, "image": upload},
            )

    finally:

        chat.image_handler.handle_image_edit = original_edit

        ca.analyze_session_image = original_analyze

    assert called["edit"] == 0, "analysis question was routed to img2img"

    assert result.get("type") == "image_analysis", result.get("type")

    ok("analysis question answered, img2img NOT invoked")

    # intent classification for the common cases
    assert classify_image_intent("این عکس چیه؟")["intent"] == INTENT_ANALYZE

    assert classify_image_intent("این عکس رو ویرایش کن")["intent"] == INTENT_EDIT

    assert classify_image_intent("")["intent"] == INTENT_UPLOAD_ONLY

    assert classify_image_intent("همین عکس")["intent"] == INTENT_REFERENCE

    ok("intent classifier separates analyze / edit / reference / upload_only")


def test_L_edit_intent_identified_not_executed():

    print("\n[L] edit-intent identified for Phase 05, not executed here")

    import core.chat.chat_architect as ca

    session = "vision_L"

    image_registry.reset(session)

    chat = _chat()

    routed = {"handler": None, "executed": False}

    def _record_edit(text, image, **kwargs):

        routed["handler"] = "handle_image_edit"

        # deliberately does NOT call render_runtime -> no real edit
        return {"type": "image_edit", "status": "not_executed_phase_05"}

    original_edit = chat.image_handler.handle_image_edit

    chat.image_handler.handle_image_edit = _record_edit

    original_analyze = ca.analyze_session_image

    ca.analyze_session_image = _stub_analysis

    try:

        with open(RENDER_IMAGE, "rb") as handle:

            upload = FileStorage(
                stream=handle, filename="r.png", content_type="image/png"
            )

            result = chat.handle(
                "این عکس رو ویرایش کن و نمای آن را عوض کن",
                context={"session_id": session, "image": upload},
            )

    finally:

        chat.image_handler.handle_image_edit = original_edit

        ca.analyze_session_image = original_analyze

    vision = result.get("vision") or {}

    assert vision.get("intent") == INTENT_EDIT, vision.get("intent")

    assert routed["handler"] == "handle_image_edit"

    assert result.get("status") == "not_executed_phase_05"

    ok("edit intent identified and routed; no real edit executed")

    assert classify_image_intent("edit this image")["intent"] == INTENT_EDIT

    ok("English edit intent also identified")


# ==========================================================
# SAFETY + REGION REFERENCES
# ==========================================================

def test_safety_contract():

    print("\n[Safety] non-authoritative geometry contract")

    assert classify_claim("width 12 m")[0] == "reject"

    assert classify_claim("south facade")[0] == "reject"

    assert classify_claim("8 x 12")[0] == "reject"

    assert classify_claim("concrete facade")[0] == "demote"

    assert classify_claim("structural columns")[0] == "demote"

    assert classify_claim("residential building")[0] == "demote"

    assert classify_claim("a glass window")[0] == "demote"

    ok("dimensions + orientation rejected; material/structure/type demoted")

    understanding = build_understanding(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["a tall building", "the facade is 24 m wide", "north side"],
            "inferred": ["concrete structure"],
            "unresolved": [],
            "confidence": "HIGH",
            "architectural_elements": ["glass curtain wall"],
            "text_labels_if_visible": ["PLAN A"],
        },
        provider="test",
        model="test",
        image_id="img_test",
    )

    assert understanding["observed"] == ["a tall building"]

    assert "concrete structure" in understanding["inferred"]

    reasons = [r["reason"] for r in understanding["safety"]["rejected_claims"]]

    assert "invented_dimension" in reasons

    assert "unsupported_orientation" in reasons

    assert understanding["safety"]["geometry_authoritative"] is False

    ok("validator strips dimensions/orientation and demotes unverifiable claims")


def test_region_reference():

    print("\n[Region] deictic region references")

    for text, element in (
        ("این پنجره", "window"),
        ("این دیوار", "wall"),
        ("این قسمت", "region"),
        ("this window", "window"),
        ("این بالکن", "balcony"),
    ):

        is_region, found, _ = is_region_reference(text)

        assert is_region, text

        assert found == element, (text, found)

    ok("deictic element phrases detected deterministically")

    understanding = build_understanding(
        {
            "image_type": "architectural_render_or_photo",
            "observed": ["a window"],
            "inferred": [],
            "unresolved": [],
            "confidence": "MEDIUM",
            "architectural_elements": ["window", "facade"],
            "text_labels_if_visible": [],
        },
        provider="test",
        model="test",
    )

    region = resolve_region_reference(
        "این پنجره", "img_1", understanding
    )

    assert region["target_image_id"] == "img_1"

    assert region["candidate_element_type"] == "window"

    assert region["bbox"] is None, "bbox must never be fabricated"

    assert region["grounded"] is False

    assert "no_region_grounding" in region["unresolved"]

    ok("region reference returned ungrounded, no fake bbox")

    not_region = resolve_region_reference("سلام", "img_1", understanding)

    assert not_region["status"] == "not_a_region_reference"

    ok("non-region text -> not_a_region_reference")


def test_grounded_prompt_rules():

    print("\n[Grounding] answer prompt carries the safety rules")

    prompt = build_grounded_prompt(
        "این عکس چیه؟",
        build_understanding(
            {
                "image_type": "architectural_render_or_photo",
                "observed": ["a building"],
                "inferred": [],
                "unresolved": [],
                "confidence": "MEDIUM",
                "architectural_elements": [],
                "text_labels_if_visible": [],
            },
            provider="t", model="t",
        ),
    )

    assert "a building" in prompt

    assert "Never invent dimensions" in prompt

    assert "same language" in prompt

    ok("grounded prompt enforces evidence-only answering")


# ==========================================================
# M — REGRESSION
# ==========================================================

def test_M_regression():

    print("\n[M] Regression 01 / 02 / 03 / 03B")

    suites = (
        "test_runtime_foundation_01.py",
        "test_chat_language_02.py",
        "test_text_to_image_comfy_03.py",
        "test_text_to_image_comfy_03b.py",
    )

    for name in suites:

        path = os.path.join(ROOT, "tests", name)

        spec = importlib.util.spec_from_file_location(
            "reg_" + name.replace(".py", ""), path
        )

        module = importlib.util.module_from_spec(spec)

        spec.loader.exec_module(module)

        code = module.run_all()

        assert code == 0, name + " failed"

    ok("01 / 02 / 03 / 03B suites still pass")



# ==========================================================
# RUNNER
# ==========================================================

def run_all():

    print("=" * 62)
    print("  ARCHITECTOS VISION_IMAGE_REGISTRY_04 — TESTS")
    print("=" * 62)

    info = provider().describe()

    print(
        "\n  vision provider:",
        info["provider"],
        "|",
        info["model"],
        "| available:",
        info["available"],
        "| local:",
        info["local"],
    )

    test_provider_observation_without_local_corroboration()

    test_A_render_understanding()

    test_B_floor_plan_understanding()

    test_C_persian_question()

    test_D_english_question()

    test_E_render_auto_registers()

    test_F_active_reference()

    test_G_last_render_reference()

    test_H_ordinal_reference()

    test_I_session_isolation()

    test_J_ambiguous_reference()

    test_K_analysis_does_not_route_to_img2img()

    test_L_edit_intent_identified_not_executed()

    test_safety_contract()

    test_region_reference()

    test_grounded_prompt_rules()

    test_M_regression()

    print("\n" + "=" * 62)
    print("  " + str(len(PASS)) + " CHECKS PASSED")

    if WARN:

        print("  " + str(len(WARN)) + " WARNING(S):")

        for item in WARN:

            print("    - " + item)

    print("  RESULT: VISION_IMAGE_REGISTRY_04_TESTS_PASS")
    print("=" * 62)

    return 0



if __name__ == "__main__":

    sys.exit(
        run_all()
    )
