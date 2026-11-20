# ==========================================================
# ArchitectOS Reference Image Architectural Understanding v1.0
#
# PHASE 2D-5 — REFERENCE IMAGE ARCHITECTURAL UNDERSTANDING
#
# Canonical architectural interpretation contract for reference/building
# images, plus a provider boundary and a validating interpreter.
#
# ANALYSIS ONLY.  No image generation.  No rendering.  No ComfyUI.
# No plan/BIM/IFC inference.  No site-orientation inference.
#
# CRITICAL: this module NEVER fabricates image semantics.  If no real
# vision provider is configured, it returns PROVIDER_UNAVAILABLE — it does
# NOT guess style/material from filename, metadata, dimensions or user text.
#
# The user's TEXTUAL reference policy (2D-2 / 2D-4) remains authoritative
# about how much of the reference may be borrowed.  This module only
# provides source evidence.
# ==========================================================


from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid


CONTRACT = "ReferenceArchitecturalAnalysisV1"
VERSION = "1.0"


# ==========================================================
# CONTRACT
# ==========================================================

class ReferenceArchitecturalAnalysisV1(dict):
    """Versioned, dict-compatible reference-image architectural analysis."""

    CONTRACT = CONTRACT
    VERSION = VERSION


# ==========================================================
# STATUSES
# ==========================================================

STATUS_ANALYZED = "ANALYZED"
STATUS_ANALYZED_WITH_UNCERTAINTY = "ANALYZED_WITH_UNCERTAINTY"
STATUS_PARTIAL = "PARTIAL"
STATUS_PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
STATUS_UNSUPPORTED_IMAGE = "UNSUPPORTED_IMAGE"
STATUS_INSUFFICIENT_VISUAL_EVIDENCE = "INSUFFICIENT_VISUAL_EVIDENCE"
STATUS_FAILED = "FAILED"

SOURCE_TYPES = ("reference_image", "base_building_image", "render_candidate", "unknown")


# ==========================================================
# CONTROLLED VOCABULARY
# ==========================================================

STYLE_CANONICAL = {
    "modern", "minimal", "contemporary", "neoclassical", "classical",
    "modern_classic", "traditional", "industrial", "vernacular", "mixed",
}

MATERIAL_CANONICAL = {
    "stone", "travertine_like_stone", "brick", "wood", "metal", "glass",
    "concrete", "stucco_render", "painted_surface", "ceramic_cladding",
}

ORNAMENT_LEVELS = {"LOW", "MEDIUM", "HIGH"}
CONFIDENCE_LEVELS = {"LOW", "MEDIUM", "HIGH"}

ARCH_INTENSITY = {"LOW", "MEDIUM", "HIGH"}
RHYTHM_VALUES = {"regular", "irregular", "mixed", "unknown"}
DEPTH_VALUES = {"flat", "shallow_relief", "deep_relief", "mixed", "unknown"}
EMPHASIS_VALUES = {"vertical", "horizontal", "balanced", "unknown"}
SYMMETRY_VALUES = {"symmetric", "asymmetric", "partially_symmetric", "unknown"}
WINDOW_ASPECT = {"tall", "square", "horizontal", "mixed", "unknown"}
WINDOW_FRAME = {"thin", "heavy", "recessed", "flush", "mixed", "unknown"}
QUALITY_VALUES = {"high", "medium", "low", "poor", "unknown"}


# ==========================================================
# REJECTION RULES (no fabrication, no overreach)
# ==========================================================

_DIMENSION_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:m|meter|meters|metre|metres|cm|mm|ft|feet|foot|inch|inches"
    r"|متر|سانتی\s*متر|میلی\s*متر)\b",
    re.IGNORECASE,
)

_ORIENTATION_TERMS = (
    "north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest",
    "شمال", "جنوب", "شرق", "غرب", "sun exposure", "solar orientation",
)

_STRUCTURAL_CLAIM_TERMS = (
    "reinforced concrete frame", "load-bearing masonry", "load bearing masonry",
    "steel frame", "concrete frame", "اسکلت فلزی", "بتن آرمه", "دیوار باربر",
)

_IDENTITY_KEYS = (
    "architect", "designer", "city", "country", "year", "era", "project_name",
    "project", "location", "address", "author", "photographer", "owner",
)

# numeric values under measurement-like keys are never canonical (no scale)
_MEASUREMENT_KEY_RE = re.compile(
    r"(width|height|depth|length|dimension|size|area|meter|metre|_m$|_mm$|_cm$|_ft$|_in$)",
    re.IGNORECASE,
)

# provider keys that are never canonical state
_NON_CANONICAL_KEYS = ("description", "narrative", "summary", "caption", "text", "comment")


# ==========================================================
# PROVIDER BOUNDARY
# ==========================================================

class ArchitecturalVisionProvider:
    """Boundary for a real architectural vision provider.

    Implementations must return a raw structured observation dict (or raise).
    No credentials are hardcoded here; nothing is downloaded.
    """

    name = "none"
    model = "none"

    def is_available(self):
        return False

    def analyze(self, image_asset):  # pragma: no cover - interface
        raise NotImplementedError


class NullVisionProvider(ArchitecturalVisionProvider):
    """Default provider: no real vision capability is configured."""

    name = "none"
    model = "none"

    def is_available(self):
        return False


# ==========================================================
# INTERPRETER / VALIDATOR
# ==========================================================

class ArchitecturalReferenceInterpreter:

    VERSION = VERSION

    def __init__(self):
        print("👁️ ARCHITECTURAL REFERENCE INTERPRETER v1.0 ONLINE (validating)")

    # ------------------------------------------------------
    # sanitisation helpers
    # ------------------------------------------------------

    @staticmethod
    def _clean_string(value, unsupported, field):
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        if _DIMENSION_RE.search(text):
            unsupported.append({"field": field, "reason": "invented_dimension", "value": text})
            return None
        lowered = text.lower()
        for term in _ORIENTATION_TERMS:
            if term in lowered:
                unsupported.append({"field": field, "reason": "unsupported_orientation", "value": text})
                return None
        for term in _STRUCTURAL_CLAIM_TERMS:
            if term in lowered:
                unsupported.append({"field": field, "reason": "unsupported_structural_claim", "value": text})
                return None
        return text

    @staticmethod
    def _confidence(value):
        if isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0:
            return round(float(value), 2)
        if isinstance(value, str) and value.strip().upper() in CONFIDENCE_LEVELS:
            return value.strip().upper()
        return None

    def _enum(self, value, allowed, unsupported, field):
        if isinstance(value, str):
            candidate = value.strip()
            if candidate in allowed:
                return candidate
            lowered = candidate.lower()
            for option in allowed:
                if option.lower() == lowered:
                    return option
        if value not in (None, "", [], {}):
            unsupported.append({"field": field, "reason": "non_canonical_value", "value": value})
        return None

    def _string_list(self, value, unsupported, field):
        if not isinstance(value, (list, tuple)):
            return []
        result = []
        for item in value:
            cleaned = self._clean_string(item, unsupported, field)
            if cleaned and cleaned not in result:
                result.append(cleaned)
        return result

    # ------------------------------------------------------
    # recursive rejection scan
    # ------------------------------------------------------

    def _scan_rejections(self, node, unsupported, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                child = f"{path}.{key}" if path else str(key)
                if isinstance(value, str):
                    if _DIMENSION_RE.search(value):
                        unsupported.append({"field": child, "reason": "invented_dimension", "value": value})
                    lowered = value.lower()
                    if any(term in lowered for term in _ORIENTATION_TERMS):
                        unsupported.append({"field": child, "reason": "unsupported_orientation", "value": value})
                    if any(term in lowered for term in _STRUCTURAL_CLAIM_TERMS):
                        unsupported.append({"field": child, "reason": "unsupported_structural_claim", "value": value})
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    if _MEASUREMENT_KEY_RE.search(str(key)):
                        unsupported.append({"field": child, "reason": "non_canonical_numeric_measurement", "value": value})
                else:
                    self._scan_rejections(value, unsupported, child)
        elif isinstance(node, (list, tuple)):
            for index, item in enumerate(node):
                self._scan_rejections(item, unsupported, f"{path}[{index}]")

    # ------------------------------------------------------
    # main interpret
    # ------------------------------------------------------

    def interpret(self, raw, provider_name, model_name, source_hash, image_id, source_type="unknown"):
        unsupported = []
        uncertainties = []
        evidence = []

        raw = raw if isinstance(raw, dict) else {}

        # reject invented measurements / orientation / structural claims anywhere
        self._scan_rejections(raw, unsupported)

        # identity / non-canonical keys are never canonical state
        for key in _IDENTITY_KEYS:
            if key in raw and raw.get(key) not in (None, "", [], {}):
                unsupported.append({"field": key, "reason": "identity_or_metadata_claim", "value": raw.get(key)})
        for key in _NON_CANONICAL_KEYS:
            if key in raw and raw.get(key) not in (None, "", [], {}):
                unsupported.append({"field": key, "reason": "free_form_narrative_rejected", "value": str(raw.get(key))[:200]})

        # ---------------- style ----------------
        style_candidates = []
        for item in raw.get("style_candidates") or []:
            if not isinstance(item, dict):
                continue
            style = self._enum(item.get("style"), STYLE_CANONICAL, unsupported, "style_candidates.style")
            if not style:
                continue
            entry = {"style": style}
            conf = self._confidence(item.get("confidence"))
            if conf is not None:
                entry["confidence"] = conf
            style_candidates.append(entry)

        facade_style = self._enum(raw.get("facade_style"), STYLE_CANONICAL, unsupported, "facade_style")
        if facade_style and not any(c["style"] == facade_style for c in style_candidates):
            style_candidates.insert(0, {"style": facade_style})

        style_confidence = None
        if style_candidates and "confidence" in style_candidates[0]:
            style_confidence = style_candidates[0]["confidence"]
        if len(style_candidates) > 1:
            uncertainties.append("multiple_style_candidates")

        # ---------------- materials ----------------
        materials = []
        for item in raw.get("materials") or []:
            if isinstance(item, str):
                item = {"type": item}
            if not isinstance(item, dict):
                continue
            mtype = self._enum(item.get("type"), MATERIAL_CANONICAL, unsupported, "materials.type")
            if not mtype:
                continue
            entry = {"type": mtype}
            conf = self._confidence(item.get("confidence"))
            if conf is not None:
                entry["confidence"] = conf
            ev = self._clean_string(item.get("evidence"), unsupported, "materials.evidence")
            if ev:
                entry["evidence"] = ev
                evidence.append(ev)
            materials.append(entry)

        # ---------------- palette / tones ----------------
        color_palette = self._string_list(raw.get("color_palette"), unsupported, "color_palette")
        dominant_tones = self._string_list(raw.get("dominant_tones"), unsupported, "dominant_tones")

        # ---------------- element blocks ----------------
        def _block(key, enum_fields):
            block = raw.get(key)
            result = {}
            if isinstance(block, dict):
                for field, allowed in enum_fields.items():
                    value = block.get(field)
                    if allowed is None:
                        if isinstance(value, bool):
                            result[field] = value
                        elif value is not None:
                            cleaned = self._clean_string(value, unsupported, f"{key}.{field}")
                            if cleaned:
                                result[field] = cleaned
                    else:
                        result[field] = self._enum(value, allowed, unsupported, f"{key}.{field}")
            # drop empty blocks entirely (unknown stays unknown)
            result = {k: v for k, v in result.items() if v not in (None, "", [], {})}
            return result or None

        arches = _block("arches", {"present": None, "intensity": ARCH_INTENSITY, "type_family": None})
        windows = _block("windows", {"aspect": WINDOW_ASPECT, "frame": WINDOW_FRAME, "rhythm": RHYTHM_VALUES, "arch_headed": None, "palette": None})
        balconies = _block("balconies", {"present": None, "type": None, "railing": None, "rhythm": RHYTHM_VALUES, "visual_weight": None})
        entrance = _block("entrance", {"visible": None, "emphasis": None, "projection": None, "canopy": None, "material_contrast": None, "vertical_emphasis": None})

        # ---------------- facade composition ----------------
        facade_rhythm = self._enum(raw.get("facade_rhythm"), RHYTHM_VALUES, unsupported, "facade_rhythm")
        facade_depth = self._enum(raw.get("facade_depth"), DEPTH_VALUES, unsupported, "facade_depth")
        verticality = self._enum(raw.get("verticality"), EMPHASIS_VALUES, unsupported, "verticality")
        horizontality = self._enum(raw.get("horizontality"), EMPHASIS_VALUES, unsupported, "horizontality")
        symmetry = self._enum(raw.get("symmetry"), SYMMETRY_VALUES, unsupported, "symmetry")

        # ---------------- ornament ----------------
        ornament_level = self._enum(raw.get("ornament_level"), ORNAMENT_LEVELS, unsupported, "ornament_level")
        classical_features = self._string_list(raw.get("classical_features"), unsupported, "classical_features")
        modern_features = self._string_list(raw.get("modern_features"), unsupported, "modern_features")

        # FACADE-04D.3C-9M — the visible roof. The provider already grounds this
        # (facade_reference_vision_provider_v1.py `map_to_contract` -> "roof_features")
        # but it never reached this canonical contract, so the render-instruction
        # roof branch (architectural_render_instruction_v1.py:695-696) was dead.
        # SAFE: an absent or invalid value yields [] — never a default/guessed roof.
        roof_features = self._string_list(raw.get("roof_features"), unsupported, "roof_features")

        # ---------------- limitations ----------------
        occlusions = self._string_list(raw.get("occlusions"), unsupported, "occlusions")
        perspective_limitations = self._string_list(raw.get("perspective_limitations"), unsupported, "perspective_limitations")
        provider_uncertainties = self._string_list(raw.get("uncertainties"), unsupported, "uncertainties")
        uncertainties.extend(provider_uncertainties)

        reference_quality = self._enum(raw.get("reference_quality"), QUALITY_VALUES, unsupported, "reference_quality")

        visible_floor_count = None
        raw_floors = raw.get("visible_floor_count")
        if isinstance(raw_floors, int) and 0 < raw_floors <= 200:
            visible_floor_count = raw_floors
        elif raw_floors not in (None, "", [], {}):
            unsupported.append({"field": "visible_floor_count", "reason": "non_canonical_value", "value": raw_floors})

        # ---------------- status ----------------
        canonical_signal = any([
            style_candidates, materials, color_palette, arches, windows,
            balconies, entrance, facade_rhythm, ornament_level, classical_features,
            modern_features, symmetry,
        ])
        if not canonical_signal:
            status = STATUS_INSUFFICIENT_VISUAL_EVIDENCE
        elif raw.get("partial") is True or "partial_facade" in occlusions:
            status = STATUS_PARTIAL
        elif uncertainties or occlusions or perspective_limitations or reference_quality in ("low", "poor"):
            status = STATUS_ANALYZED_WITH_UNCERTAINTY
        else:
            status = STATUS_ANALYZED

        # de-duplicate rejections
        unique_unsupported = []
        seen = set()
        for item in unsupported:
            key = (item.get("field"), item.get("reason"), str(item.get("value")))
            if key not in seen:
                seen.add(key)
                unique_unsupported.append(item)
        unsupported = unique_unsupported

        result = ReferenceArchitecturalAnalysisV1({
            "contract": CONTRACT,
            "version": VERSION,

            "image_id": image_id,
            "source_type": source_type if source_type in SOURCE_TYPES else "unknown",
            "source_hash": source_hash,

            "analysis_status": status,

            "building_type": self._clean_string(raw.get("building_type"), unsupported, "building_type"),
            "facade_style": facade_style,
            "style_candidates": style_candidates,
            "style_confidence": style_confidence,

            "materials": materials,
            "material_regions": [],          # deferred (requires region grounding)
            "color_palette": color_palette,
            "dominant_tones": dominant_tones,

            "arches": arches,
            "windows": windows,
            "balconies": balconies,
            "entrance": entrance,

            "facade_rhythm": facade_rhythm,
            "facade_depth": facade_depth,
            "verticality": verticality,
            "horizontality": horizontality,

            "solid_void_ratio": None,        # requires measurement — never guessed
            "opening_pattern": None,

            "ornament_level": ornament_level,
            "classical_features": classical_features,
            "modern_features": modern_features,

            # FACADE-04D.3C-9M — carry the provider's grounded roof observation.
            # Placed adjacent to `visible_floor_count` because both describe the
            # building envelope; the existing consumer ignores an empty list.
            "roof_features": roof_features,

            "entrance_hierarchy": (entrance or {}).get("emphasis") if entrance else None,

            "window_proportions": (windows or {}).get("aspect") if windows else None,
            "window_frame_language": (windows or {}).get("frame") if windows else None,

            "balcony_language": (balconies or {}).get("type") if balconies else None,

            "surface_texture": None,         # deferred
            "material_contrast": (entrance or {}).get("material_contrast") if entrance else None,

            "symmetry": symmetry,
            "composition": facade_rhythm,

            "visible_floor_count": visible_floor_count,

            "reference_quality": reference_quality,
            "occlusions": occlusions,
            "perspective_limitations": perspective_limitations,

            "uncertainties": uncertainties,
            "unsupported_inferences": unsupported,
            "evidence": evidence,

            "provider": provider_name,
            "model": model_name,

            "provenance": {
                "engine": "ArchitecturalReferenceInterpreter",
                "version": VERSION,
                "analysis_only": True,
                "pixel_analysis": True,
            },
        })

        result["analysis_hash"] = self._hash(result)
        return result

    @staticmethod
    def _hash(analysis):
        payload = {k: v for k, v in analysis.items() if k not in ("analysis_hash", "provenance")}
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ==========================================================
# ANALYZER
# ==========================================================

class ReferenceImageArchitecturalUnderstandingV1:

    VERSION = VERSION

    def __init__(self, provider=None):
        self.provider = provider or NullVisionProvider()
        self.interpreter = ArchitecturalReferenceInterpreter()
        self._cache = {}
        print("👁️ REFERENCE IMAGE ARCHITECTURAL UNDERSTANDING v1.0 ONLINE")

    # ------------------------------------------------------
    # provider management
    # ------------------------------------------------------

    def register_provider(self, provider):
        self.provider = provider or NullVisionProvider()
        return self.provider

    # ------------------------------------------------------
    # helpers
    # ------------------------------------------------------

    @staticmethod
    def _image_path(image_asset):
        if isinstance(image_asset, str):
            return image_asset
        if isinstance(image_asset, dict):
            return image_asset.get("path") or image_asset.get("file_path")
        return None

    @staticmethod
    def _source_hash(path):
        if not path or not isinstance(path, str) or not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as fh:
                return hashlib.sha256(fh.read()).hexdigest()
        except Exception:
            return None

    def _unavailable(self, status, image_id, source_hash, source_type, reason, provider_name, model_name):
        result = ReferenceArchitecturalAnalysisV1({
            "contract": CONTRACT,
            "version": VERSION,
            "image_id": image_id,
            "source_type": source_type,
            "source_hash": source_hash,
            "analysis_status": status,
            "building_type": None,
            "facade_style": None,
            "style_candidates": [],
            "style_confidence": None,
            "materials": [],
            "material_regions": [],
            "color_palette": [],
            "dominant_tones": [],
            "arches": None,
            "windows": None,
            "balconies": None,
            "entrance": None,
            "facade_rhythm": None,
            "facade_depth": None,
            "verticality": None,
            "horizontality": None,
            "solid_void_ratio": None,
            "opening_pattern": None,
            "ornament_level": None,
            "classical_features": [],
            "modern_features": [],
            "entrance_hierarchy": None,
            "window_proportions": None,
            "window_frame_language": None,
            "balcony_language": None,
            "surface_texture": None,
            "material_contrast": None,
            "symmetry": None,
            "composition": None,
            "visible_floor_count": None,
            "reference_quality": None,
            "occlusions": [],
            "perspective_limitations": [],
            "uncertainties": [],
            "unsupported_inferences": [],
            "evidence": [],
            "provider": provider_name,
            "model": model_name,
            "provenance": {
                "engine": "ReferenceImageArchitecturalUnderstandingV1",
                "version": VERSION,
                "analysis_only": True,
                "pixel_analysis": False,
                "reason": reason,
            },
        })
        result["analysis_hash"] = self.interpreter._hash(result)
        return result

    # ------------------------------------------------------
    # main
    # ------------------------------------------------------

    def analyze(self, image_asset, source_type="unknown", context=None, use_cache=True, provider=None):
        context = context or {}
        image_id = None
        if isinstance(image_asset, dict):
            image_id = image_asset.get("asset_id") or image_asset.get("filename")
        elif isinstance(image_asset, str):
            image_id = os.path.basename(image_asset)

        # -------- no image supplied: never analyse --------
        if not image_asset:
            return self._unavailable(
                STATUS_UNSUPPORTED_IMAGE, None, None, source_type,
                "no_image_supplied", "none", "none",
            )

        path = self._image_path(image_asset)
        source_hash = self._source_hash(path)

        if source_hash is None:
            # cannot verify image content -> do not pretend
            return self._unavailable(
                STATUS_UNSUPPORTED_IMAGE, image_id, None, source_type,
                "image_not_readable", "none", "none",
            )

        # FACADE-03 — an explicit role-bound provider may be supplied (A vs B);
        # otherwise the registered default is used. Backward compatible.
        provider = provider or self.provider or NullVisionProvider()
        provider_name = getattr(provider, "name", "none")
        model_name = getattr(provider, "model", "none")

        # -------- cache (by content hash + provider) --------
        cache_key = (source_hash, provider_name)
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        # -------- provider unavailable: structured, no fake semantics --------
        try:
            available = bool(provider.is_available())
        except Exception:
            available = False

        if not available:
            result = self._unavailable(
                STATUS_PROVIDER_UNAVAILABLE, image_id, source_hash, source_type,
                "no_vision_provider_configured", provider_name, model_name,
            )
            if use_cache:
                self._cache[cache_key] = result
            return result

        # -------- provider call --------
        try:
            raw = provider.analyze(image_asset)
        except Exception as exc:
            return self._unavailable(
                STATUS_FAILED, image_id, source_hash, source_type,
                f"provider_error:{exc}", provider_name, model_name,
            )

        if not isinstance(raw, dict):
            return self._unavailable(
                STATUS_FAILED, image_id, source_hash, source_type,
                "provider_non_structured_output", provider_name, model_name,
            )

        result = self.interpreter.interpret(
            raw,
            provider_name=provider_name,
            model_name=model_name,
            source_hash=source_hash,
            image_id=image_id,
            source_type=source_type,
        )
        if use_cache:
            self._cache[cache_key] = result
        return result

    def analyze_if_present(self, image_asset, source_type="unknown", context=None):
        """Runtime-safe helper: returns {} when no image is present."""
        if not image_asset:
            return {}
        return self.analyze(image_asset, source_type=source_type, context=context)


# ==========================================================
# SINGLETON + CONVENIENCE
# ==========================================================

reference_image_understanding = ReferenceImageArchitecturalUnderstandingV1()


def analyze_reference_image(image_asset, source_type="unknown", context=None):
    """Module-level convenience wrapper over the canonical analyzer."""
    return reference_image_understanding.analyze(image_asset, source_type=source_type, context=context)
