"""Validated, provenance-aware precedent importer, contextual mapper and replay gate."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Sequence


SOURCE_KINDS = ("local", "manual", "online", "image_plan_analysis")
AUTHORITY_CLASSES = (
    "REGULATION", "PROJECT_REQUIREMENT", "DESIGN_ASSUMPTION",
    "PRECEDENT_NON_REGULATORY", "HUMAN_FEEDBACK",
)
TRANSFER_FIELDS = (
    "problem", "constraints", "design_move", "reasoning", "outcome",
    "trade_off", "applicability",
)
FORBIDDEN_GEOMETRY_KEYS = {
    "geometry", "geometries", "coordinate", "coordinates", "vertex", "vertices",
    "angle", "angles", "radius", "radii", "shape", "named_shape", "polygon",
    "polyline", "wkt", "geojson", "points", "boundary",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _id(prefix: str, value: Any) -> str:
    return f"{prefix}_{sha256(_canonical(value).encode('utf-8')).hexdigest()[:16]}"


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return sorted({str(item).strip().lower() for item in values if str(item).strip()})


def _assert_no_geometry(value: Any, path: str = "case") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_GEOMETRY_KEYS:
                raise ValueError(f"Copyable geometry is forbidden at {path}.{key}")
            _assert_no_geometry(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_no_geometry(child, f"{path}[{index}]")


class ValidatedPrecedentImporterV2:
    """Normalizes heterogeneous sources to one geometry-free abstract case."""

    def import_case(self, raw: Mapping[str, Any], *, source_kind: str) -> dict:
        original = deepcopy(raw)
        if source_kind not in SOURCE_KINDS:
            raise ValueError(f"Unsupported source_kind: {source_kind}")
        source = raw.get("source")
        if not isinstance(source, Mapping) or not str(source.get("reference", "")).strip():
            raise ValueError("source.reference is required")
        authority = str(raw.get("authority_class", "PRECEDENT_NON_REGULATORY"))
        if authority not in AUTHORITY_CLASSES:
            raise ValueError("Unknown authority_class")
        if authority in {"REGULATION", "PROJECT_REQUIREMENT"}:
            raise ValueError("Precedent importer cannot create binding authority")

        knowledge = raw.get("knowledge")
        if not isinstance(knowledge, Mapping):
            raise ValueError("knowledge object is required")
        forbidden_knowledge_keys = FORBIDDEN_GEOMETRY_KEYS & {str(key).lower() for key in knowledge}
        if forbidden_knowledge_keys:
            raise ValueError(f"Transferable knowledge contains geometry fields: {sorted(forbidden_knowledge_keys)}")
        missing = [field for field in TRANSFER_FIELDS if field not in knowledge]
        if missing:
            raise ValueError(f"Missing transferable fields: {missing}")
        normalized = {field: _list(knowledge[field]) for field in TRANSFER_FIELDS}
        if any(not normalized[field] for field in ("problem", "design_move", "reasoning", "applicability")):
            raise ValueError("problem, design_move, reasoning and applicability must be non-empty")
        _assert_no_geometry(normalized)

        context = deepcopy(dict(raw.get("context", {})))
        _assert_no_geometry(context)
        feedback = None
        if authority == "HUMAN_FEEDBACK":
            if not context.get("context_id") or not context.get("scope"):
                raise ValueError("HUMAN_FEEDBACK requires context_id and scope")
            feedback = {"context_specific": True, "general_rule": False,
                        "context_id": context["context_id"], "scope": context["scope"]}

        source_record = {
            "kind": source_kind,
            "reference": str(source["reference"]),
            "retrieved_at": source.get("retrieved_at"),
            "content_digest": source.get("content_digest"),
            "online_optional_enrichment": source_kind == "online",
        }
        payload = {"source": source_record, "authority_class": authority,
                   "context": context, **normalized, "human_feedback_policy": feedback}
        result = {
            "contract": "AbstractPrecedentCaseV2", "id": _id("abstract_case", payload),
            **payload, "contains_transferable_geometry": False,
            "normalization_audit": {
                "source_kind": source_kind,
                "accepted_fields": list(TRANSFER_FIELDS),
                "discarded_source_geometry": any(str(k).lower() in FORBIDDEN_GEOMETRY_KEYS for k in raw),
            },
        }
        if raw != original:
            raise RuntimeError("Importer mutated input")
        return result


class ContextualDesignMoveMapperV2:
    """Produces non-authoritative candidates using explicit applicability evidence."""

    def map(self, *, project_context: Mapping[str, Any], patterns: Sequence[Mapping[str, Any]],
            agi_adapter: Callable[[dict], Any] | None = None) -> dict:
        original_context, original_patterns = deepcopy(project_context), deepcopy(patterns)
        problems = set(_list(project_context.get("problems")))
        constraints = set(_list(project_context.get("constraints")))
        dominant = set(_list(project_context.get("dominant_geometry")))
        goals = set(_list(project_context.get("goals")))
        candidates = []
        for pattern in patterns:
            if pattern.get("contract") != "AbstractPrecedentCaseV2":
                raise ValueError("Only AbstractPrecedentCaseV2 patterns are accepted")
            matched_problems = problems & set(_list(pattern.get("problem")))
            matched_constraints = constraints & set(_list(pattern.get("constraints")))
            applicability = set(_list(pattern.get("applicability")))
            geometry_evidence = dominant & applicability
            benefit = (problems | goals) & set(_list(pattern.get("outcome")))
            trade_offs = _list(pattern.get("trade_off"))
            if not matched_problems:
                continue
            evidence_count = len(matched_problems) + len(matched_constraints) + len(geometry_evidence) + len(benefit)
            confidence = round(min(0.9, 0.25 + 0.1 * evidence_count - 0.03 * len(trade_offs)), 3)
            candidate = {
                "id": _id("mapping", {"pattern": pattern["id"], "context": original_context}),
                "source_pattern_id": pattern["id"],
                "authority_class": "PRECEDENT_NON_REGULATORY",
                "spatial_problem": sorted(matched_problems),
                "design_move": _list(pattern.get("design_move")),
                "applicability_evidence": {
                    "matched_constraints": sorted(matched_constraints),
                    "dominant_geometry_compatibility": sorted(geometry_evidence),
                    "multi_problem_benefit": sorted(benefit),
                    "requires_project_validation": True,
                },
                "trade_offs_to_validate": trade_offs,
                "confidence": confidence,
                "status": "NON_AUTHORITATIVE_HYPOTHESIS",
                "geometry": None,
                "is_winner": False,
            }
            candidates.append(candidate)
        candidates.sort(key=lambda item: item["id"])
        payload = {"contract": "PrecedentToAGISpatialProblemV2", "candidates": deepcopy(candidates),
                   "winner": None, "authoritative_ranking": False}
        agi_result = agi_adapter(deepcopy(payload)) if agi_adapter else {"status": "NOT_EXECUTED_NO_ADAPTER"}
        if project_context != original_context or patterns != original_patterns:
            raise RuntimeError("Mapper mutated input")
        return {**payload, "agi_adapter_result": agi_result}


class PrecedentReplayGateV2:
    """Hides source geometry and checks transfer from problems/constraints to moves."""

    def run(self, *, held_out_case: Mapping[str, Any], learned_patterns: Sequence[Mapping[str, Any]],
            mapper: ContextualDesignMoveMapperV2 | None = None) -> dict:
        expected = set(_list(held_out_case.get("design_move")))
        context = {
            "problems": _list(held_out_case.get("problem")),
            "constraints": _list(held_out_case.get("constraints")),
            "dominant_geometry": _list(held_out_case.get("context", {}).get("dominant_geometry")),
            "goals": _list(held_out_case.get("outcome")),
        }
        mapping = (mapper or ContextualDesignMoveMapperV2()).map(
            project_context=context, patterns=deepcopy(learned_patterns)
        )
        proposed = {move for item in mapping["candidates"] for move in item["design_move"]}
        overlap = sorted(expected & proposed)
        passed = bool(overlap) and all(item["geometry"] is None for item in mapping["candidates"])
        return {
            "contract": "PrecedentReplayGateV2", "geometry_visible_to_reasoning": False,
            "exact_geometry_reconstruction_attempted": False,
            "expected_design_moves_withheld_from_reasoning": True,
            "proposed_design_moves": sorted(proposed), "expected_overlap": overlap,
            "winner": None, "authoritative_ranking": False,
            "status": "PASS" if passed else "FAIL_CLOSED", "mapping": mapping,
        }
