# ==========================================================
# ArchitectOS Architectural Conversation Context v1.0
#
# PHASE 2D-4 — MEMORY / CONTEXT REPAIR
#
# ONE canonical session context for multi-turn architectural conversation:
#   - ArchitecturalConversationContextV1   (versioned contract)
#   - ArchitecturalConversationContextMergerV1  (deterministic delta merge)
#   - architectural_conversation_context   (session store singleton)
#
# Deterministic. Session-only. No LLM. No persistent-file writes.
# Does not implement reference-image vision, render, or translation.
# ==========================================================


from __future__ import annotations

import hashlib
import json
import time
import uuid
from copy import deepcopy


CONTRACT = "ArchitecturalConversationContextV1"
VERSION = "1.0"

MAX_RECENT_TURNS = 20
MAX_ACTIVE_TARGETS = 24


class ArchitecturalConversationContextV1(dict):
    """Versioned, dict-compatible session architectural context."""

    CONTRACT = CONTRACT
    VERSION = VERSION


# ==========================================================
# DETERMINISTIC RULES
# ==========================================================

# change target token -> preserve constraint field (same authority as 2D-3)
TARGET_TO_PRESERVE_FIELD = {
    "massing": "massing",
    "geometry": "geometry",
    "windows": "windows",
    "window_frame": "openings",
    "openings": "openings",
    "balconies": "balconies",
    "entrance": "entrance_location",
    "floors": "floor_count",
    "structure": "structure",
    "materials": "material",
    "material": "material",
    "style": "style",
    "facade": "facade",
    "arches": "arches",
    "plan": "geometry",
}

# explicit context-reset signals (new independent design / start over)
RESET_PHRASES = (
    "از اول",
    "دوباره طراحی",
    "start over",
    "from scratch",
    "new design",
    "design a new",
    "طراحی جدید",
    "ویلای جدید",
    "خانه جدید",
    "خونه جدید",
    "ساختمان جدید",
    "پروژه جدید",
    "project جدید",
    "ریست کن",
    "فراموش کن",
)

# modifiers that can be safely resolved against a UNIQUE active target
_TARGETED_EMPHASIS = (
    "قوی‌تر", "قویتر", "شاخص‌تر", "شاخصتر", "برجسته‌تر", "برجستهتر",
)

_PRESERVE_INTERNAL_KEYS = ("explicit", "scope_unspecified")


def _has_architectural_signal(understanding):
    if not isinstance(understanding, dict) or not understanding:
        return False
    if (understanding.get("style") or {}).get("target"):
        return True
    if (understanding.get("materials") or {}).get("primary"):
        return True
    if understanding.get("negative_constraints"):
        return True
    if (understanding.get("reference_image_policy") or {}).get("referenced"):
        return True
    for op in understanding.get("change_operations", []) or []:
        if op.get("operation") != "preserve":
            return True
    preserve = understanding.get("preserve_constraints") or {}
    for key, value in preserve.items():
        if key not in _PRESERVE_INTERNAL_KEYS and value is True:
            return True
    return False


# ==========================================================
# MERGER
# ==========================================================

class ArchitecturalConversationContextMergerV1:

    VERSION = VERSION

    def __init__(self):
        print("🧠 ARCHITECTURAL CONTEXT MERGER v1.0 ONLINE (deterministic)")

    # ------------------------------------------------------
    # reset detection
    # ------------------------------------------------------

    @staticmethod
    def _is_reset(understanding, normalized_text, context):
        context = context or {}
        if context.get("reset") or context.get("new_design"):
            return True
        text = str(normalized_text or "").lower()
        for phrase in RESET_PHRASES:
            if phrase in text:
                return True
        if "جدید" in text and any(
            word in text
            for word in ("طراحی", "بساز", "ویلا", "خانه", "خونه", "ساختمان", "پروژه", "project")
        ):
            return True
        return False

    @staticmethod
    def _changed_preserve_fields(understanding):
        fields = set()
        for op in understanding.get("change_operations", []) or []:
            if op.get("operation") == "preserve":
                continue
            field = TARGET_TO_PRESERVE_FIELD.get(op.get("target"))
            if field:
                fields.add(field)
        return fields

    # ------------------------------------------------------
    # main merge
    # ------------------------------------------------------

    def merge(self, previous, understanding, raw_text="", normalized_text="", context=None):
        context = context or {}
        u = understanding if isinstance(understanding, dict) else {}
        prev = previous if isinstance(previous, dict) else {}

        reset = self._is_reset(u, normalized_text, context)
        has_signal = _has_architectural_signal(u)
        ambiguities = list(u.get("ambiguities") or [])

        resolutions = []
        resolved_from_context = []

        # ---------------- base state ----------------
        if reset:
            prev_scope = None
            prev_style = {}
            prev_materials = {}
            prev_preserve = {}
            prev_negatives = []
            prev_reference = {}
            prev_targets = []
            prev_elements = {}
        else:
            prev_scope = prev.get("active_scope")
            prev_style = deepcopy(prev.get("active_style") or {})
            prev_materials = deepcopy(prev.get("active_materials") or {})
            prev_preserve = {
                k: v for k, v in (prev.get("active_preserve_constraints") or {}).items()
                if v is True and k not in _PRESERVE_INTERNAL_KEYS
            }
            prev_negatives = list(prev.get("active_negative_constraints") or [])
            prev_reference = deepcopy(prev.get("active_reference_policy") or {})
            prev_targets = list(prev.get("active_targets") or [])
            prev_elements = deepcopy(prev.get("active_elements") or {})

        # ---------------- context resolution of ambiguity ----------------
        unique_prev_targets = sorted(set(prev_targets))
        if ambiguities and not has_signal:
            resolvable = [a for a in ambiguities if a.get("modifier") in _TARGETED_EMPHASIS]
            if resolvable and len(unique_prev_targets) == 1:
                target = unique_prev_targets[0]
                u = dict(u)
                u["change_operations"] = list(u.get("change_operations") or []) + [
                    {"operation": "increase", "target": target, "attribute": "emphasis",
                     "resolved_from_context": True}
                ]
                resolved_from_context.append({
                    "modifier": resolvable[0].get("modifier"),
                    "resolved_target": target,
                    "reason": "unique_active_target",
                    "source": "session_context",
                })
                ambiguities = [a for a in ambiguities if a is not resolvable[0]]
                has_signal = True

        # ---------------- scope ----------------
        delta_scope = u.get("scope")
        if delta_scope and delta_scope != "unknown":
            new_scope = delta_scope
        else:
            new_scope = prev_scope or "unknown"

        # ---------------- style ----------------
        new_style = deepcopy(prev_style)
        dstyle = u.get("style") or {}
        if dstyle.get("target"):
            new_style = {
                "target": dstyle.get("target"),
                "direction": dstyle.get("direction"),
                "mix": list(dstyle.get("mix") or []),
            }
        elif dstyle.get("direction") and new_style.get("target"):
            new_style["direction"] = dstyle.get("direction")

        # ---------------- materials ----------------
        new_materials = deepcopy(prev_materials)
        dm = u.get("materials") or {}
        if dm.get("primary"):
            if dm["primary"] != new_materials.get("primary"):
                new_materials = {
                    "primary": dm["primary"],
                    "tone": dm.get("tone"),
                    "tone_direction": dm.get("tone_direction"),
                }
            else:
                new_materials["primary"] = dm["primary"]
                if dm.get("tone"):
                    new_materials["tone"] = dm["tone"]
                    new_materials["tone_direction"] = dm.get("tone_direction")
        elif dm.get("tone") and new_materials.get("primary"):
            new_materials["tone"] = dm["tone"]
            new_materials["tone_direction"] = dm.get("tone_direction")

        # ---------------- elements ----------------
        new_elements = deepcopy(prev_elements)
        for key in ("entrance", "arches", "facade", "windows", "balconies"):
            incoming = u.get(key) or {}
            if not isinstance(incoming, dict):
                continue
            current = new_elements.get(key) or {}
            for field, value in incoming.items():
                if value not in (None, "", [], {}):
                    current[field] = value
            new_elements[key] = current

        # ---------------- preserve ----------------
        new_preserve = dict(prev_preserve)
        for field in self._changed_preserve_fields(u):
            if new_preserve.pop(field, None) is not None:
                resolutions.append({
                    "field": field,
                    "resolution": "latest_change_overrides_preserve",
                })
        delta_preserve = {
            k: v for k, v in (u.get("preserve_constraints") or {}).items()
            if v is True and k not in _PRESERVE_INTERNAL_KEYS
        }
        for field in delta_preserve:
            new_preserve[field] = True
            resolutions.append({"field": field, "resolution": "latest_preserve_set"})

        # ---------------- negatives ----------------
        new_negatives = list(prev_negatives)
        for item in u.get("negative_constraints") or []:
            token = item.get("constraint")
            if token and token not in new_negatives:
                new_negatives.append(token)

        # ---------------- reference policy ----------------
        new_reference = deepcopy(prev_reference)
        dref = u.get("reference_image_policy") or {}
        new_reference_requested = bool(
            context.get("new_reference")
            or (
                context.get("reference_id")
                and context.get("reference_id") != prev.get("active_reference_id")
            )
        )
        if reset:
            new_reference = {}
        elif new_reference_requested:
            new_reference = {}
        elif dref.get("referenced"):
            new_reference = {
                "referenced": True,
                "role": dref.get("role"),
                "copy_reference_geometry": dref.get("copy_reference_geometry", False),
                "preserve_base_geometry": dref.get("preserve_base_geometry", False),
                "requires_image": dref.get("requires_image", True),
                # LIVE_HANDOFF_V1 — this whitelist silently dropped the
                # user's own prohibition on copying the reference's geometry.
                # Without it `_prohibited_elements` saw an empty channel and
                # the reference's columns/arches were emitted as REQUIRED.
                "do_not_copy": list(dref.get("do_not_copy") or []),
            }

        # ---------------- targets ----------------
        merged_targets = list(prev_targets)
        for target in u.get("targets") or []:
            if target not in merged_targets:
                merged_targets.append(target)
        merged_targets = sorted(set(merged_targets))[:MAX_ACTIVE_TARGETS]

        # ---------------- merged 2D-2-shaped understanding ----------------
        change_ops = list(u.get("change_operations") or [])
        # clarify is decided by the CURRENT TURN's delta, not carried state
        if ambiguities and not (change_ops or delta_preserve):
            merged_intent = "clarify"
        elif change_ops and new_preserve:
            merged_intent = "mixed"
        elif change_ops:
            merged_intent = "change"
        elif new_preserve:
            merged_intent = "preserve"
        elif new_negatives:
            merged_intent = "constraint"
        elif new_reference.get("referenced"):
            merged_intent = "reference"
        else:
            merged_intent = "none"

        merged_u = {
            "contract": u.get("contract") or "PersianArchitecturalUnderstandingV1",
            "version": u.get("version") or "1.0",
            "raw_text": raw_text,
            "normalized_text": normalized_text,
            "language": u.get("language", "unknown"),
            "scope": new_scope,
            "intent_type": merged_intent,
            "targets": merged_targets,
            "style": new_style,
            "materials": new_materials,
            "facade": new_elements.get("facade", {}),
            "entrance": new_elements.get("entrance", {}),
            "windows": new_elements.get("windows", {}),
            "balconies": new_elements.get("balconies", {}),
            "arches": new_elements.get("arches", {}),
            "preserve_constraints": {**new_preserve, "explicit": bool(new_preserve)},
            "negative_constraints": [{"constraint": c} for c in new_negatives],
            "change_operations": change_ops,

            # CLASSICAL_DETAIL_RETENTION_V1 — these three channels describe
            # THIS turn's request (which elements the user named, how the
            # building must be framed, whether stone courses were asked for).
            # They are turn-local by nature, so they are carried from the
            # current understanding rather than merged across turns. Without
            # them the whitelist below silently dropped the user's own
            # architectural vocabulary before the compiler ever saw it.
            "elements": list(u.get("elements") or []),
            "framing": dict(u.get("framing") or {}),
            "stone_detail": bool(u.get("stone_detail")),
            "intensity": u.get("intensity") or {"level": "MEDIUM", "value": 0.5, "evidence": []},
            "reference_image_policy": new_reference,
            "ambiguities": ambiguities,
            "confidence": {
                "deterministic": bool(change_ops or new_preserve or new_negatives or new_reference.get("referenced")),
                "ambiguous": bool(ambiguities),
            },
            "deterministic_evidence": ["context_merge"],
            "llm_enrichment": {},
            "conflicts": [],
            "provenance": {
                "engine": "ArchitecturalConversationContextMergerV1",
                "version": VERSION,
                "merged": True,
                "reset": reset,
            },
        }

        # ---------------- recent turns ----------------
        recent_turns = list(prev.get("recent_turns") or [])
        recent_turns.append({
            "turn": len(recent_turns) + 1,
            "raw_text": raw_text,
            "normalized_text": normalized_text,
            "scope": new_scope,
            "intent_type": merged_intent,
        })
        recent_turns = recent_turns[-MAX_RECENT_TURNS:]

        # ---------------- ids (never invented) ----------------
        session_id = prev.get("session_id") or str(uuid.uuid4())
        conversation_id = prev.get("conversation_id") or str(uuid.uuid4())

        def _carry_id(key):
            if reset:
                return None
            if context.get(key):
                return context.get(key)
            return prev.get(key)

        result = ArchitecturalConversationContextV1({
            "contract": CONTRACT,
            "version": VERSION,

            "session_id": session_id,
            "conversation_id": conversation_id,

            "recent_turns": recent_turns,

            "active_topic": context.get("topic") or prev.get("active_topic") or ("architecture" if has_signal else None),
            "active_scope": new_scope,

            "active_architectural_intent": dict(new_style),
            "active_architectural_understanding": merged_u,
            "active_compiled_prompt": {} if reset else (prev.get("active_compiled_prompt") or {}),

            "active_preserve_constraints": new_preserve,
            "active_negative_constraints": new_negatives,
            "active_materials": new_materials,
            "active_style": new_style,
            "active_reference_policy": new_reference,
            "active_targets": merged_targets,
            "active_elements": new_elements,

            "pending_ambiguities": ambiguities,
            "pending_clarifications": [a.get("reason") for a in ambiguities],

            "active_design_id": _carry_id("design_id"),
            "active_candidate_id": _carry_id("candidate_id"),
            "active_render_id": _carry_id("render_id"),
            "active_reference_id": _carry_id("reference_id"),

            "user_profile_summary": context.get("user_profile_summary", prev.get("user_profile_summary", {})),
            "persistent_user_facts": context.get("persistent_user_facts", prev.get("persistent_user_facts", {})),

            "turn_has_architectural_signal": bool(has_signal or ambiguities),

            "context_sources": sorted(set(
                ["session_state"]
                + (["user_intent"] if has_signal else [])
                + (["session_context"] if resolved_from_context else [])
                + (["reference_context"] if new_reference.get("referenced") else [])
            )),
            "provenance": {
                "merger": "ArchitecturalConversationContextMergerV1",
                "merger_version": VERSION,
                "reset": reset,
                "resolutions": resolutions,
                "resolved_from_context": resolved_from_context,
                "merged_at": time.time(),
            },
        })

        result["context_hash"] = self._hash(result)
        return result

    # ------------------------------------------------------
    # deterministic hash
    # ------------------------------------------------------

    @staticmethod
    def _hash(context):
        payload = {
            k: v for k, v in context.items()
            if k not in ("context_hash", "active_compiled_prompt", "provenance")
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ==========================================================
# SESSION STORE (single active conversation)
# ==========================================================

class ArchitecturalConversationContextStore:

    VERSION = VERSION

    def __init__(self):
        self._context = {}
        self.merger = ArchitecturalConversationContextMergerV1()
        print("🧠 ARCHITECTURAL CONVERSATION CONTEXT STORE v1.0 ONLINE")

    def get(self):
        return dict(self._context) if self._context else {}

    def reset(self, reason=None):
        self._context = {}
        return {}

    def apply_turn(self, understanding, raw_text="", normalized_text="", context=None):
        previous = self._context or {}
        merged = self.merger.merge(
            previous,
            understanding,
            raw_text=raw_text,
            normalized_text=normalized_text,
            context=context,
        )
        self._context = merged
        return merged

    def set_compiled_prompt(self, compiled):
        if not self._context:
            return {}
        self._context["active_compiled_prompt"] = compiled
        return self._context


# ==========================================================
# SINGLETON + CONVENIENCE
# ==========================================================

architectural_conversation_context = ArchitecturalConversationContextStore()


def merge_context(previous, understanding, raw_text="", normalized_text="", context=None):
    """Module-level convenience wrapper over the canonical merger."""
    return ArchitecturalConversationContextMergerV1().merge(
        previous, understanding, raw_text=raw_text, normalized_text=normalized_text, context=context
    )
