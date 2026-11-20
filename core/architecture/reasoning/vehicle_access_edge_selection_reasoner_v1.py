"""Evidence-driven selection among authoritative vehicle-access road edges."""

from __future__ import annotations


class VehicleAccessEdgeSelectionReasonerV1:
    VERSION = "1.0"
    EPS = 1e-9

    def resolve(self, access_edges, parking_level_z, allowable_slopes,
                level_connection_tolerance=1e-6):
        result={"contract":"VehicleAccessEdgeSelectionContractV1","version":self.VERSION,
                "status":"pending","evaluated_edges":[],"selected_edge":None,
                "selection_status":"pending","unresolved_evidence":[]}
        if parking_level_z is None or not allowable_slopes:
            result["unresolved_evidence"]=["parking_level_z_or_allowable_slopes"]
            return result
        for edge in access_edges:
            missing=[key for key in ("access_edge_id","geometry","road_width","road_elevation",
                                      "source","evidence_status") if edge.get(key) is None]
            if missing:
                result["evaluated_edges"].append({"access_edge_id":edge.get("access_edge_id"),
                    "hard_valid":False,"failure_reasons":["missing_"+key for key in missing]})
                continue
            dz=float(parking_level_z)-float(edge["road_elevation"])
            direct=abs(dz)<=float(level_connection_tolerance)
            runs={f"{float(slope):.6f}":0.0 if direct else abs(dz)/float(slope)
                  for slope in allowable_slopes}
            failures=list(edge.get("hard_failure_reasons",[]))
            available=edge.get("available_geometric_run")
            if not direct and available is not None and min(runs.values())>float(available)+self.EPS:
                failures.append("required_ramp_run_exceeds_available_geometry")
            evaluated={"access_edge_id":edge["access_edge_id"],"geometry":edge["geometry"],
                "road_width":float(edge["road_width"]),"road_elevation":float(edge["road_elevation"]),
                "parking_level_z":float(parking_level_z),"delta_z":dz,
                "vehicle_opening_feasibility":edge.get("vehicle_opening_feasibility","resolved"),
                "vehicle_access_type":"direct_at_grade" if direct else "ramp",
                "ramp_required":not direct,"required_ramp_runs":runs,
                "available_geometric_run":available,
                "parking_capacity":int(edge.get("parking_capacity",0)),
                "central_field_fragmentation":float(edge.get("central_field_fragmentation",0.0)),
                "pedestrian_core_status":edge.get("pedestrian_core_status","unresolved"),
                "ramp_geometry":None if direct else {"status":"required_not_generated_by_edge_selector"},
                "hard_valid":not failures,"failure_reasons":sorted(set(failures)),
                "source":edge["source"],"evidence_status":edge["evidence_status"]}
            result["evaluated_edges"].append(evaluated)
        valid=[edge for edge in result["evaluated_edges"] if edge.get("hard_valid")]
        if not valid:
            result.update({"status":"not_feasible","selection_status":"unresolved_no_hard_valid_edge"})
            return result
        def rank(edge):
            shortest=min(edge["required_ramp_runs"].values()) if edge["ramp_required"] else 0.0
            return (int(not edge["ramp_required"]),-abs(edge["delta_z"]),-shortest,
                    edge["parking_capacity"],-edge["central_field_fragmentation"])
        best=max(rank(edge) for edge in valid); winners=[edge for edge in valid if rank(edge)==best]
        if len(winners)!=1:
            result.update({"status":"pending_tie","selection_status":"pending_tie",
                           "unresolved_evidence":["decisive_access_edge_evidence"]})
            return result
        result.update({"status":"resolved","selection_status":"resolved","selected_edge":winners[0]})
        return result
