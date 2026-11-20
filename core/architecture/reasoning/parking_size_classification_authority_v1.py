"""Regulatory parking-size classification without geometry or minimum-demand inference."""
from copy import deepcopy
import math


class ParkingSizeClassificationAuthorityV1:
    """Classify only an authoritative achieved/final vehicle-space count."""

    FORBIDDEN_SOURCE_KINDS = {"geometry_candidate", "candidate_geometry", "geometry_derived"}
    ALLOWED_CAPACITY_SEMANTICS = {"authoritative_achieved_capacity", "authoritative_final_capacity"}

    def resolve(self, regulation_evidence=None, capacity_evidence=None):
        original = deepcopy((regulation_evidence, capacity_evidence))
        result = {"contract": "ParkingSizeClassificationAuthorityResultV1", "status": "unresolved",
                  "parking_size_class": None, "classification_basis": None, "authority_class": None,
                  "provenance": [], "failure_reasons": [], "input_mutated": False}
        definition = (regulation_evidence or {}).get("parking_size_classification") if isinstance(regulation_evidence, dict) else None
        failures = self._definition_failures(regulation_evidence, definition)
        failures.extend(self._capacity_failures(capacity_evidence))
        if failures:
            result["failure_reasons"] = sorted(set(failures))
            return self._finish(result, original, regulation_evidence, capacity_evidence)
        count = int(capacity_evidence["value"])
        matches = [row for row in definition["classes"] if self._contains(row, count)]
        if len(matches) != 1:
            result["failure_reasons"] = ["regulatory_classification_boundary_missing_or_ambiguous"]
            return self._finish(result, original, regulation_evidence, capacity_evidence)
        row = matches[0]; source = definition["source"]
        result.update(status="resolved", parking_size_class=row["class"], classification_basis=count,
                      authority_class="HARD_REGULATION", provenance=[{
                          "document": regulation_evidence["document"], "edition": regulation_evidence["edition"],
                          "publisher": regulation_evidence["publisher"], "section": source["section"],
                          "printed_page": source["printed_page"], "pdf_page_index_zero_based": source["pdf_page_index_zero_based"],
                          "source_kind": source["kind"], "source_url": source["document_url"],
                          "retrieved_on": source["retrieved_on"], "capacity_evidence": deepcopy(capacity_evidence["provenance"])
                      }])
        return self._finish(result, original, regulation_evidence, capacity_evidence)

    @staticmethod
    def _definition_failures(evidence, definition):
        if not isinstance(evidence, dict) or evidence.get("contract") != "IranTopic4VehicleParkingRampSlopeEvidenceV1":
            return ["regulation_evidence_contract_missing_or_invalid"]
        if not isinstance(definition, dict) or definition.get("status") != "resolved_source_evidence":
            return ["regulatory_parking_classification_missing"]
        source = definition.get("source") or {}
        if source.get("kind") != "primary_regulation_document_reproduction" or not source.get("document_url") or not source.get("printed_page"):
            return ["regulatory_parking_classification_source_invalid"]
        if not isinstance(definition.get("classes"), list) or len(definition["classes"]) != 3:
            return ["regulatory_parking_classification_boundaries_invalid"]
        return []

    def _capacity_failures(self, fact):
        if not isinstance(fact, dict) or fact.get("status") != "resolved":
            return ["authoritative_achieved_or_final_capacity_unresolved"]
        if fact.get("semantic") not in self.ALLOWED_CAPACITY_SEMANTICS:
            return ["minimum_or_nonfinal_capacity_cannot_classify_parking"]
        if fact.get("authority_class") != "AUTHORITATIVE_PROJECT_FACT" or not fact.get("provenance"):
            return ["capacity_authority_or_provenance_invalid"]
        if fact.get("source_kind") in self.FORBIDDEN_SOURCE_KINDS:
            return ["geometry_or_candidate_capacity_forbidden"]
        value = fact.get("value")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or not math.isfinite(float(value)):
            return ["authoritative_capacity_must_be_nonnegative_integer"]
        return []

    @staticmethod
    def _contains(row, value):
        lower = row.get("minimum_capacity"); upper = row.get("maximum_capacity")
        return value >= lower and (upper is None or value <= upper)

    @staticmethod
    def _finish(result, original, evidence, capacity):
        result["input_mutated"] = original != (evidence, capacity)
        return result
