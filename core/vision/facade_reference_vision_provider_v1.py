# ==========================================================
# ArchitectOS FACADE-03 — FACADE / BUILDING VISION PROVIDER v1
#
# The smallest compatible adapter between the EXISTING Ollama vision
# infrastructure (config.vision_config + core/vision/vision_provider_ollama_v1
# image preparation + transport) and the EXISTING 2D-5 architectural
# reference analysis contract
# (core/prompt_intelligence/reference_image_architectural_understanding_v1.py).
#
# WHY AN ADAPTER IS REQUIRED (verified, not assumed):
#   * `OllamaVisionProvider.analyze()` returns a two-stage
#     `GeneralVisualObserverBridgeV1` result
#     ({"raw_observer": ..., "normalization": {"structured": {<drawing
#     categories>}}}).  It is DRAWING oriented (walls, stairs, axes, OCR)
#     and is NOT the facade schema the 2D-5 interpreter consumes.
#   * `ArchitecturalReferenceInterpreter.interpret()` expects
#     `style_candidates` / `materials` / `arches` / `windows` / `balconies` /
#     `entrance` / `facade_style` / ... .  Feeding it a bridge result yields
#     INSUFFICIENT_VISUAL_EVIDENCE — a silent no-op.
#
# This adapter issues ONE real vision call per image against the same Ollama
# endpoint/model (same session, same bounded image preparation, same timeout),
# with a role-specific architectural prompt, then maps the model's JSON into
# the 2D-5 contract.  Verified live: the full JSON-schema `format` grammar
# degenerates gemma4 to "{" + length-stop, so `format="json"` + an explicit
# key/values instruction is used instead.
#
# ANALYSIS ONLY.  No generation, no rendering, no ComfyUI, no downloads.
# The model input is ALWAYS the actual image bytes (base64 of the file at the
# asset path) — never a filename and never a text description.
# ==========================================================

from __future__ import annotations

import json
import re

from core.prompt_intelligence.reference_image_architectural_understanding_v1 import (
    ArchitecturalVisionProvider,
    STYLE_CANONICAL,
    MATERIAL_CANONICAL,
    ARCH_INTENSITY,
    RHYTHM_VALUES,
    DEPTH_VALUES,
    EMPHASIS_VALUES,
    SYMMETRY_VALUES,
    WINDOW_ASPECT,
    WINDOW_FRAME,
    QUALITY_VALUES,
)
from core.vision.vision_provider_ollama_v1 import (
    OllamaVisionProvider,
    _prepare_observer_image,
    get_vision_provider,
)

CONTRACT = "FacadeReferenceVisionProviderV1"
VERSION = "1.1"

ROLE_STYLE_REFERENCE = "facade_style_reference"
ROLE_TARGET_BUILDING = "target_building"

CERTAINTY_LEVELS = ("OBSERVED", "INFERRED", "UNKNOWN")

_ORN = ("LOW", "MEDIUM", "HIGH")

# VISION_LIGHTING_OUTPUT_VERIFICATION_V2 — additive observation vocabulary.
#
# Time of day and exposure are SEPARATE axes on purpose: a floodlit building
# at night is still night, and a nearly black image is not automatically a
# good night render. `time_of_day` answers "when", `facade_readability`
# answers "how well can it be read", and they are never collapsed.
TIME_OF_DAY = ("night", "dusk", "daylight", "unknown")

FACADE_READABILITY = ("clear", "partial", "silhouette", "unknown")

# What a reported floor number actually MEANS. A fully framed image does not
# make its count reliable: storey divisions can be illegible even when the
# whole building is visible.
FLOOR_COUNT_TYPES = ("TOTAL", "VISIBLE_LEVELS", "LOWER_BOUND", "AMBIGUOUS", "UNKNOWN")

# VISION_PER_LEVEL_ARCHITECTURAL_EVIDENCE_V4 — optional, additive vocabulary
# inside the existing floor_observation block.  It gives the fidelity owner a
# structured account of what the provider counted without creating a second
# counter or changing legacy V2/V3 observations.
LEVEL_CATEGORIES = (
    "principal_storey",
    "roof_opening",
    "attic_or_roof_storey",
    "mezzanine",
    "ambiguous",
)


# ==========================================================
# ROLE PROMPTS
# ==========================================================

_SCHEMA_SPEC = """
Return ONLY a JSON object with EXACTLY these keys (use null / [] when the
image does not show it). Allowed values are listed after each key:
- facade_style: one of modern, minimal, contemporary, neoclassical, classical,
  modern_classic, traditional, industrial, vernacular, mixed, or null
- style_candidates: [{{"style": <as above>, "confidence": 0.0-1.0}}]
- building_type: short string or null
- materials: [{{"type": one of stone, travertine_like_stone, brick, wood, metal,
  glass, concrete, stucco_render, painted_surface, ceramic_cladding,
  "confidence": 0.0-1.0, "evidence": "what in the image shows it"}}]
- color_palette: [short colour names actually seen]
- dominant_tones: [short tone names, e.g. light neutral, warm]
- arches: {{"present": true/false, "intensity": LOW|MEDIUM|HIGH|null, "type_family": string|null}}
- windows: {{"aspect": tall|square|horizontal|mixed|unknown, "frame": thin|heavy|recessed|flush|mixed|unknown, "rhythm": regular|irregular|mixed|unknown, "arch_headed": true/false}}
- balconies: {{"present": true/false, "type": string|null, "railing": string|null, "rhythm": regular|irregular|mixed|unknown, "visual_weight": string|null}}
- entrance: {{"visible": true/false, "emphasis": string|null, "projection": string|null, "canopy": string|null, "material_contrast": string|null, "vertical_emphasis": string|null}}
- facade_rhythm: regular|irregular|mixed|unknown
- facade_depth: flat|shallow_relief|deep_relief|mixed|unknown
- verticality: vertical|horizontal|balanced|unknown
- horizontality: vertical|horizontal|balanced|unknown
- symmetry: symmetric|asymmetric|partially_symmetric|unknown
- ornament_level: LOW|MEDIUM|HIGH|null
- classical_features: [short strings]
- modern_features: [short strings]
- roof_features: [short strings describing the visible roof only]
- visible_floor_count: integer actually countable, or null
- floor_observation: {{"count": integer|null,
  "count_type": TOTAL|VISIBLE_LEVELS|LOWER_BOUND|AMBIGUOUS|UNKNOWN,
  "storey_divisions_legible": true/false,
  "evidence": "what in the image shows it",
  "per_level_evidence": [{{
    "level_position": "visually grounded position such as ground, middle, upper, or roof volume"|null,
    "category": principal_storey|roof_opening|attic_or_roof_storey|mezzanine|ambiguous,
    "evidence": "directly visible architectural evidence for this classification",
    "confidence": 0.0-1.0|null,
    "uncertainty": "specific unresolved visual issue"|null,
    "contributes_to_floor_count": true|false
  }}]}}
  per_level_evidence is OPTIONAL. When the image supports it, include one
  entry for every visible horizontal level or roof-level band considered in
  the count. Use roof_opening for an opening contained within a roof/gable
  volume; it must not contribute to the floor count. Use principal_storey for
  a full storey and count it. An attic_or_roof_storey contributes only when
  directly visible evidence supports a sustained occupiable level and a
  legible division. A mezzanine is not automatically a full storey: state
  explicitly whether it contributes. Use ambiguous when the pixels do not
  resolve the classification; an ambiguous level cannot justify TOTAL.
  Every entry must state confidence or a specific uncertainty, and its
  contributes_to_floor_count value must agree with the stated category.
  A principal storey is evidenced by a row of windows or doors at one height
  that repeats across more than one bay of the facade and has its own head and
  sill. Count each such row as its own storey.
  A storey division does not have to be a projecting balcony, cornice or
  string course. A flush sill, ledge or wall band divides storeys just as
  well: a new row of window heads or sills at a different height is a legible
  division. When the facade carries separate rows of windows at different
  heights, count each row as a separate storey, even when no projecting band
  separates them, and even when a central bay runs one continuous double-height
  window across both rows while the side bays show distinct windows at each
  height. Never merge adjacent rows into one storey merely because the
  division between them is flush.
  Do NOT count as a storey an opening or small group of openings that does not
  repeat across the facade and sits inside the roof volume above the eave or
  roof base. Conversely, a roof window is not automatically evidence of an
  additional principal storey: a gable window, a dormer window, a roof parapet
  and a roof terrace are roof-level features, not storeys, and a single lit
  attic window is not a storey. Judge every band by the structural test above
  rather than by whether it is lit or by what it is called. Classify such an
  opening as roof_opening.
  A habitable attic or roof storey counts only under that same test, and never
  from one opening: never infer room function from a single window.
  In evidence, state which rows were counted and which roof-level openings were
  excluded or remain ambiguous. If the pixels cannot resolve whether a band is
  a separate storey or part of the roof volume, use ambiguous rather than
  inventing a total.
  TOTAL = the whole building is visible AND every storey division is legible.
  VISIBLE_LEVELS = whole building visible but storey divisions are not legible.
  LOWER_BOUND = the building is cropped/occluded, so the count is a minimum.
  AMBIGUOUS = cannot decide; UNKNOWN = no count attempted.
- lighting: {{"time_of_day": night|dusk|daylight|unknown,
  "facade_readability": clear|partial|silhouette|unknown,
  "artificial_lighting_visible": true/false,
  "evidence": "what in the image shows it",
  "confidence": 0.0-1.0}}
  Judge time_of_day ONLY from the pixels (sky brightness, visible sun or
  lamps, shadow direction, window glow). A brightly floodlit building at
  night is still night. A dark or underexposed image is NOT automatically a
  good night photograph. facade_readability describes how well the facade can
  actually be read, separately from the time of day.
- reference_quality: high|medium|low|poor|unknown
- occlusions: [short strings]
- perspective_limitations: [short strings]
- uncertainties: [short strings]
- certainty: {{"facade_style": OBSERVED|INFERRED|UNKNOWN, "materials": ..., "windows": ..., "visible_floor_count": ..., "roof_features": ..., "lighting": ..., "floor_observation": ...}}
Never put a unit (m, cm, ft) or a compass direction (north/south) in any value.
"""

_COMMON = """You are an architectural vision analyst. You are shown ONE photograph
of a building. Report ONLY what the pixels support. Never invent dimensions,
floor counts, materials, structure or hidden geometry. Never guess location,
orientation (north/south/...), architect or year. For every claim mark certainty:
OBSERVED (visibly present), INFERRED (reasonable reading from visible cues),
UNKNOWN (cannot be determined).""" + _SCHEMA_SPEC

_ROLE_PROMPTS = {
    ROLE_STYLE_REFERENCE: _COMMON + """
THIS IMAGE IS THE STYLE REFERENCE. Focus on APPEARANCE ONLY: architectural
style, facade materials, colours/tones, facade elements, ornament, classical
vs modern details, and the visible roof features (shape/parapet/eaves as seen).
Do NOT report massing, floor counts or structural framing beyond the facade.""",
    ROLE_TARGET_BUILDING: _COMMON + """
THIS IMAGE IS THE TARGET BUILDING (geometry authority). Focus on FORM ONLY:
building massing and silhouette, visible floor levels, openings (windows/doors)
and their arrangement, balconies, roof geometry, structural or unfinished
elements (scaffolding, exposed structure, missing facade), and the camera
viewpoint. Do NOT copy a style reference: describe THIS building's own
geometry. Report style/materials only if directly visible on THIS building.""",
}


# ==========================================================
# MAPPING  (model JSON -> 2D-5 raw contract)
# ==========================================================

_CERT_RE = re.compile(r"\s*\((OBSERVED|INFERRED|UNKNOWN)\)\s*", re.IGNORECASE)


def _strip_cert(text):
    if not isinstance(text, str):
        return text
    return _CERT_RE.sub(" ", text).strip()


def _canon(value, allowed):
    """Canonicalise a model value against an allowed set (tolerant).

    ``allowed is None`` means the field is free text (any short string).
    """
    if not isinstance(value, str):
        return None
    cleaned = _strip_cert(value)
    if not cleaned:
        return None
    if allowed is None:
        return cleaned
    if cleaned in allowed:
        return cleaned
    norm = cleaned.lower().replace(" ", "_").replace("-", "_")
    for option in allowed:
        if option.lower() == norm:
            return option
    # fuzzy: a canonical token appearing as a whole word inside the text
    lowered = cleaned.lower()
    for option in sorted(allowed, key=len, reverse=True):
        if option.lower() in lowered:
            return option
    return None


def _str_list(value):
    if isinstance(value, str):
        value = [part for part in re.split(r"[;,]\s*", value) if part.strip()]
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for item in value:
        if isinstance(item, str):
            cleaned = _strip_cert(item)
            if cleaned and cleaned not in out:
                out.append(cleaned)
    return out


def _first(parsed, *keys):
    for key in keys:
        if key in parsed and parsed[key] not in (None, "", [], {}):
            return parsed[key]
    return None


def _parse_json(text):
    """Parse the model's JSON, with a minimal fence/brace repair.

    gemma4 occasionally wraps or pads JSON even under format="json"; this
    only strips code fences and takes the outermost object. It never
    fabricates keys — a truly invalid payload still raises.
    """
    if not isinstance(text, str):
        raise ValueError("empty_model_text")
    candidate = text.strip()
    try:
        return json.loads(candidate)
    except Exception:
        pass
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z]*\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate).strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start >= 0 and end > start:
        return json.loads(candidate[start:end + 1])
    raise ValueError("no_json_object")


def _block(value, enum_fields, bool_fields=()):
    if not isinstance(value, dict):
        return None
    result = {}
    for field, allowed in enum_fields.items():
        mapped = _canon(value.get(field), allowed)
        if mapped:
            result[field] = mapped
    for field in bool_fields:
        if isinstance(value.get(field), bool):
            result[field] = value[field]
    for field in value:
        if field in result or field in enum_fields or field in bool_fields:
            continue
        if isinstance(value[field], str):
            cleaned = _strip_cert(value[field])
            if cleaned and field in ("type_family", "type", "railing", "visual_weight",
                                     "emphasis", "projection", "canopy",
                                     "material_contrast", "vertical_emphasis"):
                result[field] = cleaned
    return result or None


def _materials(value):
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for item in value:
        if isinstance(item, str):
            item = {"type": item}
        if not isinstance(item, dict):
            continue
        mtype = _canon(item.get("type"), MATERIAL_CANONICAL)
        if not mtype:
            continue
        entry = {"type": mtype}
        conf = item.get("confidence")
        if isinstance(conf, (int, float)) and 0.0 <= float(conf) <= 1.0:
            entry["confidence"] = round(float(conf), 2)
        ev = _strip_cert(item.get("evidence"))
        if ev:
            entry["evidence"] = ev
        out.append(entry)
    return out


def _style_candidates(parsed):
    facade_style = _canon(_first(parsed, "facade_style", "architectural_style"), STYLE_CANONICAL)
    candidates = []
    raw = _first(parsed, "style_candidates")
    if isinstance(raw, (list, tuple)):
        for item in raw:
            if isinstance(item, str):
                item = {"style": item}
            if not isinstance(item, dict):
                continue
            style = _canon(item.get("style"), STYLE_CANONICAL)
            if not style:
                continue
            entry = {"style": style}
            conf = item.get("confidence")
            if isinstance(conf, (int, float)) and 0.0 <= float(conf) <= 1.0:
                entry["confidence"] = round(float(conf), 2)
            candidates.append(entry)
    if facade_style and not any(c["style"] == facade_style for c in candidates):
        candidates.insert(0, {"style": facade_style})
    return facade_style, candidates


def _lighting(value):
    """Map the additive `lighting` block. Never invents a time of day."""

    if not isinstance(value, dict):
        return None

    confidence = value.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        confidence = None
    else:
        confidence = max(0.0, min(1.0, float(confidence)))

    visible = value.get("artificial_lighting_visible")
    if not isinstance(visible, bool):
        visible = None

    result = {
        "time_of_day": _canon(value.get("time_of_day"), TIME_OF_DAY),
        "facade_readability": _canon(value.get("facade_readability"), FACADE_READABILITY),
        "artificial_lighting_visible": visible,
        "evidence": _strip_cert(value.get("evidence")) or None,
        "confidence": confidence,
    }

    return result if any(item is not None for item in result.values()) else None


def _floor_observation(value):
    """Map the additive `floor_observation` block (count + what it MEANS)."""

    if not isinstance(value, dict):
        return None

    count = value.get("count")
    if not (isinstance(count, int) and not isinstance(count, bool)
            and 0 < count <= 200):
        count = None

    legible = value.get("storey_divisions_legible")
    if not isinstance(legible, bool):
        legible = None

    result = {
        "count": count,
        "count_type": _canon(value.get("count_type"), FLOOR_COUNT_TYPES),
        "storey_divisions_legible": legible,
        "evidence": _strip_cert(value.get("evidence")) or None,
    }

    # Absence stays absence for exact V2/V3 compatibility.  When present,
    # retain only the provider's structured claims; never infer a category,
    # contribution, confidence, or position in the mapper.
    if "per_level_evidence" in value:
        levels = []
        raw_levels = value.get("per_level_evidence")
        if isinstance(raw_levels, list):
            for raw in raw_levels:
                if not isinstance(raw, dict):
                    continue

                confidence = raw.get("confidence")
                if isinstance(confidence, bool) or not isinstance(
                    confidence, (int, float)
                ):
                    confidence = None
                else:
                    confidence = max(0.0, min(1.0, float(confidence)))

                contributes = raw.get("contributes_to_floor_count")
                if not isinstance(contributes, bool):
                    contributes = None

                levels.append({
                    "level_position": _strip_cert(raw.get("level_position")) or None,
                    "category": _canon(raw.get("category"), LEVEL_CATEGORIES),
                    "evidence": _strip_cert(raw.get("evidence")) or None,
                    "confidence": confidence,
                    "uncertainty": _strip_cert(raw.get("uncertainty")) or None,
                    "contributes_to_floor_count": contributes,
                })
        result["per_level_evidence"] = levels

    return result if any(item is not None for item in result.values()) else None


def map_to_contract(parsed):
    """Map the model's JSON into the 2D-5 raw contract (tolerant, never invents)."""
    parsed = parsed if isinstance(parsed, dict) else {}

    facade_style, style_candidates = _style_candidates(parsed)

    visible_floors = _first(parsed, "visible_floor_count")
    if not (isinstance(visible_floors, int) and not isinstance(visible_floors, bool)
            and 0 < visible_floors <= 200):
        visible_floors = None

    mapped = {
        "facade_style": facade_style,
        "style_candidates": style_candidates,
        "building_type": _strip_cert(_first(parsed, "building_type")) or None,
        "materials": _materials(_first(parsed, "materials", "facade_materials")),
        "color_palette": _str_list(_first(parsed, "color_palette", "facade_colors")),
        "dominant_tones": _str_list(_first(parsed, "dominant_tones")),
        "arches": _block(_first(parsed, "arches"), {"intensity": ARCH_INTENSITY, "type_family": None},
                         bool_fields=("present",)),
        "windows": _block(_first(parsed, "windows"),
                          {"aspect": WINDOW_ASPECT, "frame": WINDOW_FRAME, "rhythm": RHYTHM_VALUES},
                          bool_fields=("arch_headed",)),
        "balconies": _block(_first(parsed, "balconies"),
                            {"rhythm": RHYTHM_VALUES, "type": None, "railing": None, "visual_weight": None},
                            bool_fields=("present",)),
        "entrance": _block(_first(parsed, "entrance"),
                           {"emphasis": None, "projection": None, "canopy": None,
                            "material_contrast": None, "vertical_emphasis": None},
                           bool_fields=("visible",)),
        "facade_rhythm": _canon(_first(parsed, "facade_rhythm"), RHYTHM_VALUES),
        "facade_depth": _canon(_first(parsed, "facade_depth"), DEPTH_VALUES),
        "verticality": _canon(_first(parsed, "verticality"), EMPHASIS_VALUES),
        "horizontality": _canon(_first(parsed, "horizontality"), EMPHASIS_VALUES),
        "symmetry": _canon(_first(parsed, "symmetry"), SYMMETRY_VALUES),
        "ornament_level": _canon(_first(parsed, "ornament_level"), _ORN),
        "classical_features": _str_list(_first(parsed, "classical_features")),
        "modern_features": _str_list(_first(parsed, "modern_features")),
        "roof_features": _str_list(_first(parsed, "roof_features")),
        "visible_floor_count": visible_floors,
        # VISION_LIGHTING_OUTPUT_VERIFICATION_V2 — additive keys. Older
        # consumers ignore them; nothing existing is removed or renamed.
        "floor_observation": _floor_observation(_first(parsed, "floor_observation")),
        "lighting": _lighting(_first(parsed, "lighting")),
        "reference_quality": _canon(_first(parsed, "reference_quality"), QUALITY_VALUES),
        "occlusions": _str_list(_first(parsed, "occlusions")),
        "perspective_limitations": _str_list(_first(parsed, "perspective_limitations")),
        "uncertainties": _str_list(_first(parsed, "uncertainties")),
    }

    certainty = _first(parsed, "certainty")
    if isinstance(certainty, dict):
        mapped["certainty"] = {
            k: v for k, v in certainty.items()
            if isinstance(v, str) and v.upper() in CERTAINTY_LEVELS
        }
    return mapped


# ==========================================================
# PROVIDER
# ==========================================================

class FacadeReferenceVisionProvider(ArchitecturalVisionProvider):
    """Real facade/building vision provider over the existing Ollama stack."""

    name = "ollama_facade"

    def __init__(self, role, *, underlying=None, config=None):
        self.role = role
        if underlying is not None:
            self.underlying = underlying
        elif config is not None:
            self.underlying = OllamaVisionProvider(config=config)
        else:
            self.underlying = get_vision_provider()
        self.config = self.underlying.config
        self.session = self.underlying.session
        self.model = self.underlying.model
        self.endpoint = self.underlying.endpoint
        self.timeout = self.config.timeout

    def is_available(self):
        try:
            return bool(self.underlying.is_available())
        except Exception:
            return False

    def describe(self):
        return {
            "contract": CONTRACT,
            "version": VERSION,
            "provider": self.name,
            "role": self.role,
            "model": self.model,
            "endpoint": self.endpoint,
            "available": bool(self.is_available()),
            "architecture": "single_call_facade_schema",
        }

    def analyze(self, image_asset):
        path = OllamaVisionProvider.resolve_path(image_asset)
        if not path:
            raise ValueError("image_not_readable")

        diagnostics = {}
        encoded = _prepare_observer_image(path, self.config, diagnostics)

        prompt = _ROLE_PROMPTS.get(self.role, _ROLE_PROMPTS[ROLE_TARGET_BUILDING])

        # FACADE-04D.3C-5B — hold the cross-process lease for this Ollama
        # model for the duration of the vision call. H2 takes the same lease
        # exclusively, so this is what proves the model is free before it is
        # unloaded for the render.
        from core.runtime.gpu_handoff_v1 import (
            ollama_model_call,
            OllamaModelBusy,
        )

        try:

            with ollama_model_call(self.model):

                response = self.session.post(
                    self.endpoint + "/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "images": [encoded],
                        "stream": False,
                        "format": "json",
                        "think": False,
                        "options": {
                            "temperature": 0,
                            "num_predict": 1600,
                            "num_ctx": self.config.observer_ctx,
                        },
                    },
                    timeout=self.config.observer_timeout,
                )

        except OllamaModelBusy:

            # Another request owns the model. Fail truthfully (the 2D-5
            # analyzer records STATUS_FAILED) — never infer outside the
            # handoff's accounting.
            raise RuntimeError("ollama_model_busy")

        if response.status_code != 200:
            raise RuntimeError("ollama_http_" + str(response.status_code))

        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("invalid_envelope")
        if body.get("error"):
            raise RuntimeError(str(body["error"]))

        try:
            parsed = _parse_json(body.get("response", ""))
        except Exception as exc:
            raise RuntimeError("unparseable_structured_output:" + type(exc).__name__)

        if not isinstance(parsed, dict):
            raise RuntimeError("non_object_structured_output")

        mapped = map_to_contract(parsed)

        # Kept on the instance for reporting/audit; NOT returned inside the
        # contract dict, so the 2D-5 interpreter scans only real contract keys.
        self.last_raw_model_json = parsed
        self.last_provenance = {
            "contract": CONTRACT,
            "version": VERSION,
            "role": self.role,
            "model": self.model,
            "endpoint": self.endpoint,
            "image_preparation": diagnostics,
            "done_reason": body.get("done_reason"),
            "eval_count": body.get("eval_count"),
        }
        return mapped


# ==========================================================
# SINGLETONS
# ==========================================================

_PROVIDERS = {}


def get_facade_provider(role):
    """Return the cached role-bound provider (one underlying Ollama client)."""
    if role not in _PROVIDERS:
        _PROVIDERS[role] = FacadeReferenceVisionProvider(role)
    return _PROVIDERS[role]


def analyze_ab_references(references, context=None):
    """Run the EXISTING 2D-5 analysis on BOTH role-bound assets.

    Image A -> facade style reference (appearance only).
    Image B -> target building (geometry authority).

    Returns {"A": <ReferenceArchitecturalAnalysisV1>, "B": ..., "roles": {...}}
    or {} when the A/B pair is incomplete. Analysis only — no render.
    """
    from core.prompt_intelligence.reference_image_architectural_understanding_v1 import (
        reference_image_understanding,
    )

    if not isinstance(references, dict):
        return {}

    asset_a = references.get("A")
    asset_b = references.get("B")
    if not asset_a or not asset_b:
        return {}

    return {
        "A": reference_image_understanding.analyze(
            asset_a,
            source_type="reference_image",
            context=context,
            provider=get_facade_provider(ROLE_STYLE_REFERENCE),
        ),
        "B": reference_image_understanding.analyze(
            asset_b,
            source_type="base_building_image",
            context=context,
            provider=get_facade_provider(ROLE_TARGET_BUILDING),
        ),
        "roles": {
            "A": "facade_reference",
            "B": "target_building",
            "geometry_authority": "target_building",
        },
    }
