# ==========================================================
# ARCHITECTOS — GEOMETRY AUTHORITY HANDOFF V1.1 — TESTS
#
# Deterministic. No GPU, no network, no ComfyUI, no render submission.
# Every test asserts the EFFECTIVE FINAL PROMPT and/or the PRE-DISPATCH
# DECISION — never an intermediate ontology object.
# ==========================================================

import pytest

import core.runtime.gpu_handoff_v1 as gh
from core.prompt_intelligence.image_edit_prompt_builder import ImageEditPromptBuilder
from core.prompt_intelligence.geometry_authority_handoff_v1 import (
    STATUS_OK,
    STATUS_SUGGESTIONS_FILTERED,
    STATUS_AUTHORIZED,
    STATUS_CONFLICT,
    STATUS_UNRESOLVED,
    DISCLOSURE_STRICT_PRESERVATION,
)
from core.render.render_runtime import RenderRuntime

BASE_IMAGE = "runs/architectos_product_integration_v3/p3a_transfer_output.png"


# ----------------------------------------------------------
# FIXTURES
# ----------------------------------------------------------

def _resolved():
    return {
        "contract": "ResolvedFacadeKnowledgeV1",
        "version": "1.0",
        "canonical_style": "neoclassical",
        "facade_language": {"name": "neoclassical",
                            "composition": ["classical order", "balanced volume"]},
        "composition": ["classical order", "balanced volume", "classical grid",
                        "symmetrical composition"],
        "symmetry": ["symmetrical composition"],
        "vertical_horizontal_emphasis": ["vertical emphasis"],
        "solid_void_strategy": ["solid void contrast"],
        "entrance_hierarchy": ["formal entry"],
        "opening_treatment": ["classical windows", "stone frames around openings"],
        "balcony_treatment": [],
        "parapet_treatment": ["strong horizontal cornice"],
        "architectural_elements": {
            "arches": ["tall arch"], "columns": ["engaged columns"],
            "pilasters": ["pilasters"], "cornices": ["dentilled cornice"],
            "moldings": [], "frames": ["stone frames"],
            "balustrades": ["stone balustrades"], "louvers": [],
            "brick_screens": [], "recessed_frames": [], "projecting_frames": [],
        },
        "materials": {"primary": ["light travertine stone", "natural stone"],
                      "cladding": ["travertine"], "texture": ["natural texture"]},
        "surface_strategy": {"cladding": ["travertine"], "finish": ["honed finish"]},
        "user_facade_details": [],
        "unresolved": [],
    }


FIXED = (
    "number_of_floors", "overall_massing", "building_silhouette",
    "major_proportions", "roofline", "main_balconies",
    "main_window_positions", "main_door_positions",
    "camera", "perspective", "major_recess_projection_geometry",
)


def _intent(user_text, *, preserve_geometry=True, constraints=FIXED,
            resolved=True, materials=None, style="neoclassical", edit_class=None):
    architectural = {
        "building_type": "villa",
        "style": style,
        "materials": materials or ["light travertine stone"],
        "normalized_prompt": user_text,
        "preserve_geometry": preserve_geometry,
        "geometry_authority": "SOURCE_IMAGE",
        "preserve_constraints": list(constraints),
        "request_type": "facade_material_edit",
    }
    if resolved:
        architectural["resolved_facade_knowledge"] = _resolved()
    payload = {"architectural_intent": architectural, "_user_prompt": user_text}
    if edit_class:
        payload["edit_delta"] = {"edit_class": edit_class}
    return payload


def _build(user_text, **kw):
    builder = ImageEditPromptBuilder()
    prompt = builder.build(_intent(user_text, **kw))
    return prompt, builder.last_geometry_authority


def _low(prompt):
    return prompt.lower()


# ==========================================================
# MANDATORY REGRESSION 1 — "Change the roof color only"
# ==========================================================

def test_roof_colour_change_does_not_authorise_geometry():
    prompt, auth = _build("Change the roof color only", edit_class="color_change")

    assert auth["authorized_domains"] == []
    assert auth["conflicts"] == []
    assert auth["status"] != STATUS_CONFLICT
    assert "roof" in auth["fixed_domains"], "the roof stays fixed for a colour change"

    # the roof-preservation wording must still be present
    assert "roof shape" in _low(prompt)
    # and no roof vocabulary was injected
    assert "dentilled cornice" not in _low(prompt)


# ==========================================================
# MANDATORY REGRESSION 2 — material change + roof kept
# ==========================================================

def test_material_change_with_roof_kept_does_not_authorise_roof():
    prompt, auth = _build(
        "Change the facade material and keep the roof unchanged"
    )

    assert auth["authorized_domains"] == []
    assert auth["conflicts"] == []
    assert "roof" in auth["explicit_preserved_domains"]
    assert "roof shape" in _low(prompt)
    assert "travertine" in _low(prompt)


# ==========================================================
# MANDATORY REGRESSION 3 — unrelated negation must not cancel
# ==========================================================

def test_window_preservation_does_not_cancel_roof_authorisation():
    prompt, auth = _build(
        "Keep windows fixed. Redesign the roof to include a pediment"
    )

    assert auth["status"] == STATUS_AUTHORIZED
    assert "roof" in auth["authorized_domains"]
    assert "opening" in auth["explicit_preserved_domains"]
    assert "opening" in auth["fixed_domains"], "windows stay protected"

    low = _low(prompt)
    assert "roof shape" not in low, "the authorised roof must not be preserved"
    assert "windows" in low, "the explicitly preserved windows must remain"


# ==========================================================
# MANDATORY REGRESSION 4 — contradictory request
# ==========================================================

def test_redesign_roof_but_preserve_its_shape_is_a_conflict():
    _prompt, auth = _build("Redesign the roof but preserve its original shape")

    assert auth["status"] == STATUS_CONFLICT
    assert [c["domain"] for c in auth["conflicts"]] == ["roof"]
    assert "roof" in auth["fixed_domains"], "a conflicted domain is never lifted"


# ==========================================================
# MANDATORY REGRESSION 5 / 6 — add, default vs explicit preservation
# ==========================================================

def test_add_pediment_with_default_preservation_is_authorised():
    prompt, auth = _build("Add a pediment")

    assert auth["status"] == STATUS_AUTHORIZED
    assert "roof" in auth["authorized_domains"]
    assert auth["conflicts"] == []
    assert "roof shape" not in _low(prompt)


def test_add_pediment_against_explicit_roofline_preservation_conflicts():
    _prompt, auth = _build(
        "Add a pediment while explicitly requiring the roofline to remain unchanged"
    )

    assert auth["status"] == STATUS_CONFLICT
    assert [c["domain"] for c in auth["conflicts"]] == ["roof"]


# ==========================================================
# MANDATORY REGRESSION 7 — no-ontology fallback obeys authority
# ==========================================================

def test_travertine_fallback_without_ontology_adds_no_structural_elements():
    prompt, auth = _build("Apply travertine", resolved=False, materials=["travertine"])

    low = _low(prompt)
    assert "travertine" in low
    # the legacy structural block must not be emitted under fixed geometry
    assert "Create classical architectural facade language" not in prompt
    assert "Apply classical detailing as a SURFACE treatment only" in prompt
    assert "massing" in auth["fixed_domains"]


# ==========================================================
# MANDATORY REGRESSION 8 / 9 — Persian
# ==========================================================

def test_persian_roof_redesign_is_authorised():
    _prompt, auth = _build("سقف را بازطراحی کن و یک سنتوری اضافه کن")

    assert auth["language"] == "fa"
    assert auth["status"] == STATUS_AUTHORIZED
    assert "roof" in auth["authorized_domains"]


def test_persian_material_change_keeps_roof_fixed():
    _prompt, auth = _build("فقط مصالح نما را تغییر بده، فرم بام ثابت بماند")

    assert auth["language"] == "fa"
    assert auth["authorized_domains"] == []
    assert "roof" in auth["explicit_preserved_domains"]
    assert "roof" in auth["fixed_domains"]


# ==========================================================
# V1 ACCEPTANCE CASES (reinterpreted: default != explicit preservation)
# ==========================================================

def test_material_only_request_remains_admissible():
    prompt, auth = _build("Apply light travertine, keep the exact building geometry.")

    assert auth["status"] in (STATUS_OK, STATUS_SUGGESTIONS_FILTERED)
    assert auth["conflicts"] == []

    low = _low(prompt)
    assert "travertine" in low
    for term in ("engaged columns", "pilasters", "dentilled cornice", "stone balustrades"):
        assert term not in low


def test_neoclassical_style_kept_but_structural_elements_withheld():
    prompt, auth = _build(
        "Make the facade neoclassical without changing the roof, openings or floor count."
    )

    assert auth["conflicts"] == []
    assert DISCLOSURE_STRICT_PRESERVATION in auth["disclosures"]

    low = _low(prompt)
    assert "neoclassical" in low
    assert "engaged columns" not in low
    assert "dentilled cornice" not in low


def test_explicit_pediment_addition_against_explicit_roof_preservation_conflicts():
    prompt, auth = _build(
        "Add a triangular pediment; the roofline must stay unchanged"
    )

    assert auth["status"] == STATUS_CONFLICT
    assert "triangular pediment" not in _low(prompt)
    assert "needs clarification" in _low(prompt)


def test_authorized_roof_redesign_is_not_rejected():
    prompt, auth = _build("Redesign the roof to include a pediment.")

    assert auth["status"] == STATUS_AUTHORIZED
    assert auth["conflicts"] == []
    assert "roof" not in auth["fixed_domains"]

    low = _low(prompt)
    assert "dentilled cornice" in low or "cornice" in low
    assert "roof shape" not in low
    assert "redesign any element outside the authorised scope" in low
    assert "Explicitly authorised geometry change" in prompt


def test_material_only_edit_emits_no_site_or_landscape_instruction():
    prompt, auth = _build("Change the facade material only; do not modify the site.")

    low = _low(prompt)
    for term in ("landscap", "foreground", "plaza", "paving", "site plan", "garden"):
        assert term not in low
    assert auth["conflicts"] == []


def test_non_architectural_intent_does_not_invoke_authority():
    builder = ImageEditPromptBuilder()
    prompt = builder.build(
        {"architectural_intent": {"normalized_prompt": "hello"}, "_user_prompt": "hello"}
    )
    auth = builder.last_geometry_authority
    assert auth["status"] == STATUS_OK
    assert auth["conflicts"] == []
    assert "GEOMETRY PRESERVATION" in prompt
    assert "Apply the resolved ArchitectOS facade knowledge" not in prompt


def test_source_geometry_constraints_reach_the_final_instruction():
    prompt, _auth = _build("Apply light travertine, keep the exact building geometry.")

    for line in ("original building silhouette", "roof shape", "openings",
                 "floor count", "camera angle", "perspective"):
        assert line in _low(prompt)


def test_negated_verb_is_not_treated_as_authorisation():
    _prompt, auth = _build(
        "Repaint the facade in stone, do not redesign the roof or move any walls."
    )
    assert auth["authorized_domains"] == []
    assert auth["conflicts"] == []


def test_material_mention_of_an_element_word_is_not_a_conflict():
    _prompt, auth = _build("Use stone cladding on the facade.")
    assert auth["status"] != STATUS_CONFLICT
    assert auth["conflicts"] == []


def test_absence_of_preserve_geometry_disables_the_filter():
    prompt, auth = _build(
        "Redesign the facade in neoclassical style.",
        preserve_geometry=False, constraints=(),
    )
    assert auth["preserve_geometry"] is False
    assert auth["suppressed_terms"] == []
    assert "engaged columns" in _low(prompt)


def test_unsupported_language_is_unresolved_not_authorised():
    _prompt, auth = _build("Rekonstruiere das Dach mit einem Giebel")
    # German is not parsed; no authority may be granted
    assert auth["authorized_domains"] == []


# ==========================================================
# PRE-DISPATCH DECISION
# ==========================================================

class _FakeLease:
    def __init__(self):
        self.acquires = 0
        self.releases = 0

    def acquire(self):
        self.acquires += 1
        return True

    def release(self):
        self.releases += 1


class _CaptureExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, injected_workflow, engine, **kwargs):
        # R4_POSITIVE_INSTRUCTION_CONTRACT_V1 — harness compatibility only.
        # `RenderRuntime.render()` passes `on_submitted=` to the executor; this
        # capture fake was written before that keyword existed (2026-10-19 vs
        # render_runtime 2026-10-23), so every dispatch test in this file died
        # with TypeError before reaching its assertions. Accepting the keyword
        # changes no assertion and no expectation.
        self.calls.append(engine)
        return {"status": "dry_run_capture", "engine": engine}


def _design(text, *, edit_class=None, constraints=FIXED):
    intent = {
        "building_type": "villa", "style": "neoclassical",
        "materials": ["light travertine stone"],
        "normalized_prompt": text,
        "preserve_geometry": True,
        "geometry_authority": "SOURCE_IMAGE",
        "preserve_constraints": list(constraints),
        "levels": {"basement": 0, "ground": 1, "above_ground": 3,
                   "mezzanine": 0, "total": 4},
    }
    design = {
        "prompt": text, "original_prompt": text, "mode": "img2img",
        "architectural_intent": intent,
        "compiled_render_prompt": "REFERENCE: r, DELTA: d, PRESERVE: p, QUALITY: q",
        "preservation": {"level": "high_preservation", "denoise": 0.3},
        "edit_conflict_terms": [], "seed": 7,
    }
    if edit_class:
        design["edit_delta"] = {"edit_class": edit_class}
    return design


@pytest.fixture
def gpu_isolated(monkeypatch, tmp_path):
    """Every GPU entry point is stubbed. Nothing can reach ComfyUI or Ollama."""

    target = tmp_path / "gpu_handoff"
    target.mkdir()
    monkeypatch.setenv("ARCHITECTOS_GPU_HANDOFF_DIR", str(target))
    monkeypatch.delenv("ARCHITECTOS_RENDER_MIN_FREE_VRAM_MIB", raising=False)

    lease = _FakeLease()
    monkeypatch.setattr(gh, "gpu_render_lease", lambda wait=None: lease)
    monkeypatch.setattr(gh, "unload_ollama_models_for_render", lambda **k: {
        "status": "not_loaded", "reason": None, "ownership": "exclusive",
        "loaded_before": [], "unloaded": [], "failed": [], "skipped_in_use": [],
        "vram_free_before": 16 * 1024 ** 3, "vram_free_after": 16 * 1024 ** 3,
    })
    monkeypatch.setattr(gh, "require_render_vram", lambda h2=None, *a, **k: {
        "ok": True, "reason": "ok", "free_mib": 16000.0, "min_free_mib": 11264.0,
        "measurement_source": "h2.vram_free_after", "raw_bytes": 16 * 1024 ** 3,
    })
    monkeypatch.setattr(gh, "release_comfyui_for_vision",
                        lambda *a, **k: {"status": "blocked"})

    # hard network block: a regression fails loudly instead of reaching ComfyUI
    import socket
    attempts = []

    def _blocked(self, address, *a, **k):
        attempts.append(address)
        raise AssertionError("network access attempted: %r" % (address,))

    monkeypatch.setattr(socket.socket, "connect", _blocked)

    return {"lease": lease, "attempts": attempts}


def _run(design, gpu_isolated):
    runtime = RenderRuntime()
    executor = _CaptureExecutor()
    runtime.executor = executor
    result = runtime.render(
        "auth-test", design, "flux",
        {"path": BASE_IMAGE, "filename": "base.png"},
    )
    return runtime, executor, result


def test_dispatch_blocks_a_conflicting_geometry_request(gpu_isolated):
    runtime, executor, result = _run(
        _design("Add a pediment while explicitly requiring the roofline to remain unchanged"),
        gpu_isolated,
    )

    assert result["status"] == "geometry_authority_blocked"
    assert result["reason"] == STATUS_CONFLICT
    assert gpu_isolated["lease"].acquires == 0, "no lease may be taken"
    assert executor.calls == [], "nothing may be submitted"
    assert gpu_isolated["attempts"] == [], "no socket may be opened"


def test_dispatch_blocks_an_unresolved_geometric_request(gpu_isolated):
    runtime, executor, result = _run(
        _design("Rekonstruiere das Dach mit einem Giebel"), gpu_isolated
    )

    assert result["status"] == "geometry_authority_blocked"
    assert result["reason"] == STATUS_UNRESOLVED
    assert gpu_isolated["lease"].acquires == 0
    assert executor.calls == []


def test_dispatch_allows_a_material_only_request(gpu_isolated):
    runtime, executor, result = _run(
        _design("Apply light travertine, keep the exact building geometry."),
        gpu_isolated,
    )

    assert result.get("status") != "geometry_authority_blocked"
    assert gpu_isolated["lease"].acquires == 1, "a material-only request must reach dispatch"
    assert executor.calls == ["comfyui"]


# ==========================================================
# FAIL-CLOSED — a resolver failure is an UNRESOLVED authorisation
#
# A resolver that raises proves nothing about the instruction. The previous
# pre-dispatch handler set the verdict to None, which read as "no block" and
# fell through to dispatch: a broken or unavailable resolver sent an unchecked
# geometric request to the GPU. With no verdict there is no authority, so the
# request must be refused before the lease.
# ==========================================================

def _break_resolver(monkeypatch):
    import core.prompt_intelligence.geometry_authority_handoff_v1 as authority_module

    def _raise(*_args, **_kwargs):
        raise RuntimeError("resolver unavailable")

    monkeypatch.setattr(authority_module, "resolve_geometry_authority", _raise)


def test_dispatch_is_blocked_when_the_authority_resolver_raises(
    gpu_isolated, monkeypatch
):
    _break_resolver(monkeypatch)

    runtime, executor, result = _run(
        _design("Add a pediment while explicitly requiring the roofline to remain unchanged"),
        gpu_isolated,
    )

    assert result["status"] == "geometry_authority_blocked"
    assert result["reason"] == "authority_resolver_failed"
    assert executor.calls == [], "nothing may be submitted"
    assert gpu_isolated["attempts"] == [], "no socket may be opened"


def test_dispatch_is_blocked_on_resolver_failure_even_for_a_harmless_request(
    gpu_isolated, monkeypatch
):
    """Fail-closed: with no verdict a legitimate request is refused rather than
    an unchecked one admitted. The lease is never acquired."""

    _break_resolver(monkeypatch)

    runtime, executor, result = _run(
        _design("Apply light travertine, keep the exact building geometry."),
        gpu_isolated,
    )

    assert result["status"] == "geometry_authority_blocked"
    assert result["reason"] == "authority_resolver_failed"
    assert gpu_isolated["lease"].acquires == 0, "no lease may be taken"
    assert executor.calls == []


# ==========================================================
# EXPLICIT NEW-ELEMENT REQUESTS MUST SURVIVE (user-facing capability)
#
# The authority filter exists to suppress ONTOLOGY SUGGESTIONS, never an
# explicit user request. "Add a railing" must authorise circulation even when
# the word never appears in the style vocabulary.
# ==========================================================

def test_explicit_railing_request_is_preserved_not_filtered():
    prompt, auth = _build("Add a railing")

    assert auth["status"] == STATUS_AUTHORIZED
    assert "circulation" in auth["authorized_domains"]
    assert "circulation" not in auth["fixed_domains"]
    # the ontology's railing vocabulary is now admissible instead of withheld
    assert "stone balustrades" in _low(prompt)


def test_explicit_railing_on_balcony_is_preserved():
    prompt, auth = _build("Add a new railing to the balcony")

    assert "circulation" in auth["authorized_domains"]
    assert "stone balustrades" in _low(prompt)
    # unrelated domains stay protected
    assert "opening" in auth["fixed_domains"]


def test_explicit_window_request_is_preserved():
    prompt, auth = _build("Add a window on the west facade")

    assert "opening" in auth["authorized_domains"]
    assert "opening" not in auth["fixed_domains"]

    preserve_block = prompt.split("PRESERVE EXACTLY:")[1].split("DO NOT:")[0].lower()
    assert "windows" not in preserve_block, "an authorised opening must not be preserved"
    assert "openings" not in preserve_block


def test_ontology_railing_is_still_filtered_when_not_requested():
    """The contrast case: no user request, so the suggestion has no authority."""

    prompt, auth = _build("Apply light travertine, keep the exact building geometry.")

    assert auth["authorized_domains"] == []
    assert "stone balustrades" not in _low(prompt)


def test_explicit_persian_railing_request_is_preserved():
    _prompt, auth = _build("نرده جدید به بالکن اضافه کن")

    assert auth["language"] == "fa"
    assert "circulation" in auth["authorized_domains"]


# ==========================================================
# CIRCULATION MUST APPEAR IN THE EMITTED PRESERVATION TEXT
#
# `circulation` (terraces, balconies, stairs, railings) is fixed for a default
# edit, but the emitted PRESERVE EXACTLY block never named it while naming
# openings, roof and camera. The night acceptance recorded the consequence: an
# ornate balcony was replaced by a thin railing. A domain that is fixed in the
# authority dict but absent from the instruction protects nothing.
# ==========================================================

def test_default_preservation_names_circulation():
    prompt, auth = _build("Apply light travertine, keep the exact building geometry.")

    assert "circulation" in auth["fixed_domains"]
    assert auth["authorized_domains"] == []
    assert "existing terraces, balconies, stairs and railings" in _low(prompt)


def test_night_edit_preservation_names_the_balcony_and_railings():
    """The day->night case that actually drifted: the balcony/railing line must
    be in the night prompt's PRESERVE EXACTLY block."""

    prompt, auth = _build("Make it night", edit_class="time_of_day_change")

    assert auth["authorized_domains"] == []
    assert "circulation" in auth["fixed_domains"]

    preserve_block = prompt.split("PRESERVE EXACTLY:")[1].split("DO NOT:")[0].lower()
    assert "terraces" in preserve_block
    assert "balconies" in preserve_block
    assert "railings" in preserve_block


def test_authorized_circulation_is_not_contradicted_by_a_railing_prohibition():
    """The converse of the line above: once circulation IS authorised, the
    instruction must not simultaneously forbid touching the railings."""

    prompt, auth = _build("Add a railing")

    assert "circulation" in auth["authorized_domains"]
    prohibit_block = prompt.split("DO NOT:")[1].lower()
    assert "remove terraces, balconies, stairs or railings" not in prohibit_block
    assert "redesign any element outside the authorised scope" in prohibit_block


def test_circulation_stays_protected_when_another_domain_is_authorised():
    """Railing protection must still be emitted when a *different* domain was
    authorised — the roof case here — so the two never trade off."""

    prompt, auth = _build("Add a pediment")

    assert "roof" in auth["authorized_domains"]
    assert "circulation" in auth["fixed_domains"]

    prohibit_block = prompt.split("DO NOT:")[1].lower()
    assert "remove terraces, balconies, stairs or railings" in prohibit_block
    assert "railings" in prompt.split("PRESERVE EXACTLY:")[1].split("DO NOT:")[0].lower()
