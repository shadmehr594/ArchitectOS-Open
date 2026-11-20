"""Unit-safe spatial sizing authority between program demand and allocation."""
from copy import deepcopy

MODES=frozenset(("COUNT_ONLY","FIXED_AUTHORITATIVE_AREA","MINIMUM_FUNCTIONAL_AREA",
                 "FLEXIBLE_AREA_DEMAND","DERIVED_GEOMETRIC_FOOTPRINT"))
NON_AREAL_FUNCTIONS=frozenset(("vehicle_circulation","pedestrian_access","corridor","common",
                               "site_vehicle_entrance","public_pedestrian_entrance"))


class SpatialDemandSizingAndCapacityV1:
    def resolve(self,demand_profile):
        functions=[]
        for source in demand_profile.get("functions",[]):
            fn=deepcopy(source); count=float(fn.get("quantity",1)); dimensions=fn.get("dimensional_requirements")
            explicit=fn.get("explicit_area")
            if explicit is None: explicit=fn.get("required_capacity")
            minimum=fn.get("minimum_area"); maximum=fn.get("maximum_area"); target=fn.get("target_area")
            requested=fn.get("sizing_mode")
            if requested is not None and requested not in MODES:
                raise ValueError("unknown spatial sizing mode: "+str(requested))
            if requested:
                mode=requested
            elif fn.get("function") in NON_AREAL_FUNCTIONS:
                mode="COUNT_ONLY"
            elif fn.get("capacity_derivation")=="dimensions_width_x_depth" or (
                    explicit is None and dimensions and len(dimensions)>=2 and dimensions[0] is not None and dimensions[1] is not None):
                mode="DERIVED_GEOMETRIC_FOOTPRINT"
            elif explicit is not None:
                mode="FIXED_AUTHORITATIVE_AREA"
            elif minimum is not None:
                mode="MINIMUM_FUNCTIONAL_AREA"
            else:
                mode="FLEXIBLE_AREA_DEMAND"
            provenance=[]; per_item=None; status="spatial_area_unresolved"
            if mode=="FIXED_AUTHORITATIVE_AREA" and explicit is not None:
                per_item=float(explicit); provenance=["program.required_capacity"]
            elif mode=="MINIMUM_FUNCTIONAL_AREA" and minimum is not None:
                per_item=float(minimum); provenance=["program.minimum_area"]
            elif mode=="DERIVED_GEOMETRIC_FOOTPRINT" and dimensions and len(dimensions)>=2:
                per_item=float(dimensions[0])*float(dimensions[1]); provenance=["dimensional_requirements.width_x_depth"]
            elif mode=="FLEXIBLE_AREA_DEMAND" and target is not None:
                per_item=float(target); provenance=["program.target_area"]
            if per_item is not None:
                if per_item<=0 or count<=0: raise ValueError("spatial area and count must be positive")
                status="resolved"; resolved=per_item*count
            else:
                resolved=None
            fn["spatial_sizing"]={"sizing_mode":mode,"count":count,"count_unit":fn.get("count_unit","count"),
                "area_unit":"m2","fixed_area":float(explicit) if mode=="FIXED_AUTHORITATIVE_AREA" and explicit is not None else None,
                "minimum_area":float(minimum) if minimum is not None else None,
                "maximum_area":float(maximum) if maximum is not None else None,
                "target_area":float(target) if target is not None else None,
                "flexible_weight":fn.get("flexible_weight"),"floor_scope":deepcopy(fn.get("floor_scope",[])),
                "derived_footprint":per_item if mode=="DERIVED_GEOMETRIC_FOOTPRINT" else None,
                "resolved_spatial_area":resolved,"status":status,"source":"program_and_dimensions",
                "provenance":provenance,"confidence":float(fn.get("operational_requirements",{}).get("confidence",.8))}
            functions.append(fn)
        return {"contract":"SpatialDemandSizingAndCapacityV1","source_contract":demand_profile.get("contract"),
                "functions":functions,"area_unit":"m2","count_is_area":False,"complete":bool(functions)}
