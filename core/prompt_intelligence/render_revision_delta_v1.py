# ==========================================================
# ArchitectOS Render Revision / Delta Understanding v1.0
#
# PHASE 2D-7 — RENDER REVISION / DELTA UNDERSTANDING
#
# A semantic DELTA layer for render revisions.
#
# A revision request binds to:
#   - the APPROVED DESIGN  (authority, from 2D-6), and
#   - a specific BASE RENDER (appearance reference only)
# and produces a versioned RenderRevisionDeltaV1 describing the
# appearance-only change while preserving approved geometry.
#
# SEMANTIC DELTA ONLY.
#   No RenderRuntime.  No ComfyUI.  No img2img / text2img.  No image
#   files.  No design mutation.  No PromptRouter / prompt-ownership change.
#
# AUTHORITY ORDER (highest first):
#   approved design
#   > hard preserve constraints
#   > render revision delta
#   > previous render appearance
#   > reference image evidence
# ==========================================================


from __future__ import annotations

import hashlib
import json
import re
import time

from core.prompt_intelligence.approved_design_render_contract_v1 import (
    ApprovedDesignRenderContractBuilder,
    DEFAULT_ALLOWED_RENDER_CHANGES,
    DEFAULT_PRESERVE,
    FORBIDDEN_GEOMETRY_CHANGES,
)


CONTRACT = "RenderRevisionDeltaV1"
VERSION = "1.0"


# ==========================================================
# CONTRACT
# ==========================================================

class RenderRevisionDeltaV1(dict):
    """Versioned, dict-compatible render-revision semantic delta."""

    CONTRACT = CONTRACT
    VERSION = VERSION


# ==========================================================
# STATUSES  (§16)
# ==========================================================

STATUS_READY = "READY"
STATUS_READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
STATUS_BASE_RENDER_REQUIRED = "BASE_RENDER_REQUIRED"
STATUS_AMBIGUOUS_REVISION_TARGET = "AMBIGUOUS_REVISION_TARGET"
STATUS_DESIGN_REVISION_REQUIRED = "DESIGN_REVISION_REQUIRED"
STATUS_APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
STATUS_INVALID_BASE_RENDER = "INVALID_BASE_RENDER"
STATUS_REFERENCE_CONFLICT = "REFERENCE_CONFLICT"
STATUS_NO_RENDER_REVISION_INTENT = "NO_RENDER_REVISION_INTENT"
STATUS_FAILED = "FAILED"

STATUSES = (
    STATUS_READY,
    STATUS_READY_WITH_WARNINGS,
    STATUS_BASE_RENDER_REQUIRED,
    STATUS_AMBIGUOUS_REVISION_TARGET,
    STATUS_DESIGN_REVISION_REQUIRED,
    STATUS_APPROVAL_REQUIRED,
    STATUS_INVALID_BASE_RENDER,
    STATUS_REFERENCE_CONFLICT,
    STATUS_NO_RENDER_REVISION_INTENT,
    STATUS_FAILED,
)


# ==========================================================
# REVISION SCOPE
# ==========================================================

SCOPE_RENDER_ONLY = "RENDER_ONLY"
SCOPE_REFERENCE_ONLY = "REFERENCE_ONLY"
SCOPE_DESIGN = "DESIGN"
SCOPE_NONE = "NONE"


# ==========================================================
# APPEARANCE-ONLY REVISION TYPES  (§5 — canonical, deterministic)
# ==========================================================

RT_MATERIAL_CHANGE = "MATERIAL_CHANGE"
RT_MATERIAL_TONE_CHANGE = "MATERIAL_TONE_CHANGE"
RT_STYLE_REFINEMENT = "STYLE_REFINEMENT"
RT_COLOUR_CHANGE = "COLOUR_CHANGE"
RT_LIGHTING_CHANGE = "LIGHTING_CHANGE"
RT_CAMERA_PRESENTATION_CHANGE = "CAMERA_PRESENTATION_CHANGE"
RT_ENTRANCE_EMPHASIS_CHANGE = "ENTRANCE_EMPHASIS_CHANGE"
RT_ORNAMENT_REDUCTION = "ORNAMENT_REDUCTION"
RT_ARCH_INTENSITY_CHANGE = "ARCH_INTENSITY_CHANGE"
RT_WINDOW_FRAME_EXPRESSION_CHANGE = "WINDOW_FRAME_EXPRESSION_CHANGE"
RT_BALCONY_RAILING_EXPRESSION_CHANGE = "BALCONY_RAILING_EXPRESSION_CHANGE"
RT_FACADE_DEPTH_VISUAL_CHANGE = "FACADE_DEPTH_VISUAL_CHANGE"
RT_LANDSCAPE_PRESENTATION_CHANGE = "LANDSCAPE_PRESENTATION_CHANGE"
RT_REFERENCE_USAGE_CHANGE = "REFERENCE_USAGE_CHANGE"

REVISION_TYPES = (
    RT_MATERIAL_CHANGE,
    RT_MATERIAL_TONE_CHANGE,
    RT_STYLE_REFINEMENT,
    RT_COLOUR_CHANGE,
    RT_LIGHTING_CHANGE,
    RT_CAMERA_PRESENTATION_CHANGE,
    RT_ENTRANCE_EMPHASIS_CHANGE,
    RT_ORNAMENT_REDUCTION,
    RT_ARCH_INTENSITY_CHANGE,
    RT_WINDOW_FRAME_EXPRESSION_CHANGE,
    RT_BALCONY_RAILING_EXPRESSION_CHANGE,
    RT_FACADE_DEPTH_VISUAL_CHANGE,
    RT_LANDSCAPE_PRESENTATION_CHANGE,
    RT_REFERENCE_USAGE_CHANGE,
)

# canonical operation names
OP_SET_MATERIAL_TONE = "SET_MATERIAL_TONE"
OP_SET_MATERIAL = "SET_MATERIAL"
OP_ADJUST_STYLE = "ADJUST_STYLE"
OP_SET_COLOUR = "SET_COLOUR"
OP_SET_LIGHTING = "SET_LIGHTING"
OP_SET_CAMERA = "SET_CAMERA"
OP_ADJUST_ENTRANCE_EMPHASIS = "ADJUST_ENTRANCE_EMPHASIS"
OP_ADJUST_ORNAMENT = "ADJUST_ORNAMENT"
OP_ADJUST_ARCH_INTENSITY = "ADJUST_ARCH_INTENSITY"
OP_SET_WINDOW_FRAME_EXPRESSION = "SET_WINDOW_FRAME_EXPRESSION"
OP_SET_BALCONY_RAILING_EXPRESSION = "SET_BALCONY_RAILING_EXPRESSION"
OP_ADJUST_FACADE_DEPTH = "ADJUST_FACADE_DEPTH"
OP_SET_LANDSCAPE = "SET_LANDSCAPE"
OP_SET_REFERENCE_USAGE = "SET_REFERENCE_USAGE"

# revision type -> allowed_render_changes category (2D-6 §7 vocabulary)
REVISION_TYPE_TO_ALLOWED = {
    RT_MATERIAL_CHANGE: "facade_materials",
    RT_MATERIAL_TONE_CHANGE: "facade_materials",
    RT_STYLE_REFINEMENT: "facade_style",
    RT_COLOUR_CHANGE: "colour_palette",
    RT_LIGHTING_CHANGE: "lighting",
    RT_CAMERA_PRESENTATION_CHANGE: "camera",
    RT_ENTRANCE_EMPHASIS_CHANGE: "entrance_emphasis",
    RT_ORNAMENT_REDUCTION: "ornament_level",
    RT_ARCH_INTENSITY_CHANGE: "ornament_level",
    RT_WINDOW_FRAME_EXPRESSION_CHANGE: "window_frame_expression",
    RT_BALCONY_RAILING_EXPRESSION_CHANGE: "balcony_railing_expression",
    RT_FACADE_DEPTH_VISUAL_CHANGE: "facade_depth_visualization",
    RT_LANDSCAPE_PRESENTATION_CHANGE: "landscape_presentation",
    RT_REFERENCE_USAGE_CHANGE: None,   # reference policy is a separate axis
}


# ==========================================================
# TONE VOCABULARY
# ==========================================================

TONE_LIGHTER = "LIGHTER"
TONE_DARKER = "DARKER"
TONE_WARMER = "WARMER"
TONE_COOLER = "COOLER"
TONE_CREAM = "CREAM"
TONE_MORE = "MORE"
TONE_LESS = "LESS"

_TONE_CANONICAL = {
    "light": TONE_LIGHTER,
    "dark": TONE_DARKER,
    "warm": TONE_WARMER,
    "cool": TONE_COOLER,
    "cream": TONE_CREAM,
}

# direct comparative scan (supplements 2D-2 tone detection)
_DIRECT_TONE = (
    ("light", ("روشن‌تر", "روشنتر", "روشن تر")),
    ("dark", ("تیره‌تر", "تیرهتر", "تیره تر")),
    ("warm", ("گرم‌تر", "گرمتر", "گرم تر")),
    ("cool", ("سرد‌تر", "سردتر", "سرد تر")),
)

# direct comparative style scan — used ONLY when 2D-2 produced no style target
# (2D-2 may drop a style whose negation window overlaps an unrelated negative
# clause, e.g. "لوکس‌ترش کن ولی شلوغ نشه").  Ordered most-specific first.
_STYLE_DIRECT = (
    ("neoclassical", ("نئوکلاسیک", "نوکلاسیک")),
    ("modern_classic", ("مدرن کلاسیک",)),
    ("minimal", ("مینیمال",)),
    ("luxury", ("لاکچری", "لوکس", "luxury")),
    ("modern", ("مدرن", "modern")),
    ("traditional", ("سنتی", "traditional")),
    ("industrial", ("صنعتی", "industrial")),
    ("roman", ("رومی", "roman")),
    ("classic", ("کلاسیک", "classic")),
    ("simple", ("ساده", "simple")),
)

_DIRECT_TONE_MAP = dict(_DIRECT_TONE)

# 2D7_LOCAL_COMPATIBILITY_GUARD — in-place comparative negation.
# Narrow, deterministic, revision-specific: a positive delta is suppressed ONLY
# when the comparative marker is IMMEDIATELY followed (allowing ZWNJ/space) by a
# negation tail.  This compensates for the frozen 2D-2 window-based negation
# handling, which can leave a negated comparative looking like an increase
# ("مدرن‌تر نشه", "قوس‌ها بیشتر نشن").  It never rewrites 2D-2 semantics.
_NEGATION_TAIL = (
    "نشه", "نشن", "نشین", "نباشه", "نباشن", "نکن", "نکنه",
    "نشود", "نباشد", "نباش", "نمی‌شه", "نمیشه",
)
_STYLE_DIRECT_MAP = dict(_STYLE_DIRECT)

# comparative increase markers for arch intensity (2D-7 arch-negation guard)
_ARCH_INCREASE_FORMS = ("بیشتر", "زیاد", "افزایش")


# ==========================================================
# LEXICONS
# ==========================================================

# --- design-revision geometry detection (2D-7 extension of 2D-6) ---
_ENTRANCE_NOUNS = ("ورودی", "ورودیش", "ورودی‌ش", "درب ورودی", "entrance", "entry")
_BALCONY_NOUNS = ("بالکن", "بالکن‌ها", "بالکنها", "تراس", "terrace", "balcony", "balconies")
_BUILDING_TERMS = ("ساختمون", "ساختمان", "بنا", "building", "خانه", "خونه")

_GEOMETRY_VERBS = (
    "جابه‌جا", "جابجا", "جابه جا", "عوض", "تغییر", "حذف", "اضافه", "بردار",
    "بزرگ", "کوچک", "بکش", "ببر", "منتقل", "کشیده", "کوتاه", "بلند", "عریض", "باریک",
    "move", "relocate", "replace", "remove", "add", "resize", "shift", "extend",
    "enlarge", "widen", "reposition",
)
_MOVE_VERBS = (
    "جابه‌جا", "جابجا", "جابه جا", "ببر", "منتقل", "سمت راست", "سمت چپ",
    "واسه سمت", "ببر سمت", "move", "relocate", "reposition",
)
_PROPORTION_TERMS = (
    "کشیده", "کوتاه", "بلند", "عریض", "باریک", "قد", "ارتفاع",
    "proportion", "taller", "longer", "shorter", "wider", "narrower",
)
# presentation / emphasis qualifiers that must NOT trigger a design revision
_APPEARANCE_EXCLUSIONS = (
    "شاخص", "برجسته", "قوی", "نمایان", "واضح", "نشون", "نشان", "دیده", "تأکید", "تاکید",
    "emphasis", "prominent", "visible", "highlight", "show",
)

# --- lighting ---
_LIGHTING_WORDS = ("نور", "روشنایی", "نورپردازی", "نور پردازی", "lighting", "light")
_TIME_OF_DAY = (
    ("evening", ("عصر", "evening", "dusk")),
    ("sunset", ("غروب", "sunset", "golden hour")),
    ("night", ("شب", "night")),
    ("noon", ("ظهر", "نیمروز", "noon", "midday")),
    ("afternoon", ("بعدازظهر", "بعد از ظهر", "afternoon")),
    ("morning", ("صبح", "بامداد", "morning")),
    ("sunrise", ("طلوع", "sunrise")),
)

# --- camera ---
_CAMERA_WORDS = ("دوربین", "camera", "زاویه", "view", "نما از")
_CAMERA_DIRECTIONS = (
    ("lower", ("پایین‌تر", "پایینتر", "lower")),
    ("higher", ("بالاتر", "higher", "بالا‌تر")),
    ("closer", ("نزدیک‌تر", "نزدیکتر", "closer")),
    ("farther", ("دور‌تر", "دورتر", "farther", "further")),
    ("wider", ("واید", "wide", "گسترده‌تر")),
    ("left", ("سمت چپ", "چپ")),
    ("right", ("سمت راست", "راست")),
)

# --- landscape ---
_LANDSCAPE_WORDS = ("محوطه", "لنداسکیپ", "لنداسکپ", "فضای سبز", "محوطه‌سازی", "باغ", "landscape")

# --- ornament / arches / facade depth / balcony expression ---
_ORNAMENT_WORDS = ("تزئینات", "تزیینات", "تزئین", "تزیین", "ornament", "decoration")
_DECREASE_MARKERS = ("کمتر", "کم کن", "کمش کن", "کاهش", "بیشتر نکن", "حذف", "ساده‌تر", "ساده تر")
_INCREASE_MARKERS = ("بیشتر", "افزایش", "ترش کن", "تر کن", "تر باشه", "تر شه")
_RAILING_WORDS = ("نرده", "railing", "handrail")
_FACADE_DEPTH_WORDS = ("عمق نما", "عمق", "depth", "برجستگی نما")
_DEPTH_MORE = ("بیشتر", "زیاد", "داشته باشه", "داشته باشد", "more")

# --- reference ---
_REFERENCE_WORDS = ("رفرنس", "reference", "عکس", "تصویر", "image", "photo")
_REFERENCE_DISABLE = (
    "استفاده نکن", "استفاده نشه", "استفاده نکنیم", "دیگه از این", "دیگه این",
    "حذف کن", "بردار", "نمیخوام", "نمی‌خوام", "نمیخام", "لازم نیست", "نیازی نیست",
    "بی‌خیال", "بی خیال", "disable", "ignore the reference", "don't use",
)
_REFERENCE_COLOUR_ROLE = ("فقط رنگ", "رنگش رو از رفرنس", "رنگ رو از رفرنس", "colour from reference", "color from reference")
_REFERENCE_STYLE_DISABLE = ("سبکش رو نگیر", "سبک رو نگیر", "سبکش نباشه", "سبک نگیر")

# --- preserve language (§10) ---
_PRESERVE_ALL_MARKERS = (
    "همه‌چی همین بمونه", "همه چی همین بمونه", "همه‌چیز همین بمونه", "همه چیز همین بمونه",
    "هیچی رو عوض نکن", "هیچی عوض نشه", "هیچ چی رو عوض نکن", "همین خوبه فقط",
    "همین بمونه", "همین باشه", "فرم دست نخوره", "دست نزن", "تغییر نده",
    "همه‌چی همین", "همه چی همین",
)
_PRESERVE_FIELDS_MARKERS = {
    "windows": ("پنجره‌ها همین", "پنجره ها همین", "پنجره‌ها بمونه", "پنجره‌ها دست نخوره"),
    "balconies": ("بالکن همین", "بالکن‌ها همین", "بالکن دست نخوره"),
    "geometry": ("فرم دست نخوره", "هندسه دست نخوره", "فرم همینه"),
}

_GEOMETRY_PRESERVE_FIELDS = (
    "massing", "floor_count", "plan", "primary_openings",
    "windows", "balconies", "entrance_location", "geometry",
)

_MATERIAL_TARGET_TOKENS = {
    "stone", "brick", "wood", "metal", "glass", "concrete", "travertine",
    "white_cement", "light_color", "dark_color",
    "materials", "material", "متریال",
}


# ==========================================================
# ORDINALS / SELECTION  (§14)
# ==========================================================

_ORDINALS = (
    ("اولین", 1), ("اولی", 1), ("اول", 1), ("یکم", 1),
    ("دومین", 2), ("دومی", 2), ("دوم", 2),
    ("سومین", 3), ("سومی", 3), ("سوم", 3),
    ("چهارمین", 4), ("چهارمی", 4), ("چهارم", 4),
    ("پنجمین", 5), ("پنجمی", 5), ("پنجم", 5),
    ("first", 1), ("second", 2), ("third", 3), ("fourth", 4),
)
_STRONG_ORDINALS = ("اولین", "اولی", "دومین", "دومی", "سومین", "سومی", "چهارمی", "پنجمی")
_LAST_MARKERS = ("آخرین", "آخری", "last one", "last")
_OPTION_CONTEXT_WORDS = ("گزینه", "option", "variant", "واریانت", "انتخاب", "رندر", "تصویر")
_PREVIOUS_MARKERS = ("قبلی", "قبل", "previous", "prior")
_CURRENT_MARKERS = ("همینه", "همین", "همون", "این یکی", "current", "this one")


# ==========================================================
# BASE RENDER RESOLVER  (§15 — minimal read-only adapter)
# ==========================================================

class RenderRevisionBaseResolverV1:
    """Minimal, read-only base-render resolver.

    Responsibilities (only):
      - current active render
      - previous render
      - option index lookup
      - explicit render_id lookup

    No persistence redesign.  Never invents a render id / hash / index.
    """

    VERSION = VERSION

    def __init__(self):
        print("🎯 RENDER REVISION BASE RESOLVER v1.0 ONLINE (read-only)")

    # ------------------------------------------------------
    # helpers
    # ------------------------------------------------------

    @staticmethod
    def _entry(raw, position):
        if not isinstance(raw, dict):
            return None
        return {
            "render_id": raw.get("render_id") or raw.get("id"),
            "render_hash": raw.get("render_hash") or raw.get("hash"),
            "render_index": raw.get("render_index", position + 1),
            "reference": (
                raw.get("reference")
                or raw.get("asset")
                or raw.get("path")
                or raw.get("filename")
            ),
        }

    @classmethod
    def _history(cls, render_state):
        history = render_state.get("render_history")
        if not isinstance(history, (list, tuple)):
            return []
        out = []
        for position, raw in enumerate(history):
            entry = cls._entry(raw, position)
            if entry is not None:
                out.append(entry)
        return out

    @staticmethod
    def _option_index(text):
        lowered = str(text or "").lower()
        has_context = any(word in lowered for word in _OPTION_CONTEXT_WORDS)
        if any(marker in lowered for marker in _LAST_MARKERS):
            return "LAST"
        for word, index in _ORDINALS:
            if word in lowered and (has_context or word in _STRONG_ORDINALS):
                return index
        return None

    @staticmethod
    def _found(entry, source, reason):
        return {
            "status": "RESOLVED",
            "base_render_id": entry.get("render_id"),
            "base_render_hash": entry.get("render_hash"),
            "base_render_index": entry.get("render_index"),
            "base_render_reference": entry.get("reference"),
            "source": source,
            "reason": reason,
            "gaps": [k for k in ("render_id", "render_hash", "render_index", "reference")
                     if entry.get(k) in (None, "", [])],
        }

    @staticmethod
    def _unresolved(status, reason, gaps=None, candidates=None):
        return {
            "status": status,
            "base_render_id": None,
            "base_render_hash": None,
            "base_render_index": None,
            "base_render_reference": None,
            "source": None,
            "reason": reason,
            "gaps": list(gaps or []),
            "candidates": list(candidates or []),
        }

    # ------------------------------------------------------
    # main
    # ------------------------------------------------------

    def resolve(self, render_state, text="", selection=None):
        render_state = render_state if isinstance(render_state, dict) else {}
        selection = selection if isinstance(selection, dict) else {}

        history = self._history(render_state)
        active_id = render_state.get("active_render_id") or selection.get("active_render_id")
        explicit_id = (
            render_state.get("explicit_base_render_id")
            or selection.get("base_render_id")
            or selection.get("render_id")
        )

        by_id = {}
        for entry in history:
            rid = entry.get("render_id")
            if rid not in (None, "", []) and rid not in by_id:
                by_id[rid] = entry

        # -------- explicit render_id lookup --------
        if explicit_id not in (None, "", []):
            entry = by_id.get(explicit_id)
            if entry is None:
                return self._unresolved(
                    "INVALID_BASE_RENDER", "explicit_render_id_unknown",
                    gaps=["render_id"], candidates=sorted(by_id.keys()),
                )
            return self._found(entry, "explicit_render_id", "explicit_id_found")

        # -------- option index lookup --------
        option = self._option_index(text)
        if option is not None:
            if not history:
                return self._unresolved("BASE_RENDER_REQUIRED", "no_render_history", gaps=["render_history"])
            if option == "LAST":
                return self._found(history[-1], "selected_option", "last_option")
            if option < 1 or option > len(history):
                return self._unresolved(
                    "INVALID_BASE_RENDER", "option_index_out_of_range",
                    gaps=["render_index"], candidates=list(range(1, len(history) + 1)),
                )
            return self._found(history[option - 1], "selected_option", f"option_{option}")

        lowered = str(text or "").lower()

        # -------- previous render --------
        if any(marker in lowered for marker in _PREVIOUS_MARKERS):
            if len(history) < 2:
                return self._unresolved("BASE_RENDER_REQUIRED", "previous_render_not_unique", gaps=["render_history"])
            return self._found(history[-2], "previous_turn", "previous_render")

        # -------- current active render --------
        if active_id not in (None, "", []):
            if history and active_id not in by_id:
                return self._unresolved(
                    "INVALID_BASE_RENDER", "active_render_id_not_in_history",
                    gaps=["render_id"], candidates=sorted(by_id.keys()),
                )
            if active_id in by_id:
                return self._found(by_id[active_id], "active_render", "active_render_in_history")
            # history empty: accept the declared active render (ids read, never invented)
            asset = render_state.get("last_render_asset")
            reference = None
            if isinstance(asset, dict):
                reference = asset.get("filename") or asset.get("path")
            return self._found(
                {"render_id": active_id, "render_hash": render_state.get("active_render_hash"),
                 "render_index": render_state.get("active_render_index"), "reference": reference},
                "active_render", "active_render_declared",
            )

        if history:
            return self._found(history[-1], "active_render", "latest_history_entry")

        # -------- nothing to bind to --------
        asset = render_state.get("last_render_asset")
        if isinstance(asset, dict) and (asset.get("filename") or asset.get("path")):
            return self._found(
                {"render_id": None, "render_hash": None, "render_index": None,
                 "reference": asset.get("filename") or asset.get("path")},
                "active_render", "last_render_asset_only",
            )

        return self._unresolved("BASE_RENDER_REQUIRED", "no_active_render", gaps=["active_render", "render_history"])


# ==========================================================
# BUILDER
# ==========================================================

class RenderRevisionDeltaBuilderV1:

    VERSION = VERSION

    def __init__(self):
        self.resolver = RenderRevisionBaseResolverV1()
        print("🎨 RENDER REVISION DELTA BUILDER v1.0 ONLINE (semantic delta only)")

    # ------------------------------------------------------
    # design-revision detection (2D-6 reuse + 2D-7 extension)
    # ------------------------------------------------------

    @staticmethod
    def detect_design_revision(text):
        lowered = str(text or "").lower()
        if not lowered:
            return []
        found = list(ApprovedDesignRenderContractBuilder._detect_design_revision(text))

        # entrance geometry (appearance/emphasis wording excluded)
        if any(noun in lowered for noun in _ENTRANCE_NOUNS):
            if any(v in lowered for v in _GEOMETRY_VERBS):
                if not any(x in lowered for x in _APPEARANCE_EXCLUSIONS):
                    if any(m in lowered for m in _MOVE_VERBS):
                        found.append("move_entrance")
                    else:
                        found.append("resize_entrance")

        # balcony geometry
        if any(noun in lowered for noun in _BALCONY_NOUNS):
            if any(v in lowered for v in _GEOMETRY_VERBS):
                if not any(x in lowered for x in _APPEARANCE_EXCLUSIONS):
                    found.append("resize_balcony")

        # building proportions
        if any(term in lowered for term in _BUILDING_TERMS):
            if any(term in lowered for term in _PROPORTION_TERMS):
                found.append("change_building_proportions")

        canonical = list(FORBIDDEN_GEOMETRY_CHANGES) + [
            "resize_entrance", "move_entrance", "resize_balcony", "change_building_proportions",
        ]
        ordered = []
        for token in canonical:
            if token in found and token not in ordered:
                ordered.append(token)
        return ordered

    # ------------------------------------------------------
    # small helpers
    # ------------------------------------------------------

    @staticmethod
    def _intensity(understanding):
        return ((understanding or {}).get("intensity") or {}).get("level") or "MEDIUM"

    @staticmethod
    def _has_any(text, words):
        return any(word in text for word in words)

    @staticmethod
    def _direction_from_text(text):
        if any(marker in text for marker in _DECREASE_MARKERS):
            return "decrease"
        if any(marker in text for marker in _INCREASE_MARKERS):
            return "increase"
        return None

    # ------------------------------------------------------
    # typed deltas
    # ------------------------------------------------------

    def _material_delta(self, understanding, text):
        materials = (understanding or {}).get("materials") or {}
        primary = materials.get("primary")
        if not primary:
            return {}, None

        tone = materials.get("tone")
        direction = materials.get("tone_direction")

        if not tone:
            for canon, phrases in _DIRECT_TONE:
                if any(phrase in text for phrase in phrases):
                    tone = canon
                    direction = "increase"
                    break

        if direction == "decrease" and not tone:
            tone_direction = TONE_LESS
        elif tone:
            tone_direction = _TONE_CANONICAL.get(tone, TONE_MORE)
        elif direction == "increase":
            tone_direction = TONE_MORE
        elif "کمتر" in text:
            tone_direction = TONE_LESS
        else:
            tone_direction = TONE_MORE

        # 2D7_LOCAL_COMPATIBILITY_GUARD — a directly negated comparative tone
        # ("سنگش روشن‌تر نشه") must not become a positive tone delta.
        if tone and self._negated_comparative_in_place(text, _DIRECT_TONE_MAP.get(tone, ())):
            return {}, None

        delta = {
            "material": primary,
            "tone": tone,
            "tone_direction": tone_direction,
            "intensity": self._intensity(understanding),
            "operation": OP_SET_MATERIAL_TONE if tone else OP_SET_MATERIAL,
        }
        return delta, {
            "operation": delta["operation"],
            "target": "material",
            "attribute": "tone" if tone else "presence",
            "material": primary,
            "value": tone_direction,
            "direction": "set",
            "revision_type": RT_MATERIAL_TONE_CHANGE if tone else RT_MATERIAL_CHANGE,
            "intensity": delta["intensity"],
        }

    @staticmethod
    def _negated_comparative_in_place(text, forms):
        """2D7_LOCAL_COMPATIBILITY_GUARD — deterministic in-place negation scan.

        Returns True when one of ``forms`` (a comparative marker such as
        "بیشتر" / "روشن‌تر") is DIRECTLY negated in place ("بیشتر نشن",
        "روشن‌تر نشه").  Only the marker's immediate tail is inspected, so an
        unrelated negative clause elsewhere in the sentence cannot trigger it.
        """
        for form in forms:
            start = 0
            while True:
                idx = text.find(form, start)
                if idx < 0:
                    break
                tail = text[idx + len(form): idx + len(form) + 8]
                tail = tail.replace("\u200c", " ").lstrip()
                if any(tail.startswith(neg) for neg in _NEGATION_TAIL):
                    return True
                start = idx + len(form)
        return False

    @staticmethod
    def _style_negated_in_place(text, canonical):
        """True when the comparative style form is directly negated
        ("مدرن‌تر نشه") — an in-place refusal, not an increase request."""
        for phrase in _STYLE_DIRECT_MAP.get(canonical, ()):
            found = re.search(re.escape(phrase) + r"[\u200c\s]*تر", text)
            if not found:
                continue
            tail = text[found.end():found.end() + 8].lstrip()
            if any(tail.startswith(neg) for neg in _NEGATION_TAIL):
                return True
        return False

    def _style_delta(self, understanding, text):
        style = (understanding or {}).get("style") or {}
        target = style.get("target")
        direction = style.get("direction")
        recovered_by = None

        if target and self._style_negated_in_place(text, target):
            return {}, None

        if not target:
            # supplement: explicit comparative style form not negated in place
            # (2D-2's negation window may drop a style whose negative clause is
            #  unrelated, e.g. "لوکس‌ترش کن ولی شلوغ نشه").
            for canon, phrases in _STYLE_DIRECT:
                matched = None
                for phrase in phrases:
                    found = re.search(re.escape(phrase) + r"[\u200c\s]*تر", text)
                    if found:
                        matched = found
                        break
                if not matched:
                    continue
                tail = text[matched.end():matched.end() + 8].lstrip()
                if any(tail.startswith(neg) for neg in _NEGATION_TAIL):
                    continue
                target = canon
                direction = "increase"
                recovered_by = "2D7_STYLE_DIRECT_SCAN"
                break

        if not target:
            return {}, None

        if not direction:
            direction = self._direction_from_text(text)
        if not direction:
            direction = "increase"

        delta = {
            "target": target,
            "direction": direction,
            "intensity": self._intensity(understanding),
            "mix": list(style.get("mix") or []),
            "negative_constraints": list((understanding or {}).get("negative_constraints") or []),
        }
        if recovered_by:
            # provenance for the narrow 2D-7 supplemental scan (subordinate to 2D-2)
            delta["recovered_by"] = recovered_by
            delta["recovery_scope"] = "2D7_LOCAL_COMPATIBILITY_GUARD"
        return delta, {
            "operation": OP_ADJUST_STYLE,
            "target": "style",
            "attribute": "style",
            "style": target,
            "value": direction,
            "direction": direction,
            "revision_type": RT_STYLE_REFINEMENT,
            "intensity": delta["intensity"],
        }

    def _window_frame_delta(self, understanding, text, targets):
        if "window_frame" not in targets:
            return {}, None
        materials = (understanding or {}).get("materials") or {}
        tone = materials.get("tone")
        if not tone:
            for canon, phrases in _DIRECT_TONE:
                if any(phrase in text for phrase in phrases):
                    tone = canon
                    break
        direction = self._direction_from_text(text)
        if not tone and not direction:
            return {}, None
        tone_direction = _TONE_CANONICAL.get(tone) if tone else (
            TONE_LESS if direction == "decrease" else TONE_MORE
        )
        delta = {
            "tone": tone,
            "tone_direction": tone_direction,
            "intensity": self._intensity(understanding),
        }
        return delta, {
            "operation": OP_SET_WINDOW_FRAME_EXPRESSION,
            "target": "window_frame",
            "attribute": "colour",
            "value": tone_direction,
            "direction": "set",
            "revision_type": RT_WINDOW_FRAME_EXPRESSION_CHANGE,
            "intensity": delta["intensity"],
        }

    def _colour_delta(self, understanding, text, targets, has_material, has_window_frame):
        if has_material or has_window_frame:
            return {}, None
        materials = (understanding or {}).get("materials") or {}
        tone = materials.get("tone")
        if not tone and "facade" not in targets:
            return {}, None
        if not tone:
            return {}, None
        # 2D7_LOCAL_COMPATIBILITY_GUARD — a directly negated comparative tone
        # must not leak into a colour delta when the material delta is suppressed.
        if self._negated_comparative_in_place(text, _DIRECT_TONE_MAP.get(tone, ())):
            return {}, None
        delta = {
            "tone": tone,
            "tone_direction": _TONE_CANONICAL.get(tone, TONE_MORE),
            "intensity": self._intensity(understanding),
        }
        return delta, {
            "operation": OP_SET_COLOUR,
            "target": "colour",
            "attribute": "tone",
            "value": delta["tone_direction"],
            "direction": "set",
            "revision_type": RT_COLOUR_CHANGE,
            "intensity": delta["intensity"],
        }

    def _lighting_delta(self, understanding, text, targets):
        has_lighting_word = self._has_any(text, _LIGHTING_WORDS) or "lighting" in targets
        time_of_day = None
        for canon, phrases in _TIME_OF_DAY:
            if any(phrase in text for phrase in phrases):
                time_of_day = canon
                break
        direction = None
        negated_illumination = False
        if any(phrase in text for phrase in ("روشن‌تر", "روشنتر", "brighter", "روشن تر")):
            direction = "brighter"
            # 2D7_LOCAL_COMPATIBILITY_GUARD — "نور روشن‌تر نشه" is a refusal.
            if self._negated_comparative_in_place(text, ("روشن‌تر", "روشنتر", "روشن تر")):
                direction = None
                negated_illumination = True
        elif any(phrase in text for phrase in ("تیره‌تر", "تیرهتر", "dimmer", "تیره تر")):
            direction = "dimmer"
            if self._negated_comparative_in_place(text, ("تیره‌تر", "تیرهتر", "تیره تر")):
                direction = None
                negated_illumination = True

        if not (has_lighting_word or time_of_day):
            return {}, None
        if negated_illumination and not time_of_day:
            return {}, None

        delta = {
            "time_of_day": time_of_day,
            "direction": direction,
            "intensity": self._intensity(understanding),
        }
        return delta, {
            "operation": OP_SET_LIGHTING,
            "target": "lighting",
            "attribute": "time_of_day" if time_of_day else "illumination",
            "value": time_of_day or direction,
            "direction": "set",
            "revision_type": RT_LIGHTING_CHANGE,
            "intensity": delta["intensity"],
        }

    def _camera_delta(self, understanding, text):
        if not self._has_any(text, _CAMERA_WORDS):
            return {}, None
        direction = None
        for canon, phrases in _CAMERA_DIRECTIONS:
            if any(phrase in text for phrase in phrases):
                direction = canon
                break
        delta = {"direction": direction, "intensity": self._intensity(understanding)}
        return delta, {
            "operation": OP_SET_CAMERA,
            "target": "camera",
            "attribute": "presentation",
            "value": direction,
            "direction": "set",
            "revision_type": RT_CAMERA_PRESENTATION_CHANGE,
            "intensity": delta["intensity"],
        }

    def _entrance_delta(self, understanding, targets):
        entrance = (understanding or {}).get("entrance") or {}
        emphasis = entrance.get("emphasis")
        if "entrance" not in targets or not emphasis:
            return {}, None
        delta = {"emphasis": emphasis, "mode": "PRESENTATION"}
        return delta, {
            "operation": OP_ADJUST_ENTRANCE_EMPHASIS,
            "target": "entrance",
            "attribute": "emphasis",
            "value": emphasis,
            "direction": emphasis,
            "revision_type": RT_ENTRANCE_EMPHASIS_CHANGE,
            "intensity": self._intensity(understanding),
        }

    def _arch_delta(self, understanding, targets, text):
        arches = (understanding or {}).get("arches") or {}
        direction = arches.get("direction")
        if "arches" not in targets or not direction:
            return {}, None
        # 2D7_LOCAL_COMPATIBILITY_GUARD — a directly negated comparative
        # ("قوس‌ها بیشتر نشن") must not become an increase delta.
        if direction == "increase" and self._negated_comparative_in_place(text, _ARCH_INCREASE_FORMS):
            return {}, None
        delta = {"direction": direction, "intensity": self._intensity(understanding)}
        return delta, {
            "operation": OP_ADJUST_ARCH_INTENSITY,
            "target": "arches",
            "attribute": "intensity",
            "value": direction,
            "direction": direction,
            "revision_type": RT_ARCH_INTENSITY_CHANGE,
            "intensity": delta["intensity"],
        }

    def _ornament_delta(self, understanding, text):
        negatives = [c.get("constraint") for c in ((understanding or {}).get("negative_constraints") or [])]
        wants_reduction = (
            self._has_any(text, _ORNAMENT_WORDS)
            and self._has_any(text, _DECREASE_MARKERS)
        ) or any(n in ("avoid_heavy_ornament", "avoid_excessive_ornament") for n in negatives)
        if not wants_reduction:
            return {}, None
        delta = {"direction": "decrease", "intensity": self._intensity(understanding)}
        return delta, {
            "operation": OP_ADJUST_ORNAMENT,
            "target": "ornament",
            "attribute": "level",
            "value": "decrease",
            "direction": "decrease",
            "revision_type": RT_ORNAMENT_REDUCTION,
            "intensity": delta["intensity"],
        }

    def _balcony_expression_delta(self, understanding, targets, text):
        if "balconies" not in targets:
            return {}, None
        if not (self._has_any(text, _RAILING_WORDS) or self._has_any(text, ("ظریف", "ساده"))):
            return {}, None
        delta = {"expression": "lighter", "intensity": self._intensity(understanding)}
        return delta, {
            "operation": OP_SET_BALCONY_RAILING_EXPRESSION,
            "target": "balconies",
            "attribute": "railing_expression",
            "value": "lighter",
            "direction": "decrease",
            "revision_type": RT_BALCONY_RAILING_EXPRESSION_CHANGE,
            "intensity": delta["intensity"],
        }

    def _facade_depth_delta(self, understanding, text, targets):
        if "facade" not in targets and not self._has_any(text, _FACADE_DEPTH_WORDS):
            return {}, None
        if not self._has_any(text, ("عمق", "depth")):
            return {}, None
        direction = "increase" if self._has_any(text, _DEPTH_MORE) else "decrease"
        delta = {"depth": direction, "intensity": self._intensity(understanding)}
        return delta, {
            "operation": OP_ADJUST_FACADE_DEPTH,
            "target": "facade",
            "attribute": "depth",
            "value": direction,
            "direction": direction,
            "revision_type": RT_FACADE_DEPTH_VISUAL_CHANGE,
            "intensity": delta["intensity"],
        }

    def _landscape_delta(self, understanding, text):
        if not self._has_any(text, _LANDSCAPE_WORDS):
            return {}, None
        delta = {"presentation": "adjust", "intensity": self._intensity(understanding)}
        return delta, {
            "operation": OP_SET_LANDSCAPE,
            "target": "landscape",
            "attribute": "presentation",
            "value": "adjust",
            "direction": "set",
            "revision_type": RT_LANDSCAPE_PRESENTATION_CHANGE,
            "intensity": delta["intensity"],
        }

    # ------------------------------------------------------
    # reference delta  (§19)
    # ------------------------------------------------------

    def _reference_delta(self, understanding, text, context, contract):
        lowered = str(text or "").lower()
        policy = (understanding or {}).get("reference_image_policy") or {}
        active_reference_id = context.get("active_reference_id")
        mentions_reference = self._has_any(lowered, _REFERENCE_WORDS)
        mentions_style_only = self._has_any(lowered, ("سبک", "style"))

        action = "NONE"
        role = None

        if mentions_reference:
            if self._has_any(lowered, _REFERENCE_DISABLE):
                action = "DISABLE"
            elif self._has_any(lowered, _REFERENCE_COLOUR_ROLE):
                action = "SET_ROLE"
                role = "colour_only"
            elif self._has_any(lowered, _REFERENCE_STYLE_DISABLE):
                action = "SET_ROLE"
                role = "style_disabled"
            elif "متریال" in lowered:
                action = "SET_ROLE"
                role = "material_only"
            elif mentions_style_only and ("نگیر" in lowered or "نباشه" in lowered):
                action = "SET_ROLE"
                role = "style_disabled"
        elif mentions_style_only and active_reference_id and self._has_any(lowered, ("نگیر", "نکن")):
            action = "SET_ROLE"
            role = "style_disabled"

        if action == "NONE":
            return {}, None

        delta = {
            "action": action,
            "role": role,
            "source_reference_id": active_reference_id,
            "requested_by_text": bool(mentions_reference),
            "pixel_analysis": False,
        }
        if action == "DISABLE":
            delta["effective_reference_policy"] = {
                "referenced": False,
                "role": "none",
                "reason": "user_disabled_reference",
            }
        elif role == "style_disabled":
            delta["effective_reference_policy"] = {
                "referenced": True,
                "role": "material_or_colour_only",
                "style_transfer": False,
                "reason": "user_disabled_reference_style",
            }
        else:
            delta["effective_reference_policy"] = {
                "referenced": True,
                "role": role,
                "reason": "user_set_reference_role",
            }

        op = {
            "operation": OP_SET_REFERENCE_USAGE,
            "target": "reference",
            "attribute": "usage",
            "value": role or action,
            "direction": "set",
            "revision_type": RT_REFERENCE_USAGE_CHANGE,
            "intensity": self._intensity(understanding),
        }
        return delta, op

    # ------------------------------------------------------
    # preserve  (§10)
    # ------------------------------------------------------

    def _preserve(self, understanding, text, contract, changed_fields):
        preserve_all = self._has_any(text, _PRESERVE_ALL_MARKERS)
        if "همین" in text and "فقط" in text:
            preserve_all = True
        if ("هیچی" in text or "هیچ چی" in text) and ("عوض" in text or "تغییر" in text) and (
            "نکن" in text or "نشه" in text
        ):
            preserve_all = True

        constraints = {}
        for source in (DEFAULT_PRESERVE, contract.get("preserve_constraints") or {},
                       (understanding or {}).get("preserve_constraints") or {}):
            for field, value in source.items():
                if field in ("explicit", "scope_unspecified"):
                    continue
                if value is True:
                    constraints[field] = True

        for field, markers in _PRESERVE_FIELDS_MARKERS.items():
            if self._has_any(text, markers):
                constraints[field] = True

        if preserve_all:
            for field in _GEOMETRY_PRESERVE_FIELDS:
                constraints[field] = True

        fields = sorted(constraints.keys())
        return fields, constraints, preserve_all

    # ------------------------------------------------------
    # ambiguity resolution for bare tone  (§13)
    # ------------------------------------------------------

    def _bare_tone(self, understanding, text, targets):
        materials = (understanding or {}).get("materials") or {}
        if materials.get("primary"):
            return None
        if "window_frame" in targets:
            return None
        if self._has_any(text, _LIGHTING_WORDS):
            return None
        if self._has_any(text, _CAMERA_WORDS):
            return None

        tone = materials.get("tone")
        direction = materials.get("tone_direction")
        if not tone and not direction:
            for canon, phrases in _DIRECT_TONE:
                if any(phrase in text for phrase in phrases):
                    tone = canon
                    direction = "increase"
                    break
        if not tone and not direction:
            return None
        return {"tone": tone, "direction": direction}

    def _resolve_bare_tone(self, tone_info, context, prior_revision):
        candidates = []

        active_targets = list(context.get("active_targets") or [])
        if context.get("active_target"):
            active_targets.append(context["active_target"])
        active_materials = context.get("active_materials") or {}
        active_elements = context.get("active_elements") or {}

        if active_materials.get("primary"):
            candidates.append(("material", "active_target", active_materials["primary"]))
        for target in active_targets:
            if target in _MATERIAL_TARGET_TOKENS:
                candidates.append(("material", "active_target", target))
            if target == "lighting":
                candidates.append(("lighting", "active_target", "lighting"))
        if active_elements.get("lighting") or active_elements.get("time_of_day"):
            candidates.append(("lighting", "active_target", "lighting"))

        previous_target = context.get("previous_turn_target")
        if previous_target in _MATERIAL_TARGET_TOKENS:
            candidates.append(("material", "previous_turn", previous_target))
        if previous_target == "lighting":
            candidates.append(("lighting", "previous_turn", "lighting"))

        if isinstance(prior_revision, dict):
            for op in prior_revision.get("delta_operations") or []:
                if op.get("target") == "material" and op.get("material"):
                    candidates.append(("material", "previous_turn", op["material"]))
                if op.get("target") == "lighting":
                    candidates.append(("lighting", "previous_turn", "lighting"))

        unique = {}
        for kind, source, value in candidates:
            if kind not in unique:
                unique[kind] = (source, value)

        if len(unique) == 1:
            kind = next(iter(unique))
            source, value = unique[kind]
            return kind, value, source, None
        if len(unique) > 1:
            return None, None, None, {
                "type": "ambiguous_revision_target",
                "reason": "multiple_plausible_targets",
                "candidates": sorted(unique.keys()),
            }
        return None, None, None, {
            "type": "ambiguous_revision_target",
            "reason": "no_unique_target",
            "candidates": ["lighting", "material"],
        }

    # ------------------------------------------------------
    # main
    # ------------------------------------------------------

    def build(self, approved_render_contract, understanding=None, render_state=None,
              context=None, prior_revision=None, selection=None, session_id=None):
        context = context if isinstance(context, dict) else {}
        render_state = render_state if isinstance(render_state, dict) else {}

        warnings = []
        required_context = []
        conflicts = []
        ambiguities = []
        resolutions = []

        # normalize understanding (accept a raw string for convenience)
        u = understanding
        if isinstance(u, str):
            from core.prompt_intelligence.persian_architectural_understanding import understand as _understand
            u = _understand(u)
        u = u if isinstance(u, dict) else {}

        text = str(u.get("normalized_text") or u.get("raw_text") or "")
        targets = list(u.get("targets") or [])

        contract = approved_render_contract if isinstance(approved_render_contract, dict) else {}

        # -------- §20 approved-design gate (never inferred) --------
        if not contract:
            return self._empty(
                STATUS_APPROVAL_REQUIRED, contract,
                warnings=[{"code": "NO_APPROVED_DESIGN_CONTRACT"}],
                required_context=["approved_design_contract"],
                reason="no_approved_design_contract",
            )

        contract_status = contract.get("status")
        if contract_status in (STATUS_APPROVAL_REQUIRED, "NO_APPROVED_DESIGN",
                               "INVALID_APPROVAL", "DESIGN_LINEAGE_INCOMPLETE"):
            return self._empty(
                STATUS_APPROVAL_REQUIRED, contract,
                warnings=[{"code": "APPROVED_DESIGN_NOT_AVAILABLE", "contract_status": contract_status}],
                required_context=["approved_design_contract"],
                reason="approved_design_not_available",
            )

        if contract_status == STATUS_DESIGN_REVISION_REQUIRED:
            return self._empty(
                STATUS_DESIGN_REVISION_REQUIRED, contract,
                warnings=[{"code": "DESIGN_REVISION_REQUIRED",
                           "forbidden_changes": contract.get("forbidden_geometry_changes") or []}],
                forbidden=contract.get("forbidden_geometry_changes") or list(FORBIDDEN_GEOMETRY_CHANGES),
                reason="upstream_design_revision_required",
            )

        # -------- §12 design-revision gate --------
        forbidden = self.detect_design_revision(text)
        if forbidden:
            return self._empty(
                STATUS_DESIGN_REVISION_REQUIRED, contract,
                warnings=[{"code": "DESIGN_REVISION_REQUIRED", "forbidden_changes": forbidden}],
                forbidden=forbidden,
                reason="design_level_change_requested",
            )

        # -------- typed deltas + operations --------
        ops = []
        typed = {
            "style_delta": {}, "material_delta": {}, "colour_delta": {},
            "lighting_delta": {}, "camera_delta": {}, "entrance_delta": {},
            "ornament_delta": {}, "arch_delta": {}, "window_frame_delta": {},
            "balcony_expression_delta": {}, "facade_delta": {}, "landscape_delta": {},
            "reference_delta": {},
        }
        context_resolutions = []

        material_delta, material_op = self._material_delta(u, text)
        if material_delta:
            typed["material_delta"] = material_delta
            ops.append(material_op)

        window_frame_delta, window_frame_op = self._window_frame_delta(u, text, targets)
        if window_frame_delta:
            typed["window_frame_delta"] = window_frame_delta
            ops.append(window_frame_op)

        colour_delta, colour_op = self._colour_delta(u, text, targets, bool(material_delta), bool(window_frame_delta))
        if colour_delta:
            typed["colour_delta"] = colour_delta
            ops.append(colour_op)

        style_delta, style_op = self._style_delta(u, text)
        if style_delta:
            typed["style_delta"] = style_delta
            ops.append(style_op)

        lighting_delta, lighting_op = self._lighting_delta(u, text, targets)
        if lighting_delta:
            typed["lighting_delta"] = lighting_delta
            ops.append(lighting_op)

        camera_delta, camera_op = self._camera_delta(u, text)
        if camera_delta:
            typed["camera_delta"] = camera_delta
            ops.append(camera_op)

        entrance_delta, entrance_op = self._entrance_delta(u, targets)
        if entrance_delta:
            typed["entrance_delta"] = entrance_delta
            ops.append(entrance_op)

        arch_delta, arch_op = self._arch_delta(u, targets, text)
        if arch_delta:
            typed["arch_delta"] = arch_delta
            ops.append(arch_op)

        ornament_delta, ornament_op = self._ornament_delta(u, text)
        if ornament_delta:
            typed["ornament_delta"] = ornament_delta
            ops.append(ornament_op)

        balcony_delta, balcony_op = self._balcony_expression_delta(u, targets, text)
        if balcony_delta:
            typed["balcony_expression_delta"] = balcony_delta
            ops.append(balcony_op)

        facade_delta, facade_op = self._facade_depth_delta(u, text, targets)
        if facade_delta:
            typed["facade_delta"] = facade_delta
            ops.append(facade_op)

        landscape_delta, landscape_op = self._landscape_delta(u, text)
        if landscape_delta:
            typed["landscape_delta"] = landscape_delta
            ops.append(landscape_op)

        reference_delta, reference_op = self._reference_delta(u, text, context, contract)
        if reference_delta:
            typed["reference_delta"] = reference_delta
            ops.append(reference_op)

        # -------- bare tone ambiguity (§13) --------
        tone_info = self._bare_tone(u, text, targets)
        resolved_target = None
        if tone_info:
            kind, value, source, ambiguity = self._resolve_bare_tone(tone_info, context, prior_revision)
            if ambiguity:
                ambiguities.append(ambiguity)
            elif kind == "material":
                tone_direction = _TONE_CANONICAL.get(tone_info.get("tone"), TONE_MORE)
                typed["material_delta"] = {
                    "material": value,
                    "tone": tone_info.get("tone"),
                    "tone_direction": tone_direction,
                    "intensity": self._intensity(u),
                    "operation": OP_SET_MATERIAL_TONE,
                    "resolved_from_context": True,
                    "resolution_source": source,
                }
                ops.append({
                    "operation": OP_SET_MATERIAL_TONE,
                    "target": "material",
                    "attribute": "tone",
                    "material": value,
                    "value": tone_direction,
                    "direction": "set",
                    "revision_type": RT_MATERIAL_TONE_CHANGE,
                    "intensity": self._intensity(u),
                    "resolved_from_context": True,
                    "resolution_source": source,
                })
                resolved_target = f"material:{value}"
                context_resolutions.append({
                    "target": resolved_target, "source": source, "reason": "bare_tone_resolved",
                })
            elif kind == "lighting":
                direction = "brighter" if _TONE_CANONICAL.get(tone_info.get("tone")) == TONE_LIGHTER else "dimmer"
                typed["lighting_delta"] = {
                    "time_of_day": None,
                    "direction": direction,
                    "intensity": self._intensity(u),
                    "resolved_from_context": True,
                    "resolution_source": source,
                }
                ops.append({
                    "operation": OP_SET_LIGHTING,
                    "target": "lighting",
                    "attribute": "illumination",
                    "value": direction,
                    "direction": "set",
                    "revision_type": RT_LIGHTING_CHANGE,
                    "intensity": self._intensity(u),
                    "resolved_from_context": True,
                    "resolution_source": source,
                })
                resolved_target = "lighting"
                context_resolutions.append({
                    "target": "lighting", "source": source, "reason": "bare_tone_resolved",
                })

        # -------- preserve (§10) --------
        changed_fields = {
            op.get("target") for op in ops
            if op.get("target") in ("material", "style", "geometry", "plan", "massing", "windows")
        }
        preserve_fields, preserve_constraints, preserve_all = self._preserve(
            u, text, contract, changed_fields
        )

        # -------- revision intent --------
        selection_intent = bool(
            RenderRevisionBaseResolverV1._option_index(text) is not None
            or self._has_any(text, _PREVIOUS_MARKERS)
            or self._has_any(text, _CURRENT_MARKERS)
            or self._has_any(text, ("گزینه", "option", "variant", "انتخاب"))
        )
        has_intent = (
            bool(ops)
            or bool(ambiguities)
            or preserve_all
            or selection_intent
            or bool([c for c in ((u.get("preserve_constraints") or {}).items()) if c[1] is True])
        )
        if not has_intent:
            return self._empty(
                STATUS_NO_RENDER_REVISION_INTENT, contract,
                warnings=[{"code": "NO_RENDER_REVISION_INTENT"}],
                reason="no_revision_intent",
            )

        # -------- base render resolution (§3 / §26) --------
        base = self.resolver.resolve(render_state, text, selection)
        if base["status"] == "INVALID_BASE_RENDER":
            return self._empty(
                STATUS_INVALID_BASE_RENDER, contract, base=base,
                warnings=[{"code": "INVALID_BASE_RENDER", "reason": base.get("reason"),
                           "candidates": base.get("candidates") or []}],
                required_context=["valid_base_render"],
                reason=base.get("reason") or "invalid_base_render",
            )
        if base["status"] != "RESOLVED":
            return self._empty(
                STATUS_BASE_RENDER_REQUIRED, contract, base=base,
                warnings=[{"code": "BASE_RENDER_REQUIRED", "reason": base.get("reason")}],
                required_context=["base_render"] + list(base.get("gaps") or []),
                reason=base.get("reason") or "base_render_required",
            )

        # -------- ambiguity (§13) --------
        if ambiguities:
            return self._empty(
                STATUS_AMBIGUOUS_REVISION_TARGET, contract, base=base,
                warnings=[{"code": "AMBIGUOUS_REVISION_TARGET"}],
                ambiguities=ambiguities,
                required_context=["revision_target"],
                reason="ambiguous_revision_target",
            )

        # -------- prior-revision override (§11) --------
        if isinstance(prior_revision, dict) and prior_revision.get("delta_operations"):
            prior_ops = list(prior_revision.get("delta_operations") or [])

            def key(op):
                return (op.get("target"), op.get("attribute"), op.get("revision_type"))

            new_keys = {key(op) for op in ops}
            carried, overridden = [], []
            for op in prior_ops:
                if key(op) in new_keys:
                    overridden.append({
                        **op,
                        "overridden_by": "latest_explicit_delta",
                        "override_source": "current_turn",
                    })
                else:
                    carried.append({**op, "carried_from": "prior_revision"})
            if overridden:
                ops = carried + ops
                warnings.append({"code": "EXPLICIT_DELTA_OVERRIDE", "count": len(overridden)})
                resolutions.append({
                    "resolution": "latest_explicit_delta_wins",
                    "overridden_count": len(overridden),
                })
        else:
            overridden = []

        # -------- §20 validation against allowed render changes --------
        allowed = list(contract.get("allowed_render_changes") or DEFAULT_ALLOWED_RENDER_CHANGES)
        for op in ops:
            category = REVISION_TYPE_TO_ALLOWED.get(op.get("revision_type"))
            if category is None:
                continue
            if category not in allowed:
                warnings.append({
                    "code": "REVISION_TYPE_NOT_ALLOWED",
                    "revision_type": op.get("revision_type"),
                    "category": category,
                })

        # -------- §19 reference conflict --------
        policy = u.get("reference_image_policy") or {}
        if policy.get("copy_reference_geometry"):
            conflicts.append({
                "code": "REFERENCE_GEOMETRY_COPY_REQUESTED",
                "resolution": "approved_design_authoritative",
            })

        # -------- §4 approved design authority / §15 base render drift --------
        approved_floor_count = context.get("approved_floor_count")
        observed_floor_count = render_state.get("base_render_observed_floor_count")
        drift = {
            "detected": bool(
                isinstance(approved_floor_count, int)
                and isinstance(observed_floor_count, int)
                and approved_floor_count != observed_floor_count
            ),
            "approved_floor_count": approved_floor_count,
            "base_render_observed_floor_count": observed_floor_count,
            "preserved": False,
            "resolution": "approved_design_authoritative",
        }
        if drift["detected"]:
            warnings.append({"code": "BASE_RENDER_VISUAL_DRIFT", "detail": "base_render_not_geometry_authority"})

        authority = {
            "authoritative_geometry_source": contract.get("authoritative_geometry_source") or "APPROVED_DESIGN",
            "approved_design_id": contract.get("approved_design_id"),
            "approved_candidate_id": contract.get("approved_candidate_id"),
            "approved_candidate_hash": contract.get("approved_candidate_hash"),
            "base_render_is_authority": False,
            "base_render_is_appearance_reference_only": True,
            "priority_order": [
                "approved_design",
                "hard_preserve_constraints",
                "render_revision_delta",
                "previous_render_appearance",
                "reference_image_evidence",
            ],
        }

        # -------- revision scope --------
        if ops and any(op.get("revision_type") != RT_REFERENCE_USAGE_CHANGE for op in ops):
            revision_scope = SCOPE_RENDER_ONLY
        elif typed.get("reference_delta"):
            revision_scope = SCOPE_REFERENCE_ONLY
        else:
            revision_scope = SCOPE_NONE

        # -------- status --------
        status = STATUS_READY_WITH_WARNINGS if warnings else STATUS_READY
        if conflicts:
            status = STATUS_REFERENCE_CONFLICT

        if resolved_target is None and ops:
            resolved_target = ops[0].get("target")

        result = RenderRevisionDeltaV1({
            "contract": CONTRACT,
            "version": VERSION,
            "status": status,
            "revision_status": status,

            "session_id": session_id or context.get("session_id"),
            "approved_design_id": contract.get("approved_design_id"),
            "approved_candidate_id": contract.get("approved_candidate_id"),
            "approved_candidate_hash": contract.get("approved_candidate_hash"),

            "base_render_id": base.get("base_render_id"),
            "base_render_hash": base.get("base_render_hash"),
            "base_render_index": base.get("base_render_index"),
            "base_render_reference": base.get("base_render_reference"),
            "base_render_resolution": base,

            "revision_scope": revision_scope,
            "delta_operations": ops,
            "overridden_operations": overridden,

            "preserve_fields": preserve_fields,
            "preserve_constraints": preserve_constraints,
            "preserve_all_requested": preserve_all,

            "style_delta": typed["style_delta"],
            "material_delta": typed["material_delta"],
            "colour_delta": typed["colour_delta"],
            "lighting_delta": typed["lighting_delta"],
            "camera_delta": typed["camera_delta"],
            "entrance_delta": typed["entrance_delta"],
            "ornament_delta": typed["ornament_delta"],
            "arch_delta": typed["arch_delta"],
            "window_frame_delta": typed["window_frame_delta"],
            "balcony_expression_delta": typed["balcony_expression_delta"],
            "facade_delta": typed["facade_delta"],
            "landscape_delta": typed["landscape_delta"],

            "reference_delta": typed["reference_delta"],

            "design_revision_requests": [],
            "forbidden_changes": list(contract.get("forbidden_geometry_changes") or FORBIDDEN_GEOMETRY_CHANGES),

            "resolved_target": resolved_target,
            "resolved_from_context": context_resolutions,
            "selection_provenance": {
                "source": base.get("source"),
                "reason": base.get("reason"),
                "gaps": base.get("gaps") or [],
            },

            "approved_design_authority": authority,
            "base_render_drift": drift,

            "ambiguities": ambiguities,
            "conflicts": conflicts,
            "warnings": warnings,
            "required_context": sorted(set(required_context)),

            "source_understanding": {
                "contract": u.get("contract"),
                "version": u.get("version"),
                "normalized_text": u.get("normalized_text"),
                "targets": targets,
                "intent_type": u.get("intent_type"),
                "scope": u.get("scope"),
            },

            "provenance": {
                "builder": "RenderRevisionDeltaBuilderV1",
                "builder_version": VERSION,
                "sources": ["approved_design_render_contract"]
                + (["architectural_understanding"] if u else [])
                + (["render_state"] if render_state else [])
                + (["session_context"] if context else [])
                + (["prior_revision"] if isinstance(prior_revision, dict) and prior_revision else []),
                "resolutions": resolutions,
                "built_at": time.time(),
                "semantic_delta_only": True,
                "render_execution": False,
                "design_mutation": False,
            },
        })

        result["delta_hash"] = self._hash(result)
        return result

    # ------------------------------------------------------
    # blocked / empty contract
    # ------------------------------------------------------

    def _empty(self, status, contract, base=None, warnings=None, required_context=None,
               forbidden=None, ambiguities=None, reason=None):
        contract = contract if isinstance(contract, dict) else {}
        base = base or {}
        result = RenderRevisionDeltaV1({
            "contract": CONTRACT,
            "version": VERSION,
            "status": status,
            "revision_status": status,

            "session_id": None,
            "approved_design_id": contract.get("approved_design_id"),
            "approved_candidate_id": contract.get("approved_candidate_id"),
            "approved_candidate_hash": contract.get("approved_candidate_hash"),

            "base_render_id": base.get("base_render_id"),
            "base_render_hash": base.get("base_render_hash"),
            "base_render_index": base.get("base_render_index"),
            "base_render_reference": base.get("base_render_reference"),
            "base_render_resolution": base,

            "revision_scope": SCOPE_DESIGN if status == STATUS_DESIGN_REVISION_REQUIRED else SCOPE_NONE,
            "delta_operations": [],
            "overridden_operations": [],

            "preserve_fields": [],
            "preserve_constraints": {},
            "preserve_all_requested": False,

            "style_delta": {},
            "material_delta": {},
            "colour_delta": {},
            "lighting_delta": {},
            "camera_delta": {},
            "entrance_delta": {},
            "ornament_delta": {},
            "arch_delta": {},
            "window_frame_delta": {},
            "balcony_expression_delta": {},
            "facade_delta": {},
            "landscape_delta": {},

            "reference_delta": {},

            "design_revision_requests": list(forbidden or []),
            "forbidden_changes": list(forbidden or contract.get("forbidden_geometry_changes") or []),

            "resolved_target": None,
            "resolved_from_context": [],
            "selection_provenance": {
                "source": base.get("source"),
                "reason": base.get("reason"),
                "gaps": base.get("gaps") or [],
            },

            "approved_design_authority": {
                "authoritative_geometry_source": contract.get("authoritative_geometry_source"),
                "base_render_is_authority": False,
                "base_render_is_appearance_reference_only": True,
            },
            "base_render_drift": {},

            "ambiguities": list(ambiguities or []),
            "conflicts": [],
            "warnings": list(warnings or []),
            "required_context": sorted(set(required_context or [])),

            "source_understanding": {},

            "provenance": {
                "builder": "RenderRevisionDeltaBuilderV1",
                "builder_version": VERSION,
                "built_at": time.time(),
                "semantic_delta_only": True,
                "blocked": True,
                "reason": reason,
            },
        })
        result["delta_hash"] = self._hash(result)
        return result

    # ------------------------------------------------------
    # deterministic delta hash (§25)
    # ------------------------------------------------------

    @staticmethod
    def _hash(delta):
        payload = {
            k: v for k, v in delta.items()
            if k not in ("delta_hash", "provenance", "warnings", "required_context")
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ==========================================================
# OPTIONAL ADDITIVE PROMPT HINT (§17 — does NOT modify 2D-3)
# ==========================================================

def as_prompt_delta_hint(delta):
    """Optional, read-only projection of a READY delta into minimal English
    instruction hints for FUTURE prompt regeneration (2D-3).

    Does not modify 2D-3 and owns no render prompt.  Returns {} unless the
    delta is READY / READY_WITH_WARNINGS.
    """
    if not isinstance(delta, dict) or delta.get("status") not in (STATUS_READY, STATUS_READY_WITH_WARNINGS):
        return {}

    changes = []
    preserves = []

    for op in delta.get("delta_operations") or []:
        rt = op.get("revision_type")
        target = op.get("target")
        value = op.get("value")
        changes.append(f"{rt}: {target}={value}")
    for field in delta.get("preserve_fields") or []:
        preserves.append(f"Preserve {field}.")

    return {
        "change_instructions": changes,
        "preservation_instructions": preserves,
        "base_render_id": delta.get("base_render_id"),
        "approved_candidate_id": delta.get("approved_candidate_id"),
    }


# ==========================================================
# SINGLETON + CONVENIENCE
# ==========================================================

render_revision_delta = RenderRevisionDeltaBuilderV1()


def build_render_revision_delta(approved_render_contract, understanding=None, render_state=None,
                                context=None, prior_revision=None, selection=None, session_id=None):
    """Module-level convenience wrapper over the canonical builder."""
    return render_revision_delta.build(
        approved_render_contract,
        understanding=understanding,
        render_state=render_state,
        context=context,
        prior_revision=prior_revision,
        selection=selection,
        session_id=session_id,
    )
