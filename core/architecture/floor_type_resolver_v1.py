"""Evidence-bearing canonical floor-type resolution for architecture contracts."""
from copy import deepcopy


class CanonicalFloorTypeResolverV1:
    """Resolve floor type from explicit project/program semantics, never geometry."""

    LEVEL_ROLE_TYPES = {
        "basement": "basement",
        "residential_floor_1": "residential",
        "residential_floor_2": "residential",
        "roof": "roof",
        "stairhouse": "roof_superstructure",
        "stairhouse_base": "roof_superstructure",
        "stairhouse_top": "roof_superstructure",
    }
    RESIDENTIAL_SPACE_ROLES = frozenset({
        "bedroom", "dining", "family", "kitchen", "living", "residential",
    })

    def resolve(self, floor_name, building_program, explicit_type=None):
        if explicit_type is not None:
            return {"type": deepcopy(explicit_type), "status": "resolved",
                    "source": "explicit_floor_type",
                    "evidence": [{"kind": "explicit_floor_type", "value": deepcopy(explicit_type)}]}

        program = building_program if isinstance(building_program, dict) else {}
        level_roles = program.get("level_roles", {})
        role = level_roles.get(floor_name) if isinstance(level_roles, dict) else None
        canonical_role = str(role).lower() if role else str(floor_name).lower()
        if canonical_role in self.LEVEL_ROLE_TYPES:
            return {"type": self.LEVEL_ROLE_TYPES[canonical_role], "status": "resolved",
                    "source": "project_level_role_semantics",
                    "evidence": [{"kind": "level_role", "level": floor_name, "role": canonical_role}]}

        vertical = program.get("vertical_organization", {})
        members = vertical.get(floor_name, []) if isinstance(vertical, dict) else []
        spaces = program.get("spaces", [])
        roles = {str(space.get("role", space.get("type", ""))).lower()
                 for space in spaces if isinstance(space, dict) and
                 (space.get("name") in members or space.get("floor") == floor_name)}
        roles.discard("")
        if roles and roles.issubset(self.RESIDENTIAL_SPACE_ROLES):
            return {"type": "residential", "status": "resolved",
                    "source": "floor_program_space_roles",
                    "evidence": [{"kind": "program_space_roles", "level": floor_name,
                                  "roles": sorted(roles)}]}

        return {"type": None, "status": "unresolved",
                "source": "insufficient_semantic_evidence", "evidence": []}
