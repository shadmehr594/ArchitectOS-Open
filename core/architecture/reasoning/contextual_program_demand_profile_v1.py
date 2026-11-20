"""Layered function-level resource demand before spatial realization."""
from copy import deepcopy

CHANNELS = ("frontage_need", "public_access_need", "daylight_need", "visibility_need",
            "privacy_need", "quietness_need", "terrace_relation_need", "service_access_need", "noise_tolerance")

DEFAULTS = {
 "commercial": (1,.95,.45,1,.05,.05,.2,.55,.9),
 "residential_unit": (.65,.6,1,.65,.45,.45,.8,.25,.45), "living": (.65,.6,1,.65,.45,.45,.8,.25,.45),
 "bedroom": (.25,.2,.9,.15,1,1,.35,.1,.1), "kitchen": (.2,.3,.55,.15,.35,.35,.2,.85,.65),
 "terrace": (.65,.2,.85,.7,.45,.35,1,.1,.7), "stair": (.08,.75,.2,.1,.1,.15,.05,.65,.9),
 "elevator": (.02,.8,.02,.02,.2,.35,.02,.8,.9), "lobby": (.55,1,.45,.65,.15,.15,.2,.4,.8),
 "corridor": (.05,.9,.15,.05,.15,.25,.05,.45,.8), "bathroom": (.01,.1,.1,.01,.9,.6,.01,.85,.8),
 "wc": (.01,.1,.03,.01,.95,.6,.01,.9,.85), "storage": (0,.05,.02,0,.5,.5,0,.65,.9),
 "service": (.02,.2,.08,.02,.4,.35,.01,1,.95), "shaft": (0,.05,0,0,.5,.5,0,1,1),
 "parking": (.02,1,0,.05,0,0,0,1,1)}


class ContextualProgramDemandProfileV1:
    def build(self, program, requirements=None, regulations=None, context=None):
        layers = (("program", program), ("requirements", requirements or {}),
                  ("regulations", regulations or {}), ("context", context or {}))
        functions = program.get("functions", program if isinstance(program, list) else [])
        result = []
        for index, raw in enumerate(functions):
            kind = str(raw.get("function", raw.get("space_type", ""))).lower()
            fallback = DEFAULTS.get(kind)
            values = {}
            for pos, channel in enumerate(CHANNELS):
                item = ({"value": fallback[pos], "status": "fallback", "source": "documented_default",
                         "provenance": ["ContextualProgramDemandProfileV1.DEFAULTS"], "confidence": .35}
                        if fallback is not None else {"value": None, "status": "unknown", "source": None,
                                                      "provenance": [], "confidence": 0.0})
                for layer_name, layer in layers:
                    override = layer.get("demands", {}).get(kind, {}).get(channel) if isinstance(layer, dict) else None
                    direct = raw.get("demands", {}).get(channel) if layer_name == "program" else None
                    override = direct if direct is not None else override
                    if override is not None:
                        payload = override if isinstance(override, dict) else {"value": override}
                        item = {"value": float(payload["value"]) if payload.get("value") is not None else None,
                                "status": payload.get("status", "known"), "source": payload.get("source", layer_name),
                                "provenance": deepcopy(payload.get("provenance", [layer_name])),
                                "confidence": float(payload.get("confidence", .8))}
                values[channel] = item
            parking_requirements=(requirements or {}).get("parking",{}) if kind=="parking" else {}
            dimensions=raw.get("dimensions") or ([parking_requirements.get("stall_width"),parking_requirements.get("stall_depth")]
                if parking_requirements.get("stall_width") is not None and parking_requirements.get("stall_depth") is not None else None)
            quantity=raw.get("quantity",parking_requirements.get("minimum_count",1))
            capacity=raw.get("required_capacity")
            capacity_derivation="authoritative_input" if capacity is not None else None
            if capacity is None and dimensions:
                capacity=float(dimensions[0])*float(dimensions[1]); capacity_derivation="dimensions_width_x_depth"
            operational=deepcopy(raw.get("operational_requirements",{}))
            if kind=="parking":
                operational.update({k:deepcopy(v) for k,v in parking_requirements.items() if k not in ("minimum_count",)})
                operational["dependencies"]=list(dict.fromkeys(operational.get("dependencies",[])+["vehicle_access","vehicle_circulation","maneuvering_field"]))
                operational["provenance"]=deepcopy(raw.get("provenance",[(requirements or {}).get("source","requirements.parking")]))
                operational["confidence"]=float(raw.get("confidence",.9 if parking_requirements else .35))
            result.append({"function_id": raw.get("function_id", "%s-%d" % (kind or "unknown", index)),
                           "function": kind or "unknown", "floor_scope": list(raw.get("floor_scope", [])),
                           "quantity": float(quantity), "count_unit":raw.get("count_unit","count"),
                           "required_capacity":float(capacity) if capacity is not None else None,
                           "capacity_unit":raw.get("capacity_unit",("m" if kind in ("vehicle_circulation","pedestrian_access","corridor","common") else "m2")) if capacity is not None else None,
                           "capacity_derivation":capacity_derivation,
                           "sizing_mode":raw.get("sizing_mode"),
                           "explicit_area":raw.get("explicit_area"),"minimum_area":raw.get("minimum_area"),
                           "maximum_area":raw.get("maximum_area"),"target_area":raw.get("target_area"),
                           "flexible_weight":raw.get("flexible_weight"),
                           "dimensional_requirements":deepcopy(dimensions),"operational_requirements":operational,
                           "prerequisites": list(raw.get("prerequisites", [])), "demands": values,
                           "status": "known" if fallback is not None else "unknown_function_fail_closed"})
        return {"contract": "ContextualProgramDemandProfileV1", "functions": result,
                "unknown_function_policy": "fail_closed", "complete": bool(result)}
