"""Floor-level terminal alignment and downstream maneuver-field proof.

This reasoner is deliberately downstream of EdgeControlledCurvedRampTopologyV3.
It consumes recorded V3 candidates and never regenerates their XY ramp geometry.
"""
from math import atan2, cos, pi, sin

from shapely.geometry import LineString, Point, Polygon, box


class TerminalRampFloorAlignmentV1:
    EPS = 1e-7

    def resolve(self, candidates, inner_clear_face, basement_z=-2.4,
                terminal_width=3.0, preferred=5.0, minimum=4.5):
        inner = inner_clear_face if isinstance(inner_clear_face, Polygon) else Polygon(inner_clear_face)
        result = {
            "contract": "TerminalRampFloorAlignmentV1Search",
            "source": "recorded_edge_controlled_v3_hard_valid_candidates",
            "v3_search_rerun": False,
            "candidates": [],
            "hard_valid_candidates": [],
            "parking_search_status": "not_run_terminal_arrival_validation",
            "physical_ramp_published": False,
            "human_visual_acceptance": "pending",
        }
        for source in candidates:
            if source.get("geometry_status") != "hard_valid":
                continue
            for target_heading_name, target_heading in self._site_local_transverse_headings(source):
                for radius in (6.5, 7.0, 7.5):  # centerline radii; 3m floor corridor => Rinner >= 5m
                    for straight_length in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
                        alignment = self._alignment(source, target_heading_name, target_heading,
                                                    radius, straight_length, basement_z, terminal_width)
                        for size in (preferred, minimum):
                            record = self._bind_field(source, alignment, inner, size, basement_z)
                            result["candidates"].append(record)
                            if record["geometry_status"] == "hard_valid":
                                result["hard_valid_candidates"].append(record["candidate_id"])
        result["status"] = "terminal_arrival_resolved" if result["hard_valid_candidates"] else "terminal_arrival_unresolved"
        return result

    @staticmethod
    def _site_local_transverse_headings(source):
        # V3 is already expressed in the parcel-local frame: frontage is local U,
        # depth is local V.  The two operational transverse directions are +/-U.
        return (("parcel_local_transverse_negative", (-1.0, 0.0)),
                ("parcel_local_transverse_positive", (1.0, 0.0)))

    def _alignment(self, source, target_name, target, radius, straight_length, z, width):
        topology = source["topology"]
        start = tuple(topology["end_point"])
        h0 = self._unit(topology["end_heading"])
        a0, at = atan2(h0[1], h0[0]), atan2(target[1], target[0])
        delta = self._wrap(at - a0)
        turn = 1.0 if delta >= 0 else -1.0
        normal = (-h0[1] * turn, h0[0] * turn)
        center = (start[0] + normal[0] * radius, start[1] + normal[1] * radius)
        radial0 = (start[0] - center[0], start[1] - center[1])
        steps = max(3, int(abs(delta) / (pi / 72)) + 1)
        arc = []
        for i in range(steps + 1):
            q = delta * i / steps
            arc.append((center[0] + radial0[0] * cos(q) - radial0[1] * sin(q),
                        center[1] + radial0[0] * sin(q) + radial0[1] * cos(q)))
        terminal_start = arc[-1]
        terminal_end = (terminal_start[0] + target[0] * straight_length,
                        terminal_start[1] + target[1] * straight_length)
        centerline = arc + [terminal_end]
        surface = LineString(centerline).buffer(width / 2, cap_style=2, join_style=1)
        end_edge = self._edge(terminal_end, target, width)
        movement = list(topology["centerline"]) + centerline[1:]
        return {
            "contract": "TerminalRampFloorAlignmentV1",
            "tangent_out": topology["tangent_out"],
            "terminal_leg_start": list(terminal_start),
            "terminal_leg_end": list(terminal_end),
            "terminal_heading": list(target),
            "terminal_heading_name": target_name,
            "end_edge": end_edge,
            "end_edge_heading": [-target[1], target[0]],
            "end_edge_width": width,
            "end_left": end_edge[0] + [z],
            "end_right": end_edge[1] + [z],
            "end_midpoint": [terminal_end[0], terminal_end[1], z],
            "z_start": z, "z_end": z,
            "terminal_length": straight_length,
            "steering_transition_centerline": [list(p) for p in arc],
            "steering_transition_radius_centerline": radius,
            "steering_transition_inner_radius": radius - width / 2,
            "terminal_surface": [list(p) for p in list(surface.exterior.coords)[:-1]],
            "terminal_floor_interface": end_edge,
            "center_movement_path": [list(p) for p in movement],
            "return_movement_path": [list(p) for p in reversed(movement)],
        }

    def _bind_field(self, source, alignment, inner, size, z):
        h = alignment["terminal_heading"]
        e = alignment["end_midpoint"]
        # Axis-aligned field begins exactly at the END cross-section and lies downstream.
        if h[0] < -0.5:
            field = box(e[0] - size, e[1] - size / 2, e[0], e[1] + size / 2)
        elif h[0] > 0.5:
            field = box(e[0], e[1] - size / 2, e[0] + size, e[1] + size / 2)
        else:
            field = box(e[0] - size / 2, e[1], e[0] + size / 2, e[1] + size)
        ramp = Polygon(source["surface"])
        terminal = Polygon(alignment["terminal_surface"])
        overlap_ramp = field.intersection(ramp).area
        overlap_terminal = field.intersection(terminal).area
        interface = LineString(alignment["end_edge"]).intersection(field.boundary)
        interface_length = interface.length
        samples = [field.representative_point()] + [Point(x, y) for x, y in list(field.exterior.coords)[:-1]]
        downstream = all((p.x - e[0]) * h[0] + (p.y - e[1]) * h[1] >= -self.EPS for p in samples)
        failures = []
        if alignment["steering_transition_inner_radius"] < 5.0 - self.EPS: failures.append("terminal_heading_not_operational")
        if alignment["terminal_length"] <= self.EPS: failures.append("terminal_leg_not_generated")
        if not inner.buffer(self.EPS).covers(terminal): failures.append("terminal_leg_outside_clear_face")
        if not inner.buffer(self.EPS).covers(field): failures.append("maneuvering_field_outside_clear_face")
        if overlap_ramp > self.EPS: failures.append("maneuvering_field_overlaps_sloped_ramp")
        if overlap_terminal > self.EPS: failures.append("maneuvering_field_overlaps_terminal_surface")
        if not downstream: failures.append("maneuvering_field_behind_end")
        if interface_length < 3.0 - self.EPS: failures.append("end_to_maneuver_shared_boundary_insufficient")
        if abs(alignment["z_end"] - z) > self.EPS: failures.append("terminal_end_not_level")
        field_center = [field.centroid.x, field.centroid.y]
        path = alignment["center_movement_path"] + [field_center]
        if not inner.buffer(self.EPS).covers(LineString(path[-2:])): failures.append("vehicle_path_end_to_field_disconnected")
        cid = f"TFA-{source['candidate_id']}-{alignment['terminal_heading_name']}-R{alignment['steering_transition_radius_centerline']:.1f}-L{alignment['terminal_length']:.1f}-M{size:.1f}"
        return {
            "candidate_id": cid, "source_candidate_id": source["candidate_id"],
            "geometry_status": "hard_valid" if not failures else "not_feasible",
            "failure_reasons": failures,
            "source_ramp_surface": source["surface"],
            "source_ramp_centerline": source["topology"]["centerline"],
            "alignment": alignment,
            "maneuvering_field": [list(p) for p in list(field.exterior.coords)[:-1]],
            "maneuvering_dimensions": [size, size],
            "maneuvering_floor_z": z,
            "end_interface_segment": alignment["end_edge"] if interface_length >= 3.0 - self.EPS else [],
            "end_interface_width": interface_length,
            "ramp_maneuver_overlap_area": overlap_ramp,
            "terminal_maneuver_overlap_area": overlap_terminal,
            "downstream_half_plane_valid": downstream,
            "vehicle_path": path,
            "return_path": list(reversed(path)),
            "parking_search_status": "not_run_terminal_arrival_validation",
        }

    @staticmethod
    def _edge(center, heading, width):
        n = (-heading[1], heading[0])
        return [[center[0] - n[0] * width / 2, center[1] - n[1] * width / 2],
                [center[0] + n[0] * width / 2, center[1] + n[1] * width / 2]]

    @staticmethod
    def _unit(v):
        length = (v[0] ** 2 + v[1] ** 2) ** .5
        return (v[0] / length, v[1] / length)

    @staticmethod
    def _wrap(a):
        while a <= -pi: a += 2 * pi
        while a > pi: a -= 2 * pi
        return a
