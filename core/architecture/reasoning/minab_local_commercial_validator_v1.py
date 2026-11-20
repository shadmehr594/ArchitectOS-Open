"""Minab-only commercial-rule validator; never a project-value generator."""
from copy import deepcopy


class MinabLocalCommercialValidatorV1:
    def validate(self, fields):
        values = {key: deepcopy(item.get("value")) for key, item in fields.items()}
        if values.get("local_regulation_jurisdiction") != "MINAB_LOCAL_ONLY":
            return {"status": "pass", "applicable": False, "reason": "jurisdiction_not_minab", "input_overwritten": False, "findings": []}
        needed = [x for x in ("commercial_area_target", "commercial_use_type") if values.get(x) is None]
        if needed:
            return {"status": "unresolved", "applicable": True, "human_input_required": needed, "input_overwritten": False, "findings": []}
        area = float(values["commercial_area_target"])
        use = values["commercial_use_type"]
        findings = []
        status = "pass"
        if use == "floating_commercial_eligible_axis" and area > 100:
            status = "approval_required"; findings.append("ARTICLE_5_CASE_SPECIFIC_APPROVAL_REQUIRED")
        elif use == "residential_land_neighborhood_exception" and area > 18:
            status = "conflict"; findings.append("ONE_COMMERCIAL_UNIT_MAX_18_M2_WITH_PARKING")
        elif use == "commercial_service_land":
            findings.append("NO_GLOBAL_100_M2_CAP_LOCAL_ZONING_CONTROLS_APPLY")
        return {"status": status, "applicable": True, "jurisdiction": "MINAB_LOCAL_ONLY",
                "document_status": "PRIMARY_LOCAL_WORKING_REGULATION", "promulgation_status": "promulgation_unverified",
                "findings": findings, "input_overwritten": False}
