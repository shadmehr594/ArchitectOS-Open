"""Evidence-driven architectural clearance and slab voids for resolved straight ramps."""

from __future__ import annotations

from math import hypot, isfinite


class ArchitecturalRampClearanceResolverV1:
    VERSION = "1.0"
    EPS = 1e-8

    def resolve(self, ramp, slabs, requirement):
        base = {
            "ramp_id": ramp.get("ramp_id") or ramp.get("access_id"),
            "access_id": ramp.get("access_id"),
            "ramp_surface": ramp.get("polygon"),
            "centerline_3d": ramp.get("centerline_3d"),
            "start_z": ramp.get("start_z"), "end_z": ramp.get("end_z"),
            "slope": ramp.get("slope"), "required_headroom": None,
            "clearance_envelope": None, "clearance_start": None,
            "clearance_end": None, "open_to_sky_zone": None,
            "slab_opening_polygon": None, "affected_slab": None,
            "affected_floor": None, "protected_zone": None,
            "geometry_status": "pending", "unresolved_evidence": [],
            "source": "architectural_ramp_clearance_resolver_v1",
        }
        if not isinstance(requirement, dict) or requirement.get("evidence_status") not in ("authoritative", "resolved"):
            base["unresolved_evidence"].append("authoritative_vehicle_ramp_requirement")
            return base
        headroom = requirement.get("required_headroom")
        if not self._positive(headroom):
            base["unresolved_evidence"].append("required_headroom")
            return base
        centerline = ramp.get("centerline_3d")
        width = ramp.get("width")
        if not (isinstance(centerline, list) and len(centerline) >= 2
                and self._point3(centerline[0]) and self._point3(centerline[-1])
                and self._positive(width)):
            base["unresolved_evidence"].append("resolved_ramp_surface_and_centerline_3d")
            return base
        p, q = [float(v) for v in centerline[0][:3]], [float(v) for v in centerline[-1][:3]]
        base["required_headroom"] = float(headroom)
        base["clearance_start"] = [p[0], p[1], p[2], p[2] + float(headroom)]
        base["clearance_end"] = [q[0], q[1], q[2], q[2] + float(headroom)]
        base["clearance_envelope"] = {
            "surface_polygon": ramp.get("polygon"), "bottom_centerline": centerline,
            "top_centerline": [[float(x), float(y), float(z) + float(headroom)] for x, y, z in centerline],
            "width": float(width), "side_clearance": requirement.get("side_clearance"),
        }

        candidates = []
        for index, slab in enumerate(slabs if isinstance(slabs, list) else []):
            if not isinstance(slab, dict):
                continue
            slab_z = slab.get("elevation", slab.get("bottom"))
            points = self._points((slab.get("footprint") or {}).get("points")
                                  if isinstance(slab.get("footprint"), dict) else slab.get("footprint"))
            if not self._number(slab_z) or len(points) < 3:
                continue
            bbox = self._bbox(points)
            inside = self._segment_bbox_interval(p, q, bbox)
            clearance = self._clearance_interval(p[2], q[2], float(slab_z), float(headroom))
            if inside is None or clearance is None:
                continue
            lo, hi = max(inside[0], clearance[0]), min(inside[1], clearance[1])
            if hi - lo > self.EPS:
                candidates.append((index, slab, lo, hi))
        if len(candidates) != 1:
            base["unresolved_evidence"].append(
                "unique_affected_slab" if candidates else "ramp_does_not_require_resolved_slab_void"
            )
            return base
        index, slab, lo, hi = candidates[0]
        a = self._lerp3(p, q, lo)
        b = self._lerp3(p, q, hi)
        polygon = self._corridor(a[:2], b[:2], float(width))
        if not polygon:
            base["unresolved_evidence"].append("slab_opening_polygon")
            return base
        opening = {
            "opening_id": f"{base['access_id']}_ramp_clearance_void",
            "type": "vehicle_ramp_clearance_slab_opening",
            "host_level": slab.get("floor"), "z": slab.get("elevation", slab.get("bottom")),
            "polygon": polygon, "geometry_status": "resolved",
            "source_evidence": "resolved_ramp_clearance_envelope",
        }
        base.update({
            "slab_opening_polygon": polygon,
            "affected_slab": slab.get("slab_id") or slab.get("id") or index,
            "affected_floor": slab.get("floor"),
            "protected_zone": {"type": "vehicle_vertical_clearance", "polygon": polygon,
                               "bottom_centerline": [a, b], "required_headroom": float(headroom),
                               "structural_exclusion_contract": True},
            "slab_opening": opening, "geometry_status": "resolved",
        })
        if lo > self.EPS:
            base["open_to_sky_zone"] = self._corridor(p[:2], self._lerp3(p, q, lo)[:2], float(width))
        else:
            base["open_to_sky_zone"] = []
        return base

    def _clearance_interval(self, z0, z1, slab_z, headroom):
        dz = z1 - z0
        if abs(dz) <= self.EPS:
            return (0.0, 1.0) if z0 < slab_z < z0 + headroom else None
        values = sorted(((slab_z - z0) / dz, (slab_z - headroom - z0) / dz))
        lo, hi = max(0.0, values[0]), min(1.0, values[1])
        return (lo, hi) if hi - lo > self.EPS else None

    def _segment_bbox_interval(self, p, q, bbox):
        lo, hi = 0.0, 1.0
        dx, dy = q[0] - p[0], q[1] - p[1]
        for origin, delta, minimum, maximum in ((p[0], dx, bbox[0], bbox[2]), (p[1], dy, bbox[1], bbox[3])):
            if abs(delta) <= self.EPS:
                if origin < minimum or origin > maximum:
                    return None
                continue
            a, b = (minimum-origin)/delta, (maximum-origin)/delta
            if a > b: a, b = b, a
            lo, hi = max(lo, a), min(hi, b)
        return (lo, hi) if hi - lo > self.EPS else None

    def _corridor(self, a, b, width):
        length = hypot(b[0]-a[0], b[1]-a[1])
        if length <= self.EPS: return None
        nx, ny = -(b[1]-a[1])/length*width/2, (b[0]-a[0])/length*width/2
        return [[a[0]+nx,a[1]+ny],[b[0]+nx,b[1]+ny],[b[0]-nx,b[1]-ny],[a[0]-nx,a[1]-ny]]

    @staticmethod
    def _lerp3(a, b, t): return [a[i] + (b[i]-a[i])*t for i in range(3)]
    @staticmethod
    def _number(v): return isinstance(v, (int,float)) and isfinite(float(v))
    @classmethod
    def _positive(cls,v): return cls._number(v) and float(v)>0
    @classmethod
    def _point3(cls,v): return isinstance(v,(list,tuple)) and len(v)>=3 and all(cls._number(x) for x in v[:3])
    @staticmethod
    def _points(v): return [[float(p[0]),float(p[1])] for p in v or [] if isinstance(p,(list,tuple)) and len(p)>=2]
    @staticmethod
    def _bbox(points):
        return [min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
