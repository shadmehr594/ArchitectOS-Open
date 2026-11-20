import hashlib
import json


class ProgramAlternativeRecommendationV1:
    """Escalates an exhausted local design conflict without mutating the program."""

    REQUIRED_BASIS = [
        'all_local_core_candidates_fail_commercial_quality',
        'basement_ramp_consumes_ground_floor_design_capacity',
        'ramp_and_core_combination_fragments_commercial_space',
        'commercial_rear_tail_dependency',
        'commercial_narrow_neck_dependency',
        'local_core_repositioning_failed_to_resolve_problem',
    ]

    def resolve(self, commercial_checkpoint):
        count = int(commercial_checkpoint['candidate_count'])
        failed = sum(
            c['commercial_spatial_quality']['architectural_quality_status'] == 'quality_failed'
            for c in commercial_checkpoint['candidates']
        )
        exhausted = count == 7 and failed == count
        baseline = commercial_checkpoint['current_diagnostic_counterexample']
        if not exhausted:
            return self._unresolved(count, failed, baseline)

        return {
            'contract': 'ProgramAlternativeRecommendationV1',
            'site': 'REAL Parcel 2',
            'baseline_scenario': 'basement_parking',
            'baseline_status': 'technically_feasible_architecturally_poor',
            'baseline_scenario_a': self._baseline(baseline),
            'local_candidate_count': count,
            'local_commercial_quality_failure_count': failed,
            'local_commercial_quality_failure_ratio': failed / count,
            'local_core_optimization_exhausted': True,
            'local_optimization_status': 'exhausted',
            'preferred_program_direction': 'evaluate_pilot_parking_without_basement',
            'recommended_alternative': 'pilot_parking_without_basement',
            'recommended_next_scenario': 'pilot_parking_without_basement',
            'recommended_next_action': 'generate_pilot_parking_feasibility_study',
            'recommendation_strength': 'strong',
            'recommendation_basis': list(self.REQUIRED_BASIS),
            'basement_removal_recommended_for_evaluation': True,
            'basement_removal_approved': False,
            'pilot_parking_feasibility_status': 'not_tested',
            'pilot_parking_capacity': None,
            'pilot_vehicle_maneuvering_status': 'not_generated',
            'pilot_parking_claimed_feasible': False,
            'pilot_study_contract': {
                'contract': 'PilotParkingFeasibilityStudyV1',
                'status': 'not_generated',
                'next_study_only': True,
                'core_repositioning_permitted': True,
                'existing_core_reuse_required': False,
                'required_scenario_families': ['PILOT-P01','PILOT-P02','PILOT-P03','PILOT-P04'],
                'geometry_generation_executed': False,
            },
            'hypotheses_requiring_geometric_test': [
                'ramp_area_may_be_released',
                'parking_excavation_may_be_removed',
                'core_placement_freedom_may_increase',
                'commercial_continuity_and_frontage_quality_may_improve',
            ],
            'user_facing_advisory': (
                'The current basement parking scheme is geometrically feasible, but all seven locally valid '
                'vertical-core alternatives produce unacceptable commercial spatial quality. Local core '
                'repositioning has therefore failed to resolve the architectural conflict. ArchitectOS '
                'recommends testing removal of basement parking and providing the required parking at pilot/'
                'ground-floor level. This may eliminate the vehicle ramp, reduce excavation, increase core '
                'placement freedom, and improve commercial continuity. Pilot parking capacity and vehicle '
                'maneuvering have not been proven and must be tested geometrically before basement removal '
                'can be recommended for approval.'
            ),
            'program_changed': False,
            'basement_deleted': False,
            'baseline_geometry_regenerated': False,
            'pilot_geometry_generated': False,
            'structure_executed': False,
            'bim_executed': False,
            'ifc_executed': False,
            'human_decision_required': True,
            'publication_status': 'recommendation_pending_human_review',
        }

    @staticmethod
    def _fingerprint(value):
        payload=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
        return hashlib.sha256(payload).hexdigest()

    def _baseline(self, c):
        geometry = {
            'core_polygon': c['core_polygon'],
            'ramp_conflict_area': c['basement']['ramp_conflict_area'],
            'parking_capacity_preserved': c['basement']['parking_capacity_preserved'],
            'stairs_by_span': c['stairs_by_span'],
            'elevator': c['elevator'],
        }
        return {
            'candidate_id': c['candidate_id'],
            'geometry_status': c['geometry_status'],
            'commercial_architectural_quality_status': 'rejected_by_human_review',
            'human_rejection_reason': 'commercial_space_fragmented_by_core_with_narrow_rear_tail',
            'whole_building_architectural_status': 'requires_tradeoff_review',
            'parking_capacity': c['basement']['parking_capacity_preserved'],
            'geometry_preservation_fingerprint': self._fingerprint(geometry),
            'geometry_preserved_as_read_only_baseline': True,
        }

    def _unresolved(self, count, failed, baseline):
        return {
            'contract':'ProgramAlternativeRecommendationV1',
            'baseline_scenario':'basement_parking',
            'baseline_scenario_a':self._baseline(baseline),
            'local_candidate_count':count,
            'local_commercial_quality_failure_count':failed,
            'local_core_optimization_exhausted':False,
            'recommendation_strength':'insufficient_evidence',
            'program_changed':False,
            'basement_deleted':False,
            'human_decision_required':True,
        }
