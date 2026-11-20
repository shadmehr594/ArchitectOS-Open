"""Conditional zoning-rule applicability contract."""
class ZoningRuleApplicabilityV1:
    def evaluate(self,rule_id,rule_name,source,value,applies_if,does_not_apply_if,context):
        blocked=all(context.get(k)==v for k,v in does_not_apply_if.items()) if does_not_apply_if else False
        matched=all(context.get(k)==v for k,v in applies_if.items()) if applies_if else True
        status="not_applicable" if blocked else "applicable" if matched else "unresolved"
        return {"contract":"ZoningRuleApplicabilityV1","rule_id":rule_id,"rule_name":rule_name,"source":source,"value":value,
                "applies_if":applies_if,"does_not_apply_if":does_not_apply_if,"current_case_status":status,
                "current_case_reason":"explicit_current_case_exclusion" if blocked else "applicability_conditions_satisfied" if matched else "applicability_conditions_not_proven"}
