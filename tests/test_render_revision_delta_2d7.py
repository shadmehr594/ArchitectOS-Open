# ==========================================================
# PHASE 2D-7 — RENDER REVISION / DELTA UNDERSTANDING
# Semantic delta only: no render execution, no ComfyUI, no design mutation.
# ==========================================================

import copy
import inspect
import json

from core.prompt_intelligence.render_revision_delta_v1 import (
    CONTRACT,
    VERSION,
    REVISION_TYPES,
    RenderRevisionDeltaV1,
    RenderRevisionBaseResolverV1,
    RenderRevisionDeltaBuilderV1,
    build_render_revision_delta,
    as_prompt_delta_hint,
)
from core.prompt_intelligence.approved_design_render_contract_v1 import (
    build_render_contract,
)
from core.prompt_intelligence.persian_architectural_understanding import understand


APPROVED = {
    "approval_status": True,
    "design_status": "approved",
    "project_state": "APPROVED",
    "last_design": {"type": "villa"},
    "last_architectural_intent": {"style": "modern"},
    "approved_design_id": "D-1",
    "approved_candidate_id": "C-7",
    "approved_candidate_version": "3",
    "approved_candidate_hash": "abc123",
    "design_source_type": "approved_bim_design",
}

NOT_APPROVED = {
    "approval_status": False,
    "design_status": "waiting_approval",
    "project_state": "WAITING_APPROVAL",
    "last_design": {"type": "villa"},
}

RENDER_STATE = {
    "active_render_id": "R-3",
    "active_render_hash": "rh3",
    "render_history": [
        {"render_id": "R-1", "render_hash": "rh1", "render_index": 1, "reference": "render1.png"},
        {"render_id": "R-2", "render_hash": "rh2", "render_index": 2, "reference": "render2.png"},
        {"render_id": "R-3", "render_hash": "rh3", "render_index": 3, "reference": "render3.png"},
    ],
}


def _contract(state=APPROVED, text="نمای مدرن‌تر شه"):
    return build_render_contract(state, understanding=understand(text))


def _rev(text, contract=None, render_state=None, context=None, prior=None, selection=None):
    c = _contract() if contract is None else contract
    return build_render_revision_delta(
        c,
        understanding=understand(text),
        render_state=render_state if render_state is not None else RENDER_STATE,
        context=context,
        prior_revision=prior,
        selection=selection,
    )


# ==========================================================
# A — active approved design + active render, material tone
# ==========================================================

def test_A_active_render_material_tone_lighter():
    d = _rev("همینه فقط سنگش روشن‌تر شه")
    assert isinstance(d, RenderRevisionDeltaV1)
    assert d["status"] == "READY"
    assert d["base_render_id"] == "R-3"
    assert d["base_render_hash"] == "rh3"
    assert d["material_delta"]["material"] == "stone"
    assert d["material_delta"]["tone_direction"] == "LIGHTER"
    assert d["approved_design_authority"]["authoritative_geometry_source"] == "APPROVED_DESIGN"
    for field in ("massing", "geometry", "windows", "floor_count", "plan"):
        assert field in d["preserve_fields"]


# ==========================================================
# B / C — option selection with and without history
# ==========================================================

def test_B_option_two_from_history():
    d = _rev("گزینه دوم خوبه، قوس‌هاش کمتر شه")
    assert d["status"] == "READY"
    assert d["base_render_id"] == "R-2"
    assert d["base_render_index"] == 2
    assert d["selection_provenance"]["source"] == "selected_option"
    assert d["arch_delta"]["direction"] == "decrease"
    assert any(op["revision_type"] == "ARCH_INTENSITY_CHANGE" for op in d["delta_operations"])


def test_C_option_without_render_history():
    d = _rev("گزینه دوم خوبه، قوس‌هاش کمتر شه", render_state={})
    assert d["status"] == "BASE_RENDER_REQUIRED"
    assert d["base_render_id"] is None
    assert d["delta_operations"] == []
    assert "base_render" in d["required_context"]


# ==========================================================
# D — lighting only
# ==========================================================

def test_D_lighting_time_of_day_evening():
    d = _rev("نور عصر باشه")
    assert d["status"] == "READY"
    assert d["lighting_delta"]["time_of_day"] == "evening"
    assert d["material_delta"] == {}
    assert d["window_frame_delta"] == {}
    assert len(d["delta_operations"]) == 1
    assert d["delta_operations"][0]["revision_type"] == "LIGHTING_CHANGE"


# ==========================================================
# E / F / G — entrance emphasis vs entrance / window geometry
# ==========================================================

def test_E_entrance_emphasis_is_render_delta():
    d = _rev("ورودی رو شاخص‌تر نشون بده")
    assert d["status"] == "READY"
    assert d["entrance_delta"]["emphasis"] == "increase"
    assert d["entrance_delta"]["mode"] == "PRESENTATION"
    assert d["revision_scope"] == "RENDER_ONLY"


def test_F_enlarge_entrance_requires_design_revision():
    d = _rev("ورودی رو بزرگ‌تر کن")
    assert d["status"] == "DESIGN_REVISION_REQUIRED"
    assert d["delta_operations"] == []
    assert d["revision_scope"] == "DESIGN"
    assert any(tok in d["forbidden_changes"] for tok in ("resize_entrance", "move_entrance"))


def test_F2_move_entrance_requires_design_revision():
    d = _rev("ورودی رو ببر سمت راست")
    assert d["status"] == "DESIGN_REVISION_REQUIRED"
    assert "move_entrance" in d["forbidden_changes"]


def test_G_move_windows_requires_design_revision():
    d = _rev("پنجره‌ها رو جابه‌جا کن")
    assert d["status"] == "DESIGN_REVISION_REQUIRED"
    assert "move_primary_openings" in d["forbidden_changes"]


def test_G2_add_floor_and_balcony_resize():
    assert _rev("یه طبقه اضافه کن")["status"] == "DESIGN_REVISION_REQUIRED"
    assert "add_floor" in _rev("یه طبقه اضافه کن")["forbidden_changes"]
    d = _rev("بالکن رو بزرگ‌تر کن")
    assert d["status"] == "DESIGN_REVISION_REQUIRED"
    assert "resize_balcony" in d["forbidden_changes"]


# ==========================================================
# H — preserve-all + window frame colour
# ==========================================================

def test_H_preserve_all_with_window_frame_colour():
    d = _rev("همه‌چی همین بمونه فقط قاب پنجره‌ها تیره‌تر شه")
    assert d["status"] == "READY"
    assert d["preserve_all_requested"] is True
    assert d["window_frame_delta"]["tone_direction"] == "DARKER"
    for field in ("massing", "floor_count", "plan", "primary_openings", "windows", "balconies",
                  "entrance_location", "geometry"):
        assert field in d["preserve_fields"]
        assert d["preserve_constraints"][field] is True
    assert d["approved_design_authority"]["base_render_is_authority"] is False


# ==========================================================
# I — latest explicit delta wins
# ==========================================================

def test_I_latest_explicit_delta_wins():
    c = _contract()
    rev1 = _rev("سنگش تیره‌تر شه", contract=c)
    assert rev1["material_delta"]["tone_direction"] == "DARKER"

    rev2 = _rev("نه روشن‌ترش کن", contract=c, prior=rev1)
    assert rev2["status"] in ("READY", "READY_WITH_WARNINGS")
    assert rev2["material_delta"]["material"] == "stone"
    assert rev2["material_delta"]["tone_direction"] == "LIGHTER"
    assert rev2["overridden_operations"], "override provenance must be recorded"
    assert rev2["overridden_operations"][0]["overridden_by"] == "latest_explicit_delta"
    assert any(w["code"] == "EXPLICIT_DELTA_OVERRIDE" for w in rev2["warnings"])


# ==========================================================
# J / K — ambiguity and unique-context resolution
# ==========================================================

def test_J_ambiguous_when_material_and_lighting_both_active():
    d = _rev("روشن‌ترش کن", context={"active_targets": ["stone", "lighting"]})
    assert d["status"] == "AMBIGUOUS_REVISION_TARGET"
    assert d["delta_operations"] == []
    assert d["ambiguities"][0]["type"] == "ambiguous_revision_target"
    assert "revision_target" in d["required_context"]


def test_K_bare_tone_resolved_from_context():
    d = _rev("روشن‌ترش کن", context={
        "active_targets": ["stone"],
        "active_materials": {"primary": "stone"},
    })
    assert d["status"] == "READY"
    assert d["material_delta"]["material"] == "stone"
    assert d["material_delta"]["tone_direction"] == "LIGHTER"
    assert d["material_delta"]["resolved_from_context"] is True
    assert d["resolved_from_context"][0]["source"] == "active_target"


# ==========================================================
# L — reference revision
# ==========================================================

def test_L_disable_active_reference():
    d = _rev("دیگه از این رفرنس استفاده نکن", context={"active_reference_id": "REF-1"})
    assert d["status"] == "READY"
    assert d["reference_delta"]["action"] == "DISABLE"
    assert d["reference_delta"]["source_reference_id"] == "REF-1"
    assert d["reference_delta"]["effective_reference_policy"]["referenced"] is False
    assert d["reference_delta"]["pixel_analysis"] is False
    assert d["revision_scope"] == "REFERENCE_ONLY"


def test_L2_reference_colour_only_role():
    d = _rev("فقط رنگش رو از رفرنس بگیر", context={"active_reference_id": "REF-2"})
    assert d["reference_delta"]["action"] == "SET_ROLE"
    assert d["reference_delta"]["role"] == "colour_only"


def test_L3_reference_geometry_copy_is_conflict():
    d = _rev("مثل این عکس باشه", context={"active_reference_id": "REF-3"})
    # reference may not become geometry authority; no silent geometry copy
    assert d["approved_design_authority"]["base_render_is_authority"] is False


# ==========================================================
# M / N — approval gate and base render validity
# ==========================================================

def test_M_no_approved_design_contract():
    assert build_render_revision_delta(None, understanding=understand("سنگش روشن‌تر شه"))["status"] == "APPROVAL_REQUIRED"
    assert build_render_revision_delta({}, understanding=understand("سنگش روشن‌تر شه"))["status"] == "APPROVAL_REQUIRED"
    not_approved = build_render_contract(NOT_APPROVED, understanding=understand("نمای مدرن‌تر شه"))
    assert build_render_revision_delta(
        not_approved, understanding=understand("سنگش روشن‌تر شه"), render_state=RENDER_STATE
    )["status"] == "APPROVAL_REQUIRED"


def test_N_stale_active_render_is_invalid():
    stale = {
        "active_render_id": "R-9",
        "render_history": [
            {"render_id": "R-1", "render_hash": "rh1", "render_index": 1, "reference": "render1.png"},
        ],
    }
    d = _rev("سنگش روشن‌تر شه", render_state=stale)
    assert d["status"] == "INVALID_BASE_RENDER"
    assert d["delta_operations"] == []


def test_N2_unknown_explicit_render_id_is_invalid():
    state = {**RENDER_STATE, "explicit_base_render_id": "R-99"}
    d = _rev("سنگش روشن‌تر شه", render_state=state)
    assert d["status"] == "INVALID_BASE_RENDER"


def test_N3_option_out_of_range_is_invalid():
    d = _rev("گزینه پنجم خوبه", render_state=RENDER_STATE)
    assert d["status"] == "INVALID_BASE_RENDER"


# ==========================================================
# O — approved design wins over base-render visual drift
# ==========================================================

def test_O_approved_design_wins_over_drift():
    state = {**RENDER_STATE, "base_render_observed_floor_count": 5}
    d = _rev("سنگش روشن‌تر شه", render_state=state, context={"approved_floor_count": 3})
    assert d["base_render_drift"]["detected"] is True
    assert d["base_render_drift"]["preserved"] is False
    assert d["base_render_drift"]["resolution"] == "approved_design_authoritative"
    assert d["approved_design_authority"]["base_render_is_authority"] is False
    assert d["approved_design_authority"]["base_render_is_appearance_reference_only"] is True
    assert "floor_count" in d["preserve_fields"]
    assert any(w["code"] == "BASE_RENDER_VISUAL_DRIFT" for w in d["warnings"])


# ==========================================================
# P — deterministic serialization / hash
# ==========================================================

def test_P_deterministic_hash_and_round_trip():
    a = _rev("سنگش روشن‌تر شه")
    b = _rev("سنگش روشن‌تر شه")
    assert a["delta_hash"] == b["delta_hash"]
    assert len(a["delta_hash"]) == 64
    assert json.loads(json.dumps(a, ensure_ascii=False)) == a


def test_P_different_delta_different_hash():
    a = _rev("سنگش روشن‌تر شه")
    b = _rev("سنگش تیره‌تر شه")
    assert a["delta_hash"] != b["delta_hash"]


def test_P_delta_hash_distinct_from_design_and_render_hash():
    d = _rev("سنگش روشن‌تر شه")
    assert d["delta_hash"] != d["approved_candidate_hash"]
    assert d["delta_hash"] != d["base_render_hash"]
    assert d["approved_candidate_hash"] == "abc123"   # preserved, not recomputed
    assert d["base_render_hash"] == "rh3"             # read, never invented


def test_P_delta_hash_changes_with_base_render():
    a = _rev("سنگش روشن‌تر شه", render_state=RENDER_STATE)
    b = _rev("سنگش روشن‌تر شه", render_state={**RENDER_STATE, "active_render_id": "R-2"})
    assert a["delta_hash"] != b["delta_hash"]


# ==========================================================
# Q / R — purity and no side effects
# ==========================================================

def test_Q_no_render_or_generation_side_effect():
    source = inspect.getsource(
        inspect.getmodule(RenderRevisionDeltaBuilderV1)
    ).lower()
    for forbidden in (
        "import requests", "from core.render", "import comfy", "from comfy",
        "comfyui_bridge", "render_runtime(", "text2img(", "img2img(",
        "workflow_executor", "subprocess", "open(",
    ):
        assert forbidden not in source, forbidden


def test_R_no_design_or_input_mutation():
    contract = _contract()
    state = copy.deepcopy(RENDER_STATE)
    ctx = copy.deepcopy({"active_targets": ["stone"], "active_materials": {"primary": "stone"}})
    understanding = understand("سنگش روشن‌تر شه")

    contract_snap = copy.deepcopy(contract)
    state_snap = copy.deepcopy(state)
    ctx_snap = copy.deepcopy(ctx)
    u_snap = copy.deepcopy(understanding)

    builder = RenderRevisionDeltaBuilderV1()
    builder.build(contract, understanding=understanding, render_state=state, context=ctx)

    assert contract == contract_snap, "approved contract must not be mutated"
    assert state == state_snap, "render state must not be mutated"
    assert ctx == ctx_snap, "context must not be mutated"
    assert understanding == u_snap, "understanding must not be mutated"

    source = inspect.getsource(inspect.getmodule(RenderRevisionDeltaBuilderV1)).lower()
    for forbidden in (".update(", ".setdefault(", ".pop(", ".clear("):
        assert forbidden not in source, forbidden


def test_R_no_render_execution_flags():
    d = _rev("سنگش روشن‌تر شه")
    assert d["provenance"]["semantic_delta_only"] is True
    assert d["provenance"]["render_execution"] is False
    assert d["provenance"]["design_mutation"] is False


# ==========================================================
# contract shape / statuses / revision types
# ==========================================================

def test_contract_identity_and_fields():
    d = _rev("سنگش روشن‌تر شه")
    assert d["contract"] == CONTRACT
    assert d["version"] == VERSION
    assert d["revision_status"] == d["status"]
    for key in (
        "contract", "version", "status", "revision_status", "session_id",
        "approved_design_id", "approved_candidate_id", "approved_candidate_hash",
        "base_render_id", "base_render_hash", "base_render_index", "base_render_reference",
        "revision_scope", "delta_operations", "preserve_fields", "preserve_constraints",
        "style_delta", "material_delta", "colour_delta", "lighting_delta", "camera_delta",
        "entrance_delta", "ornament_delta", "arch_delta", "window_frame_delta",
        "balcony_expression_delta", "landscape_delta", "reference_delta",
        "design_revision_requests", "forbidden_changes", "resolved_target",
        "resolved_from_context", "selection_provenance", "ambiguities", "conflicts",
        "warnings", "required_context", "source_understanding", "provenance", "delta_hash",
    ):
        assert key in d, key


def test_revision_types_are_canonical():
    d = _rev("سنگش روشن‌تر شه")
    for op in d["delta_operations"]:
        assert op["revision_type"] in REVISION_TYPES


def test_no_render_revision_intent():
    d = _rev("سلام، خوبی؟")
    assert d["status"] == "NO_RENDER_REVISION_INTENT"


def test_camera_and_style_and_ornament_deltas():
    cam = _rev("دوربین یکم پایین‌تر")
    assert cam["camera_delta"]["direction"] == "lower"

    style = _rev("یه کم مدرن‌ترش کن")
    assert style["style_delta"]["target"] == "modern"
    assert style["style_delta"]["direction"] == "increase"
    assert style["style_delta"]["intensity"] == "LOW"

    orn = _rev("تزئینات کمتر شه")
    assert orn["ornament_delta"]["direction"] == "decrease"


def test_base_resolver_is_read_only_and_minimal():
    resolver = RenderRevisionBaseResolverV1()
    state = copy.deepcopy(RENDER_STATE)
    snap = copy.deepcopy(state)
    resolver.resolve(state, "همینه")
    assert state == snap


def test_optional_prompt_hint_is_read_only():
    d = _rev("سنگش روشن‌تر شه")
    hint = as_prompt_delta_hint(d)
    assert "change_instructions" in hint
    assert hint["base_render_id"] == "R-3"
    assert as_prompt_delta_hint({"status": "BASE_RENDER_REQUIRED"}) == {}


# ==========================================================
# S — 2D-1 … 2D-6 regressions remain green
# ==========================================================

def test_S_2d1_to_2d6_still_work():
    from core.cognition.persian_normalizer import persian_normalizer
    from core.prompt_intelligence.architectural_prompt_compiler_v1 import compile_prompt
    from core.chat.architectural_conversation_context_v1 import ArchitecturalConversationContextMergerV1
    from core.prompt_intelligence.reference_image_architectural_understanding_v1 import (
        ReferenceImageArchitecturalUnderstandingV1,
    )

    assert persian_normalizer.normalize("نماي ۲")["normalized_text"] == "نمای 2"

    u = understand("یه نمای سنگ روشن میخوام ولی خیلی رومی نشه")
    assert compile_prompt(u)["status"] == "COMPILED"

    merged = ArchitecturalConversationContextMergerV1().merge({}, u, raw_text="x", normalized_text="x")
    assert merged["contract"] == "ArchitecturalConversationContextV1"

    assert ReferenceImageArchitecturalUnderstandingV1().analyze(None)["analysis_status"] == "UNSUPPORTED_IMAGE"

    c6 = _contract()
    assert c6["status"] == "READY"
    assert c6["approved_candidate_id"] == "C-7"


# ==========================================================
# T / U / V — interrupted edge cases
#   2D7_LOCAL_COMPATIBILITY_GUARD: narrow, in-place comparative handling
# ==========================================================

def test_T_luxury_increase_keeps_ornament_negative_constraint():
    d = _rev("لوکس‌ترش کن ولی شلوغ نشه")
    assert d["status"] == "READY"

    # STYLE_REFINEMENT → luxury / increase
    assert d["style_delta"]["target"] == "luxury"
    assert d["style_delta"]["direction"] == "increase"
    assert any(op["revision_type"] == "STYLE_REFINEMENT" for op in d["delta_operations"])

    # the narrow supplemental scan is provenance-recorded and subordinate
    assert d["style_delta"].get("recovered_by") == "2D7_STYLE_DIRECT_SCAN"
    assert d["style_delta"].get("recovery_scope") == "2D7_LOCAL_COMPATIBILITY_GUARD"

    # the "شلوغ" negation survives as a negative complexity/ornament constraint
    assert d["ornament_delta"]["direction"] == "decrease"
    codes = {c.get("constraint") for c in d["style_delta"]["negative_constraints"]}
    assert "avoid_heavy_ornament" in codes

    # approved geometry remains preserved / authoritative
    assert d["approved_design_authority"]["authoritative_geometry_source"] == "APPROVED_DESIGN"
    assert d["approved_design_authority"]["base_render_is_authority"] is False
    for field in ("massing", "geometry", "floor_count", "plan"):
        assert field in d["preserve_fields"]


def test_T2_luxury_positive_without_negation_is_not_a_supplement():
    d = _rev("لوکس‌ترش کن")
    assert d["style_delta"]["target"] == "luxury"
    assert d["style_delta"]["direction"] == "increase"
    assert "recovered_by" not in d["style_delta"]


def test_U_negated_style_comparatives_never_increase():
    for text in ("مدرن‌تر نشه", "کلاسیک‌تر نشه", "لوکس‌تر نشه"):
        d = _rev(text)
        assert d["style_delta"] == {}, text
        assert all(
            op["revision_type"] != "STYLE_REFINEMENT" for op in d["delta_operations"]
        ), text
        assert d["status"] in ("NO_RENDER_REVISION_INTENT", "READY", "READY_WITH_WARNINGS"), text


def test_U2_positive_style_comparative_still_works():
    d = _rev("یه کم مدرن‌ترش کن")
    assert d["style_delta"]["target"] == "modern"
    assert d["style_delta"]["direction"] == "increase"
    assert d["style_delta"]["intensity"] == "LOW"


def test_V_negated_arch_comparative_never_increases():
    d = _rev("قوس‌ها بیشتر نشن")
    assert d["arch_delta"] == {}
    assert all(
        op["revision_type"] != "ARCH_INTENSITY_CHANGE" for op in d["delta_operations"]
    )
    assert d["status"] == "NO_RENDER_REVISION_INTENT"

    d2 = _rev("قوس‌ها زیاد نشه")
    assert d2["arch_delta"] == {}


def test_V2_positive_arch_comparatives_still_work():
    assert _rev("قوس‌ها بیشتر شن")["arch_delta"]["direction"] == "increase"
    assert _rev("قوس‌ها کمتر شن")["arch_delta"]["direction"] == "decrease"


def test_V3_negated_tone_comparatives_never_leak_positive():
    m = _rev("سنگش روشن‌تر نشه")
    assert m["material_delta"] == {}
    assert m["colour_delta"] == {}
    assert all(
        op["revision_type"] not in ("MATERIAL_TONE_CHANGE", "COLOUR_CHANGE")
        for op in m["delta_operations"]
    ), m["delta_operations"]

    assert _rev("نور روشن‌تر نشه")["lighting_delta"] == {}
    assert _rev("نور تیره‌تر نشه")["lighting_delta"] == {}

    # a positive comparative is untouched
    assert _rev("سنگش روشن‌تر شه")["material_delta"]["tone_direction"] == "LIGHTER"


def test_V4_guard_is_in_place_only():
    # an unrelated negative clause elsewhere must not swallow a positive delta
    d = _rev("نور عصر باشه، روشن‌تر نشه")
    assert d["lighting_delta"]["time_of_day"] == "evening"
    assert d["lighting_delta"]["direction"] is None


def test_V5_no_broad_2d2_bypass_and_no_fabrication():
    # no comparative form + no revision intent → nothing invented
    d = _rev("سلام، خوبی؟")
    assert d["status"] == "NO_RENDER_REVISION_INTENT"
    assert d["style_delta"] == {}
    assert d["delta_operations"] == []


# ==========================================================
# RUNTIME INTEGRATION (ChatArchitect) — 2D-7 wiring
# ==========================================================

def _chat_architect_source():
    with open("core/chat/chat_architect.py", encoding="utf-8") as fh:
        return fh.read()


def test_W_runtime_wiring_present_and_request_scoped():
    src = _chat_architect_source()
    assert "PHASE 2D-7" in src
    assert "render_revision_delta.build(" in src
    assert '"render_revision_delta"' in src

    block = src.split("PHASE 2D-7 — RENDER REVISION / DELTA UNDERSTANDING", 1)[1]
    block = block.split("SAVE CURRENT USER PROMPT", 1)[0]

    # request-scoped, read-only: the 2D-7 block must not write any state
    assert "self.state.update" not in block
    assert "apply_turn" not in block

    # no render execution / comfy side effect in the block (call/import sites)
    for forbidden in ("RenderRuntime(", "import comfy", "from comfy",
                      "img2img(", "text2img(", "workflow_executor", "subprocess"):
        assert forbidden.lower() not in block.lower(), forbidden


def test_W2_public_surface_is_semantic_only():
    module = inspect.getmodule(RenderRevisionDeltaBuilderV1)
    for name in ("render", "run_render", "generate_image", "execute_workflow",
                 "submit_render", "run"):
        assert not hasattr(module, name), name


def test_W3_runtime_does_not_persist_or_mutate_design():
    # the delta is a projection of state, never a writer of state
    d = _rev("سنگش روشن‌تر شه")
    assert d["provenance"]["design_mutation"] is False
    assert d["provenance"]["render_execution"] is False
    assert d["approved_candidate_hash"] == "abc123"   # read from contract, unchanged


