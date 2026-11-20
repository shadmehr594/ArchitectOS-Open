"""Vertical stack proof for a projection usable at the first residential floor."""


class ProjectionVerticalStackIntelligenceV1:
    def resolve(self, levels, minimum_clear_height, road_reference_elevation=0.0,
                projection_enabled=False, projection_use="PRIVATE_TERRACE"):
        ground_floor = levels.get("ground_floor_floor_level")
        ground_ceiling = levels.get("ground_floor_ceiling_level")
        first_floor = levels.get("first_residential_floor_level")
        first_ceiling = levels.get("first_residential_ceiling_level")
        lower = levels.get("projection_lower_slab_level")
        upper = levels.get("projection_upper_boundary_level")
        underside = levels.get("underside_projection_elevation")
        lower_exists = lower is not None
        aligned = lower_exists and first_floor is not None and abs(lower-first_floor) <= 1e-6
        clearance = None if underside is None else underside-road_reference_elevation
        clearance_status = "pending_rule_resolution" if clearance is None else "passed" if clearance >= minimum_clear_height else "failed"
        usable = projection_enabled and lower_exists and aligned and upper is not None and upper > lower
        return {
            "contract":"ProjectionVerticalStackIntelligenceV1",
            "ground_floor_floor_level":ground_floor, "ground_floor_ceiling_level":ground_ceiling,
            "first_residential_floor_level":first_floor, "first_residential_ceiling_level":first_ceiling,
            "projection_lower_slab_level":lower, "projection_upper_boundary_level":upper,
            "underside_projection_elevation":underside,
            "projection_floor_slab":{"level":lower, "role":"GROUND_FLOOR_ROOF_AND_FIRST_RESIDENTIAL_FLOOR_SLAB"} if lower_exists else None,
            "projection_upper_cover_or_next_floor_slab":{"level":upper, "role":"FIRST_RESIDENTIAL_ROOF_OR_NEXT_SLAB"} if upper is not None else None,
            "projection_lower_slab_equals_first_residential_floor_level":aligned,
            "usable_projection_vertical_zone":{"lower_level":lower,"upper_level":upper,"use":projection_use} if usable else None,
            "usable_projection_area_claim_permitted":usable,
            "upper_roof_overhang_only":projection_enabled and not lower_exists,
            "road_reference_elevation":road_reference_elevation, "actual_public_road_clear_height":clearance,
            "minimum_required_clear_height":minimum_clear_height, "public_road_clearance_status":clearance_status,
            "clearance_check_geometry":"underside_of_lower_projection_slab",
            "far_treatment_status":"pending_rule_resolution", "regulatory_status":"pending_exact_boundary_condition_and_local_approval_interpretation",
        }
