"""Normalized, source-aware space requirements for program-driven planning."""


class ProgramSpaceRequirementV1:
    CATEGORIES = {
        "commercial": "public_commercial", "commercial_entrance": "public_commercial", "storefront": "public_commercial",
        "common_lobby": "residential_common", "stair": "residential_common", "elevator": "residential_common",
        "common_wc": "residential_common", "guard_room": "optional_occupied_support", "caretaker_unit": "optional_occupied_support",
        "parking": "vehicle", "vehicle_entrance": "vehicle", "drive_lane": "vehicle", "maneuvering_field": "vehicle",
        "mechanical_room": "service", "electrical_room": "service", "utility_room": "service", "refuse_room": "service",
        "residential_storage": "residential_support", "bicycle_storage": "residential_support", "stroller_storage": "residential_support",
    }

    @classmethod
    def normalize(cls, requirement):
        r = dict(requirement)
        space_type = r["space_type"]
        required = bool(r.get("required", False))
        preferred = bool(r.get("preferred", False))
        source = r.get("requirement_source", "unresolved_source")
        hard = bool(r.get("hard_requirement", required))
        return {
            "contract": "ProgramSpaceRequirementV1", "space_type": space_type,
            "space_category": r.get("space_category", cls.CATEGORIES.get(space_type, "unclassified")),
            "required": required, "preferred": preferred, "count": int(r.get("count", r.get("required_count", 1))),
            "required_count": int(r.get("required_count", r.get("count", 1))) if required else int(r.get("required_count", 0)),
            "minimum_area": r.get("minimum_area"), "maximum_area": r.get("maximum_area"),
            "preferred_area": r.get("preferred_area"), "area_goal": r.get("area_goal"),
            "minimum_width": r.get("minimum_width"), "maximum_width": r.get("maximum_width"),
            "maximum_area_per_unit": r.get("maximum_area_per_unit"),
            "preferred_area_per_unit": r.get("preferred_area_per_unit"),
            "expandable": bool(r.get("expandable", False)), "shrinkable": bool(r.get("shrinkable", False)),
            "removable": bool(r.get("removable", not required)), "hard_requirement": hard,
            "soft_preference": bool(r.get("soft_preference", preferred and not hard)),
            "adjacency_preferences": list(r.get("adjacency_preferences", [])),
            "separation_requirements": list(r.get("separation_requirements", [])),
            "access_requirements": list(r.get("access_requirements", [])),
            "priority": int(r.get("priority", 100 if hard else 50 if preferred else 10)),
            "requirement_source": source,
            "regulatory_status": r.get("regulatory_status", "pending_rule_resolution" if source in ("engineering_assumption", "unresolved_source") else "project_input"),
        }

    @classmethod
    def manifest(cls, requirements):
        normalized = [cls.normalize(r) for r in requirements]
        return {
            "contract": "ProgramManifestV1", "requirements": normalized,
            "required_program": [r for r in normalized if r["required"]],
            "preferred_program": [r for r in normalized if not r["required"] and r["preferred"]],
            "optional_program": [r for r in normalized if not r["required"] and not r["preferred"]],
            "priority_reasoning": sorted(({"space_type": r["space_type"], "priority": r["priority"],
                                             "hard_requirement": r["hard_requirement"]} for r in normalized),
                                            key=lambda x: -x["priority"]),
        }
