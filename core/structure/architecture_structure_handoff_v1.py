from copy import deepcopy


class ArchitectureStructureContractError(ValueError):
    """Raised when architecture-first evidence is unsafe for structure."""


class ArchitectureStructureHandoffV1:
    """Read-only boundary between authoritative architecture and structure."""

    VERSION = "1.0"

    FLOOR_SPAN_COLLECTIONS = (
        "spaces",
        "boundaries",
        "boundary_segments",
        "physical_walls",
        "floor_geometry",
    )

    @classmethod
    def require_ready(cls, handoff, consumer="structure"):
        """Fail closed for rejected or incomplete architecture-first handoffs."""
        if not isinstance(handoff, dict):
            return

        status = handoff.get("status")
        architecture_first = bool(handoff.get("architecture_first", False))
        must_reject = status == "rejected" or (
            architecture_first and status != "ready"
        )

        if not must_reject:
            return

        errors = handoff.get("errors", [])
        if not isinstance(errors, list):
            errors = [str(errors)]
        detail = ", ".join(str(error) for error in errors) or (
            f"invalid_handoff_status:{status}"
        )
        raise ArchitectureStructureContractError(
            f"architecture_structure_handoff_rejected:{consumer}:{detail}"
        )

    def create(self, architectural_model, vertical_section):
        architectural_model = (
            architectural_model
            if isinstance(architectural_model, dict)
            else {}
        )
        vertical_section = (
            vertical_section
            if isinstance(vertical_section, dict)
            else {}
        )

        architecture_first = bool(
            architectural_model.get("architecture_first", False)
        )
        architectural_geometry = architectural_model.get(
            "architectural_geometry",
            {}
        )
        if not isinstance(architectural_geometry, dict):
            architectural_geometry = {}

        source_levels = vertical_section.get("levels", [])
        if not isinstance(source_levels, list):
            source_levels = []

        levels = [
            deepcopy(level)
            for level in source_levels
            if isinstance(level, dict)
        ]
        levels_by_name = {
            level.get("name"): level
            for level in levels
            if level.get("name") is not None
        }

        errors = []

        if architecture_first:
            if not architectural_geometry:
                errors.append("architectural_geometry_missing")

            if not levels:
                errors.append("vertical_section_levels_missing")

            for level in levels:
                level_name = level.get("name")
                if level_name is None:
                    errors.append("level_name_missing")
                    continue

                for key in ("bottom", "top", "height"):
                    if not isinstance(level.get(key), (int, float)):
                        errors.append(
                            f"level_{key}_missing:{level_name}"
                        )

            for collection_name in self.FLOOR_SPAN_COLLECTIONS:
                collection = architectural_geometry.get(
                    collection_name,
                    []
                )
                if not isinstance(collection, list):
                    errors.append(
                        f"invalid_architectural_collection:{collection_name}"
                    )
                    continue

                for item in collection:
                    if not isinstance(item, dict):
                        continue

                    floor = item.get("floor")
                    level = levels_by_name.get(floor)
                    if level is None:
                        errors.append(
                            f"unknown_architectural_floor:{collection_name}:{floor}"
                        )
                        continue

                    for key in ("bottom", "top", "height"):
                        if item.get(key) != level.get(key):
                            errors.append(
                                f"architectural_span_mismatch:{collection_name}:{floor}:{key}"
                            )

            for slab in architectural_geometry.get("slabs", []):
                if not isinstance(slab, dict):
                    continue
                floor = slab.get("floor")
                level = levels_by_name.get(floor)
                if level is None:
                    errors.append(f"unknown_architectural_floor:slabs:{floor}")
                    continue
                for key in ("bottom", "top"):
                    if slab.get(key) != level.get(key):
                        errors.append(
                            f"architectural_span_mismatch:slabs:{floor}:{key}"
                        )

        if architecture_first:
            status = "ready" if not errors else "rejected"
        else:
            status = "legacy_compatible"

        return {
            "version": self.VERSION,
            "status": status,
            "architecture_first": architecture_first,
            "ownership": "architecture_authoritative_structure_read_only",
            "errors": list(dict.fromkeys(errors)),
            "levels": levels,
            "levels_by_name": deepcopy(levels_by_name),
            "architectural_geometry": deepcopy(architectural_geometry),
            "coordinate_frame": deepcopy(
                architectural_model.get("coordinate_frame", {})
            ),
            "parcel_placement": deepcopy(
                architectural_model.get("parcel_placement", {})
            ),
        }
