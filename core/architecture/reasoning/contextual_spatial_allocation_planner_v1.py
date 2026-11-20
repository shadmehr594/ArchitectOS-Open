"""Multi-hypothesis allocation planning before any geometry realization."""
from copy import deepcopy
from itertools import product
import json

from shapely.geometry import shape

DMAP={"frontage_value":"frontage_need","public_access_value":"public_access_need","daylight_value":"daylight_need","visibility_value":"visibility_need","privacy_value":"privacy_need","quietness_value":"quietness_need","terrace_value":"terrace_relation_need"}

SPATIAL_REQUIREMENTS={
    "commercial":"AREA_OCCUPANCY","residential_unit":"AREA_OCCUPANCY","living":"AREA_OCCUPANCY",
    "bedroom":"AREA_OCCUPANCY","kitchen":"AREA_OCCUPANCY","terrace":"AREA_OCCUPANCY",
    "stair":"AREA_OCCUPANCY","elevator":"AREA_OCCUPANCY","lobby":"AREA_OCCUPANCY",
    "bathroom":"AREA_OCCUPANCY","wc":"AREA_OCCUPANCY","storage":"AREA_OCCUPANCY",
    "service":"AREA_OCCUPANCY","shaft":"AREA_OCCUPANCY","parking":"AREA_OCCUPANCY",
    "daylight_source":"AREA_OCCUPANCY","void":"AREA_OCCUPANCY",
    "vehicle_circulation":"LINEAR_ROUTE","pedestrian_access":"LINEAR_ROUTE",
    "corridor":"LINEAR_ROUTE","common":"LINEAR_ROUTE",
    "site_vehicle_entrance":"EDGE_ATTACHMENT","public_pedestrian_entrance":"EDGE_ATTACHMENT",
}

GEOMETRY_COMPATIBILITY={
    "AREA_OCCUPANCY":{"Polygon","MultiPolygon"},
    "LINEAR_ROUTE":{"LineString","MultiLineString","Polygon","MultiPolygon"},
    "EDGE_ATTACHMENT":{"Point","MultiPoint","LineString","MultiLineString"},
    "POINT_ACCESS":{"Point","MultiPoint"},
}


def _stable_unique_provenance(records):
    """Deduplicate complete JSON-like records while preserving first-seen order and structure."""
    unique=[]; seen=set()
    for record in records:
        key=json.dumps(record,sort_keys=True,separators=(",",":"),ensure_ascii=False)
        if key in seen: continue
        seen.add(key); unique.append(deepcopy(record))
    return unique


def _spatial_requirement(function):
    explicit=function.get("operational_requirements",{}).get("spatial_requirement")
    return explicit or SPATIAL_REQUIREMENTS.get(function.get("function"))


def _resource_utility(resource,function):
    utility=0.0; evidence=[]
    for channel,need_channel in DMAP.items():
        rv=resource["channels"][channel]; dv=function["demands"][need_channel]
        if rv["status"]!="unknown" and dv["status"]!="unknown":
            utility+=(rv["value"] or 0)*(dv["value"] or 0)
            evidence += rv["provenance"]+dv["provenance"]
    return utility,evidence


class ContextualSpatialAllocationPlannerV1:
    def plan(self, resource_map, demand_profile, scarcity, dependencies=None, max_hypotheses=6):
        resources=resource_map.get("resources",[]); functions=demand_profile.get("functions",[])
        unknown=[f["function_id"] for f in functions if f.get("status","").startswith("unknown")]
        prereq={f["function_id"]:set(f.get("prerequisites",[])) for f in functions}
        scarce={x["resource_channel"] for x in scarcity.get("resources",[]) if x["scarcity_class"]=="scarce"}
        def pressure(fn):
            area=fn.get("spatial_sizing",{}).get("resolved_spatial_area")
            if area is None and fn.get("required_capacity") is not None and fn.get("capacity_unit")=="m2":
                area=float(fn["required_capacity"])*float(fn.get("quantity",1))
            return 0 if area is None else sum((fn["demands"][need]["value"] or 0)*area for ch,need in DMAP.items() if ch in scarce)
        order=[]; pending={f["function_id"]:f for f in functions}
        while pending:
            ready=[f for fid,f in pending.items() if prereq[fid].issubset({x["function_id"] for x in order})]
            if not ready: break
            ready.sort(key=lambda f:(-pressure(f),f["function_id"])); order.extend(ready)
            for f in ready: pending.pop(f["function_id"])
        choices=[]
        for fn in order:
            requirement=_spatial_requirement(fn); compatible_types=GEOMETRY_COMPATIBILITY.get(requirement,set())
            options=[]
            for r in resources:
                if fn.get("floor_scope") and not set(fn["floor_scope"]).intersection(r.get("floor_scope",[])): continue
                if r.get("usable_capacity") is None: continue
                if r.get("geometry_type") not in compatible_types: continue
                utility,evidence=_resource_utility(r,fn); host_geometry=shape(r["geometry"]); attachments=[]
                for benefit in resources:
                    if benefit["resource_id"]==r["resource_id"]: continue
                    if fn.get("floor_scope") and not set(fn["floor_scope"]).intersection(benefit.get("floor_scope",[])): continue
                    benefit_geometry=shape(benefit["geometry"])
                    if benefit_geometry.geom_type in compatible_types or not host_geometry.intersects(benefit_geometry): continue
                    value,benefit_evidence=_resource_utility(benefit,fn)
                    if value or benefit_evidence:
                        utility+=value; evidence+=benefit_evidence
                        attachments.append({"resource_id":benefit["resource_id"],"geometry_type":benefit_geometry.geom_type,
                            "role":"resource_benefit","utility":value})
                options.append((r["resource_id"],utility,_stable_unique_provenance(evidence),attachments,requirement))
            choices.append(options+[None])
        alternatives=[]
        for combination in product(*choices):
            consumed={r["resource_id"]:0.0 for r in resources}; consumed_by_floor={}; assignments=[]; unresolved=[]; feasible=True
            for fn,choice in zip(order,combination):
                sizing=fn.get("spatial_sizing",{}); need=sizing.get("allocated_area_m2",sizing.get("resolved_spatial_area"))
                requirement=_spatial_requirement(fn)
                expected_unit="m2" if requirement=="AREA_OCCUPANCY" else "m" if requirement=="LINEAR_ROUTE" else "count"
                unit=sizing.get("area_unit") if need is not None else fn.get("capacity_unit")
                if need is None and fn.get("required_capacity") is not None and unit==expected_unit:
                    need=float(fn["required_capacity"])*float(fn.get("quantity",1))
                if need is None or unit!=expected_unit:
                    unresolved.append({"function_id":fn["function_id"],"reason":"resolved_spatial_area_required"}); continue
                if choice is None: unresolved.append({"function_id":fn["function_id"],"reason":"no_selected_known_capacity"}); continue
                rid,utility,evidence,attachments,requirement=choice
                resource=next(r for r in resources if r["resource_id"]==rid)
                capacity=resource["usable_capacity"]
                consumption_floors=sorted(set(fn.get("floor_scope",[])).intersection(resource.get("floor_scope",[]))) or [None]
                for floor in consumption_floors:
                    key=(rid,floor); consumed_by_floor[key]=consumed_by_floor.get(key,0.0)+need
                    if consumed_by_floor[key]>capacity: feasible=False; break
                if not feasible: break
                consumed[rid]+=need*len(consumption_floors)
                assignments.append({"function_id":fn["function_id"],"resource_id":rid,"host_resource_id":rid,
                    "spatial_requirement":requirement,"resource_attachments":attachments,
                    "floor_scope":consumption_floors,
                    "consumed_capacity":need,"consumed_area":need if expected_unit=="m2" else None,"capacity_unit":expected_unit,
                    "sizing_mode":sizing.get("sizing_mode"),"utility":utility,"evidence":evidence+sizing.get("provenance",[])})
            if feasible: alternatives.append((len(unresolved),-sum(a["utility"] for a in assignments),assignments,unresolved,consumed,consumed_by_floor))
        alternatives.sort(key=lambda x:(x[0],x[1],tuple((a["function_id"],a["resource_id"]) for a in x[2])))
        hypotheses=[]
        for _,_,assignments,unresolved,consumed,consumed_by_floor in alternatives[:max_hypotheses]:
            hypotheses.append({"hypothesis_id":"allocation-%d"%(len(hypotheses)+1),"allocation_order":[x["function_id"] for x in order],"assignments":assignments,
                               "resource_consumption":consumed,
                               "resource_consumption_by_floor":[{"resource_id":rid,"floor_id":floor,"consumed_capacity":value}
                                   for (rid,floor),value in sorted(consumed_by_floor.items(),key=lambda item:(item[0][0],str(item[0][1])))],
                               "unresolved_demands":unresolved+[{'function_id':x,'reason':'unknown_function'} for x in unknown],
                               "prerequisites":{k:sorted(v) for k,v in prereq.items()},"feasibility_preconditions":["ownership_hard_valid","known_usable_capacity"],
                               "rationale":{"derived_from":["prerequisites","resource_contention","scarcity","joint_assignment_enumeration"],"geometry_realized":False}})
        return {"contract":"ContextualSpatialAllocationPlannerV1","hypotheses":hypotheses,"multiple_hypotheses":len(hypotheses)>1,
                "geometry_realized":False,"complete":bool(hypotheses)}
