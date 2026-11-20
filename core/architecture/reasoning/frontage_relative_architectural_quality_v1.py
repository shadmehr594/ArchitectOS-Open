"""Frontage-relative human architectural quality review; never selects a winner."""
from __future__ import annotations

from copy import deepcopy
from math import hypot

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import transform, unary_union


class FrontageRelativeArchitecturalQualityV1:
    EPS = 1e-7

    def evaluate(self, domain_evidence, frontage_evidence, candidates):
        frozen = deepcopy((domain_evidence, frontage_evidence, candidates))
        domain = Polygon(domain_evidence["polygon"])
        frontage = LineString(frontage_evidence["segment"])
        origin = Point(frontage.coords[0])
        dx, dy = frontage.coords[-1][0]-origin.x, frontage.coords[-1][1]-origin.y
        length = hypot(dx, dy); tx, ty = dx/length, dy/length
        normals = [(-ty, tx), (ty, -tx)]
        midpoint = frontage.interpolate(.5, normalized=True)
        nx, ny = max(normals, key=lambda n: domain.buffer(self.EPS).contains(Point(midpoint.x+n[0]*.1, midpoint.y+n[1]*.1)))
        local = lambda g: transform(lambda x,y,z=None: ((x-origin.x)*tx+(y-origin.y)*ty, (x-origin.x)*nx+(y-origin.y)*ny), g)
        local_domain = local(domain)
        min_depth, max_depth = local_domain.bounds[1], local_domain.bounds[3]
        parcel_depth = max_depth-min_depth
        reviewed = [self._candidate(domain, frontage, local, parcel_depth, item) for item in candidates]
        reviewed.sort(key=lambda c: (-c["architectural_quality"]["score"], -c["parking_count"], c["candidate_id"]))
        for rank, item in enumerate(reviewed, 1): item["bounded_review_rank"] = rank
        return {"contract":"FrontageRelativeArchitecturalQualityV1","authority_class":"PROJECT_HUMAN_DESIGN_CRITIQUE",
                "frontage_relative_frame":{"origin":list(frontage.coords[0]),"tangent":[tx,ty],"inward_normal":[nx,ny],"parcel_depth_m":round(parcel_depth,6)},
                "candidates":reviewed,"candidate_count":len(reviewed),"selected_candidate":None,"final_selection_performed":False,
                "input_mutated":frozen != (domain_evidence, frontage_evidence, candidates)}

    def _candidate(self, domain, frontage, local, depth, source):
        item = deepcopy(source); core=Polygon(item["temp_core"])
        stalls=[Polygon(s["polygon"]) for s in item["stalls"]]; aisle=Polygon(item["aisle_manoeuvre"])
        ped=Polygon(item["public_pedestrian_path"]); shared_raw=item.get("pedestrian_shared_with_manoeuvre_region",[])
        shared=Polygon(shared_raw) if shared_raw and isinstance(shared_raw[0][0],(int,float)) else Polygon()
        ped_exclusive=ped.difference(shared)
        residual=domain.difference(unary_union(stalls+[aisle,core,ped_exclusive]))
        parts=[residual] if residual.geom_type=="Polygon" else [g for g in getattr(residual,"geoms",[]) if g.geom_type=="Polygon"]
        touching=[p for p in parts if p.buffer(self.EPS).intersection(frontage).length>self.EPS]
        commercial=max(touching,key=lambda p:(p.intersection(frontage).length,p.area)) if touching else Polygon()
        lc, lcore = local(commercial), local(core)
        front_contact=commercial.buffer(self.EPS).intersection(frontage).length if not commercial.is_empty else 0
        front_parts=self._frontage_intervals(commercial,frontage)
        continuity=1.0 if len(front_parts)==1 else (0.0 if not front_parts else 1.0/len(front_parts))
        core_centroid=max(0.0,lcore.centroid.y)/depth; core_front=max(0.0,lcore.bounds[1])/depth
        mean_depth=max(0.0,lc.centroid.y)/depth if not commercial.is_empty else 1.0
        near_band=local(domain).intersection(Polygon([(-1e6,-1e6),(1e6,-1e6),(1e6,.40*depth),(-1e6,.40*depth)]))
        near_area=lc.intersection(near_band).area if not commercial.is_empty else 0
        near_share=near_area/commercial.area if commercial.area>self.EPS else 0
        commercial_frontage_quality=min(1.0,front_contact/max(frontage.length*.35,self.EPS))*(.5+.5*near_share)
        core_intrusion=max(0.0,(.35-core_front)/.35)
        depth_penalty=max(0.0,(mean_depth-.45)/.55)
        vehicle=LineString(item["vehicle_entrance"]); public_contact=ped.buffer(self.EPS).intersection(frontage).length
        competition=min(1.0,(vehicle.length+public_contact+core.buffer(self.EPS).intersection(frontage).length)/frontage.length)
        reasons=[]
        if core_intrusion>0: reasons.append("FRONT_CORE_BLOCKS_COMMERCIAL_FRONTAGE")
        if near_share<.5 or mean_depth>.6: reasons.append("REAR_COMMERCIAL_LOW_VALUE")
        if front_contact<=self.EPS: reasons.append("NO_USABLE_COMMERCIAL_FRONTAGE")
        if continuity<1: reasons.append("COMMERCIAL_FRONTAGE_DISCONTINUOUS")
        rejected=front_contact<=self.EPS or (near_share<.25 and mean_depth>.65)
        disfavored=(not rejected) and bool(reasons)
        status="rejected" if rejected else ("architecturally_disfavored" if disfavored else "passing")
        score=max(0.0,min(1.0,.35*commercial_frontage_quality+.2*continuity+.2*(1-depth_penalty)+.15*(1-core_intrusion)+.1*(1-competition)))
        quality={"status":status,"score":round(score,6),"commercial_frontage_quality":round(commercial_frontage_quality,6),
                 "core_frontage_intrusion":round(core_intrusion,6),"commercial_depth_penalty":round(depth_penalty,6),
                 "frontage_continuity":round(continuity,6),"access_competition_at_frontage":round(competition,6),
                 "core_centroid_depth_m":round(lcore.centroid.y,6),"core_centroid_depth_ratio":round(core_centroid,6),
                 "core_front_edge_depth_m":round(lcore.bounds[1],6),"core_position":"rear_interior" if core_centroid>=.55 else "front_or_mid",
                 "commercial_frontage_length_m":round(front_contact,6),"commercial_area_m2":round(commercial.area,6),
                 "commercial_mean_depth_m":round(lc.centroid.y,6) if not commercial.is_empty else None,
                 "commercial_mean_depth_ratio":round(mean_depth,6),"commercial_near_frontage_area_share":round(near_share,6),
                 "reasons":reasons,"source":"PROJECT/HUMAN DESIGN CRITIQUE"}
        item["direct_commercial_street_frontage_region"]=self._coords(commercial) if not commercial.is_empty else []
        item["commercial_candidate_area_m2"]=quality["commercial_area_m2"]
        item["architectural_quality"]=quality; item["human_quality_status"]=status
        item["selection_status"]="not_selected"; return item

    def _frontage_intervals(self, poly, frontage):
        hit=poly.buffer(self.EPS).intersection(frontage)
        if hit.is_empty:return []
        if hit.geom_type=="LineString":return [hit]
        return [g for g in getattr(hit,"geoms",[]) if g.geom_type=="LineString" and g.length>self.EPS]

    @staticmethod
    def _coords(poly): return [[round(x,9),round(y,9)] for x,y in list(poly.exterior.coords)[:-1]]
