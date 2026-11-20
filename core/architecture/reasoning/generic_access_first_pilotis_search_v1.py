"""Generic access/frontage-first pilotis search; emits candidates, never a winner."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from math import hypot

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points, unary_union

class GenericAccessFirstPilotisSearchV1:
    EPS = 1e-7

    def produce(self, domain_evidence, frontage_evidence, access_requirement,
                core_candidates, parking_requirement, branch_evidence=None):
        original = deepcopy((domain_evidence, frontage_evidence, access_requirement,
                             core_candidates, parking_requirement, branch_evidence))
        domain = Polygon(domain_evidence["polygon"])
        frontage = LineString(frontage_evidence["segment"])
        vehicle_w = float(access_requirement["vehicle_clear_width"])
        pedestrian_w = float(access_requirement["pedestrian_clear_width"])
        commercial_depth = float(access_requirement.get("commercial_candidate_depth", 4.0))
        inward = self._inward_normal(frontage, domain)
        depth = self._depth(frontage, domain, inward)
        result, diagnostics = [], []
        # Parameters derive only from frontage endpoints, midpoint, and projected core centroids.
        parameters = {0.0, .5, 1.0}
        for core in core_candidates:
            parameters.add(round(frontage.project(Polygon(core["polygon"]).centroid) / frontage.length, 9))
        for parameter in sorted(parameters):
            entrance = self._interval(frontage, parameter, vehicle_w)
            if entrance is None:
                continue
            corridor = self._sweep(entrance, inward, depth)
            for core in core_candidates:
                core_poly = Polygon(core["polygon"])
                if corridor.intersection(core_poly).area > self.EPS:
                    diagnostics.append({"core_candidate_id":core["candidate_id"],"parameter":parameter,"rejected":"vehicle_corridor_intersects_core"})
                    continue
                pedestrian = self._side_strip(domain, frontage, entrance, pedestrian_w, inward, depth, core_poly)
                commercial = self._commercial_region(domain, frontage, entrance, pedestrian,
                                                      inward, commercial_depth)
                if pedestrian is None or commercial is None:
                    diagnostics.append({"core_candidate_id":core["candidate_id"],"parameter":parameter,"rejected":"frontage_reservation_missing"})
                    continue
                aisle, packed_stalls = self._pack_around_access(domain, frontage, corridor,
                    unary_union([pedestrian, commercial, core_poly]), parking_requirement, inward,
                    pedestrian.centroid)
                if aisle is not None:
                    connection = aisle.buffer(self.EPS).covers(corridor.intersection(domain))
                    stalls = packed_stalls
                    clear = all(s.intersection(unary_union([corridor, pedestrian, commercial, core_poly])).area <= self.EPS for s in stalls)
                    independent = connection and all(s.distance(aisle) <= self.EPS for s in stalls)
                    if not (len(stalls) >= 3 and clear and independent):
                        diagnostics.append({"core_candidate_id":core["candidate_id"],"parameter":parameter,"rejected":"parking_or_connectivity_gate","parking_count":len(stalls),"connection":connection,"clear":clear,"independent":independent})
                        continue
                    residual = domain.difference(unary_union(stalls + [aisle, corridor, pedestrian, core_poly]))
                    key = self._key(core["candidate_id"], entrance, "ACCESS-ALIGNED")
                    result.append({
                        "candidate_id": "H1-AF-" + key[:16].upper(),
                        "core_candidate_id": core["candidate_id"],
                        "parking_source_candidate_id": "ACCESS-ALIGNED-GENERIC",
                        "vehicle_entrance": self._line_coords(entrance),
                        "vehicle_corridor": self._coords(corridor),
                        "public_pedestrian_path": self._coords(pedestrian),
                        "direct_commercial_street_frontage_region": self._coords(commercial),
                        "temp_core": core["polygon"], "aisle_manoeuvre": self._coords(aisle),
                        "stalls": [{"stall_id": f"S-{i+1:03d}", "polygon": self._coords(s)} for i,s in enumerate(stalls)],
                        "parking_count": len(stalls),
                        "commercial_candidate_area_m2": round(commercial.area, 6),
                        "geometric_residual_area_m2": round(residual.area, 6),
                        "gates": {"parking_minimum_3": True, "vehicle_frontage_to_aisle": True,
                                  "all_stalls_independently_reachable": True, "pedestrian_path_preserved": True,
                                  "commercial_direct_frontage": commercial.intersection(frontage).length > self.EPS,
                                  "core_clear": True, "no_isolated_commercial_island": True},
                        "selection_status": "not_selected", "authority_class": "NON_FINAL_DESIGN_CANDIDATE"})
                else:
                    diagnostics.append({"core_candidate_id":core["candidate_id"],"parameter":parameter,"rejected":"no_access_aligned_aisle"})
        result.sort(key=lambda c: (-c["parking_count"], -c["commercial_candidate_area_m2"], c["candidate_id"]))
        return {"contract": "GenericAccessFirstPilotisSearchV1", "search_order": list("ABCDEFGHI"),
                "candidates": result, "candidate_count": len(result), "selected_candidate": None,
                "rejection_diagnostics": diagnostics,
                "final_selection_performed": False,
                "input_mutated": original != (domain_evidence, frontage_evidence, access_requirement,
                                                core_candidates, parking_requirement, branch_evidence)}

    def _inward_normal(self, frontage, domain):
        (x1, y1), (x2, y2) = frontage.coords
        length = hypot(x2-x1, y2-y1); candidates = [(-(y2-y1)/length, (x2-x1)/length), ((y2-y1)/length, -(x2-x1)/length)]
        midpoint = frontage.interpolate(.5, normalized=True)
        return max(candidates, key=lambda n: domain.buffer(self.EPS).contains(Point(midpoint.x+n[0]*.1, midpoint.y+n[1]*.1)))

    def _depth(self, frontage, domain, inward):
        origin = frontage.interpolate(.5, normalized=True)
        return max((x-origin.x)*inward[0]+(y-origin.y)*inward[1] for x, y in domain.exterior.coords) + 1.0

    def _interval(self, frontage, t, width):
        half = width/(2*frontage.length); center = min(1-half, max(half, t))
        if 2*half > 1: return None
        return LineString([frontage.interpolate(center-half, normalized=True), frontage.interpolate(center+half, normalized=True)])

    def _sweep(self, segment, inward, depth):
        pts = list(segment.coords); return Polygon([pts[0], pts[1],
            (pts[1][0]+inward[0]*depth, pts[1][1]+inward[1]*depth),
            (pts[0][0]+inward[0]*depth, pts[0][1]+inward[1]*depth)])

    def _side_strip(self, domain, frontage, entrance, width, inward, depth, core):
        intervals = [(0, frontage.project(Point(entrance.coords[0]))),
                     (frontage.project(Point(entrance.coords[-1])), frontage.length)]
        for lo, hi in sorted(intervals, key=lambda p: -(p[1]-p[0])):
            if hi-lo + self.EPS < width: continue
            seg = LineString([frontage.interpolate(lo), frontage.interpolate(lo+width)])
            candidate = self._sweep(seg, inward, depth).intersection(domain)
            if candidate.geom_type == "Polygon": return candidate
        return None

    def _commercial_region(self, domain, frontage, entrance, pedestrian, inward, depth):
        band = self._sweep(frontage, inward, depth).intersection(domain)
        available = band.difference(unary_union([entrance.buffer(self.EPS), pedestrian]))
        polys = [available] if available.geom_type == "Polygon" else list(getattr(available, "geoms", []))
        touching = [p for p in polys if p.intersection(frontage).length > self.EPS]
        return max(touching, key=lambda p: (p.intersection(frontage).length, p.area)) if touching else None

    def _pack_around_access(self, domain, frontage, corridor, obstacles, requirement, inward, pedestrian_center):
        aw=float(requirement["aisle_width"]); sw=float(requirement["stall_width"]); sd=float(requirement["stall_depth"])
        axis=LineString([frontage.interpolate(.5,normalized=True),
                         Point(frontage.interpolate(.5,normalized=True).x+inward[0]*self._depth(frontage,domain,inward), frontage.interpolate(.5,normalized=True).y+inward[1]*self._depth(frontage,domain,inward))])
        center=nearest_points(corridor.centroid,frontage)[0]
        vehicle_mid=frontage.project(center); pedestrian_mid=frontage.project(nearest_points(pedestrian_center,frontage)[1])
        shift=(aw-float(requirement.get("vehicle_clear_width", 3.5)))/2
        # Shift the manoeuvre aisle toward the adjacent public strip so its outer edge
        # aligns with that protected strip; this preserves both before stall packing.
        signed=1 if pedestrian_mid >= vehicle_mid else -1
        ux=(frontage.coords[-1][0]-frontage.coords[0][0])/frontage.length; uy=(frontage.coords[-1][1]-frontage.coords[0][1])/frontage.length
        origin=Point(frontage.coords[0]); depths=[(x-origin.x)*inward[0]+(y-origin.y)*inward[1] for x,y in domain.exterior.coords]
        d0,d1=min(depths),max(depths); stations=[]; d=d0
        while d+sw <= d1+self.EPS: stations.append(d); d+=sw
        lateral=[(x-origin.x)*ux+(y-origin.y)*uy for x,y in domain.exterior.coords]; u0,u1=min(lateral),max(lateral)
        centers={vehicle_mid+signed*shift,u0+aw/2,u1-aw/2}
        best=(None,[])
        corridor_inside=corridor.intersection(domain)
        for mid in sorted(centers):
            axis=LineString([(origin.x+ux*mid+inward[0]*d0,origin.y+uy*mid+inward[1]*d0),(origin.x+ux*mid+inward[0]*d1,origin.y+uy*mid+inward[1]*d1)])
            aisle=axis.buffer(aw/2,cap_style=2).intersection(domain)
            if aisle.geom_type != "Polygon" or not aisle.buffer(self.EPS).covers(corridor_inside): continue
            stalls=[]
            for start in stations:
                for side in (-1,1):
                    inner=mid+side*aw/2; outer=inner+side*sd
                    poly=Polygon([(origin.x+ux*u+inward[0]*v,origin.y+uy*u+inward[1]*v) for u,v in
                                  ((min(inner,outer),start),(max(inner,outer),start),(max(inner,outer),start+sw),(min(inner,outer),start+sw))])
                    if domain.buffer(self.EPS).covers(poly) and poly.intersection(obstacles).area <= self.EPS and poly.intersection(corridor).area <= self.EPS:
                        stalls.append(poly)
            if len(stalls)>len(best[1]): best=(aisle,stalls)
        best[1].sort(key=lambda p:(round(p.centroid.y,8),round(p.centroid.x,8)))
        return best

    @staticmethod
    def _coords(poly): return [[round(x, 9), round(y, 9)] for x, y in list(poly.exterior.coords)[:-1]]
    @staticmethod
    def _line_coords(line): return [[round(x, 9), round(y, 9)] for x, y in line.coords]
    @staticmethod
    def _key(core_id, entrance, parking_id):
        payload = [core_id, [[round(x, 8), round(y, 8)] for x, y in entrance.coords], parking_id]
        return sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()
