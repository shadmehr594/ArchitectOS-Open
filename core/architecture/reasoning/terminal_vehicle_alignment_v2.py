"""Floor-level terminal alignment coupled to an axis-aligned maneuver field."""
from shapely.geometry import LineString, Polygon

from core.architecture.reasoning.terminal_vehicle_alignment_v1 import TerminalVehicleAlignmentV1
from core.architecture.reasoning.ramp_centerline_topology_v2 import RampCenterlineTopologyV2


class TerminalVehicleAlignmentV2:
    EPS = 1e-7

    def resolve(self, start_point, start_heading, clear_envelope, ramp_surface,
                end_width=3.0, preferred=(5.0, 5.0), minimum=(4.5, 4.5), inner_radius=5.0):
        envelope = Polygon(clear_envelope)
        ramp = Polygon(ramp_surface)
        alignment = TerminalVehicleAlignmentV1().resolve(
            start_point, start_heading, clear_envelope, end_width, inner_radius)
        trials = []
        for alternative in alignment["alternatives"]:
            if alternative["geometry_status"] not in ("resolved", "already_aligned"):
                continue
            heading = alternative.get("end_heading", alternative["target_heading"])
            point = alternative["end_point"]
            lateral = [-heading[1], heading[0]]
            end_edge = [[point[0]-lateral[0]*end_width/2, point[1]-lateral[1]*end_width/2],
                        [point[0]+lateral[0]*end_width/2, point[1]+lateral[1]*end_width/2]]
            for dimensions, field_class in ((preferred, "preferred"), (minimum, "minimum")):
                width, depth = map(float, dimensions)
                for offset in (0.0, (width-end_width)/2, -(width-end_width)/2):
                    center = [point[0]+lateral[0]*offset, point[1]+lateral[1]*offset]
                    field = Polygon([
                        [center[0]-lateral[0]*width/2, center[1]-lateral[1]*width/2],
                        [center[0]+lateral[0]*width/2, center[1]+lateral[1]*width/2],
                        [center[0]+lateral[0]*width/2+heading[0]*depth, center[1]+lateral[1]*width/2+heading[1]*depth],
                        [center[0]-lateral[0]*width/2+heading[0]*depth, center[1]-lateral[1]*width/2+heading[1]*depth]])
                    interface = LineString(end_edge).intersection(field.boundary)
                    overlap = field.intersection(ramp).area
                    valid = (envelope.buffer(self.EPS).covers(field) and
                             interface.length >= end_width-self.EPS and overlap <= self.EPS)
                    trials.append({"field_class":field_class,"target_heading":heading,
                        "geometry_status":"resolved" if valid else "not_feasible",
                        "failure_reasons":[] if valid else self._failures(envelope, field, interface.length, end_width, overlap),
                        "alignment_centerline":alternative.get("centerline", []),
                        "alignment_clearance_corridor":alternative.get("clearance_corridor", []),
                        "final_end_point":point,"final_end_heading":heading,"final_end_edge":end_edge,
                        "maneuvering_polygon":RampCenterlineTopologyV2._poly(field),
                        "maneuvering_dimensions":[width,depth],"maneuvering_orientation":"site_local_axes",
                        "end_interface":self._coords(interface),"end_interface_width":interface.length,
                        "floor_elevation":-2.4})
        resolved = [trial for trial in trials if trial["geometry_status"] == "resolved"]
        selected = min(resolved, key=lambda item:(item["field_class"] != "preferred", item["target_heading"])) if resolved else None
        return {"contract":"TerminalVehicleAlignmentV2",
            "terminal_alignment_status":"hard_valid" if selected else "alignment_path_pending",
            "site_local_axes":{"longitudinal":[0,1],"transverse":[1,0]},
            "selected":selected,"trials":trials,
            "failure_reasons":[] if selected else sorted({reason for trial in trials for reason in trial["failure_reasons"]})}

    @staticmethod
    def _failures(envelope, field, interface_width, required_width, overlap):
        failures=[]
        if not envelope.buffer(1e-7).covers(field): failures.append("aligned_maneuvering_field_outside_clear_envelope")
        if interface_width < required_width-1e-7: failures.append("aligned_end_interface_width_insufficient")
        if overlap > 1e-7: failures.append("aligned_maneuvering_field_overlaps_ramp")
        return failures

    @staticmethod
    def _coords(geometry):
        if geometry.is_empty:return []
        if geometry.geom_type == "LineString":return [[float(x),float(y)] for x,y in geometry.coords]
        return [[[float(x),float(y)] for x,y in part.coords] for part in geometry.geoms]
