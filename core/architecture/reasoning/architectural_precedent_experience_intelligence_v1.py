"""Offline-first, audit-friendly architectural precedent and experience intelligence."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from math import hypot
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


PROVENANCE_CLASSES = (
    "REGULATION",
    "PROJECT_REQUIREMENT",
    "HUMAN_FEEDBACK",
    "PRECEDENT_NON_REGULATORY",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{sha256(_canonical(value).encode('utf-8')).hexdigest()[:16]}"


def _tokens(values: Iterable[Any]) -> set[str]:
    return {str(value).strip().lower() for value in values if str(value).strip()}


@dataclass(frozen=True)
class ArchitecturalExperienceMemoryV1:
    """Immutable return-value memory: no hidden writes and no model-weight updates."""

    case_memory: tuple[dict, ...] = ()
    pattern_knowledge: tuple[dict, ...] = ()
    performance_statistics: tuple[dict, ...] = ()

    def record(self, *, case: Mapping[str, Any], patterns: Sequence[Mapping[str, Any]],
               evaluation: Mapping[str, Any], feedback: Mapping[str, Any] | None = None) -> "ArchitecturalExperienceMemoryV1":
        feedback_record = None
        if feedback is not None:
            feedback_record = {
                "id": _stable_id("feedback", feedback),
                "authority_class": "HUMAN_FEEDBACK",
                "content": deepcopy(dict(feedback)),
            }
        case_record = {
            "id": _stable_id("case", case),
            "authority_class": "PRECEDENT_NON_REGULATORY",
            "case": deepcopy(dict(case)),
            "evaluation": deepcopy(dict(evaluation)),
            "human_feedback_id": feedback_record["id"] if feedback_record else None,
        }
        pattern_records = tuple(deepcopy(dict(item)) for item in patterns)
        statistic = {
            "case_id": case_record["id"],
            "retrieved_case_count": evaluation.get("retrieved_case_count", 0),
            "applicable_pattern_count": evaluation.get("applicable_pattern_count", 0),
            "hypothesis_count": evaluation.get("hypothesis_count", 0),
            "human_feedback_present": feedback_record is not None,
        }
        appended_patterns = pattern_records + ((feedback_record,) if feedback_record else ())
        return ArchitecturalExperienceMemoryV1(
            self.case_memory + (case_record,),
            self.pattern_knowledge + appended_patterns,
            self.performance_statistics + (statistic,),
        )

    def as_dict(self) -> dict:
        return {
            "contract": "ArchitecturalExperienceMemoryV1",
            "learning_mechanism": ["case_memory", "pattern_knowledge", "performance_statistics"],
            "opaque_model_weight_update": False,
            "case_memory": deepcopy(list(self.case_memory)),
            "pattern_knowledge": deepcopy(list(self.pattern_knowledge)),
            "performance_statistics": deepcopy(list(self.performance_statistics)),
        }


class ArchitecturalPrecedentExperienceIntelligenceV1:
    PIPELINE = (
        "project_fingerprint", "similar_case_retrieval", "precedent_analyzer",
        "design_pattern_extraction", "applicability_reasoning",
        "design_hypothesis_generation", "agi_spatial_reasoning", "evaluation",
        "human_feedback", "experience_memory",
    )

    def __init__(self, knowledge_path: str | Path | None = None):
        self.knowledge_path = Path(knowledge_path) if knowledge_path else (
            Path(__file__).resolve().parents[1] / "knowledge" / "architectural_precedent_experience_seed_v1.json"
        )

    def run(self, *, project: Mapping[str, Any], agi_reasoner: Callable[[dict], Any] | None = None,
            feedback: Mapping[str, Any] | None = None,
            memory: ArchitecturalExperienceMemoryV1 | None = None,
            online_cases: Sequence[Mapping[str, Any]] = (), limit: int = 3) -> dict:
        original = deepcopy(project)
        knowledge = json.loads(self.knowledge_path.read_text(encoding="utf-8"))
        self._validate_knowledge(knowledge)
        fingerprint = self._fingerprint(project)
        cases = list(knowledge["cases"]) + [deepcopy(dict(c)) for c in online_cases]
        for case in cases:
            self._validate_case(case)
        retrieved = self._retrieve(fingerprint, cases, limit)
        analyses = [self._analyze(item["case"]) | {"similarity": item["similarity"]} for item in retrieved]
        patterns = self._extract_patterns(analyses)
        applicable = self._applicability(fingerprint, patterns)
        hypotheses = self._hypotheses(applicable)
        agi_input = deepcopy(hypotheses)
        agi_result = agi_reasoner(agi_input) if agi_reasoner else {
            "status": "NOT_EXECUTED_NO_ADAPTER", "hypotheses_received": len(agi_input)
        }
        evaluation = {
            "retrieved_case_count": len(retrieved),
            "applicable_pattern_count": len(applicable),
            "hypothesis_count": len(hypotheses),
            "selection": {"winner": None, "authoritative_ranking": False},
        }
        case_summary = {"fingerprint": fingerprint, "hypotheses": hypotheses}
        next_memory = (memory or ArchitecturalExperienceMemoryV1()).record(
            case=case_summary, patterns=patterns, evaluation=evaluation, feedback=feedback
        )
        return {
            "contract": "ArchitecturalPrecedentExperienceIntelligenceV1",
            "pipeline": list(self.PIPELINE),
            "offline_first": True,
            "online_role": "optional_retrieval_enrichment_only",
            "project_fingerprint": fingerprint,
            "similar_cases": retrieved,
            "precedent_analyses": analyses,
            "design_patterns": patterns,
            "applicable_patterns": applicable,
            "design_hypotheses": hypotheses,
            "agi_spatial_reasoning": agi_result,
            "evaluation": evaluation,
            "human_feedback": ({"authority_class": "HUMAN_FEEDBACK", "content": deepcopy(dict(feedback))}
                               if feedback is not None else None),
            "experience_memory": next_memory.as_dict(),
            "policy": {
                "geometric_copying": False,
                "precedent_may_resolve_regulation": False,
                "opaque_model_weight_update": False,
                "provenance_classes": list(PROVENANCE_CLASSES),
            },
            "input_mutated": project != original,
        }

    @staticmethod
    def _fingerprint(project: Mapping[str, Any]) -> dict:
        boundary = project.get("site", {}).get("boundary", [])
        lengths = []
        for index, point in enumerate(boundary):
            if len(point) >= 2 and boundary:
                other = boundary[(index + 1) % len(boundary)]
                lengths.append(hypot(float(other[0]) - float(point[0]), float(other[1]) - float(point[1])))
        aspect = round(max(lengths) / min(lengths), 3) if lengths and min(lengths) > 0 else None
        return {
            "program": str(project.get("program", "unknown")).lower(),
            "climate": str(project.get("climate", "unknown")).lower(),
            "access_types": sorted(_tokens(project.get("site", {}).get("access_types", []))),
            "floor_count_band": ArchitecturalPrecedentExperienceIntelligenceV1._band(project.get("floor_count")),
            "unit_count_band": ArchitecturalPrecedentExperienceIntelligenceV1._band(project.get("unit_count")),
            "site_edge_count": len(boundary),
            "site_aspect_ratio": aspect,
            "problems": sorted(_tokens(project.get("spatial_problems", []))),
            "goals": sorted(_tokens(project.get("design_goals", []))),
        }

    @staticmethod
    def _band(value: Any) -> str:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return "unknown"
        return "one" if number == 1 else "few" if number <= 4 else "many"

    @staticmethod
    def _retrieve(fingerprint: Mapping[str, Any], cases: Sequence[Mapping[str, Any]], limit: int) -> list[dict]:
        query = _tokens([fingerprint["program"], fingerprint["climate"], *fingerprint["access_types"],
                         *fingerprint["problems"], *fingerprint["goals"]])
        ranked = []
        for case in cases:
            tags = _tokens(case.get("retrieval_tags", []))
            union = query | tags
            score = round(len(query & tags) / len(union), 6) if union else 0.0
            ranked.append({"case": deepcopy(dict(case)), "similarity": score})
        return sorted(ranked, key=lambda item: (-item["similarity"], item["case"]["id"]))[:max(0, limit)]

    @staticmethod
    def _analyze(case: Mapping[str, Any]) -> dict:
        return {key: deepcopy(case[key]) for key in (
            "id", "authority_class", "problems", "design_moves", "reasoning", "outcomes", "trade_offs"
        )}

    @staticmethod
    def _extract_patterns(analyses: Sequence[Mapping[str, Any]]) -> list[dict]:
        patterns = []
        for analysis in analyses:
            payload = {key: analysis[key] for key in ("problems", "design_moves", "reasoning", "outcomes", "trade_offs")}
            patterns.append({
                "id": _stable_id("pattern", payload),
                "authority_class": "PRECEDENT_NON_REGULATORY",
                "source_case_id": analysis["id"],
                **deepcopy(payload),
            })
        return patterns

    @staticmethod
    def _applicability(fingerprint: Mapping[str, Any], patterns: Sequence[Mapping[str, Any]]) -> list[dict]:
        needs = _tokens([*fingerprint["problems"], *fingerprint["goals"]])
        result = []
        for pattern in patterns:
            evidence = needs & _tokens([*pattern["problems"], *pattern["outcomes"]])
            if evidence:
                result.append(deepcopy(dict(pattern)) | {
                    "applicability": {"status": "CANDIDATE", "matched_needs": sorted(evidence),
                                      "requires_project_validation": True}
                })
        return sorted(result, key=lambda item: item["id"])

    @staticmethod
    def _hypotheses(patterns: Sequence[Mapping[str, Any]]) -> list[dict]:
        return [{
            "id": _stable_id("hypothesis", {"pattern": p["id"], "moves": p["design_moves"]}),
            "source_pattern_id": p["id"],
            "authority_class": "PRECEDENT_NON_REGULATORY",
            "problem": deepcopy(p["problems"]),
            "design_move": deepcopy(p["design_moves"]),
            "reasoning": deepcopy(p["reasoning"]),
            "expected_outcome": deepcopy(p["outcomes"]),
            "trade_off": deepcopy(p["trade_offs"]),
            "status": "HYPOTHESIS_REQUIRES_AGI_AND_HUMAN_REVIEW",
            "geometry": None,
        } for p in patterns]

    @staticmethod
    def _validate_knowledge(knowledge: Mapping[str, Any]) -> None:
        if knowledge.get("authority_class") != "PRECEDENT_NON_REGULATORY":
            raise ValueError("Local precedent knowledge must be PRECEDENT_NON_REGULATORY")
        for case in knowledge.get("cases", []):
            ArchitecturalPrecedentExperienceIntelligenceV1._validate_case(case)

    @staticmethod
    def _validate_case(case: Mapping[str, Any]) -> None:
        required = {"id", "authority_class", "retrieval_tags", "problems", "design_moves", "reasoning", "outcomes", "trade_offs"}
        if not required <= set(case):
            raise ValueError(f"Precedent case missing fields: {sorted(required - set(case))}")
        if case["authority_class"] != "PRECEDENT_NON_REGULATORY":
            raise ValueError("Precedent cases cannot resolve regulation or project requirements")
        forbidden = {"coordinates", "geometry", "vertices", "radius", "angle", "shape"}
        if forbidden & set(case):
            raise ValueError("Precedent knowledge may not carry copyable geometry")
