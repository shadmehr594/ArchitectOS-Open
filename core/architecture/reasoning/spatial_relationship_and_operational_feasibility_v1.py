"""Explicit geometry proofs for architectural relationships and operations."""
from copy import deepcopy
from hashlib import sha256
import json

from shapely.geometry import LineString, Polygon, shape
from shapely.ops import unary_union


RELATIONSHIPS=("ADJACENT","DIRECT_ACCESS","CONNECTED_BY_CIRCULATION","SERVES",
    "REQUIRES_DAYLIGHT_FROM","VEHICLE_ACCESSIBLE_FROM","VERTICALLY_ALIGNED_WITH",
    "MUST_NOT_REQUIRE_TRANSIT_THROUGH")


def _geometry(value):
    if value is None: return None
    if hasattr(value,"geom_type"): return value
    if isinstance(value,dict) and "type" in value: return shape(value)
    if isinstance(value,(list,tuple)) and value:
        return LineString(value) if len(value)<3 else Polygon(value)
    return None


class SpatialRelationshipAndOperationalFeasibilityV1:
    EPS=1e-7

    def evaluate(self, realized_geometry, relationships, daylight_deficit=None, ownership=None):
        if ownership and ownership.get("hard_validation_status") != "hard_valid":
            return {"contract":"SpatialRelationshipAndOperationalFeasibilityV1","status":"skipped_upstream_ownership_failure",
                "hard_validation_status":"not_evaluated","relationship_results":[],"hard_failures":[],
                "operational_scoring_skipped":True,"critic_skipped":True,"complete":False}
        spaces={item["space_id"]:item for item in realized_geometry}; results=[]
        for index, relation in enumerate(relationships):
            kind=relation.get("relationship"); required=bool(relation.get("required",True))
            provenance=deepcopy(relation.get("provenance",[])); evidence={"relationship_id":relation.get("relationship_id","relationship-%d"%index)}
            if kind not in RELATIONSHIPS:
                status="unknown"; reason="unsupported_relationship"
            else:
                status,reason,proof=self._prove(kind,relation,spaces,daylight_deficit or {})
                evidence.update(proof)
            results.append({"relationship_id":evidence["relationship_id"],"relationship":kind,
                "from":relation.get("from"),"to":relation.get("to"),"required":required,"status":status,
                "reason":reason,"geometry_evidence":evidence,"provenance":provenance,
                "confidence":float(relation.get("confidence",0.0)) if status!="unknown" else 0.0})
        failures=[{"relationship_id":r["relationship_id"],"relationship":r["relationship"],"status":r["status"],"reason":r["reason"]}
                  for r in results if r["required"] and r["status"]!="pass"]
        if not relationships: failures.append({"relationship_id":None,"relationship":None,"status":"unknown","reason":"operational_relationship_contract_missing"})
        valid=not failures
        payload={"contract":"SpatialRelationshipAndOperationalFeasibilityV1","status":"pass" if valid else "fail",
            "hard_validation_status":"hard_valid" if valid else "not_feasible","relationship_results":results,
            "hard_failures":failures,"hard_failure_codes":list(dict.fromkeys(x["reason"] for x in failures)),
            "operational_scoring_skipped":not valid,"critic_skipped":not valid,"complete":bool(relationships)}
        payload["operational_fingerprint"]=sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
        return payload

    def _prove(self,kind,relation,spaces,daylight):
        left=spaces.get(relation.get("from")); right=spaces.get(relation.get("to"))
        if left is None or right is None:
            return "unknown","relationship_endpoint_missing",{}
        a=_geometry(left.get("polygon")); b=_geometry(right.get("polygon"))
        if a is None or b is None:
            return "unknown","relationship_geometry_missing",{}
        proof={"from_geometry":a.__geo_interface__,"to_geometry":b.__geo_interface__}
        if kind in ("ADJACENT","DIRECT_ACCESS"):
            contact=a.boundary.intersection(b.boundary); passed=not contact.is_empty and contact.length>self.EPS
            proof.update({"contact_geometry":contact.__geo_interface__,"contact_length":contact.length})
            return ("pass" if passed else "fail"),("boundary_contact_proven" if passed else "no_usable_boundary_contact"),proof
        if kind=="VERTICALLY_ALIGNED_WITH":
            overlap=a.intersection(b).area; denominator=max(a.area,b.area,self.EPS); ratio=overlap/denominator
            floor_a=set(left.get("floor_scope",[])); floor_b=set(right.get("floor_scope",[])); required_floors=set(relation.get("required_floor_scope",[]))
            scope_valid=bool(floor_a) and floor_a==floor_b and (not required_floors or required_floors.issubset(floor_a))
            passed=ratio>=float(relation.get("minimum_overlap_ratio",.999)) and scope_valid
            proof.update({"overlap_geometry":a.intersection(b).__geo_interface__,"overlap_ratio":ratio,"from_floor_scope":sorted(floor_a),"to_floor_scope":sorted(floor_b),"required_floor_scope":sorted(required_floors),"scope_valid":scope_valid})
            return ("pass" if passed else "fail"),("vertical_alignment_proven" if passed else "vertical_alignment_failed"),proof
        connector_ids=relation.get("via",[]); connectors=[_geometry(spaces[x].get("polygon")) for x in connector_ids if x in spaces]
        if kind=="MUST_NOT_REQUIRE_TRANSIT_THROUGH":
            path=_geometry(relation.get("path_geometry")); forbidden=[_geometry(spaces[x].get("polygon")) for x in relation.get("forbidden",[]) if x in spaces]
            if path is None: return "unknown","transit_path_missing",proof
            obstruction=path.intersection(unary_union(forbidden)) if forbidden else Polygon()
            passed=obstruction.is_empty or getattr(obstruction,"length",0)<=self.EPS
            proof.update({"path_geometry":path.__geo_interface__,"forbidden_intersection":obstruction.__geo_interface__})
            return ("pass" if passed else "fail"),("forbidden_transit_avoided" if passed else "route_crosses_incompatible_zone"),proof
        if not connectors:
            return "unknown","circulation_connector_missing",proof
        network=unary_union(connectors); connected=(network.geom_type not in ("MultiPolygon","MultiLineString","GeometryCollection") or len(getattr(network,"geoms",[]))<=1)
        tolerance=float(relation.get("connection_tolerance",self.EPS)); reaches_a=a.distance(network)<=tolerance; reaches_b=b.distance(network)<=tolerance
        passed=connected and reaches_a and reaches_b
        proof.update({"connector_ids":connector_ids,"connector_geometry":network.__geo_interface__,"network_connected":connected,
                      "from_distance":a.distance(network),"to_distance":b.distance(network)})
        if kind=="REQUIRES_DAYLIGHT_FROM":
            deficits={x["function_id"] for x in daylight.get("demonstrated_deficits",[])}
            if relation.get("from") not in deficits: return "fail","daylight_source_not_justified_by_demonstrated_deficit",proof
            if right.get("occupancy_role") not in ("DAYLIGHT_COURT","VOID"): return "fail","invalid_daylight_source_role",proof
        reason={"CONNECTED_BY_CIRCULATION":"circulation_connection","SERVES":"service_connection",
                "REQUIRES_DAYLIGHT_FROM":"daylight_service_connection","VEHICLE_ACCESSIBLE_FROM":"vehicle_access_connection"}[kind]
        return ("pass" if passed else "fail"),(reason+"_proven" if passed else reason+"_failed"),proof
