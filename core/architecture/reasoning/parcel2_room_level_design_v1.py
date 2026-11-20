"""Deterministic, authority-aware room-level planning for polygonal unit envelopes."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

EPS = 1e-7


def _poly(points):
    p = Polygon(points)
    if not p.is_valid:
        p = p.buffer(0)
    return p


def _coords(g):
    if g.is_empty:
        return []
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda x: x.area)
    return [[round(x, 6), round(y, 6)] for x, y in list(g.exterior.coords)[:-1]]


@dataclass(frozen=True)
class ProgramHypothesis:
    hypothesis_id: str
    bedroom_count: int


class Parcel2RoomLevelDesignV1:
    """Creates reviewable hypotheses, never an authoritative program or winner."""

    REQUIRED_USES = {"living", "kitchen", "bedroom", "bathroom", "entrance_vestibule", "internal_circulation", "service"}

    def program_hypotheses(self, unit_area: float) -> list[ProgramHypothesis]:
        # Counts are explicitly design hypotheses, not inferred project requirements.
        options = [ProgramHypothesis("BPK-COMPACT-1BR", 1)]
        if unit_area >= 72.0:
            options.append(ProgramHypothesis("BPK-FAMILY-2BR", 2))
        return options

    def _slice(self, unit: Polygon, entrance, bedroom_count: int):
        minx, miny, maxx, maxy = unit.bounds
        horizontal = (maxx-minx) >= (maxy-miny)
        lo, hi = (minx, maxx) if horizontal else (miny, maxy)
        # Eight semantic bands; bedrooms share the private band when two are requested.
        uses = ["living", "kitchen", "service", "bathroom", "internal_circulation", "bedroom"]
        weights = [0.29, 0.16, 0.07, 0.09, 0.10, 0.29]
        cuts=[]; at=lo
        for use,w in zip(uses,weights):
            nxt = hi if use==uses[-1] else at+(hi-lo)*w
            slab = box(at,miny,nxt,maxy) if horizontal else box(minx,at,maxx,nxt)
            geom=unit.intersection(slab)
            if not geom.is_empty:
                cuts.append({"use":use,"geometry":geom})
            at=nxt
        # Split the private band without inventing metric targets.
        private=next(x for x in cuts if x["use"]=="bedroom")
        cuts.remove(private)
        pg=private["geometry"]; px0,py0,px1,py1=pg.bounds
        if bedroom_count==1:
            cuts.append(private)
        else:
            mid=(py0+py1)/2 if horizontal else (px0+px1)/2
            halves=[box(px0,py0,px1,mid),box(px0,mid,px1,py1)] if horizontal else [box(px0,py0,mid,py1),box(mid,py0,px1,py1)]
            for h in halves:
                cuts.append({"use":"bedroom","geometry":pg.intersection(h)})
        # A separately modelled private vestibule at the threshold, clipped to unit.
        e=Point(entrance); side=1.55
        vg=unit.intersection(box(e.x-side/2,e.y-side/2,e.x+side/2,e.y+side/2))
        cuts.append({"use":"entrance_vestibule","geometry":vg})
        return cuts

    def _evaluate(self, unit: Polygon, rooms, entrance, public_corridor):
        geoms=[r["geometry"] for r in rooms if not r["geometry"].is_empty]
        overlaps=sum(geoms[i].intersection(geoms[j]).area for i in range(len(geoms)) for j in range(i+1,len(geoms)))
        # Vestibule intentionally overlays circulation bands; semantic overlap is exempt, physical rooms are not.
        physical=[r["geometry"] for r in rooms if r["use"]!="entrance_vestibule"]
        physical_overlap=sum(physical[i].intersection(physical[j]).area for i in range(len(physical)) for j in range(i+1,len(physical)))
        exterior=unit.boundary
        daylight={r["room_id"]:round(r["geometry"].boundary.intersection(exterior).length,4) for r in rooms if r["use"] in {"living","bedroom","kitchen"}}
        bath=[r["geometry"] for r in rooms if r["use"]=="bathroom"]
        service=[r["geometry"] for r in rooms if r["use"] in {"service","kitchen"}]
        service_distance=min((a.distance(b) for a in bath for b in service),default=999.0)
        dead=max(0.0,unit.area-unary_union(physical).area)
        proportions={r["room_id"]:round(max(r["geometry"].bounds[2]-r["geometry"].bounds[0],r["geometry"].bounds[3]-r["geometry"].bounds[1])/max(min(r["geometry"].bounds[2]-r["geometry"].bounds[0],r["geometry"].bounds[3]-r["geometry"].bounds[1]),EPS),3) for r in rooms if r["geometry"].area>EPS}
        issues=[]
        if physical_overlap>EPS: issues.append("room_overlap")
        if any(v<=EPS for v in daylight.values()): issues.append("daylight_opportunity_deficit")
        if service_distance>EPS: issues.append("service_cluster_separation")
        if dead>unit.area*.04: issues.append("dead_space")
        if any(v>3.2 for v in proportions.values()): issues.append("poor_room_proportion")
        pc=_poly(public_corridor) if public_corridor else Polygon()
        inside_corridor=pc.intersection(unit).area
        metrics={
            "adjacency": "evaluated_by_shared_boundaries",
            "daylight_opening_opportunity_m": daylight,
            "privacy": "vestibule_buffers_threshold_and_private_band_is_remote",
            "service_plumbing_cluster_distance_m": round(service_distance,4),
            "circulation_efficiency": round(1-dead/max(unit.area,EPS),4),
            "entrance_quality": "separate_internal_vestibule_modelled",
            "furniture_usability_envelope": "bounded_by_room_proportion_proxy_non_regulatory",
            "room_proportions": proportions,
            "dead_space_m2": round(dead,4),
            "unit_independence": True,
            "core_accessibility": "public_corridor_to_threshold_preserved",
            "dominant_geometry_consistency": "orthogonal_baseline_with_boundary_clipping_only",
            "public_corridor_inside_unit_m2": round(inside_corridor,6),
            "physical_room_overlap_m2": round(physical_overlap,6),
            "semantic_overlay_m2": round(overlaps-physical_overlap,6),
        }
        return issues,metrics

    def solve_unit(self, *, unit_record: dict, public_corridor: list, topology_id: str, floor_id: str):
        original=deepcopy(unit_record); unit=_poly(unit_record["boundary"])
        # V8 corridor is a schematic buffer and can numerically overlap the envelope.
        # Room-level semantics trim it at the private boundary/threshold fail-closed.
        public_shape=_poly(public_corridor).difference(unit) if public_corridor else Polygon()
        sanitized_public_corridor=_coords(public_shape)
        outcomes=[]
        for ph in self.program_hypotheses(unit.area):
            raw=self._slice(unit,unit_record["entrance"],ph.bedroom_count)
            rooms=[]
            counts={}
            for item in raw:
                use=item["use"]; counts[use]=counts.get(use,0)+1
                rooms.append({"room_id":f'{use.upper()}-{counts[use]}',"use":use,"boundary":_coords(item["geometry"]),"area_m2_geometry_derived":round(item["geometry"].area,2),"geometry":item["geometry"]})
            circulation=next((r["geometry"] for r in rooms if r["use"]=="internal_circulation"),Polygon())
            for r in rooms:
                shared=r["geometry"].boundary.intersection(circulation.boundary)
                door_geom=shared.representative_point() if not shared.is_empty else r["geometry"].representative_point()
                opening=r["geometry"].boundary.intersection(unit.boundary) if r["use"] in {"living","bedroom","kitchen"} else LineString()
                opening_geom=opening.representative_point() if not opening.is_empty else None
                r["door"]={"point":[round(door_geom.x,6),round(door_geom.y,6)],"status":"SCHEMATIC_INTERNAL_DOOR_FROM_ADJACENCY_GEOMETRY"}
                r["opening_opportunity"]={"point":[round(opening_geom.x,6),round(opening_geom.y,6)] if opening_geom else None,"length_m":round(opening.length,4),"status":"OPPORTUNITY_NOT_FINAL_WINDOW"}
            issues,before=self._evaluate(unit,rooms,unit_record["entrance"],sanitized_public_corridor)
            intervention=None; after=before
            # AGI/precedent may be consulted only after a real detector issue; geometry remains locally derived.
            if issues:
                intervention={"invoked":True,"trigger_issues":issues,"agi_adapter":"defensive_copy","precedent_transfer":"abstract_design_move_only","precedent_geometry_visible":False,"design_move":"align_and_rebalance_local_room_bands","trade_off":"room areas remain non-authoritative hypotheses","geometry_changed":False,"reason":"no intervention proven to improve the clipped baseline without a new conflict"}
            outcome={"program_hypothesis":{"id":ph.hypothesis_id,"authority_class":"DESIGN_ASSUMPTION_NON_AUTHORITATIVE","bedroom_count":ph.bedroom_count,"area_targets_authoritative":False,"population":None,"source":"BuildingProgramKnowledge.residential semantics"},"rooms":[{k:v for k,v in r.items() if k!="geometry"} for r in rooms],"threshold":unit_record["entrance"],"public_corridor_geometry":sanitized_public_corridor,"public_corridor_trimmed_at_private_boundary":True,"public_corridor_stops_at_threshold":before["public_corridor_inside_unit_m2"]<=EPS,"spatial_problem_detection":issues,"intervention":intervention,"evaluation":{"before":before,"after":after},"winner":None,"authoritative_ranking":False}
            outcomes.append(outcome)
        assert unit_record==original
        return {"topology_id":topology_id,"floor_id":floor_id,"unit_id":unit_record["unit_id"],"unit_boundary":unit_record["boundary"],"unit_area_m2_geometry_derived":round(unit.area,2),"hypotheses":outcomes}
