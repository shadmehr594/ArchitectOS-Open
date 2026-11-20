"""Daylight demand/supply proof before any new source geometry exists."""
from copy import deepcopy

STATES=("KNOWN_SUFFICIENT","KNOWN_DEFICIT","UNKNOWN_SUPPLY","INCOMPLETE_EVIDENCE")


class PreRealizationDaylightDeficitV1:
    def evaluate(self, resource_map, demand_profile):
        resources=resource_map.get("resources",[]); functions=demand_profile.get("functions",[])
        floors=sorted({floor for r in resources for floor in r.get("floor_scope",[])} |
                      {floor for f in functions for floor in f.get("floor_scope",[])})
        rows=[]; demonstrated=[]; unknown=[]
        for floor in floors:
            relevant=[r for r in resources if floor in r.get("floor_scope",[])]
            supply_records=[]; unknown_supply_records=[]
            for resource in relevant:
                daylight=resource["channels"]["daylight_value"]; capacity=resource.get("usable_capacity")
                if daylight["status"]=="unknown" or daylight["value"] is None or capacity is None:
                    unknown_supply_records.append({"resource_id":resource["resource_id"],"reason":"unknown_daylight_value_or_capacity"}); continue
                usable=float(capacity)*float(daylight["value"])
                supply_records.append({"resource_id":resource["resource_id"],"gross_capacity":resource["gross_capacity"],
                    "usable_daylight_capacity":usable,"floor":floor,"source":daylight["source"],
                    "provenance":deepcopy(daylight["provenance"]),"confidence":daylight["confidence"]})
            demands=[]
            for function in functions:
                if function.get("floor_scope") and floor not in function["floor_scope"]: continue
                daylight=function["demands"]["daylight_need"]
                amount=None if daylight["value"] is None else float(daylight["value"])*function["required_capacity"]*function["quantity"]
                demands.append({"function_id":function["function_id"],"function":function["function"],"demand":amount,
                    "status":daylight["status"],"source":daylight["source"],"provenance":deepcopy(daylight["provenance"]),
                    "confidence":daylight["confidence"]})
            demand_unknown=any(d["demand"] is None or d["status"]=="unknown" for d in demands)
            if not relevant or (not supply_records and unknown_supply_records): state="UNKNOWN_SUPPLY"
            elif unknown_supply_records or demand_unknown or not demands: state="INCOMPLETE_EVIDENCE"
            else:
                total_supply=sum(x["usable_daylight_capacity"] for x in supply_records)
                total_demand=sum(d["demand"] for d in demands)
                state="KNOWN_DEFICIT" if total_demand>total_supply+1e-9 else "KNOWN_SUFFICIENT"
            remaining=sum(x["usable_daylight_capacity"] for x in supply_records) if state.startswith("KNOWN_") else None
            assessments=[]
            for demand in sorted(demands,key=lambda d:(-(d["demand"] or 0),d["function_id"])):
                served=min(remaining,demand["demand"]) if remaining is not None and demand["demand"] is not None else None
                deficit=demand["demand"]-served if served is not None else None
                if served is not None: remaining-=served
                severity="unknown" if deficit is None else "none" if deficit<=1e-9 else "critical" if deficit/max(demand["demand"],1e-9)>.5 else "material"
                record={**demand,"floor":floor,"evidence_state":state,"existing_supply_allocated":served,
                    "deficit_magnitude":deficit,"deficit_ratio":None if deficit is None or not demand["demand"] else deficit/demand["demand"],
                    "severity":severity,"competing_functions":[x["function_id"] for x in demands if x["function_id"]!=demand["function_id"]],
                    "confidence":min([demand["confidence"]]+[x["confidence"] for x in supply_records]) if state.startswith("KNOWN_") and supply_records else 0.0}
                assessments.append(record)
                if state=="KNOWN_DEFICIT" and deficit and deficit>1e-9: demonstrated.append(record)
                elif state in ("UNKNOWN_SUPPLY","INCOMPLETE_EVIDENCE"): unknown.append(record)
            rows.append({"floor":floor,"evidence_state":state,"existing_daylight_resources":supply_records,
                "unknown_supply_records":unknown_supply_records,"gross_existing_supply":sum(x["gross_capacity"] for x in supply_records),
                "usable_existing_supply":sum(x["usable_daylight_capacity"] for x in supply_records) if state.startswith("KNOWN_") else None,
                "function_assessments":assessments})
        eligible=bool(demonstrated) and all(row["evidence_state"] not in ("UNKNOWN_SUPPLY","INCOMPLETE_EVIDENCE") for row in rows)
        required=sum(x["deficit_magnitude"] for x in demonstrated) if eligible else 0.0
        return {"contract":"PreRealizationDaylightDeficitV1","evidence_states":list(STATES),"floors":rows,
            "demonstrated_deficits":demonstrated,"unknown_assessments":unknown,
            "additional_daylight_source_required":eligible,"additional_daylight_source_eligible":eligible,
            "new_source_requirements":({"minimum_usable_capacity":required,"served_functions":sorted({x["function_id"] for x in demonstrated}),
                "floor_scope":sorted({x["floor"] for x in demonstrated}),"location_status":"not_determined",
                "must_preserve_ownership":True,"provenance":["demonstrated_pre_realization_deficit"]} if eligible else None),
            "court_assumed":False,"complete":bool(rows) and all(r["evidence_state"] in ("KNOWN_SUFFICIENT","KNOWN_DEFICIT") for r in rows)}
