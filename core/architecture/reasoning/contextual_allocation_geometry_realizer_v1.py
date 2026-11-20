"""Geometry realization driven only by joint allocation contracts."""
from copy import deepcopy
from hashlib import sha256
import json
from math import atan2, degrees

from shapely.affinity import rotate
from shapely.errors import GEOSException
from shapely.geometry import Polygon, box, mapping, shape
from shapely.ops import unary_union
from shapely.validation import explain_validity, make_valid

from .floor_program_spatial_ownership_v1 import FloorProgramSpatialOwnershipV1
from .spatial_relationship_and_operational_feasibility_v1 import SpatialRelationshipAndOperationalFeasibilityV1
from .relationship_constrained_geometry_realization_v1 import RelationshipConstrainedGeometryRealizationV1


ROLE={"commercial":"COMMERCIAL","residential_unit":"RESIDENTIAL_UNIT","living":"RESIDENTIAL_UNIT","bedroom":"RESIDENTIAL_UNIT",
      "kitchen":"RESIDENTIAL_UNIT","terrace":"TERRACE","stair":"STAIR","elevator":"ELEVATOR",
      "lobby":"LOBBY","corridor":"COMMON","bathroom":"SERVICE","wc":"SERVICE","storage":"SERVICE",
      "service":"SERVICE","shaft":"SERVICE","parking":"PARKING_STALL","vehicle_circulation":"VEHICLE_CIRCULATION",
      "pedestrian_access":"PEDESTRIAN_ACCESS","daylight_source":"DAYLIGHT_COURT","void":"VOID"}

CONTINUITY_REQUIRED_ROLES=frozenset(("RESIDENTIAL_UNIT","STAIR","ELEVATOR","LOBBY","PARKING_STALL"))


def _poly(geometry):
    if geometry.is_empty: return []
    if geometry.geom_type != "Polygon": geometry=max(geometry.geoms,key=lambda g:g.area)
    return [[float(x),float(y)] for x,y in list(geometry.exterior.coords)[:-1]]


def _principal_angle(geometry):
    rectangle=geometry.minimum_rotated_rectangle; points=list(rectangle.exterior.coords)
    edges=[(points[i],points[i+1]) for i in range(4)]
    a,b=max(edges,key=lambda e:(e[1][0]-e[0][0])**2+(e[1][1]-e[0][1])**2)
    return degrees(atan2(b[1]-a[1],b[0]-a[0]))


def _polygon_parts(geometry):
    if geometry.geom_type=="Polygon": return [geometry]
    if geometry.geom_type=="MultiPolygon": return list(geometry.geoms)
    if hasattr(geometry,"geoms"):
        return [part for child in geometry.geoms for part in _polygon_parts(child)]
    return []


def _component_count(geometry):
    if geometry.is_empty: return 0
    if hasattr(geometry,"geoms"): return len(geometry.geoms)
    return 1


def _validated_areal_geometry(geometry):
    area_before=float(geometry.area); reason=explain_validity(geometry)
    evidence={"input_validity":"valid" if geometry.is_valid else "invalid","repair_applied":False,
        "repair_method":None,"geometry_type_before":geometry.geom_type,"geometry_type_after":geometry.geom_type,
        "area_before":area_before,"area_after":area_before,"validity_reason":reason,
        "component_count_before":_component_count(geometry),"component_count_after":_component_count(geometry),
        "input_geometry":mapping(geometry),"repaired_geometry":None,"repair_status":"not_required"}
    if geometry.is_valid: return geometry,evidence,None
    try:
        repaired=make_valid(geometry)
    except (GEOSException,ValueError) as exc:
        evidence.update({"repair_applied":True,"repair_method":"GEOSMakeValid","geometry_type_after":None,
            "area_after":None,"validity_reason":reason+"; repair failed: "+str(exc),"repair_status":"rejected"})
        return Polygon(),evidence,"invalid_geometry_repair_failed"
    parts=[part for part in _polygon_parts(repaired) if not part.is_empty and part.area>0]
    area_after=float(repaired.area); tolerance=max(1e-7,abs(area_before)*1e-7)
    evidence.update({"repair_applied":True,"repair_method":"GEOSMakeValid","geometry_type_after":repaired.geom_type,
        "area_after":area_after,"component_count_after":_component_count(repaired),"repaired_geometry":mapping(repaired)})
    if not parts:
        evidence.update({"validity_reason":reason+"; repair lost areal dimension","repair_status":"rejected"})
        return Polygon(),evidence,"invalid_geometry_repair_dimensional_collapse"
    if len(parts)!=1:
        evidence.update({"validity_reason":reason+"; repair produced multiple areal components","repair_status":"rejected"})
        return Polygon(),evidence,"invalid_geometry_repair_multiple_components"
    if abs(area_after-area_before)>tolerance:
        evidence.update({"validity_reason":reason+"; repair changed area beyond tolerance","repair_status":"rejected"})
        return Polygon(),evidence,"invalid_geometry_repair_area_change"
    accepted=parts[0]
    evidence.update({"geometry_type_after":accepted.geom_type,"area_after":float(accepted.area),
        "component_count_after":_component_count(accepted),"repaired_geometry":mapping(accepted),"repair_status":"accepted"})
    return accepted,evidence,None


def _validate_operation_result(geometry,operation_name,empty_allowed=True,multipart_allowed=False):
    validated,evidence,failure=_validated_areal_geometry(geometry)
    evidence={"operation_name":operation_name,"result_validity":"valid" if validated.is_valid else "invalid",**evidence}
    if failure: return Polygon(),evidence,failure
    if validated.is_empty and not empty_allowed:
        evidence.update({"validity_reason":evidence["validity_reason"]+"; empty result is not permitted",
            "repair_status":"rejected"})
        return Polygon(),evidence,"geometry_operation_empty_result"
    if validated.geom_type=="GeometryCollection":
        evidence.update({"validity_reason":evidence["validity_reason"]+"; GeometryCollection is unsupported at this boundary",
            "repair_status":"rejected"})
        return Polygon(),evidence,"geometry_operation_unsupported_collection"
    return validated,evidence,None


def _validate_published_geometry(geometry,role,function_id):
    validated,evidence,failure=_validate_operation_result(geometry,"functional_geometry.publication",False,True)
    evidence.update({"function_id":function_id,"occupancy_role":role,
        "continuity_required":role in CONTINUITY_REQUIRED_ROLES})
    if failure: return Polygon(),evidence,failure
    if role in CONTINUITY_REQUIRED_ROLES and _component_count(validated)>1:
        evidence.update({"validity_reason":evidence["validity_reason"]+"; role requires one contiguous domain",
            "publication_status":"rejected"})
        return Polygon(),evidence,"published_function_continuity_required"
    evidence["publication_status"]="accepted"
    return validated,evidence,None


def _boolean_operation(left,right,operation_name,empty_allowed=True,multipart_result_allowed=False,
                       multipart_left_allowed=False):
    evidence=[]
    left,left_evidence,failure=_validate_operation_result(left,operation_name+".left_input",True,multipart_left_allowed)
    evidence.append(left_evidence)
    if failure: return Polygon(),evidence,failure
    right,right_evidence,failure=_validate_operation_result(right,operation_name+".right_input",True,False)
    evidence.append(right_evidence)
    if failure: return Polygon(),evidence,failure
    try:
        if operation_name.endswith("intersection"): result=left.intersection(right)
        elif operation_name.endswith("difference"): result=left.difference(right)
        elif operation_name.endswith("union"): result=left.union(right)
        else: raise ValueError("unsupported boolean operation")
    except GEOSException as exc:
        evidence.append({"operation_name":operation_name,"input_validity":"valid","result_validity":"unknown",
            "repair_applied":False,"repair_method":None,"geometry_type_before":[left.geom_type,right.geom_type],
            "geometry_type_after":None,"area_before":[float(left.area),float(right.area)],"area_after":None,
            "validity_reason":str(exc),"repair_status":"operation_failed"})
        return Polygon(),evidence,"geometry_boolean_operation_failed"
    result,result_evidence,failure=_validate_operation_result(result,operation_name+".result",empty_allowed,multipart_result_allowed)
    evidence.append(result_evidence)
    return result,evidence,failure


def _take_area(available, target):
    available,validity,failure=_validated_areal_geometry(available)
    if failure: return Polygon(),validity,failure
    validity["operation_name"]="take_area.input"
    validity["operation_evidence"]=[]
    if target<=0 or available.is_empty: return Polygon(),validity,None
    if target>=available.area-1e-8:
        result,result_evidence,failure=_validate_operation_result(available,"take_area.result",False,False)
        validity["operation_evidence"].append(result_evidence)
        return result,validity,failure
    try:
        angle=_principal_angle(available); origin=available.centroid
        aligned=rotate(available,-angle,origin=origin); x0,y0,x1,y1=aligned.bounds
        margin=max(x1-x0,y1-y0,1)*2; lo,hi=x0,x1
        for _ in range(48):
            cut=(lo+hi)/2
            portion,operation_evidence,operation_failure=_boolean_operation(
                aligned,box(x0-margin,y0-margin,cut,y1+margin),"take_area_search.intersection",True,False,False)
            if operation_failure:
                validity["operation_evidence"].extend(operation_evidence)
                return Polygon(),validity,operation_failure
            if portion.area<target: lo=cut
            else: hi=cut
        clipped,operation_evidence,operation_failure=_boolean_operation(
            aligned,box(x0-margin,y0-margin,hi,y1+margin),"take_area_final.intersection",False,False,False)
        validity["operation_evidence"].extend(operation_evidence)
        if operation_failure: return Polygon(),validity,operation_failure
        result=rotate(clipped,angle,origin=origin)
    except GEOSException as exc:
        validity.update({"operation":"intersection","operation_status":"failed",
            "operation_failure":str(exc)})
        return Polygon(),validity,"geometry_boolean_operation_failed"
    result,result_evidence,failure=_validate_operation_result(result,"take_area.rotated_result",False,False)
    validity["operation_evidence"].append(result_evidence)
    validity.update({"operation":"intersection","operation_status":"passed" if not failure else "failed"})
    return result,validity,failure


class ContextualAllocationGeometryRealizerV1:
    def realize(self, allocation_plan, resource_map, demand_profile, daylight_deficit, floor_boundaries,
                contextual_evaluator=None, relationship_contracts=None):
        resources={r["resource_id"]:shape(r["geometry"]) for r in resource_map.get("resources",[])}
        functions={f["function_id"]:f for f in demand_profile.get("functions",[])}
        candidates=[]
        for hypothesis in allocation_plan.get("hypotheses",[]):
            generated=[]; used_by_floor={floor:Polygon() for floor in floor_boundaries}; failures=[]; validity_evidence=[]
            bridge=RelationshipConstrainedGeometryRealizationV1()
            constraint_plan=bridge.compile(hypothesis,demand_profile,relationship_contracts,resource_map)
            failures.extend(constraint_plan["prepublication_failures"])
            placed={}; relationship_constraint_evidence=[]
            for assignment in constraint_plan["ordered_assignments"]:
                function=functions.get(assignment["function_id"]); region=resources.get(assignment["resource_id"])
                if function is None or region is None:
                    failures.append("assignment_reference_missing"); continue
                role=ROLE.get(function["function"])
                if role is None:
                    failures.append("unsupported_function_role"); continue
                if assignment.get("spatial_requirement")=="AREA_OCCUPANCY" and (
                        assignment.get("consumed_area") is None or assignment.get("capacity_unit")!="m2"):
                    failures.append("resolved_spatial_area_required"); continue
                if function["function"] in ("daylight_source","void") and not daylight_deficit.get("additional_daylight_source_required"):
                    failures.append("daylight_source_without_demonstrated_deficit"); continue
                floors=function.get("floor_scope") or list(floor_boundaries)
                common=region
                for floor in floors:
                    if floor not in floor_boundaries: failures.append("unknown_floor_scope"); continue
                    common,stage_evidence,stage_failure=_boolean_operation(
                        common,Polygon(floor_boundaries[floor]),"floor_boundary.intersection",True,False,False)
                    validity_evidence.extend({"function_id":function["function_id"],"resource_id":assignment["resource_id"],**entry}
                                             for entry in stage_evidence)
                    if stage_failure: failures.append(stage_failure); break
                    common,stage_evidence,stage_failure=_boolean_operation(
                        common,used_by_floor[floor],"used_space.difference",True,False,False)
                    validity_evidence.extend({"function_id":function["function_id"],"resource_id":assignment["resource_id"],**entry}
                                             for entry in stage_evidence)
                    if stage_failure: failures.append(stage_failure); break
                if stage_failure: continue
                common,constraint_evidence,constraint_failure=bridge.constrain_available(
                    function["function_id"],common,placed,constraint_plan["placement_constraints"],float(assignment["consumed_capacity"]))
                relationship_constraint_evidence.append(constraint_evidence)
                if constraint_failure:
                    failures.append(constraint_failure); continue
                geometry,validity,validity_failure=_take_area(common,float(assignment["consumed_capacity"]))
                validity={"function_id":function["function_id"],"resource_id":assignment["resource_id"],**validity}
                validity_evidence.append(validity)
                if validity_failure:
                    failures.append(validity_failure); continue
                geometry,publication_evidence,publication_failure=_validate_published_geometry(
                    geometry,role,function["function_id"])
                validity_evidence.append({"resource_id":assignment["resource_id"],**publication_evidence})
                if publication_failure:
                    failures.append(publication_failure); continue
                proof,relationship_failure=bridge.verify_before_publication(
                    function["function_id"],geometry,placed,constraint_plan["placement_constraints"])
                relationship_constraint_evidence.append(proof)
                if relationship_failure:
                    failures.append(relationship_failure); continue
                if geometry.area+1e-7<float(assignment["consumed_capacity"]):
                    failures.append("insufficient_realizable_geometry"); continue
                accumulator_failed=False
                for floor in floors:
                    updated,stage_evidence,stage_failure=_boolean_operation(
                        used_by_floor[floor],geometry,"used_by_floor.union",True,True,True)
                    validity_evidence.extend({"function_id":function["function_id"],"resource_id":assignment["resource_id"],
                        "floor":floor,**entry} for entry in stage_evidence)
                    if stage_failure:
                        failures.append(stage_failure); accumulator_failed=True; break
                    used_by_floor[floor]=updated
                if accumulator_failed: continue
                placed[function["function_id"]]=geometry
                generated.append({"space_id":function["function_id"],"function":function["function"],
                    "occupancy_role":role,"floor_scope":list(floors),"polygon":_poly(geometry),
                    "resource_id":assignment["resource_id"],"assignment_evidence":deepcopy(assignment.get("evidence",[])),
                    "geometry_validity":deepcopy(validity)})
            infrastructure,infrastructure_failures=bridge.realize_infrastructure(
                constraint_plan,placed,resources,functions,floor_boundaries)
            failures.extend(infrastructure_failures); generated.extend(infrastructure)
            prerequisites=hypothesis.get("prerequisites",{})
            realized_ids={x["space_id"] for x in generated}
            for fid,needed in prerequisites.items():
                if fid in realized_ids and not set(needed).issubset(realized_ids): failures.append("unrealized_prerequisite")
            ownership=self._ownership(floor_boundaries,generated)
            failures.extend(ownership["hard_failure_codes"])
            ownership_valid=not failures and ownership["hard_validation_status"]=="hard_valid"
            selected_relationships=self._relationships_for_hypothesis(
                constraint_plan["relationship_contract"],hypothesis["hypothesis_id"],generated)
            if selected_relationships is None:
                operational={"contract":"SpatialRelationshipAndOperationalFeasibilityV1","status":"missing_required_contract",
                    "hard_validation_status":"not_feasible","relationship_results":[],"hard_failure_codes":["operational_relationship_contract_missing"],
                    "operational_scoring_skipped":True,"critic_skipped":True,"complete":False}
            else:
                operational=SpatialRelationshipAndOperationalFeasibilityV1().evaluate(generated,selected_relationships,daylight_deficit,ownership)
            hard_valid=ownership_valid and operational["hard_validation_status"]=="hard_valid"
            evaluated=contextual_evaluator(deepcopy(hypothesis),deepcopy(generated)) if hard_valid and contextual_evaluator else None
            payload={"hypothesis_id":hypothesis["hypothesis_id"],"geometry":generated,
                "geometry_validity_evidence":validity_evidence,
                "relationship_constrained_realization":constraint_plan,
                "relationship_constraint_evidence":relationship_constraint_evidence,
                "floor_program_ownership":ownership,"hard_validation_status":"hard_valid" if hard_valid else "not_feasible",
                "spatial_relationship_and_operational_feasibility":operational,
                "hard_rejection_reasons":list(dict.fromkeys(failures+operational.get("hard_failure_codes",[]))),
                "contextual_scoring_skipped":not hard_valid,"operational_scoring_skipped":not ownership_valid,
                "contextual_evaluation":evaluated,"geometry_seed_used":False,"final_selection_performed":False,
                "winner":None,"room_layout_generated":False,"final_windows_generated":False,
                "structure_executed":False,"bim_executed":False,"ifc_executed":False,"render_executed":False}
            payload["realization_fingerprint"]=sha256(json.dumps({"hypothesis":hypothesis,"geometry":generated,
                "ownership":ownership},sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
            candidates.append(payload)
        shortlist=[c for c in candidates if c["hard_validation_status"]=="hard_valid"]
        return {"contract":"ContextualAllocationGeometryRealizerV1","candidates":candidates,"shortlist":shortlist,
            "shortlist_ids":[c["hypothesis_id"] for c in shortlist],"final_selection_performed":False,"winner":None,
            "room_layout_generated":False,"final_windows_generated":False,"geometry_seed_used":False,"complete":bool(candidates)}

    @staticmethod
    def _relationships_for_hypothesis(contract,hypothesis_id,generated=None):
        if contract is None: return None
        if not isinstance(contract,dict): return contract
        if isinstance(contract,dict) and contract.get("contract")!="OperationalRelationshipRequirementDerivationV1":
            return contract.get(hypothesis_id,[]) if isinstance(contract,dict) else contract
        item=next((x for x in contract.get("hypotheses",[]) if x["hypothesis_id"]==hypothesis_id),None)
        if item is None: return None
        requirements=item.get("relationship_requirements",[])+item.get("mandatory_unresolved",[])
        geometry_by_id={space["space_id"]:space.get("polygon") for space in (generated or [])}
        result=[]
        for req in requirements:
            relation={"relationship_id":"%s:%s:%s"%(req["relationship_type"],req["source_function"],req.get("target_function")),
                "relationship":req["relationship_type"],"from":req["source_function"],"to":req.get("target_function"),
                "via":req.get("via_functions",[]),"required":req["required"],"provenance":req["provenance"],
                "confidence":req["confidence"]}
            if req["relationship_type"]=="VERTICALLY_ALIGNED_WITH": relation["required_floor_scope"]=req["floor_scope"]
            if req["relationship_type"]=="MUST_NOT_REQUIRE_TRANSIT_THROUGH":
                via=[fid for fid in req.get("via_functions",[]) if geometry_by_id.get(fid)]
                relation["path_geometry"]=geometry_by_id.get(via[0]) if via else None
                relation["forbidden"]=[fid for fid in req.get("forbidden_functions",[]) if geometry_by_id.get(fid)]
            result.append(relation)
        return result

    @staticmethod
    def _ownership(floor_boundaries, generated):
        authority=FloorProgramSpatialOwnershipV1(); roles=authority.ROLES; records=[]
        for item in generated:
            if item.get("non_occupancy_infrastructure"): continue
            role=item["occupancy_role"]; may=set()
            if role in ("STAIR","ELEVATOR","LOBBY"): may.add("VERTICAL_CORE")
            if role=="DAYLIGHT_COURT": may.add("VOID")
            if role=="VOID": may.add("DAYLIGHT_COURT")
            extent=("CONTINUOUS:%s..%s"%(item["floor_scope"][0],item["floor_scope"][-1])
                    if role in ("STAIR","ELEVATOR","LOBBY") else "MULTI_FLOOR" if len(item["floor_scope"])>1 else "SINGLE_FLOOR")
            records.append({"space_id":item["space_id"],"floor_scope":item["floor_scope"],"vertical_extent":extent,
                "occupancy_role":role,"polygon":item["polygon"],"exclusive_with":sorted(roles-{role}-may),
                "may_overlap_with":sorted(may),"source_requirement":"allocation_hypothesis"})
        core_parts=[Polygon(x["polygon"]) for x in generated if not x.get("non_occupancy_infrastructure") and x["occupancy_role"] in ("STAIR","ELEVATOR","LOBBY")]
        if core_parts:
            members=[x for x in generated if x["occupancy_role"] in ("STAIR","ELEVATOR","LOBBY")]
            scopes=set(tuple(x["floor_scope"]) for x in members)
            if len(scopes)==1:
                scope=list(next(iter(scopes))); records.append({"space_id":"VERTICAL-CORE","floor_scope":scope,
                    "vertical_extent":"CONTINUOUS:%s..%s"%(scope[0],scope[-1]),"occupancy_role":"VERTICAL_CORE",
                    "polygon":_poly(unary_union(core_parts)),"exclusive_with":sorted(roles-{"VERTICAL_CORE","STAIR","ELEVATOR","LOBBY"}),
                    "may_overlap_with":["STAIR","ELEVATOR","LOBBY"],"source_requirement":"derived_core_components"})
        preliminary=authority.evaluate(floor_boundaries,records)
        for floor,boundary in floor_boundaries.items():
            active=[Polygon(r["polygon"]) for r in preliminary["spaces"] if floor in r["floor_scope"] and r["polygon"] and r["occupancy_role"] not in ("VERTICAL_CORE","UNALLOCATED")]
            residual=Polygon(boundary).difference(unary_union(active)) if active else Polygon(boundary)
            parts=[residual] if residual.geom_type=="Polygon" else [g for g in residual.geoms if g.geom_type=="Polygon"]
            for index,part in enumerate(parts): records.append({"space_id":"%s-UNALLOCATED-%d"%(floor,index+1),"floor_scope":[floor],
                "vertical_extent":"SINGLE_FLOOR","occupancy_role":"UNALLOCATED","polygon":_poly(part),
                "exclusive_with":sorted(roles-{"UNALLOCATED"}),"may_overlap_with":[],"source_requirement":"computed_residual"})
        return authority.evaluate(floor_boundaries,records)
