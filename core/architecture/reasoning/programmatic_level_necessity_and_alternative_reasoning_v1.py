"""Evidence-scoped programmatic level necessity and alternative reasoning."""
from copy import deepcopy


class ProgrammaticLevelNecessityAndAlternativeReasoningV1:
    """Compare level-use hypotheses without geometry, mutation, or project selection."""

    MAX_HYPOTHESES = 16
    AUTHORITATIVE_CAPACITY = "AUTHORITATIVE_PROJECT_FACT"
    SELECTION_AUTHORITIES = {"DESIGN_CONFIRMATION", "PROJECT_REQUIREMENT"}

    def evaluate(self, program_requirements=None, minimum_parking_requirement=None,
                 hypotheses=None, selection=None):
        original = deepcopy((program_requirements, minimum_parking_requirement,
                             hypotheses, selection))
        items = list(hypotheses or [])
        failures = self._input_failures(minimum_parking_requirement, items)
        result = {
            "contract": self.__class__.__name__,
            "status": "rejected" if failures else "completed",
            "scope": "architecture_only_programmatic_reasoning_no_geometry",
            "bounded": True,
            "limits": {"maximum_hypotheses": self.MAX_HYPOTHESES},
            "failure_reasons": failures,
            "comparison_matrix": [],
            "auto_selection_performed": False,
            "feasibility_is_selection": False,
            "selection_is_project_decision": False,
            "geometry_generated": False,
            "structure_executed": False,
            "bim_executed": False,
            "ifc_executed": False,
            "render_executed": False,
            "image_generation_executed": False,
            "input_mutated": False,
        }
        if not failures:
            minimum = minimum_parking_requirement["value"]
            result["minimum_parking_requirement"] = deepcopy(minimum_parking_requirement)
            result["program_requirements"] = deepcopy(program_requirements or [])
            result["comparison_matrix"] = [
                self._row(item, minimum, selection) for item in
                sorted(items, key=lambda value: str(value["hypothesis_id"]))
            ]
        result["input_mutated"] = original != (
            program_requirements, minimum_parking_requirement, hypotheses, selection)
        return result

    def _row(self, hypothesis, minimum, selection):
        hid = hypothesis["hypothesis_id"]
        basement = [deepcopy(x) for x in hypothesis.get("functions_assigned", {}).get("basement", [])]
        pilotis = [deepcopy(x) for x in hypothesis.get("functions_assigned", {}).get("pilotis", [])]
        capacity = self._authoritative_capacity(hypothesis.get("achieved_parking_capacity"))
        parking_status = ("satisfied" if capacity is not None and capacity >= minimum else
                          "unsatisfied" if capacity is not None else "unresolved")
        satisfied, unsatisfied, unresolved = self._function_buckets(basement)
        displacement = self._displacement(hypothesis.get("pilotis_displacement", []))
        eliminates = hypothesis.get("basement_status") == "eliminated"
        blockers = []
        if parking_status != "satisfied":
            blockers.append("authoritative_parking_capacity_below_minimum" if capacity is not None
                            else "authoritative_achieved_parking_capacity_required")
        if eliminates:
            blockers += [f"mandatory_basement_function_unsatisfied:{fid}" for fid in unsatisfied]
            blockers += [f"basement_function_status_unresolved:{fid}" for fid in unresolved]
        blockers += [f"mandatory_pilotis_function_displaced:{x['function_id']}"
                     for x in displacement if x["status"] == "unsatisfied"]
        blockers += [f"pilotis_displacement_unresolved:{x['function_id']}"
                     for x in displacement if x["status"] == "unresolved"]
        has_unknown = (parking_status == "unresolved" or
                       any("unresolved" in reason for reason in blockers))
        support = ("unresolved" if has_unknown else
                   "programmatically_disfavored" if blockers else "programmatically_supported")
        mandatory_remaining = bool(unsatisfied)
        necessity = ("unresolved" if unresolved else "required" if mandatory_remaining else
                     "not_required_candidate" if eliminates and support == "programmatically_supported"
                     else "retained_candidate")
        selection_status = self._selection(hid, selection)
        ramp = deepcopy(hypothesis.get("ramp_dependency") or {
            "status": "unresolved", "required": None, "evidence": []})
        impacts = self._impacts(hypothesis.get("qualitative_impacts", []))
        next_evidence = list(blockers)
        if not next_evidence and selection_status["status"] != "selected":
            next_evidence.append("design_confirmation_or_project_requirement_for_selection")
        return {
            "hypothesis_id": hid,
            "basement_necessity_status": necessity,
            "basement_functions": {"satisfied": satisfied, "unsatisfied": unsatisfied,
                                   "unresolved": unresolved},
            "pilotis_displacement": displacement,
            "parking_satisfaction": {"status": parking_status, "minimum_required": minimum,
                                     "authoritative_achieved": capacity,
                                     "candidate_or_feasible_capacity_ignored": capacity is None},
            "ramp_dependency": ramp,
            "qualitative_opportunity_costs_and_benefits": impacts,
            "hypothesis_support": support,
            "feasible": support == "programmatically_supported",
            "selection": selection_status,
            "blockers": blockers,
            "next_evidence": next_evidence,
        }

    @staticmethod
    def _authoritative_capacity(record):
        if not isinstance(record, dict):
            return None
        value = record.get("value")
        valid_value = isinstance(value, int) and not isinstance(value, bool) and value >= 0
        if (record.get("semantic") != "authoritative_achieved_capacity" or
                record.get("authority_class") != "AUTHORITATIVE_PROJECT_FACT" or
                not record.get("provenance") or not valid_value):
            return None
        return value

    @staticmethod
    def _function_buckets(functions):
        satisfied, unsatisfied, unresolved = [], [], []
        for item in sorted(functions, key=lambda value: str(value.get("function_id"))):
            fid = item.get("function_id")
            mandatory = item.get("requirement_status")
            if mandatory not in ("mandatory", "optional"):
                unresolved.append(fid)
            elif mandatory == "mandatory" and item.get("satisfaction_status") != "satisfied":
                if item.get("satisfaction_status") == "unknown": unresolved.append(fid)
                else: unsatisfied.append(fid)
            else:
                satisfied.append(fid)
        return satisfied, unsatisfied, unresolved

    @staticmethod
    def _displacement(records):
        result = []
        for item in sorted(records or [], key=lambda value: str(value.get("function_id"))):
            status = item.get("satisfaction_status")
            if item.get("requirement_status") not in ("mandatory", "optional") or status == "unknown":
                normalized = "unresolved"
            elif item.get("requirement_status") == "mandatory" and status != "satisfied":
                normalized = "unsatisfied"
            else:
                normalized = "satisfied"
            result.append({"function_id": item.get("function_id"), "status": normalized,
                           "evidence": deepcopy(item.get("evidence") or [])})
        return result

    @staticmethod
    def _impacts(records):
        return [{"impact_id": item.get("impact_id"), "direction": item.get("direction"),
                 "evidence_status": "evidence_bearing" if item.get("evidence") else "assumption_or_unresolved",
                 "evidence": deepcopy(item.get("evidence") or [])}
                for item in sorted(records or [], key=lambda value: str(value.get("impact_id")))]

    def _selection(self, hypothesis_id, selection):
        valid = (isinstance(selection, dict) and selection.get("hypothesis_id") == hypothesis_id
                 and selection.get("authority_class") in self.SELECTION_AUTHORITIES
                 and bool(selection.get("provenance")))
        return {"status": "selected" if valid else "not_selected", "selected": valid,
                "authority_class": selection.get("authority_class") if valid else None,
                "project_decision": valid}

    def _input_failures(self, minimum, hypotheses):
        failures = []
        if (not isinstance(minimum, dict) or minimum.get("authority_class") not in
                {"HARD_REGULATION", "PROJECT_REQUIREMENT"} or not minimum.get("provenance") or
                not isinstance(minimum.get("value"), int) or isinstance(minimum.get("value"), bool) or
                minimum.get("value", -1) < 0):
            failures.append("authoritative_minimum_parking_requirement_required")
        ids = [x.get("hypothesis_id") for x in hypotheses if isinstance(x, dict)]
        if len(hypotheses) > self.MAX_HYPOTHESES: failures.append("hypothesis_limit_exceeded")
        if len(ids) != len(hypotheses) or any(value is None for value in ids):
            failures.append("hypothesis_identity_missing")
        if len(set(ids)) != len(ids): failures.append("duplicate_hypothesis_identity")
        return sorted(set(failures))
