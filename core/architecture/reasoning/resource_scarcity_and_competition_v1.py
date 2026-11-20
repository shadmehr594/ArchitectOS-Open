"""Floor- and geometry-aware resource scarcity and function competition."""
from collections import defaultdict

MAP = {"frontage_value":"frontage_need", "public_access_value":"public_access_need", "daylight_value":"daylight_need",
       "visibility_value":"visibility_need", "privacy_value":"privacy_need", "quietness_value":"quietness_need",
       "terrace_value":"terrace_relation_need"}


class ResourceScarcityAndCompetitionV1:
    def evaluate(self, resource_map, demand_profile):
        rows=[]
        floors=sorted({f for r in resource_map.get("resources",[]) for f in r.get("floor_scope",[])}) or [None]
        for floor in floors:
            for resource_channel, demand_channel in MAP.items():
                matching=[r for r in resource_map.get("resources",[]) if floor in r.get("floor_scope",[]) and r["channels"][resource_channel]["status"]!="unknown"]
                capacities=[r.get("usable_capacity") for r in matching]
                supply=sum(c*r["channels"][resource_channel]["value"] for r,c in zip(matching,capacities) if c is not None)
                supply_known=bool(matching) and all(c is not None for c in capacities)
                competitors=[]; demand=0.0; confidences=[]; unresolved=[]
                for fn in demand_profile.get("functions",[]):
                    if fn.get("floor_scope") and floor not in fn["floor_scope"]: continue
                    item=fn["demands"][demand_channel]
                    if item["status"]=="unknown" or item["value"] is None: continue
                    sizing=fn.get("spatial_sizing",{})
                    area=sizing.get("resolved_spatial_area")
                    if area is None and fn.get("required_capacity") is not None and fn.get("capacity_unit")=="m2":
                        area=float(fn["required_capacity"])*float(fn.get("quantity",1))
                    if area is None or (sizing and sizing.get("area_unit")!="m2"):
                        unresolved.append(fn["function_id"]); continue
                    weighted=item["value"]*area
                    if weighted>0: competitors.append({"function_id":fn["function_id"],"weighted_demand":weighted}); demand+=weighted; confidences.append(item["confidence"])
                known=supply_known and bool(confidences) and not unresolved
                ratio=demand/supply if known and supply>0 else (float("inf") if known and demand>0 else None)
                cls=("unknown" if not known else "scarce" if ratio>.65 else "balanced" if ratio>.35 else "abundant")
                rows.append({"floor":floor,"resource_channel":resource_channel,"demand_channel":demand_channel,
                             "gross_supply":sum(r["gross_capacity"] for r in matching),"usable_supply":supply if supply_known else None,
                             "weighted_demand":demand,"demand_supply_ratio":ratio,"scarcity_class":cls,
                             "unresolved_spatial_demands":sorted(set(unresolved)),
                             "competing_functions":sorted(competitors,key=lambda x:(-x["weighted_demand"],x["function_id"])),
                             "confidence":min(confidences+[min((r["channels"][resource_channel]["confidence"] for r in matching),default=0)]) if known else 0.0,
                             "status":"known" if known else "unknown"})
        return {"contract":"ResourceScarcityAndCompetitionV1","resources":rows,"unknown_is_zero":False,"complete":bool(rows)}
