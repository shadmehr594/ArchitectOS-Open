"""Explain program compliance without silently relaxing hard requirements."""


class ProgramConflictAnalysisV1:
    def analyze(self, manifest, generated):
        satisfied, unsatisfied, hard, soft, dropped, shrunk, conflicts, relaxations = [], [], [], [], [], [], [], []
        ledger = {s["space_type"]: s for s in generated}
        for req in manifest["requirements"]:
            item = ledger.get(req["space_type"], {"generated_count": 0, "generated_area": 0})
            if not req["required"] and not req["preferred"] and item.get("generated_count", 0) == 0:
                dropped.append(req["space_type"])
                continue
            count_ok = item.get("generated_count", 0) >= (req["required_count"] if req["required"] else 0)
            area_ok = req["minimum_area"] is None or item.get("generated_area", 0) >= req["minimum_area"]
            if count_ok and area_ok and (item.get("generated_count", 0) > 0 or req["required"]):
                satisfied.append(req["space_type"])
                if req["preferred_area"] and item.get("generated_area", 0) < req["preferred_area"]: shrunk.append(req["space_type"])
            else:
                reason = f'{req["space_type"]}_count_shortfall' if not count_ok else f'{req["space_type"]}_minimum_area_shortfall'
                unsatisfied.append(reason)
                (hard if req["hard_requirement"] else soft).append(reason)
                conflicts.append({"requirement": req["space_type"], "reason": reason,
                                  "required_count": req["required_count"], "generated_count": item.get("generated_count", 0)})
                if req["removable"]: dropped.append(req["space_type"]); relaxations.append(f'remove_optional_{req["space_type"]}')
                elif req["shrinkable"]: relaxations.append(f'reduce_{req["space_type"]}_only_with_user_approval')
        pending = any(r["regulatory_status"] == "pending_rule_resolution" and r["space_type"] in satisfied for r in manifest["requirements"])
        status = "program_conflict" if hard else "program_partially_satisfied" if soft else "program_compliant_pending_regulatory_validation" if pending else "program_compliant"
        return {"contract": "ProgramConflictAnalysisV1", "program_status": status,
                "program_requirements_satisfied": satisfied, "program_requirements_unsatisfied": unsatisfied,
                "hard_requirement_failures": hard, "soft_requirement_failures": soft,
                "conflicts": conflicts, "optional_spaces_dropped": dropped, "shrinkable_spaces_reduced": shrunk,
                "suggested_relaxations": list(dict.fromkeys(relaxations)), "hard_requirements_silently_relaxed": False}
