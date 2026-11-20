"""Compose pilot-floor topology from an explicit program manifest."""
from copy import deepcopy
from math import sqrt

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from core.architecture.reasoning.pilot_parking_program_tradeoff_topology_search_v1 import PilotParkingProgramTradeoffTopologySearchV1
from core.architecture.reasoning.program_conflict_analysis_v1 import ProgramConflictAnalysisV1
from core.architecture.reasoning.program_space_requirement_v1 import ProgramSpaceRequirementV1


class ProgramDrivenPilotSpaceCompositionV1:
    EPS = 1e-6

    def compose_manifest(self, requirements):
        return ProgramSpaceRequirementV1.manifest(requirements)

    def apply_adjustment(self, manifest, space_type, changes):
        updated = deepcopy(manifest)
        target = next(r for r in updated["requirements"] if r["space_type"] == space_type)
        target.update(changes)
        return ProgramSpaceRequirementV1.manifest(updated["requirements"])

    def resolve(self, site, project_requirements, baseline_scenario_a, program_requirements, program_id):
        before_site, before_a = deepcopy(site), deepcopy(baseline_scenario_a)
        manifest = self.compose_manifest(program_requirements)
        topology = PilotParkingProgramTradeoffTopologySearchV1().resolve(site, project_requirements, baseline_scenario_a)
        # K identifiers are provenance only. Program logic consumes geometry inventory, not family intent.
        inventory = [c for c in topology["candidates"] if c["family"] == "PILOT-K01" and c["hard_geometry_status"] == "hard_valid"]
        parcel_area = Polygon(topology["local_parcel_polygon"]).area
        candidates = [self._compose_candidate(c, manifest, program_id, parcel_area) for c in inventory]
        ranked = sorted(candidates, key=self._rank_key, reverse=True)
        review = self._review_set(ranked, 3)
        assert site == before_site and baseline_scenario_a == before_a
        return {
            "contract": "ProgramDrivenPilotSpaceCompositionV1", "program_id": program_id,
            "site": "REAL Parcel 2", "site_source": site.get("source"), "source_parcel": site["parcel"],
            "source_frontage": site["frontage"], "source_road_width": site.get("road_width"),
            "local_parcel_polygon": topology["local_parcel_polygon"],
            "program_manifest": manifest, "topology_derivation": "program_requirements_over_general_geometry_inventory",
            "source_topology_families_are_program_logic": False, "candidate_count": len(candidates),
            "program_compliant_candidate_count": sum(not c["hard_requirement_failures"] for c in candidates),
            "candidates": candidates, "human_review_candidates": review,
            "human_review_candidate_ids": [c["candidate_id"] for c in review],
            "final_selection_performed": False, "final_scenario_b_candidate": None,
            "baseline_scenario_a": before_a, "baseline_geometry_preserved": True,
            "program_changed": False, "basement_deleted": False, "basement_removal_approved": False,
            "structure_executed": False, "bim_executed": False, "ifc_executed": False,
        }

    def _compose_candidate(self, topology, manifest, program_id, parcel_area):
        c = deepcopy(topology)
        residual = unary_union([Polygon(p) for p in c["residual_space_program"]["unallocated_residual_polygons"]])
        spaces = []
        reqs = {r["space_type"]: r for r in manifest["requirements"]}
        parking_count = c["parking_count"]
        spaces.append(self._ledger("parking", parking_count, sum(Polygon(s["polygon"]).area for s in c["parking_stalls"]), c["parking_stalls"]))
        commercial_polys = [Polygon(c["commercial_field"])]
        support_types = ("residential_storage", "mechanical_room", "electrical_room", "common_wc",
                         "caretaker_unit", "guard_room", "utility_room", "refuse_room", "bicycle_storage", "stroller_storage")
        generated_support = []
        for space_type in support_types:
            req = reqs.get(space_type)
            if not req: continue
            wanted = req["required_count"] if req["required"] else req["count"] if req["preferred"] else 0
            for index in range(wanted):
                shape, allocated_area = self._allocate(residual, req)
                if shape is None: break
                residual = residual.difference(shape)
                generated_support.append({"space_id": f"{space_type}_{index+1:02d}", "space_type": space_type,
                                          "polygon": self._poly(shape), "area": allocated_area,
                                          "requirement_source": req["requirement_source"],
                                          "regulatory_status": req["regulatory_status"]})
            matched = [s for s in generated_support if s["space_type"] == space_type]
            spaces.append(self._ledger(space_type, len(matched), sum(s["area"] for s in matched), matched))
        commercial_req = reqs.get("commercial")
        if commercial_req and commercial_req.get("area_goal") == "maximize":
            touching = [p for p in self._parts(residual) if p.buffer(self.EPS).intersects(unary_union(commercial_polys))]
            commercial_polys.extend(touching)
            if touching: residual = residual.difference(unary_union(touching))
        commercial_area = sum(p.area for p in commercial_polys)
        spaces.append(self._ledger("commercial", 1 if commercial_area > self.EPS else 0, commercial_area,
                                   [{"space_id":"commercial_01", "space_type":"commercial", "polygon":self._poly(p), "area":p.area} for p in commercial_polys]))
        for core_type, polygon in (("stair", c["core"]["stair"]), ("elevator", c["core"]["elevator"]), ("common_lobby", c["core"]["lobby"])):
            spaces.append(self._ledger(core_type, 1, Polygon(polygon).area,
                                       [{"space_id":f"{core_type}_01", "space_type":core_type, "polygon":polygon, "area":Polygon(polygon).area}]))
        analysis = ProgramConflictAnalysisV1().analyze(manifest, spaces)
        metrics = self._metrics(c, manifest, spaces, generated_support, residual, commercial_area, parcel_area)
        metrics["program_compliance_status"] = analysis["program_status"]
        return {
            "contract": "ProgramDrivenPilotCandidateV1", "candidate_id": f'{program_id}-{c["candidate_id"].split("-",2)[2]}',
            "program_id": program_id, "source_topology_candidate_id": c["candidate_id"],
            "geometry": c, "generated_program_spaces": generated_support,
            "commercial_polygons": [self._poly(p) for p in commercial_polys],
            "unallocated_residual_polygons": [self._poly(p) for p in self._parts(residual)],
            "program_space_ledger": spaces, "program_conflict_analysis": analysis, **analysis, **metrics,
        }

    def _allocate(self, geometry, req):
        preferred = req["preferred_area_per_unit"] or req["preferred_area"] or req["maximum_area_per_unit"] or req["maximum_area"]
        if preferred is None:
            return None, 0
        minimum = req["minimum_area"] or (preferred * .5 if req["shrinkable"] else preferred)
        areas = [preferred]
        if req["shrinkable"]: areas += [preferred*.75, max(minimum, preferred*.5)]
        for area in dict.fromkeys(round(a,6) for a in areas if a >= minimum-self.EPS):
            width = req["minimum_width"] or sqrt(area)
            depth = area/width
            for region in sorted(self._parts(geometry), key=lambda p:p.area, reverse=True):
                x0,y0,x1,y1=region.bounds
                for w,d in ((width,depth),(depth,width)):
                    for x in (x0,x1-w):
                        for y in (y0,y1-d):
                            candidate=box(x,y,x+w,y+d)
                            if region.buffer(self.EPS).covers(candidate): return candidate,candidate.area
        return None,0

    def _metrics(self, c, manifest, ledgers, support, residual, commercial_area, parcel_area):
        ld={x["space_type"]:x for x in ledgers}; req={r["space_type"]:r for r in manifest["requirements"]}
        count=lambda t:ld.get(t,{}).get("generated_count",0)
        area=lambda t:ld.get(t,{}).get("generated_area",0)
        service_types=("mechanical_room","electrical_room","utility_room","refuse_room")
        common_types=("stair","elevator","common_lobby","common_wc")
        return {
            "parking_required_count": req.get("parking",{}).get("required_count",0), "parking_generated_count":count("parking"),
            "commercial_area":commercial_area, "commercial_frontage":c["metrics"]["commercial_frontage"],
            "storage_required_count":req.get("residential_storage",{}).get("required_count",0), "storage_generated_count":count("residential_storage"),
            "storage_total_area":area("residential_storage"), "mechanical_room_generated":bool(count("mechanical_room")),
            "electrical_room_generated":bool(count("electrical_room")), "common_wc_generated":bool(count("common_wc")),
            "caretaker_unit_generated":bool(count("caretaker_unit")), "service_area":sum(area(t) for t in service_types),
            "common_area":sum(area(t) for t in common_types), "circulation_area":c["metrics"]["total_circulation_area"],
            "residual_unallocated_area":sum(p.area for p in self._parts(residual)),
            "net_programmed_area":sum(x["generated_area"] for x in ledgers),
            "whole_plan_space_utilization_ratio":sum(x["generated_area"] for x in ledgers)/parcel_area,
            "program_compliance_status": None,
        }

    @staticmethod
    def _ledger(space_type,count,area,instances): return {"space_type":space_type,"generated_count":count,"generated_area":area,"instances":instances}
    @staticmethod
    def _parts(g):
        if g.is_empty:return []
        return [g] if g.geom_type=="Polygon" else [p for p in getattr(g,"geoms",[]) if p.geom_type=="Polygon"]
    @staticmethod
    def _poly(p): return [[float(x),float(y)] for x,y in list(p.exterior.coords)[:-1]]
    @staticmethod
    def _rank_key(c):
        return (-len(c["hard_requirement_failures"]), -len(c["soft_requirement_failures"]),
                c["parking_generated_count"] == c["parking_required_count"],
                c["whole_plan_space_utilization_ratio"], c["commercial_area"], c["parking_generated_count"])
    @staticmethod
    def _review_set(ranked,count):
        out=[]; modes=set()
        for c in ranked:
            mode=c["geometry"]["entrance_mode"]
            if mode in modes and len(out)<2: continue
            out.append(c);modes.add(mode)
            if len(out)==count:break
        return out
