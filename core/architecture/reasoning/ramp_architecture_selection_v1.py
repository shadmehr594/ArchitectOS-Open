class RampArchitectureSelectionV1:
    """Hard-gate candidates before comparing complete basement quality."""

    HARD_VALID_STATUS = 'architecture_selected_candidate'

    def freeze_two_curve_baseline(self, candidate_id, remaining_contiguous_field):
        return {
            'candidate_id': candidate_id,
            'geometry_status': 'hard_valid',
            'architecture_selection_status': 'valid_but_not_preferred_for_parcel2',
            'selection_reason': 'excessive_central_field_fragmentation',
            'remaining_contiguous_usable_field': float(remaining_contiguous_field),
            'geometry_modified': False,
        }

    def select(self, candidates):
        eligible = [c for c in candidates if c['status'] == self.HARD_VALID_STATUS]
        if not eligible:
            return None
        # Capacity is a hard architectural priority.  Thereafter preserve the
        # largest contiguous field, reduce fragmentation and ramp intrusion;
        # use gentler slope only when the layouts are otherwise comparable.
        return max(eligible, key=lambda c: (
            c['parking_stall_count'],
            c['largest_contiguous_usable_field'],
            -c['fragmentation_count'],
            -c['ramp_footprint_area'],
            -c['slope'],
            c['candidate_id'],
        ))
