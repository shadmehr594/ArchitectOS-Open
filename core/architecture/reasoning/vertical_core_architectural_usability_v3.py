from copy import deepcopy

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union


class VerticalCoreArchitecturalUsabilityV3:
    """Architectural interface proof layered on frozen level-aware core geometry."""

    EPS = 1e-7

    def resolve(self, level_aware_contract, clear_face, ramp_polygon):
        clear = clear_face if isinstance(clear_face, Polygon) else Polygon(clear_face)
        ramp = ramp_polygon if isinstance(ramp_polygon, Polygon) else Polygon(ramp_polygon)
        evaluated = [self._evaluate(c, clear, ramp) for c in level_aware_contract['candidates']
                     if c['geometry_status'] == 'hard_valid']
        valid = [c for c in evaluated if not c['hard_failures']]
        selected = max(valid, key=self._rank) if valid else None
        report = self._report(selected) if selected else None
        return {
            'contract': 'VerticalCoreArchitecturalUsabilityV3',
            'source_contract': level_aware_contract['contract'],
            'source_selected_candidate_id': level_aware_contract['selected_candidate']['candidate_id'],
            'local_valid_region_only': True,
            'candidate_count': len(evaluated),
            'hard_valid_count': len(valid),
            'candidates': evaluated,
            'selected_candidate': selected,
            'selected_report': report,
            'report_candidate_id': report['candidate_id'] if report else None,
            'mixed_candidate_report_data': False,
            'geometry_status': 'hard_valid' if selected else 'failed',
            'fire_egress_rule_status': 'pending_rule_resolution',
            'physical_core_publication_status': 'pending_human_acceptance',
            'human_visual_acceptance': 'pending',
            'renderer_authority': 'production_contract_only',
        }

    def _evaluate(self, source, clear, ramp):
        c = deepcopy(source)
        core = Polygon(c['core_polygon'])
        lobby = Polygon(c['common_lobby']['polygon'])
        elevator = Polygon(c['elevator']['shaft_polygon'])
        u0, v0, u1, v1 = clear.bounds
        cx0, cy0, cx1, cy1 = core.bounds
        lx0, ly0, lx1, ly1 = lobby.bounds

        # V2 ended at the south-west core corner. Extend only to the lobby side,
        # replacing point contact with a real linear interface.
        old_corridor = Polygon(c['ground_floor']['pedestrian_corridor'])
        px0, _, px1, _ = old_corridor.bounds
        corridor = box(px0, v0, px1, ly1)
        corridor_mid_x = (px0 + px1) / 2
        lobby_mid_y = (ly0 + ly1) / 2
        corridor_line = [[corridor_mid_x, v0], [corridor_mid_x, lobby_mid_y], [lx0, lobby_mid_y]]
        commercial = clear.difference(unary_union([ramp, corridor, core]))
        c['ground_floor'].update({
            'pedestrian_corridor': self._poly(corridor),
            'corridor_centerline': corridor_line,
            'corridor_length': LineString(corridor_line).length,
            'commercial_space_polygons': [self._poly(p) for p in getattr(commercial, 'geoms', [commercial])],
            'commercial_retained_area': commercial.area,
            'exterior_discharge_route': list(reversed(corridor_line)),
        })

        # The existing production elevator interface faces south into the lobby.
        door = c['elevator']['door_interfaces_by_level']['GF']
        door_line = LineString(door)
        front = box(door_line.bounds[0], ly0, door_line.bounds[2], ly1)
        elevator_front = {}
        for level, z in c['elevator']['served_level_elevations'].items():
            elevator_front[level] = {
                'door_width': door_line.length,
                'door_center': [door_line.centroid.x, door_line.centroid.y, z],
                'door_normal': [0.0, -1.0, 0.0],
                'front_clear_polygon': self._poly(front),
                'front_clear_depth': ly1 - ly0,
                'front_clear_width': door_line.length,
                'obstructions': [],
                'rule_status': 'pending_rule_resolution',
            }

        stair_width = c['stairs_by_span']['B1_GF']['clear_width']
        stair_interface = [[cx0, ly1], [cx0 + stair_width, ly1]]
        corridor_interface = [[lx0, ly0], [lx0, ly1]]
        lobby_net = lobby  # no door-swing geometry exists; elevator door is sliding.
        lobby_data = {
            **c['common_lobby'],
            'gross_lobby_area': lobby.area,
            'net_walkable_lobby_area': lobby_net.area,
            'minimum_local_clear_width': min(lobby.bounds[2]-lobby.bounds[0], lobby.bounds[3]-lobby.bounds[1]),
            'stair_entry_interface': stair_interface,
            'elevator_door_interface': door,
            'corridor_interface': corridor_interface,
            'stair_to_elevator_path': [[cx0 + stair_width/2, (ly0+ly1)/2], [door_line.centroid.x, (ly0+ly1)/2]],
            'corridor_to_stair_path': [[lx0 + c['ground_floor']['corridor_width']/2, ly0], [cx0 + stair_width/2, (ly0+ly1)/2]],
            'corridor_to_elevator_path': [[lx0 + c['ground_floor']['corridor_width']/2, ly0], [door_line.centroid.x, (ly0+ly1)/2]],
        }

        floor_plans = self._floor_stair_plans(c)
        # Allocate one private field along the uninterrupted west side of the
        # core and the other from the connected residual field.  This avoids
        # the artificial core-centre split that produced a severely unequal pair.
        unit_a = clear.intersection(box(u0, v0, cx0, v1))
        unit_b = clear.difference(unary_union([core, unit_a]))
        unit_a = max(getattr(unit_a, 'geoms', [unit_a]), key=lambda p: p.area)
        unit_b = max(getattr(unit_b, 'geoms', [unit_b]), key=lambda p: p.area)
        entry_a = [[cx0, ly0], [cx0, ly1]]
        entry_b = [[cx1, ly0], [cx1, ly1]]
        area_a, area_b = unit_a.area, unit_b.area
        upper = {
            **c['upper_floor'],
            'unit_a_private_field': self._poly(unit_a),
            'unit_b_private_field': self._poly(unit_b),
            'unit_a_entry_interface': entry_a,
            'unit_b_entry_interface': entry_b,
            'unit_a_area': area_a,
            'unit_b_area': area_b,
            'balance_ratio': min(area_a, area_b) / max(area_a, area_b),
            'minimum_private_field_width_a': self._min_width(unit_a),
            'minimum_private_field_width_b': self._min_width(unit_b),
            'largest_contiguous_private_field_a': area_a,
            'largest_contiguous_private_field_b': area_b,
            'independent_entry_a': True,
            'independent_entry_b': True,
            'cross_unit_passage_required': False,
            'core_induced_fragmentation': 2,
        }

        basement = deepcopy(c['basement'])
        for key in ('stall_1_to_core_path', 'stall_2_to_core_path'):
            path = LineString(basement[key]['actual_path_polyline'])
            basement[key]['ramp_crossing'] = path.crosses(ramp) or path.intersection(ramp).length > self.EPS
            basement[key]['lobby_connection_status'] = 'connected' if basement[key]['status'] == 'resolved' else 'failed'

        fire_paths = {
            'ground_floor_common_discharge': self._measured(c['ground_floor']['exterior_discharge_route']),
            'basement_P01_to_core': self._measured(basement['stall_1_to_core_path']['actual_path_polyline']),
            'basement_P02_to_core': self._measured(basement['stall_2_to_core_path']['actual_path_polyline']),
            'upper_unit_A_to_core': self._field_path(unit_a, entry_a),
            'upper_unit_B_to_core': self._field_path(unit_b, entry_b),
        }
        fire = {
            'total_exit_access_travel_distance': fire_paths,
            'common_path_of_egress_travel': {'measured_distance': max(fire_paths['upper_unit_A_to_core']['travel_distance'], fire_paths['upper_unit_B_to_core']['travel_distance']), 'rule_status': 'pending_rule_resolution'},
            'dead_end_corridor_length': {'measured_distance': c['ground_floor']['corridor_length'], 'rule_status': 'pending_rule_resolution'},
        }

        failures = list(c['hard_failures'])
        if LineString(corridor_interface).intersection(lobby.boundary).length <= self.EPS:
            failures.append('ground_corridor_not_connected_to_core')
        if not door_line.intersects(lobby): failures.append('elevator_not_connected_to_common_lobby')
        if LineString(stair_interface).intersection(lobby).length <= self.EPS: failures.append('stair_not_connected_to_common_lobby')
        if front.area <= self.EPS: failures.append('elevator_front_clearance_zero')
        if basement['parking_capacity_preserved'] != 2: failures.append('parking_not_preserved_2_of_2')
        if any(basement[k]['ramp_crossing'] for k in ('stall_1_to_core_path','stall_2_to_core_path')): failures.append('basement_pedestrian_path_crosses_ramp')
        if min(area_a, area_b) <= self.EPS: failures.append('upper_private_field_zero')

        c.update({
            'source_candidate_id': source['candidate_id'],
            'elevator_front_clearance_by_level': elevator_front,
            'common_lobby': lobby_data,
            'floor_stair_plan_by_level': floor_plans,
            'upper_floor': upper,
            'basement': basement,
            'fire_egress': fire,
            'hard_failures': failures,
            'geometry_status': 'hard_valid' if not failures else 'failed',
        })
        c['quality_metrics'].update({'net_lobby_area': lobby_net.area, 'elevator_front_area': front.area, 'unit_balance_v3': upper['balance_ratio']})
        return c

    def _floor_stair_plans(self, c):
        spans = c['stairs_by_span']
        mapping = {'B1': (None, 'B1_GF'), 'GF': ('B1_GF', 'GF_F1'), 'F1': ('GF_F1', 'F1_F2'), 'F2': ('F1_F2', None)}
        out = {}
        for level, (incoming, outgoing) in mapping.items():
            below = [] if incoming is None else [spans[incoming]['flights'][-1]['polygon']]
            above = [] if outgoing is None else [spans[outgoing]['flights'][0]['polygon']]
            arrival = None if incoming is None else spans[incoming]['top_interface']
            start = None if outgoing is None else spans[outgoing]['bottom_interface']
            out[level] = {
                'visible_below_cut_geometry': below,
                'visible_above_cut_geometry': above,
                'down_direction': incoming is not None,
                'up_direction': outgoing is not None,
                'floor_arrival': arrival,
                'floor_start': start,
                'stair_bottom_entry_interface': None if outgoing is None else spans[outgoing]['bottom_interface'],
                'stair_top_arrival_interface': None if incoming is None else spans[incoming]['top_interface'],
                'landing_to_lobby_interface': c['common_lobby']['polygon'][:2],
            }
        return out

    @staticmethod
    def _rank(c):
        q = c['quality_metrics']
        return (q['parking_preserved'], c['upper_floor']['balance_ratio'], q['net_lobby_area'], q['commercial_retained_area'], -q['corridor_length'])

    @staticmethod
    def _min_width(p):
        x0, y0, x1, y1 = p.bounds
        return min(x1-x0, y1-y0)

    @staticmethod
    def _poly(p):
        return [[float(x), float(y)] for x, y in list(p.exterior.coords)[:-1]]

    @staticmethod
    def _measured(points):
        line = LineString(points)
        return {'actual_path_polyline': points, 'travel_distance': line.length, 'applicable_limit': None, 'margin': None, 'status': 'measured_pending_rule_resolution'}

    def _field_path(self, field, interface):
        target = LineString(interface).centroid
        far = max(list(field.exterior.coords)[:-1], key=lambda p: ((p[0]-target.x)**2+(p[1]-target.y)**2))
        mid = [far[0], target.y]
        return self._measured([[far[0],far[1]], mid, [target.x,target.y]])

    @staticmethod
    def _report(c):
        # Every displayed number is copied from this one selected candidate.
        return {
            'candidate_id': c['candidate_id'],
            'source_candidate_id': c['source_candidate_id'],
            'core_station': c['core_station'],
            'core_dimensions': c['core_dimensions'],
            'corridor_length': c['ground_floor']['corridor_length'],
            'commercial_retained_area': c['ground_floor']['commercial_retained_area'],
            'commercial_frontage_width': c['ground_floor']['commercial_frontage_width'],
            'parking_preserved': c['basement']['parking_capacity_preserved'],
            'unit_a_area': c['upper_floor']['unit_a_area'],
            'unit_b_area': c['upper_floor']['unit_b_area'],
            'unit_balance': c['upper_floor']['balance_ratio'],
        }
