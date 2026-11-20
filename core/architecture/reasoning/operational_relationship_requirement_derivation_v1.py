"""Derive operational relationship intent from program semantics, never geometry."""
from copy import deepcopy
from hashlib import sha256
import json


FUNCTION_TAXONOMY={
 "parking":{"roles":["PARKING"],"zone":"vehicle"},
 "vehicle_circulation":{"roles":["VEHICLE_CIRCULATION"],"zone":"vehicle"},
 "site_vehicle_entrance":{"roles":["SITE_VEHICLE_ENTRANCE"],"zone":"vehicle"},
 "commercial":{"roles":["COMMERCIAL"],"zone":"public"},
 "public_access_point":{"roles":["PUBLIC_ACCESS_POINT"],"zone":"public"},
 "public_pedestrian_entrance":{"roles":["PUBLIC_ACCESS_POINT","PUBLIC_PEDESTRIAN_ENTRANCE"],"zone":"public"},
 "pedestrian_access":{"roles":["PUBLIC_CIRCULATION"],"zone":"public"},
 "lobby":{"roles":["LOBBY","COMMON_CIRCULATION"],"zone":"common"},
 "stair":{"roles":["STAIR","VERTICAL_COMPONENT"],"zone":"common"},
 "elevator":{"roles":["ELEVATOR","VERTICAL_COMPONENT"],"zone":"common"},
 "residential_unit":{"roles":["RESIDENTIAL_UNIT"],"zone":"private"},
 "living":{"roles":["RESIDENTIAL_UNIT","PRINCIPAL_DAYLIGHT_FUNCTION"],"zone":"private"},
 "bedroom":{"roles":["RESIDENTIAL_UNIT","PRINCIPAL_DAYLIGHT_FUNCTION"],"zone":"private"},
 "common":{"roles":["COMMON_CIRCULATION"],"zone":"common"},
 "corridor":{"roles":["COMMON_CIRCULATION"],"zone":"common"},
 "terrace":{"roles":["TERRACE"],"zone":"private"},
 "daylight_source":{"roles":["DAYLIGHT_SOURCE"],"zone":"void"},
 "service":{"roles":["SERVICE"],"zone":"service"},
 "shaft":{"roles":["SERVICE","VERTICAL_COMPONENT"],"zone":"service"}}

RULES=(
 {"source_role":"PARKING","target_role":"VEHICLE_CIRCULATION","relationship_type":"VEHICLE_ACCESSIBLE_FROM","required":True,"source_requirement":"parking.vehicle_access"},
 {"source_role":"VEHICLE_CIRCULATION","target_role":"SITE_VEHICLE_ENTRANCE","relationship_type":"CONNECTED_BY_CIRCULATION","required":True,"source_requirement":"vehicle.access_to_site"},
 {"source_role":"COMMERCIAL","target_role":"PUBLIC_ACCESS_POINT","relationship_type":"CONNECTED_BY_CIRCULATION","via_role":"PUBLIC_CIRCULATION","required":True,"source_requirement":"commercial.public_access"},
 {"source_role":"LOBBY","target_role":"STAIR","relationship_type":"DIRECT_ACCESS","required":True,"source_requirement":"core.lobby_stair_access"},
 {"source_role":"LOBBY","target_role":"ELEVATOR","relationship_type":"DIRECT_ACCESS","required":True,"source_requirement":"core.lobby_elevator_access"},
 {"source_role":"RESIDENTIAL_UNIT","target_role":"COMMON_CIRCULATION","relationship_type":"CONNECTED_BY_CIRCULATION","required":True,"source_requirement":"residential.common_access"},
 {"source_role":"TERRACE","target_role":"OWNER","relationship_type":"DIRECT_ACCESS","required":True,"source_requirement":"terrace.owner_access"},
 {"source_role":"VERTICAL_COMPONENT","target_role":"SELF_VERTICAL","relationship_type":"VERTICALLY_ALIGNED_WITH","required":True,"source_requirement":"vertical.required_scope"})

FORBIDDEN_TRANSIT={"public":["private","service","vehicle"],"common":["private"],"private":["private"],
    "vehicle":["private","public"],"service":["private"]}


class OperationalRelationshipRequirementDerivationV1:
    def derive(self, demand_profile, allocation_plan, daylight_deficit, program_requirements=None):
        requirements=program_requirements or {}; taxonomy=deepcopy(FUNCTION_TAXONOMY)
        taxonomy.update(deepcopy(requirements.get("function_semantics_registry",{})))
        functions={f["function_id"]:deepcopy(f) for f in demand_profile.get("functions",[])}
        semantics={fid:self._semantics(fn,taxonomy) for fid,fn in functions.items()}
        by_role={}
        for fid,item in semantics.items():
            for role in item["roles"]: by_role.setdefault(role,[]).append(fid)
        results=[]
        for hypothesis in allocation_plan.get("hypotheses",[]):
            allocated={a["function_id"] for a in hypothesis.get("assignments",[])}
            derived=[]; unresolved=[]
            for rule in RULES:
                for source in by_role.get(rule["source_role"],[]):
                    target_ids=self._targets(rule,source,functions,semantics,by_role)
                    self._publish(rule,source,target_ids,allocated,functions,semantics,derived,unresolved,requirements)
            self._daylight(daylight_deficit,by_role,allocated,functions,semantics,derived,unresolved)
            self._transit(functions,semantics,allocated,derived,unresolved)
            results.append({"hypothesis_id":hypothesis["hypothesis_id"],"relationship_requirements":derived,
                "unresolved_requirements":unresolved,"mandatory_unresolved":[x for x in unresolved if x["required"]],
                "complete":not any(x["required"] for x in unresolved)})
        payload={"contract":"OperationalRelationshipRequirementDerivationV1","hypotheses":results,
            "taxonomy_source":"general_registry_plus_explicit_overrides","geometry_inference_used":False,
            "provenance":deepcopy(requirements.get("provenance",[])),"input_fingerprints":{
                "program":self._fingerprint(demand_profile),"allocation":self._fingerprint(allocation_plan),
                "daylight":self._fingerprint(daylight_deficit),"requirements":self._fingerprint(requirements)},
            "complete":bool(results) and all(x["complete"] for x in results)}
        payload["relationship_requirement_fingerprint"]=sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
        return payload

    @staticmethod
    def _fingerprint(value): return sha256(json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

    @staticmethod
    def _semantics(function,taxonomy):
        base=deepcopy(taxonomy.get(function.get("function"),{})); explicit=function.get("operational_requirements",{}).get("semantics",{})
        base.update(deepcopy(explicit)); base.setdefault("roles",[]); base.setdefault("zone","unknown")
        return base

    @staticmethod
    def _targets(rule,source,functions,semantics,by_role):
        if rule["target_role"]=="OWNER":
            owner=functions[source].get("operational_requirements",{}).get("owner_function_id")
            return [owner] if owner else []
        if rule["target_role"]=="SELF_VERTICAL": return [source]
        return list(by_role.get(rule["target_role"],[]))

    def _publish(self,rule,source,target_ids,allocated,functions,semantics,derived,unresolved,requirements):
        required=bool(requirements.get("relationship_overrides",{}).get(rule["source_requirement"],{}).get("required",rule["required"]))
        provenance=[rule["source_requirement"]]+deepcopy(requirements.get("provenance",[]))
        floor_scope=list(functions[source].get("floor_scope",[]))
        base={"relationship_type":rule["relationship_type"],"source_function":source,"target_role":rule["target_role"],
            "floor_scope":floor_scope,"required":required,"optional":not required,"preconditions":["source_allocated","target_allocated"],
            "source_requirement":rule["source_requirement"],"provenance":provenance,"confidence":float(requirements.get("confidence",.8)),
            "evidence_status":"derived_from_program_semantics"}
        valid_targets=[target for target in target_ids if target in functions]
        if not valid_targets:
            unresolved.append({**base,"target_function":None,"status":"unresolved","reason":"required_target_not_defined"}); return
        for target in valid_targets:
            item={**base,"target_function":target,"status":"resolved" if source in allocated and target in allocated else "unresolved",
                "reason":None if source in allocated and target in allocated else "source_or_target_not_allocated"}
            if rule.get("via_role"):
                via=[x for x in self._role_members(rule["via_role"],semantics) if x in allocated]; item["via_functions"]=via
                if not via: item.update({"status":"unresolved","reason":"circulation_connector_not_allocated"})
            (derived if item["status"]=="resolved" else unresolved).append(item)

    @staticmethod
    def _role_members(role,semantics): return [fid for fid,item in semantics.items() if role in item["roles"]]

    def _daylight(self,daylight,by_role,allocated,functions,semantics,derived,unresolved):
        states={row.get("evidence_state") for row in daylight.get("floors",[])}
        if "KNOWN_DEFICIT" not in states or states.intersection({"UNKNOWN_SUPPLY","INCOMPLETE_EVIDENCE"}): return
        sources=by_role.get("DAYLIGHT_SOURCE",[])
        for deficit in daylight.get("demonstrated_deficits",[]):
            source=deficit["function_id"]
            base={"relationship_type":"REQUIRES_DAYLIGHT_FROM","source_function":source,"target_role":"DAYLIGHT_SOURCE",
                "floor_scope":[deficit["floor"]],"required":True,"optional":False,"preconditions":["known_deficit","source_allocated"],
                "source_requirement":"pre_realization_daylight_deficit","provenance":["PreRealizationDaylightDeficitV1"],
                "confidence":deficit.get("confidence",0.0),"evidence_status":"KNOWN_DEFICIT"}
            valid=[x for x in sources if x in functions]
            if not valid: unresolved.append({**base,"target_function":None,"status":"unresolved","reason":"eligible_daylight_source_not_defined"})
            for target in valid:
                item={**base,"target_function":target,"status":"resolved" if source in allocated and target in allocated else "unresolved",
                    "reason":None if source in allocated and target in allocated else "source_or_target_not_allocated"}
                (derived if item["status"]=="resolved" else unresolved).append(item)

    def _transit(self,functions,semantics,allocated,derived,unresolved):
        route_roles={"public":{"PUBLIC_CIRCULATION"},"common":{"COMMON_CIRCULATION"},
            "private":{"COMMON_CIRCULATION"},"vehicle":{"VEHICLE_CIRCULATION"},
            "service":{"COMMON_CIRCULATION"}}
        route_relationships={"DIRECT_ACCESS","CONNECTED_BY_CIRCULATION","VEHICLE_ACCESSIBLE_FROM","SERVES"}
        route_required_sources={requirement["source_function"] for requirement in derived+unresolved
            if requirement.get("required") and requirement.get("relationship_type") in route_relationships}
        for source,item in semantics.items():
            if source not in allocated or source not in route_required_sources or item["zone"] not in FORBIDDEN_TRANSIT: continue
            via=[fid for fid,semantic in semantics.items() if fid in allocated and route_roles[item["zone"]].intersection(semantic["roles"])]
            forbidden=[fid for fid,semantic in semantics.items() if fid in allocated and fid!=source
                and semantic["zone"] in FORBIDDEN_TRANSIT[item["zone"]]]
            requirement={"relationship_type":"MUST_NOT_REQUIRE_TRANSIT_THROUGH","source_function":source,
                "target_function":source,"target_role":"ROUTE_CONSTRAINT","floor_scope":list(functions[source].get("floor_scope",[])),
                "forbidden_zones":deepcopy(FORBIDDEN_TRANSIT[item["zone"]]),
                "forbidden_functions":forbidden,"via_functions":via,
                "required":True,"optional":False,"preconditions":["route_realized"],"source_requirement":"zone_compatibility",
                "provenance":["general_zone_compatibility_registry"],"confidence":.8,"evidence_status":"derived_from_program_semantics",
                "status":"resolved" if via else "unresolved",
                "reason":None if via else "compatible_route_function_not_allocated"}
            (derived if via else unresolved).append(requirement)
