"""Architectural spatial quality evaluation; never repairs or invents layout."""

from __future__ import annotations


class ArchitecturalSpatialQualityGateV1:
    VERSION="1.0"

    def evaluate(self, geometry, requirements=None):
        requirements=requirements if isinstance(requirements,dict) else {}
        base={"version":self.VERSION,"status":"pending_requirements","architecture_authoritative":True,
              "metrics":{},"violations":[],"unresolved_evidence":[],
              "source":"architectural_spatial_quality_gate_v1"}
        if requirements.get("enforce") is not True:
            base["unresolved_evidence"].append("explicit_spatial_quality_enforcement")
            return base
        spaces=[s for s in geometry.get("spaces",[]) if isinstance(s,dict)]
        names={s.get("name") for s in spaces if s.get("name")}
        minimum_dimensions=requirements.get("minimum_usable_dimensions",{})
        violations=[]
        for space in spaces:
            footprint=space.get("footprint",{})
            width=footprint.get("width") if isinstance(footprint,dict) else None
            depth=footprint.get("depth") if isinstance(footprint,dict) else None
            minimum=minimum_dimensions.get(space.get("name"),{}) if isinstance(minimum_dimensions,dict) else {}
            if minimum and ((isinstance(minimum.get("width"),(int,float)) and (not isinstance(width,(int,float)) or width<minimum["width"]))
                            or (isinstance(minimum.get("depth"),(int,float)) and (not isinstance(depth,(int,float)) or depth<minimum["depth"]))):
                violations.append({"type":"minimum_usable_dimension","space":space.get("name")})
        edges=set()
        for opening in geometry.get("openings",[]):
            if not isinstance(opening,dict) or opening.get("geometry_status")!="resolved":continue
            a,b=opening.get("connects_from"),opening.get("connects_to")
            if a and b:edges.add(frozenset((a,b)))
        for relation in geometry.get("circulation",geometry.get("connections",[])) or []:
            if isinstance(relation,dict):
                a=relation.get("from") or relation.get("source");b=relation.get("to") or relation.get("target")
                status=relation.get("geometry_status",relation.get("status"))
                physical_ok = relation.get("door_required") is not True or relation.get("physical_connection_status") == "resolved"
                if a and b and physical_ok and isinstance(status,str) and (status.startswith("resolved") or status=="authoritative"):
                    edges.add(frozenset((a,b)))
        required=requirements.get("required_connections",[])
        for pair in required if isinstance(required,list) else []:
            if isinstance(pair,(list,tuple)) and len(pair)==2 and frozenset(pair) not in edges:
                violations.append({"type":"required_connection_missing","spaces":list(pair)})
        entrance=requirements.get("entrance_space")
        if entrance and entrance in names and not any(entrance in edge for edge in edges):
            violations.append({"type":"entrance_without_internal_connection","space":entrance})
        graph={name:set() for name in names}
        for edge in edges:
            values=list(edge)
            if len(values)==2 and values[0] in graph and values[1] in graph:
                graph[values[0]].add(values[1]);graph[values[1]].add(values[0])
        exempt=set(requirements.get("isolation_exempt_spaces",[]))
        isolated=sorted(name for name in names if not graph[name] and name not in exempt)
        for name in isolated:violations.append({"type":"isolated_space","space":name})
        privacy=requirements.get("privacy_forbidden_direct_connections",[])
        for pair in privacy if isinstance(privacy,list) else []:
            if isinstance(pair,(list,tuple)) and len(pair)==2 and frozenset(pair) in edges:
                violations.append({"type":"privacy_connection_violation","spaces":list(pair)})
        corridor_limits=requirements.get("maximum_dead_end_connections")
        dead_ends=[name for name,neighbors in graph.items() if "corridor" in str(name).lower() and len(neighbors)<=1]
        if isinstance(corridor_limits,int) and len(dead_ends)>corridor_limits:
            violations.append({"type":"excessive_dead_end_circulation","spaces":dead_ends})
        requirements_contract=geometry.get("project_requirements",{})
        window_requirements=requirements_contract.get("window_requirements",[]) if isinstance(requirements_contract,dict) else []
        resolved_windows=[item for item in geometry.get("openings",[]) if isinstance(item,dict) and item.get("type")=="window" and item.get("geometry_status")=="resolved"]
        walls={item.get("wall_id"):item for item in geometry.get("physical_walls",[]) if isinstance(item,dict)}
        for window in resolved_windows:
            if walls.get(window.get("host_wall_id"),{}).get("is_exterior") is not True:
                violations.append({"type":"window_on_non_exterior_wall","window":window.get("id")})
        for requirement in window_requirements if isinstance(window_requirements,list) else []:
            if not isinstance(requirement,dict) or requirement.get("required") is not True:continue
            if not any(item.get("served_space_id")==requirement.get("space_id") for item in resolved_windows):
                violations.append({"type":"required_exterior_window_unresolved","space":requirement.get("space_id")})
        parking_pedestrian_requirements=requirements_contract.get("parking_pedestrian_requirements",[]) if isinstance(requirements_contract,dict) else []
        parking_pedestrian=geometry.get("site_geometry",{}).get("parking_pedestrian_connection",{})
        if parking_pedestrian_requirements and parking_pedestrian.get("parking_to_building_status")!="resolved":
            violations.append({"type":"parking_to_building_pedestrian_connection_unresolved"})
        base["metrics"]={"space_count":len(spaces),"resolved_connection_count":len(edges),
                         "isolated_space_count":len(isolated),"dead_end_corridor_count":len(dead_ends),
                         "entrance_connectivity":"resolved" if entrance and any(entrance in e for e in edges) else "unresolved",
                         "parking_to_building_access":"resolved" if parking_pedestrian.get("parking_to_building_status")=="resolved" else "unresolved",
                         "stair_core_accessibility":"resolved" if any(v.get("type")=="stair_geometry" and v.get("geometry_status")=="resolved" for v in geometry.get("vertical_geometry",[])) else "unresolved"}
        base["metrics"]["resolved_exterior_window_count"]=len(resolved_windows)
        base["violations"]=violations
        base["status"]="passed" if not violations else "rejected"
        base["architecture_authoritative"]=not violations
        return base
