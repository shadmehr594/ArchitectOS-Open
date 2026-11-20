"""Compile operational relationships into constraints consumed before geometry publication."""
from copy import deepcopy

from shapely.geometry import LineString, Polygon, shape
from shapely.ops import nearest_points, unary_union


class RelationshipConstrainedGeometryRealizationV1:
    """Pre-placement relationship bridge; it never relocates published geometry."""

    def compile(self,hypothesis,demand_profile,relationship_contract,resource_map):
        functions={f["function_id"]:f for f in demand_profile.get("functions",[])}
        allocated={a["function_id"] for a in hypothesis.get("assignments",[])}
        selected=self._selected(relationship_contract,hypothesis["hypothesis_id"])
        relationships=deepcopy(selected.get("relationship_requirements",[]))
        unresolved=deepcopy(selected.get("mandatory_unresolved",[]))
        constraints=[]; infrastructure=[]; failures=[]
        for relation in relationships:
            constraints.append(self._constraint(relation))
            if relation["relationship_type"]=="CONNECTED_BY_CIRCULATION" and relation["source_requirement"]=="residential.common_access":
                route_id="DERIVED-COMMON-ROUTE:"+relation["source_function"]
                relation["via_functions"]=[route_id]
                infrastructure.append({"function_id":route_id,"kind":"COMMON_CIRCULATION_ROUTE",
                    "source_function":relation["source_function"],"target_function":relation["target_function"],
                    "floor_scope":relation["floor_scope"],"program_room":False,
                    "source_requirement":relation["source_requirement"]})
        remaining=[]
        for relation in unresolved:
            if relation["source_requirement"]=="parking.vehicle_access" and relation["source_function"] in allocated:
                target="DERIVED-VEHICLE-CIRCULATION:"+relation["source_function"]
                relation.update({"target_function":target,"status":"resolved","reason":None})
                relationships.append(relation); constraints.append(self._constraint(relation))
                infrastructure.append({"function_id":target,"kind":"VEHICLE_CIRCULATION_FIELD",
                    "source_function":relation["source_function"],"floor_scope":relation["floor_scope"],
                    "program_room":False,"source_requirement":relation["source_requirement"]})
            elif relation["source_requirement"]=="commercial.public_access" and relation["source_function"] in allocated:
                access=self._eligible_public_access(hypothesis,resource_map,relation["source_function"])
                if access is None:
                    remaining.append(relation); failures.append("eligible_public_access_resource_missing"); continue
                target="DERIVED-PUBLIC-ACCESS-POINT:"+relation["source_function"]
                route="DERIVED-PUBLIC-ROUTE:"+relation["source_function"]
                relation.update({"target_function":target,"via_functions":[route],"status":"resolved","reason":None})
                relationships.append(relation); constraints.append(self._constraint(relation))
                infrastructure.extend([
                    {"function_id":target,"kind":"PUBLIC_ACCESS_POINT","resource_id":access,
                     "floor_scope":relation["floor_scope"],"program_room":False,"dedicated_entrance":False,
                     "source_requirement":relation["source_requirement"]},
                    {"function_id":route,"kind":"PUBLIC_CIRCULATION_ROUTE","source_function":relation["source_function"],
                     "target_function":target,"floor_scope":relation["floor_scope"],"program_room":False,
                     "source_requirement":relation["source_requirement"]}])
            else: remaining.append(relation)
        for relation in remaining:
            if relation.get("required"): failures.append("relationship_constraint_unresolved")
        order=self._ordered_assignments(hypothesis.get("assignments",[]),constraints)
        derived_contract={"contract":"OperationalRelationshipRequirementDerivationV1","hypotheses":[{
            "hypothesis_id":hypothesis["hypothesis_id"],"relationship_requirements":relationships,
            "unresolved_requirements":remaining,"mandatory_unresolved":remaining,"complete":not remaining}]}
        return {"contract":"RelationshipConstrainedGeometryRealizationV1","hypothesis_id":hypothesis["hypothesis_id"],
            "ordered_assignments":order,"placement_constraints":constraints,"derived_infrastructure":infrastructure,
            "relationship_contract":derived_contract,"prepublication_failures":list(dict.fromkeys(failures)),
            "post_failure_relocation_allowed":False,"final_geometry_published":False}

    @staticmethod
    def _selected(contract,hypothesis_id):
        if not isinstance(contract,dict): return {"relationship_requirements":[],"mandatory_unresolved":[]}
        return next((x for x in contract.get("hypotheses",[]) if x["hypothesis_id"]==hypothesis_id),
                    {"relationship_requirements":[],"mandatory_unresolved":[]})

    @staticmethod
    def _constraint(relation):
        mapping={"DIRECT_ACCESS":"USABLE_SHARED_BOUNDARY","CONNECTED_BY_CIRCULATION":"CIRCULATION_CONNECTIVITY",
            "VEHICLE_ACCESSIBLE_FROM":"VEHICLE_CIRCULATION_CONNECTIVITY","VERTICALLY_ALIGNED_WITH":"VERTICAL_ALIGNMENT",
            "MUST_NOT_REQUIRE_TRANSIT_THROUGH":"FORBIDDEN_TRANSIT"}
        return {"constraint_type":mapping.get(relation["relationship_type"],relation["relationship_type"]),
            "source_function":relation["source_function"],"target_function":relation.get("target_function"),
            "floor_scope":deepcopy(relation.get("floor_scope",[])),"required":relation.get("required",True),
            "consumed_before_publication":True,"provenance":deepcopy(relation.get("provenance",[]))}

    @staticmethod
    def _ordered_assignments(assignments,constraints):
        hubs={c["source_function"] for c in constraints if c["constraint_type"]=="USABLE_SHARED_BOUNDARY"}
        targets={c["target_function"] for c in constraints if c["constraint_type"]=="USABLE_SHARED_BOUNDARY"}
        indexed=list(enumerate(deepcopy(assignments)))
        indexed.sort(key=lambda pair:(0 if pair[1]["function_id"] in hubs else 1 if pair[1]["function_id"] in targets else 2,pair[0]))
        return [assignment for _,assignment in indexed]

    @staticmethod
    def _eligible_public_access(hypothesis,resource_map,function_id):
        assignment=next((a for a in hypothesis.get("assignments",[]) if a["function_id"]==function_id),None)
        if assignment is None: return None
        resources={r["resource_id"]:r for r in resource_map.get("resources",[])}
        candidates=[]
        for attachment in assignment.get("resource_attachments",[]):
            resource=resources.get(attachment["resource_id"]); channel=(resource or {}).get("channels",{}).get("public_access_value",{})
            if channel.get("status")!="unknown" and (channel.get("value") or 0)>0: candidates.append(resource["resource_id"])
        return sorted(candidates)[0] if candidates else None

    def constrain_available(self,function_id,available,placed,constraints,required_area):
        applicable=[]
        for constraint in constraints:
            if constraint["constraint_type"]!="USABLE_SHARED_BOUNDARY": continue
            other=None
            if constraint["source_function"]==function_id: other=constraint["target_function"]
            elif constraint["target_function"]==function_id: other=constraint["source_function"]
            if other in placed: applicable.append(placed[other])
        if not applicable: return available,{"function_id":function_id,"constraints_applied":[],"status":"unconstrained"},None
        constrained=available
        for anchor in applicable:
            lo=0.0; hi=max(available.bounds[2]-available.bounds[0],available.bounds[3]-available.bounds[1],1.0)
            for _ in range(48):
                distance=(lo+hi)/2; region=constrained.intersection(anchor.buffer(distance))
                if region.area<required_area: lo=distance
                else: hi=distance
            constrained=constrained.intersection(anchor.buffer(hi))
        failure=None if constrained.area+1e-7>=required_area else "relationship_constrained_region_insufficient"
        return constrained,{"function_id":function_id,"constraints_applied":["USABLE_SHARED_BOUNDARY"]*len(applicable),
            "status":"feasible" if failure is None else "not_feasible","required_area":required_area,
            "available_area":float(constrained.area)},failure

    def verify_before_publication(self,function_id,geometry,placed,constraints):
        for constraint in constraints:
            if constraint["constraint_type"]!="USABLE_SHARED_BOUNDARY": continue
            pair={constraint["source_function"],constraint["target_function"]}
            if function_id not in pair: continue
            other=next(iter(pair-{function_id}),None)
            if other not in placed: continue
            contact=geometry.boundary.intersection(placed[other].boundary)
            if contact.is_empty or contact.length<=1e-7:
                return {"function_id":function_id,"status":"not_feasible","reason":"usable_shared_boundary_missing",
                    "other_function":other,"contact_length":float(contact.length)},"relationship_prepublication_direct_access_failed"
        return {"function_id":function_id,"status":"pass"},None

    def realize_infrastructure(self,plan,placed,resources,functions,floor_boundaries):
        generated=[]; failures=[]; self.infrastructure_publication_evidence=[]
        for spec in plan["derived_infrastructure"]:
            kind=spec["kind"]
            if kind=="PUBLIC_ACCESS_POINT":
                geometry=resources.get(spec["resource_id"])
                if geometry is None: failures.append("public_access_resource_geometry_missing"); continue
                self._publish(spec,"PEDESTRIAN_ACCESS",geometry,True,generated,failures)
            elif kind in ("COMMON_CIRCULATION_ROUTE","PUBLIC_CIRCULATION_ROUTE"):
                source=placed.get(spec["source_function"]); target=placed.get(spec["target_function"])
                if source is None or target is None: failures.append("route_endpoint_missing"); continue
                a,b=nearest_points(source,target); route=LineString([a,b])
                forbidden=[g for fid,g in placed.items() if fid!=spec["source_function"] and fid!=spec["target_function"] and fid.startswith("residential-")]
                if forbidden and route.crosses(unary_union(forbidden)):
                    failures.append("route_crosses_forbidden_private_domain"); continue
                self._publish(spec,"COMMON" if kind.startswith("COMMON") else "PEDESTRIAN_ACCESS",route,True,generated,failures)
            elif kind=="VEHICLE_CIRCULATION_FIELD":
                parking=placed.get(spec["source_function"]); function=functions.get(spec["source_function"],{})
                width=function.get("operational_requirements",{}).get("aisle_width")
                if parking is None or width is None or not spec.get("floor_scope"):
                    failures.append("vehicle_circulation_evidence_incomplete"); continue
                floor=spec["floor_scope"][0]; boundary=Polygon(floor_boundaries[floor])
                field=parking.buffer(float(width)).difference(parking).intersection(boundary)
                self._publish(spec,"VEHICLE_CIRCULATION",field,False,generated,failures)
        return generated,list(dict.fromkeys(failures))

    def _publish(self,spec,role,geometry,non_occupancy,generated,failures):
        evidence=self._publication_evidence(spec,role,geometry)
        supported_linear=role in ("COMMON","PEDESTRIAN_ACCESS")
        geometry_type=evidence["geometry_type"]
        publishable=(geometry_type in ("Polygon","MultiPolygon") or
                     supported_linear and geometry_type in ("LineString","MultiLineString"))
        if not publishable or evidence["is_empty"] or not evidence["is_valid"]:
            evidence["status"]="rejected"
            evidence["failure_code"]=("derived_infrastructure_unsupported_geometry_type" if not publishable else
                "derived_infrastructure_empty_geometry" if evidence["is_empty"] else
                "derived_infrastructure_invalid_geometry")
            self.infrastructure_publication_evidence.append(evidence)
            failures.append(evidence["failure_code"])
            return
        evidence["status"]="published"
        evidence["failure_code"]=None
        self.infrastructure_publication_evidence.append(evidence)
        generated.append(self._record(spec,role,geometry,non_occupancy))

    @staticmethod
    def _publication_evidence(spec,role,geometry):
        parts=list(geometry.geoms) if hasattr(geometry,"geoms") else []
        return {"space_id":spec["function_id"],"infrastructure_kind":spec["kind"],
            "occupancy_role":role,"geometry_type":geometry.geom_type,
            "component_count":len(parts),"component_types":[part.geom_type for part in parts],
            "is_empty":bool(geometry.is_empty),"is_valid":bool(geometry.is_valid),
            "area":float(geometry.area),"length":float(geometry.length)}

    @staticmethod
    def _record(spec,role,geometry,non_occupancy):
        if geometry.geom_type=="LineString": coordinates=list(geometry.coords)
        elif geometry.geom_type=="MultiLineString": coordinates=[list(part.coords) for part in geometry.geoms]
        elif geometry.geom_type=="Polygon": coordinates=list(geometry.exterior.coords)[:-1]
        elif geometry.geom_type=="MultiPolygon": coordinates=[list(part.exterior.coords)[:-1] for part in geometry.geoms]
        else: raise ValueError("unsupported publication geometry type: "+geometry.geom_type)
        return {"space_id":spec["function_id"],"function":spec["kind"].lower(),"occupancy_role":role,
            "floor_scope":deepcopy(spec.get("floor_scope",[])),"polygon":coordinates,
            "geometry_mapping":geometry.__geo_interface__,"derived_operational_infrastructure":True,
            "program_room":False,"non_occupancy_infrastructure":non_occupancy,
            "source_requirement":spec["source_requirement"]}
