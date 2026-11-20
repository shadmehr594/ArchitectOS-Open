"""General, geometry-derived architectural reasoning primitives.

No parcel identity or parcel-specific dimension is accepted by this module.
"""
from copy import deepcopy
from hashlib import sha256
import json
from math import hypot

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union


def _parts(g):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    return [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon" and p.area > 1e-8]


def _poly(g):
    return [[float(x), float(y)] for x, y in list(g.exterior.coords)[:-1]]


def _largest_rectangle(g, step=None):
    """Largest axis-aligned rectangle on a scale derived from the geometry."""
    x0, y0, x1, y1 = g.bounds
    span = max(x1 - x0, y1 - y0, 1e-6)
    # Quality inference is called for every coupled candidate.  A bounded,
    # geometry-relative grid preserves scale independence without an O(32^4)
    # search at each regeneration.
    step = step or span / 12.0
    best = Polygon()
    xs = [x0 + i * step for i in range(int((x1 - x0) / step) + 2)]
    ys = [y0 + i * step for i in range(int((y1 - y0) / step) + 2)]
    for i, xa in enumerate(xs[:-1]):
        for xb in xs[i + 1:]:
            if xb > x1 + 1e-8: break
            for j, ya in enumerate(ys[:-1]):
                for yb in ys[j + 1:]:
                    if yb > y1 + 1e-8: break
                    r = box(xa, ya, xb, yb)
                    if r.area > best.area and g.buffer(1e-8).covers(r): best = r
    return best


class ParkingFieldTopologyIntelligence:
    """Infer the full access/turning field from a stall array."""
    def derive(self, stalls, access_direction, vehicle_dimensions, turning_requirements):
        shapes = [Polygon(s.get("polygon", s)) if isinstance(s, dict) else Polygon(s) for s in stalls]
        if not shapes: return {"contract": self.__class__.__name__, "circulation_field": [], "groups": []}
        clearance = float(turning_requirements.get("clearance", 0.0))
        turn_depth = float(turning_requirements.get("turning_depth", turning_requirements.get("aisle_depth", vehicle_dimensions[0])))
        horizontal = sum((p.bounds[2]-p.bounds[0]) >= (p.bounds[3]-p.bounds[1]) for p in shapes) >= len(shapes)/2
        axis = "y" if horizontal else "x"
        ordered = sorted(shapes, key=lambda p: p.centroid.y if axis == "y" else p.centroid.x)
        gaps = []
        for a, b in zip(ordered, ordered[1:]):
            gaps.append(max(0.0, (b.bounds[1]-a.bounds[3]) if axis == "y" else (b.bounds[0]-a.bounds[2])))
        typical = sorted([(p.bounds[3]-p.bounds[1]) if axis == "y" else (p.bounds[2]-p.bounds[0]) for p in shapes])[len(shapes)//2]
        groups=[]; current=[ordered[0]]
        for gap, nxt in zip(gaps, ordered[1:]):
            if gap <= max(clearance, typical * .25): current.append(nxt)
            else: groups.append(current); current=[nxt]
        groups.append(current)
        fields=[]
        dx,dy={"east":(1,0),"west":(-1,0),"north":(0,1),"south":(0,-1)}[access_direction.lower()]
        for group in groups:
            u=unary_union(group); x0,y0,x1,y1=u.bounds
            if dx>0: f=box(x1,y0,x1+turn_depth,y1)
            elif dx<0: f=box(x0-turn_depth,y0,x0,y1)
            elif dy>0: f=box(x0,y1,x1,y1+turn_depth)
            else: f=box(x0,y0-turn_depth,x1,y0)
            fields.append(f.buffer(clearance, join_style=2))
        field=unary_union(fields)
        return {"contract":self.__class__.__name__,"stall_count":len(shapes),"orientation":"long_axis_east_west" if horizontal else "long_axis_north_south","access_direction":access_direction,"circulation_field":_poly(field.convex_hull),"circulation_area":field.area,"groups":[{"stall_count":len(g),"field":_poly(f)} for g,f in zip(groups,fields)],"dimension_source":"stall_array_plus_vehicle_turning_requirements"}


class CommercialViabilityIntelligence:
    def evaluate(self, polygons, frontage_edge, access_points=(), conflicts=()):
        frontage=LineString(frontage_edge); conflict=unary_union([Polygon(x) for x in conflicts]) if conflicts else Polygon()
        results=[]
        for raw in polygons:
            p=Polygon(raw) if not hasattr(raw,"area") else raw
            rect=_largest_rectangle(p); front=p.boundary.intersection(frontage.buffer(1e-7)).length
            accessible=front>1e-7 or any(p.buffer(1e-7).covers(Point(a)) for a in access_points)
            compact=p.area/p.convex_hull.area if p.area else 0
            usable=rect.area/p.area if p.area else 0
            conflict_ratio=p.intersection(conflict).area/p.area if p.area else 1
            min_dim=min(rect.bounds[2]-rect.bounds[0],rect.bounds[3]-rect.bounds[1]) if not rect.is_empty else 0
            viable=accessible and front>0 and usable>=.35 and compact>=.55 and conflict_ratio<.01 and min_dim>0
            reasons=[]
            if front<=1e-7: reasons.append("no_frontage")
            if not accessible: reasons.append("no_credible_access")
            if usable<.35: reasons.append("insufficient_usable_rectangle")
            if compact<.55: reasons.append("fragmented_or_articulated_shape")
            if conflict_ratio>=.01: reasons.append("functional_conflict")
            results.append({"polygon":_poly(p),"viable":viable,"classification":"commercial_viable" if viable else "commercially_nonviable_residual","frontage":front,"effective_depth":p.area/front if front else None,"usable_rectangle":_poly(rect) if not rect.is_empty else [],"usable_rectangle_ratio":usable,"compactness":compact,"conflict_ratio":conflict_ratio,"reasons":reasons})
        return {"contract":self.__class__.__name__,"components":results,"viable_polygons":[r["polygon"] for r in results if r["viable"]],"nonviable_polygons":[r["polygon"] for r in results if not r["viable"]]}


class EntranceImpactEvaluation:
    """Geometry-only audit of the damage caused by a pedestrian option."""
    WEIGHTS={"commercial_usable_area_loss":.30,"frontage_loss":.24,
             "largest_usable_rectangle_loss":.18,"coherence_fragmentation_penalty":.12,
             "core_service_conflict":.05,"vehicle_swept_conflict":.20,
             "path_length_turn_complexity":.07,"accessibility_penalty":.10}

    def evaluate(self, before, after, entrance=None, path=None, corridor=None,
                 core=None, service=(), vehicle=(), accessible=True):
        before_shape=unary_union([p if hasattr(p,"area") else Polygon(p) for p in before]) if before else Polygon()
        after_shape=unary_union([p if hasattr(p,"area") else Polygon(p) for p in after]) if after else Polygon()
        front=LineString(entrance["frontage_edge"]) if isinstance(entrance,dict) and entrance.get("frontage_edge") else LineString()
        before_front=before_shape.boundary.intersection(front.buffer(1e-7)).length if not front.is_empty else 0
        after_front=after_shape.boundary.intersection(front.buffer(1e-7)).length if not front.is_empty else 0
        before_rect=_largest_rectangle(before_shape) if not before_shape.is_empty else Polygon()
        after_rect=_largest_rectangle(after_shape) if not after_shape.is_empty else Polygon()
        before_coherence=before_shape.area/before_shape.convex_hull.area if before_shape.area and before_shape.convex_hull.area else 0
        after_coherence=after_shape.area/after_shape.convex_hull.area if after_shape.area and after_shape.convex_hull.area else 0
        before_count=len(_parts(before_shape));after_count=len(_parts(after_shape))
        route=LineString(path) if path and len(path)>=2 else LineString();corridor_shape=corridor if hasattr(corridor,"area") else Polygon(corridor or [])
        core_shape=core if hasattr(core,"area") else Polygon(core or [])
        service_shape=unary_union([p if hasattr(p,"area") else Polygon(p) for p in service]) if service else Polygon()
        vehicle_shape=unary_union([p if hasattr(p,"area") else Polygon(p) for p in vehicle]) if vehicle else Polygon()
        turns=0
        if path and len(path)>2:
            for a,b,c in zip(path,path[1:],path[2:]):
                v1=(b[0]-a[0],b[1]-a[1]);v2=(c[0]-b[0],c[1]-b[1])
                if abs(v1[0]*v2[1]-v1[1]*v2[0])>1e-7:turns+=1
        raw={"commercial_usable_area_loss":max(0,before_shape.area-after_shape.area),
             "frontage_loss":max(0,before_front-after_front),
             "largest_usable_rectangle_loss":max(0,before_rect.area-after_rect.area),
             "coherence_fragmentation_penalty":max(0,before_coherence-after_coherence)+max(0,after_count-before_count),
             "core_service_conflict":corridor_shape.intersection(unary_union([core_shape,service_shape])).area,
             "vehicle_swept_conflict":corridor_shape.intersection(vehicle_shape).area,
             "path_length_turn_complexity":route.length+turns,
             "accessibility_penalty":0 if accessible else 1}
        scale=max(before_shape.area,1e-7);front_scale=max(before_front,1e-7);rect_scale=max(before_rect.area,1e-7)
        normalized={**raw,"commercial_usable_area_loss":raw["commercial_usable_area_loss"]/scale,
                    "frontage_loss":raw["frontage_loss"]/front_scale,
                    "largest_usable_rectangle_loss":raw["largest_usable_rectangle_loss"]/rect_scale,
                    "core_service_conflict":raw["core_service_conflict"]/scale,
                    "vehicle_swept_conflict":raw["vehicle_swept_conflict"]/scale,
                    "path_length_turn_complexity":raw["path_length_turn_complexity"]/max(scale**.5,1e-7)}
        score=sum(self.WEIGHTS[k]*normalized[k] for k in self.WEIGHTS)
        return {"contract":self.__class__.__name__,"before":{"commercial_area":before_shape.area,"frontage":before_front,"largest_usable_rectangle_area":before_rect.area,"coherence":before_coherence,"fragment_count":before_count},
                "after":{"commercial_area":after_shape.area,"frontage":after_front,"largest_usable_rectangle_area":after_rect.area,"coherence":after_coherence,"fragment_count":after_count},
                "metrics":raw,"normalized_metrics":normalized,"weights":dict(self.WEIGHTS),"impact_score":score,
                "hard_reject":raw["vehicle_swept_conflict"]>1e-7 or not accessible}

    def rank_design_space(self, no_dedicated, dedicated, mandatory=False):
        """Rank both families without assuming a parcel side or entrance location."""
        options=[]
        if no_dedicated is not None:
            item=deepcopy(no_dedicated);item["pedestrian_mode"]="NO_DEDICATED_PEDESTRIAN_ENTRANCE"
            item["hard_reject"]=bool(mandatory);item["hard_rejection_reason"]="dedicated_pedestrian_entrance_mandatory" if mandatory else None
            options.append(item)
        for source in dedicated:
            item=deepcopy(source);item["pedestrian_mode"]="DEDICATED_PEDESTRIAN_ENTRANCE";options.append(item)
        return sorted(options,key=lambda x:(bool(x.get("hard_reject")),float(x.get("impact_score",0))))


class ArchitecturalSpaceRoleInference:
    def infer(self, leftovers, parking_field, core, frontage_edge, access_points=()):
        vehicle=parking_field if hasattr(parking_field,"area") else Polygon(parking_field); core_shape=Polygon(core); frontage=LineString(frontage_edge)
        out=[]
        for raw in leftovers:
            p=Polygon(raw) if not hasattr(raw,"area") else raw
            if p.intersection(vehicle).area>1e-7: role="vehicle_circulation"
            elif p.distance(core_shape)<1e-7 and p.boundary.intersection(frontage.buffer(1e-7)).length<=1e-7: role="common_service"
            else:
                v=CommercialViabilityIntelligence().evaluate([p],list(frontage.coords),access_points,[vehicle,core_shape])["components"][0]
                role="commercial_viable" if v["viable"] else "commercially_nonviable_residual"
            out.append({"polygon":_poly(p),"role":role,"area":p.area,"reasoning_source":"spatial_relationships"})
        return {"contract":self.__class__.__name__,"spaces":out}


class ResidentialEnvelopeQualityIntelligence:
    def evaluate(self, envelope, daylight_edges=(), court=None, access_path=None):
        p=Polygon(envelope); rect=_largest_rectangle(p); x0,y0,x1,y1=p.bounds
        short=max(min(x1-x0,y1-y0),1e-8); aspect=max(x1-x0,y1-y0)/short
        usable=rect.area/p.area if p.area else 0; compact=p.area/p.convex_hull.area if p.area else 0
        edges=[LineString(e) for e in daylight_edges]; reach=max((p.intersection(e.buffer(short)).area/p.area for e in edges),default=0)
        court_shape=Polygon(court) if court else Polygon(); court_touch=p.boundary.intersection(court_shape.boundary).length if court else 0
        bends=0
        if access_path and len(access_path)>2:
            pts=[Point(x) for x in access_path]
            for a,b,c in zip(pts,pts[1:],pts[2:]):
                v1=(b.x-a.x,b.y-a.y);v2=(c.x-b.x,c.y-b.y)
                cross=abs(v1[0]*v2[1]-v1[1]*v2[0]); dot=v1[0]*v2[0]+v1[1]*v2[1]
                if cross>1e-7 and dot>0: bends+=1
        penalties=[]
        if aspect>3: penalties.append("poor_aspect_ratio")
        if usable<.6: penalties.append("low_largest_usable_rectangle_ratio")
        if compact<.75: penalties.append("articulation_or_sliver_penalty")
        if court and court_touch<=1e-7: penalties.append("court_not_directly_accessible")
        if bends: penalties.append("artificial_angled_court_access")
        score=max(0,1-.14*len(penalties))*(.35*min(1,usable/.8)+.25*compact+.2*min(1,reach/.5)+.2/(1+max(0,aspect-1)))
        return {"contract":self.__class__.__name__,"quality_score":score,"aspect_ratio":aspect,"effective_depth":p.area/max(sum(e.intersection(p.boundary).length for e in edges),1e-8) if edges else short,"largest_usable_rectangle":_poly(rect) if not rect.is_empty else [],"usable_rectangle_ratio":usable,"compactness":compact,"daylight_edge_reach":reach,"court_direct_contact":court_touch,"access_bend_count":bends,"quality_penalties":penalties,"quality_status":"quality_pass" if not penalties else "quality_failure"}


class CorePlacementReasoning:
    def generate(self, envelope, reference_core, ground_forbidden, residential_forbidden=(), valued_frontage=(), step=None):
        parcel=Polygon(envelope); components={k:Polygon(reference_core[k]) for k in ("stair","elevator","lobby")}; core=unary_union(list(components.values())).convex_hull
        forbidden=unary_union([Polygon(x) for x in list(ground_forbidden)+list(residential_forbidden)])
        available=parcel.difference(forbidden); step=step or min(parcel.bounds[2]-parcel.bounds[0],parcel.bounds[3]-parcel.bounds[1])/12
        candidates=[]
        for angle in (0,90):
            from shapely.affinity import rotate, translate
            rotated={k:rotate(v,angle,origin=core.centroid) for k,v in components.items()}; footprint=unary_union(list(rotated.values())).convex_hull
            x0,y0,x1,y1=parcel.bounds; fw=footprint.bounds[2]-footprint.bounds[0];fh=footprint.bounds[3]-footprint.bounds[1]
            x=x0
            while x+fw<=x1+1e-8:
                y=y0
                while y+fh<=y1+1e-8:
                    dx=x-footprint.bounds[0];dy=y-footprint.bounds[1]; placed={k:translate(v,dx,dy) for k,v in rotated.items()}; shape=unary_union(list(placed.values())).convex_hull
                    if available.buffer(1e-8).covers(shape):
                        frontage_loss=sum(shape.boundary.intersection(LineString(e).buffer(1e-7)).length for e in valued_frontage)
                        daylight_clear=shape.distance(forbidden); score=1/(1+shape.centroid.distance(parcel.centroid))+daylight_clear/(1+daylight_clear)-frontage_loss
                        candidates.append({"rotation_degrees":angle,"translation_vector":[dx,dy],"core":{**reference_core,**{k:_poly(v) for k,v in placed.items()},"polygon":_poly(shape)},"score":score,"reasoning":"shared_ground_residential_feasible_region"})
                    y+=step
                x+=step
        return {"contract":self.__class__.__name__,"placement_region":[_poly(p) for p in _parts(available)],"candidates":sorted(candidates,key=lambda c:c["score"],reverse=True)}


class ArchitecturalConstraintPropagationGraph:
    DEPENDENCIES={
        "site_resource_region_derivation":(), "site_resource_map":("site_resource_region_derivation",), "program_demand_profile":(),
        "pre_realization_daylight_deficit":("site_resource_map","program_demand_profile"),
        "scarcity_model":("site_resource_map","program_demand_profile"),
        "allocation_plan":("scarcity_model","program_demand_profile"),
        "opportunity_cost":("allocation_plan",),
        "operational_relationship_requirements":("program_demand_profile","allocation_plan","pre_realization_daylight_deficit"),
        "geometry_realization":("allocation_plan","opportunity_cost","pre_realization_daylight_deficit","operational_relationship_requirements"),
        "ownership_gate":("geometry_realization",),
        "contextual_quality":("operational_feasibility",), "architectural_critic":("contextual_quality",),
        "decision_support_shortlist":("architectural_critic",),
        "parking_field":("geometry_realization",), "vehicle_movement_swept_path":("parking_field",),
        "core":("allocation_plan","vehicle_movement_swept_path"), "pedestrian_access":("core",),
        "functional_subtraction":("core","pedestrian_access"), "space_roles":("functional_subtraction",),
        "commercial_viability":("space_roles",), "residential_envelopes":("space_roles",),
        "daylight_court":("allocation_plan","residential_envelopes"),
        "operational_feasibility":("ownership_gate","vehicle_movement_swept_path","core","pedestrian_access",
            "commercial_viability","residential_envelopes","daylight_court"),
        "quality_metrics":("commercial_viability","daylight_court","contextual_quality")}
    @classmethod
    def dependency_order(cls):
        pending={k:set(v) for k,v in cls.DEPENDENCIES.items()}; result=[]
        while pending:
            ready=sorted(k for k,v in pending.items() if v.issubset(result))
            if not ready: raise ValueError("cyclic architectural propagation dependencies")
            for node in ready: result.append(node); pending.pop(node)
        return tuple(result)
    ORDER=()
    def regenerate(self, inputs, callbacks):
        state=dict(inputs); revisions={}; executions={}
        for node in self.ORDER:
            if node not in callbacks or not callable(callbacks[node]):
                raise ValueError("missing executable propagation callback: %s" % node)
            before=sha256(json.dumps(state,sort_keys=True,default=str).encode()).hexdigest()
            state[node]=callbacks[node](deepcopy(state))
            payload=json.dumps(state[node],sort_keys=True,default=str)
            revisions[node]=sha256(payload.encode()).hexdigest()
            executions[node]={"executed":True,"input_fingerprint":before,"output_fingerprint":revisions[node]}
        return {"contract":self.__class__.__name__,"order":list(self.ORDER),"revisions":revisions,
                "executions":executions,"all_dependencies_regenerated":all(n in revisions for n in self.ORDER),
                 "candidate_state_reuse":False,"state":state}


ArchitecturalConstraintPropagationGraph.ORDER=ArchitecturalConstraintPropagationGraph.dependency_order()
