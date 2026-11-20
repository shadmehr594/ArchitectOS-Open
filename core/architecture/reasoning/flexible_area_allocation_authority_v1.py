"""Evidence-bearing, floor-aware allocation of unresolved flexible area demand."""
from copy import deepcopy
import json

from shapely.geometry import shape


def _weight(sizing):
    raw=sizing.get("flexible_weight")
    if not isinstance(raw,dict) or raw.get("value") is None:
        return None
    if raw.get("unit") not in ("ratio","dimensionless") or not raw.get("provenance"):
        return None
    value=float(raw["value"])
    return (value,deepcopy(raw["provenance"]),float(raw.get("confidence",0.0))) if value>0 else None


def _signature(function):
    sizing=function["spatial_sizing"]
    demands={key:{"value":value.get("value"),"status":value.get("status")}
             for key,value in sorted(function.get("demands",{}).items())}
    value={"function":function.get("function"),"count":sizing.get("count"),
           "count_unit":sizing.get("count_unit"),"minimum_area":sizing.get("minimum_area"),
           "maximum_area":sizing.get("maximum_area"),"target_area":sizing.get("target_area"),
           "demands":demands,"prerequisites":sorted(function.get("prerequisites",[]))}
    return json.dumps(value,sort_keys=True,separators=(",",":"))


class FlexibleAreaAllocationAuthorityV1:
    """Allocate only FLEXIBLE_AREA_DEMAND from authoritative per-floor residual supply."""

    @staticmethod
    def _domain(resource_map,floor):
        candidates=[]
        for resource in resource_map.get("resources",[]):
            if floor not in resource.get("floor_scope",[]) or resource.get("usable_capacity") is None:
                continue
            if resource.get("geometry_type") not in ("Polygon","MultiPolygon"):
                continue
            geometry=shape(resource["geometry"])
            if geometry.is_empty or not geometry.is_valid: continue
            candidates.append((resource,geometry))
        preferred=[x for x in candidates if x[0].get("capacity_role")=="floor_domain" or
                   x[0].get("evidence_kind")=="interior_spatial_domain"]
        pool=preferred or candidates
        if len(pool)>1:
            containing=[x for x in pool if all(x[1].covers(other[1]) for other in pool)]
            if len(containing)!=1:
                return None,"ambiguous_floor_supply_domain"
            pool=containing
        if len(pool)!=1:
            return None,"authoritative_floor_supply_required"
        resource,geometry=pool[0]
        capacity=float(resource["usable_capacity"])
        if capacity<=0 or capacity>geometry.area+1e-7:
            return None,"invalid_floor_supply_capacity"
        return {"resource_id":resource["resource_id"],"capacity_m2":capacity,
                "capacity_unit":resource.get("capacity_unit","m2"),
                "capacity_derivation":resource.get("capacity_derivation","explicit_usable_capacity"),
                "provenance":deepcopy(resource.get("capacity_provenance") or resource.get("source_evidence") or
                                      [{"resource_id":resource["resource_id"],"geometry_type":resource["geometry_type"]}]),
                "confidence":float(resource.get("capacity_confidence",0.0))},None

    @staticmethod
    def _bounds(function):
        sizing=function["spatial_sizing"]; count=float(sizing.get("count",1))
        minimum=sizing.get("minimum_area"); maximum=sizing.get("maximum_area"); target=sizing.get("target_area")
        return (None if minimum is None else float(minimum)*count,
                None if maximum is None else float(maximum)*count,
                None if target is None else float(target)*count)

    @staticmethod
    def _weighted(claimants,available):
        bounds={f["function_id"]:FlexibleAreaAllocationAuthorityV1._bounds(f) for f in claimants}
        result={f["function_id"]:(bounds[f["function_id"]][0] or 0.0) for f in claimants}
        if sum(result.values())>available+1e-7: return None
        remaining=available-sum(result.values()); active=list(claimants)
        while active and remaining>1e-9:
            total=sum(_weight(f["spatial_sizing"])[0] for f in active); distributed=0.0; next_active=[]
            for function in active:
                fid=function["function_id"]; share=remaining*_weight(function["spatial_sizing"])[0]/total
                maximum=bounds[fid][1]; room=float("inf") if maximum is None else maximum-result[fid]
                addition=min(share,max(0.0,room)); result[fid]+=addition; distributed+=addition
                if room>addition+1e-9: next_active.append(function)
            if distributed<=1e-9: break
            remaining-=distributed; active=next_active
        return result

    def allocate(self,resource_map,demand_profile):
        resolved=deepcopy(demand_profile); functions=resolved.get("functions",[])
        floors=sorted({floor for resource in resource_map.get("resources",[]) for floor in resource.get("floor_scope",[])} |
                      {floor for function in functions for floor in function.get("floor_scope",[])})
        records=[]; unresolved=[]
        for function in functions:
            if function.get("spatial_sizing",{}).get("sizing_mode")!="FLEXIBLE_AREA_DEMAND": continue
            scope=function.get("floor_scope",[])
            if len(scope)!=1:
                unresolved.append({"function_id":function["function_id"],"floor_id":None,
                    "reason":"multi_floor_flexible_demand_requires_distinct_sizing_authority" if scope else "flexible_floor_scope_required"})
        for floor in floors:
            domain,domain_failure=self._domain(resource_map,floor)
            relevant=[f for f in functions if floor in f.get("floor_scope",[])]
            claimants=[f for f in relevant if f.get("spatial_sizing",{}).get("sizing_mode")=="FLEXIBLE_AREA_DEMAND" and
                       len(f.get("floor_scope",[]))==1]
            reservations=[]; reserved=0.0; reservation_failure=None
            for function in relevant:
                sizing=function.get("spatial_sizing",{})
                if sizing.get("sizing_mode") in ("FLEXIBLE_AREA_DEMAND","COUNT_ONLY"): continue
                area=sizing.get("resolved_spatial_area")
                if area is None: continue
                if len(function.get("floor_scope",[]))!=1 and sizing.get("sizing_mode")!="DERIVED_GEOMETRIC_FOOTPRINT":
                    reservation_failure="ambiguous_nonflexible_floor_scope"; continue
                reserved+=float(area); reservations.append({"function_id":function["function_id"],"area_m2":float(area),
                    "sizing_mode":sizing.get("sizing_mode"),"provenance":deepcopy(sizing.get("provenance",[]))})
            failure=(domain_failure or reservation_failure) if claimants else None
            available=None if domain is None else domain["capacity_m2"]
            allocatable=None if available is None else available-reserved
            allocations={}; mode=None; provenance=[]
            if not failure and allocatable is not None and allocatable<-1e-7:
                failure="over_constrained_floor"
            if not failure and claimants:
                if True:
                    targets=[f for f in claimants if self._bounds(f)[2] is not None]
                    untargeted=[f for f in claimants if f not in targets]
                    for function in targets:
                        minimum,maximum,target=self._bounds(function)
                        if (minimum is not None and target<minimum) or (maximum is not None and target>maximum):
                            failure="target_outside_bounds"; break
                        allocations[function["function_id"]]=target
                    remaining=allocatable-sum(allocations.values())
                    if not failure and remaining<-1e-7: failure="over_constrained_floor"
                    if not failure and untargeted:
                        if len(untargeted)==1:
                            function=untargeted[0]; minimum,maximum,_=self._bounds(function)
                            value=min(remaining,maximum) if maximum is not None else remaining
                            if value<0 or (minimum is not None and value+1e-7<minimum): failure="flexible_minimum_unsatisfied"
                            else:
                                allocations[function["function_id"]]=value; mode="single_claimant_residual"
                                provenance=["authoritative_floor_residual"]
                        elif all(_signature(f)==_signature(untargeted[0]) for f in untargeted):
                            value=remaining/len(untargeted); valid=all((self._bounds(f)[0] is None or value+1e-7>=self._bounds(f)[0]) and
                                (self._bounds(f)[1] is None or value<=self._bounds(f)[1]+1e-7) for f in untargeted)
                            if not valid: failure="symmetric_allocation_violates_bounds"
                            else:
                                allocations.update({f["function_id"]:value for f in untargeted}); mode="symmetry_preserving_equal"
                                provenance=["symmetry_no_distinguishing_evidence"]
                        elif all(_weight(f["spatial_sizing"]) is not None for f in untargeted):
                            weighted=self._weighted(untargeted,remaining)
                            if weighted is None: failure="flexible_minimum_unsatisfied"
                            else:
                                allocations.update(weighted); mode="evidence_weighted"
                                provenance=[p for f in untargeted for p in _weight(f["spatial_sizing"])[1]]
                        else: failure="asymmetric_claimants_without_valid_allocation_evidence"
                    elif not failure: mode="explicit_targets"; provenance=["program.target_area"]
            if failure:
                allocations={}
                for function in claimants:
                    unresolved.append({"function_id":function["function_id"],"floor_id":floor,"reason":failure})
            for function in claimants:
                if function["function_id"] not in allocations: continue
                value=allocations[function["function_id"]]; sizing=function["spatial_sizing"]
                sizing["allocated_area_m2"]=value; sizing["resolved_spatial_area"]=value; sizing["status"]="resolved"
                sizing["allocation_mode"]=mode; sizing["allocation_provenance"]=deepcopy(provenance)
                sizing["provenance"]=list(sizing.get("provenance",[]))+deepcopy(provenance)
            records.append({"floor_id":floor,"available_area_before":available,"reserved_nonflexible_area":reserved,
                "allocatable_flexible_area":max(0.0,allocatable) if allocatable is not None else None,
                "floor_supply":domain,"reservations":reservations,"claimant_ids":[f["function_id"] for f in claimants],
                "claimants":[{"function_id":f["function_id"],"bounds_m2":{"minimum":self._bounds(f)[0],
                    "maximum":self._bounds(f)[1],"target":self._bounds(f)[2]},"flexible_weight":deepcopy(f["spatial_sizing"].get("flexible_weight")),
                    "allocated_area_m2":allocations.get(f["function_id"])} for f in claimants],
                "allocation_mode":mode,"provenance":deepcopy(provenance),
                "confidence":min([domain["confidence"]]+[float(f["spatial_sizing"].get("confidence",0.0)) for f in claimants]) if domain and claimants else 0.0,
                "unresolved_reason":failure})
        resolved["source_contract"]=demand_profile.get("contract")
        resolved["contract"]="FlexibleAreaAllocatedDemandProfileV1"
        return {"contract":"FlexibleAreaAllocationAuthorityV1","area_unit":"m2","count_is_area":False,
                "floors":records,"unresolved":unresolved,"demand_profile":resolved,
                "complete":not unresolved and all(r["unresolved_reason"] is None for r in records)}
