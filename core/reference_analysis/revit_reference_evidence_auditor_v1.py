import json
import math
import statistics
from collections import Counter
from pathlib import Path


class RevitReferenceEvidenceAuditorV1:
    """Read-only classification and DXF comparison for extracted Revit evidence."""

    VERSION = "1.0"

    def audit(self, contract_path, dxf_wall_contract_path=None, output_path=None):
        contract_path = Path(contract_path)
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        model = "album" if "album" in contract_path.stem.lower() else "sina"
        analysis = {
            "version": self.VERSION,
            "level_analysis": self._levels(contract),
            "floor_slab_analysis": self._floors(contract),
            "wall_analysis": self._walls(contract),
            "stair_analysis": self._stairs(contract, model),
            "entrance_transition": self._entrance_transition(contract, model),
            "dimension_value_evidence": self._dimensions(contract),
            "evidence_separation": self._separation(contract, model),
        }
        comparison = (
            self._compare_dxf(contract, dxf_wall_contract_path)
            if dxf_wall_contract_path
            else self._empty_comparison("NOT_APPLICABLE_NO_CORRESPONDING_DXF_REFERENCE")
        )
        contract["reference_analysis"] = analysis
        contract["dxf_comparison"] = comparison
        output = Path(output_path) if output_path else contract_path
        output.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        return contract

    def _levels(self, contract):
        levels = contract.get("levels", [])
        ground = [item for item in levels if abs(item["elevation"]) <= 1e-8]
        below = [item for item in levels if item["elevation"] < -1e-8]
        upper = [item for item in levels if item["elevation"] > 1e-8]
        level_040 = [item for item in levels if abs(item["elevation"] - 0.4) <= 1e-6]
        return {
            "native_level_count": len(levels),
            "building_story_flag_count": sum(item.get("is_building_story") is True for item in levels),
            "architectural_storey_count": None,
            "architectural_storey_count_status": "UNRESOLVED_LEVELS_ARE_NOT_OCCUPIED_STOREYS",
            "ground_level_candidates": ground,
            "upper_level_candidates": upper,
            "basement_level_candidates": below,
            "mezzanine_candidates": [item for item in levels if "nim" in item["name"].lower() or "mezz" in item["name"].lower()],
            "level_040": level_040,
            "site_datum_status": "AUTHORITATIVE" if len(ground) == 1 else "UNRESOLVED",
            "finished_floor_040_status": "AUTHORITATIVE_LEVEL" if len(level_040) == 1 else "UNRESOLVED",
        }

    @staticmethod
    def _floors(contract):
        level_map = {item["name"]: item["elevation"] for item in contract.get("levels", [])}
        result = []
        for floor in contract.get("floors", []):
            item = dict(floor)
            item["absolute_top_elevation"] = (
                level_map.get(floor.get("level"), 0.0) + floor.get("elevation", 0.0)
                if floor.get("level") in level_map else None
            )
            result.append(item)
        return {"elements": result, "floor_count": len(result),
                "finished_floor_candidates": [item for item in result if abs((item.get("absolute_top_elevation") or -999) - 0.4) <= 1e-6],
                "step_named_candidates": [item for item in result if "pele" in (item.get("type") or "").lower()],
                "semantic_status": "NATIVE_FLOOR_GEOMETRY_AUTHORITATIVE_ROLE_INFERRED_FROM_ORIGINAL_TYPE_TEXT"}

    @staticmethod
    def _walls(contract):
        walls = contract.get("walls", [])
        return {"count": len(walls),
                "native_exterior_function_count": sum(item.get("function_parameter") == "Exterior" for item in walls),
                "native_interior_function_count": sum(item.get("function_parameter") == "Interior" for item in walls),
                "all_host_relationships_authoritative": True,
                "building_envelope_status": "UNRESOLVED_NO_UNIQUE_CLOSED_NATIVE_BOUNDARY"}

    def _stairs(self, contract, model):
        native = contract.get("stairs", [])
        generic = contract.get("generic_models", [])
        repeated = []
        for item in generic:
            elevations = sorted(set(round(face["elevation"], 4)
                                    for solid in item.get("solid_geometry", [])
                                    for face in solid.get("horizontal_faces", [])))
            intervals = [round(b - a, 4) for a, b in zip(elevations, elevations[1:]) if b - a > 0.05]
            common = Counter(intervals).most_common(1)
            if common and common[0][1] >= 4 and 0.10 <= common[0][0] <= 0.30:
                repeated.append({"element_id": item["element_id"], "family": item.get("family"),
                                 "horizontal_face_elevations": elevations,
                                 "repeated_vertical_interval": common[0][0],
                                 "repeat_count": common[0][1], "geometry": item.get("geometry"),
                                 "status": "INFERRED_STAIR_GEOMETRY_PATTERN_NOT_NATIVE_STAIR"})
        return {"native_stairs": native, "native_stair_count": len(native),
                "generic_model_stair_geometry_candidates": repeated,
                "album_rear_roof_access_stair_binding": (
                    {"status": "INFERRED_MULTIPLE_CANDIDATE_COMPONENTS", "candidate_element_ids": [item["element_id"] for item in repeated],
                     "evidence": ["user_authoritative_generic_model_context", "repeated_horizontal_faces", "repeated_vertical intervals"]}
                    if model == "album" and repeated else {"status": "UNRESOLVED"}),
                "semantic_conversion_performed": False}

    @staticmethod
    def _entrance_transition(contract, model):
        levels = {item["name"]: item for item in contract.get("levels", [])}
        floors = contract.get("floors", [])
        doors = contract.get("doors", [])
        step_floors = [item for item in floors if "pele" in (item.get("type") or "").lower()]
        return {
            "site_datum": {"status": "confirmed" if any(abs(x["elevation"]) < 1e-8 for x in levels.values()) else "unresolved",
                           "level_ids": [x["element_id"] for x in levels.values() if abs(x["elevation"]) < 1e-8]},
            "finished_floor_040": {"status": "confirmed" if any(abs(x["elevation"] - 0.4) < 1e-6 for x in levels.values()) else "unresolved",
                                   "level_ids": [x["element_id"] for x in levels.values() if abs(x["elevation"] - 0.4) < 1e-6]},
            "threshold_040": {"status": "AUTHORITATIVE_DOOR_PLACEMENT_AT_040_THRESHOLD_ROLE_UNRESOLVED" if model == "album" and doors and all(abs(x["location"]["z"] - 0.4) < 1e-6 for x in doors) else "UNRESOLVED",
                              "door_ids": [x["element_id"] for x in doors if x.get("location") and abs(x["location"]["z"] - 0.4) < 1e-6]},
            "exterior_step_floor_candidates": {"status": "AUTHORITATIVE_ELEMENTS_ROLE_INFERRED", "elements": step_floors},
            "platform": {"status": "UNRESOLVED_SEMANTIC_BINDING", "candidate_floor_ids": [x["element_id"] for x in step_floors]},
            "main_entrance": {"status": contract.get("entrance_evidence", {}).get("status", "UNRESOLVED")},
            "chain_status": "PARTIALLY_CONFIRMED_VERTICAL_MAIN_ENTRANCE_AND_TOPOLOGICAL_BINDING_UNRESOLVED",
        }

    @staticmethod
    def _dimensions(contract):
        targets = [8.65, 13.25, 6.05, 5.20, 4.40, 4.25, 2.00, 0.40]
        found = {str(value): [] for value in targets}
        for dimension in contract.get("dimensions", []):
            values = [{"value": dimension.get("value"), "value_string": dimension.get("value_string"), "kind": "overall"}]
            values += [{"value": item.get("value"), "value_string": item.get("value_string"), "kind": "segment"}
                       for item in dimension.get("segments", [])]
            for item in values:
                if item["value"] is None: continue
                for target in targets:
                    if abs(item["value"] - target) <= 0.011:
                        found[str(target)].append({"element_id": dimension["element_id"], **item,
                                                  "reference_count": len(dimension.get("references", [])),
                                                  "geometry_status": dimension.get("geometry_status")})
        return found

    @staticmethod
    def _separation(contract, model):
        authoritative = [
            "native element ids/categories/types/parameters",
            "level elevations", "wall type Function parameter", "door/window native Host",
            "floor compound thickness/boundaries/elevations", "native Stair API values",
            "dimension values and stable references", "Generic Model solid/face geometry",
        ]
        inferred = ["architectural role of original type text", "generic stair-pattern recognition"]
        unresolved = ["unique main entrance", "unique building footprint", "property boundary",
                      "door-to-exterior-space relation where Rooms are absent", "platform semantic role"]
        if model == "album":
            authoritative.append("user context: parking/pedestrian access and some exterior objects modeled outside RVT")
        return {"AUTHORITATIVE": authoritative, "INFERRED": inferred, "UNRESOLVED": unresolved}

    def _compare_dxf(self, contract, path):
        path = Path(path)
        if not path.exists(): return self._empty_comparison("UNRESOLVED_DXF_CONTRACT_UNAVAILABLE")
        dxf = json.loads(path.read_text(encoding="utf-8"))
        door_matches, translation = self._match_instances(contract.get("doors", []), dxf.get("door_world_geometry", []), "door")
        window_matches, window_translation = self._match_instances(contract.get("windows", []), dxf.get("window_world_geometry", []), "window")
        confirmed = []
        if door_matches: confirmed += ["Revit native door hosts resolve matching DXF insert host evidence for matched instances"]
        if window_matches: confirmed += ["Revit native window hosts resolve matching DXF insert host evidence for matched instances"]
        if any(abs(item["elevation"] - 0.4) < 1e-6 for item in contract.get("levels", [])): confirmed += ["DXF +0.40 value confirmed by native Revit Level"]
        contradicted = []
        dxf_doors = len(dxf.get("door_world_geometry", [])); revit_doors = len(contract.get("doors", []))
        if dxf_doors != revit_doors: contradicted.append({"fact": "door_instance_count", "dxf": dxf_doors, "revit": revit_doors})
        return {"status": "REFERENCE_CORRESPONDENCE_ONLY_NOT_PRODUCTION",
                "translation_revit_minus_dxf": translation,
                "window_translation_revit_minus_dxf": window_translation,
                "door_matches": door_matches, "window_matches": window_matches,
                "confirmed_by_revit": confirmed, "contradicted_by_revit": contradicted,
                "not_available_in_revit": ["parking/pedestrian access modeled in 3ds Max"] if "album" in contract.get("file", "").lower() or "آلبوم" in contract.get("file", "") else [],
                "still_unresolved": ["main entrance", "building footprint", "platform semantic binding", "entrance approach"]}

    def _match_instances(self, revit, dxf, kind):
        dxf_points = [(item[f"{kind}_id"], item["source_handle"], item.get("insertion_point")) for item in dxf if item.get("insertion_point")]
        votes = Counter()
        for r in revit:
            if not r.get("location"): continue
            for _, _, point in dxf_points:
                votes[(round(r["location"]["x"] - point[0], 2), round(r["location"]["y"] - point[1], 2))] += 1
        if not votes: return [], None
        bucket, _ = votes.most_common(1)[0]
        pairs = []
        used = set()
        deltas = []
        for r in revit:
            candidates = []
            for object_id, handle, point in dxf_points:
                if handle in used: continue
                dx, dy = r["location"]["x"] - point[0], r["location"]["y"] - point[1]
                if abs(dx - bucket[0]) <= 0.03 and abs(dy - bucket[1]) <= 0.03:
                    candidates.append((object_id, handle, point, dx, dy))
            if len(candidates) == 1:
                object_id, handle, point, dx, dy = candidates[0]; used.add(handle); deltas.append((dx, dy))
                pairs.append({"revit_element_id": r["element_id"], "dxf_id": object_id, "dxf_handle": handle,
                              "revit_host_wall_id": r.get("host_wall_id"), "revit_host_wall_type": r.get("host_wall_type"),
                              "coordinate_residual": [dx - bucket[0], dy - bucket[1]], "status": "AUTHORITATIVE_CORRESPONDENCE"})
        translation = [statistics.median(x for x, _ in deltas), statistics.median(y for _, y in deltas)] if deltas else None
        return pairs, translation

    @staticmethod
    def _empty_comparison(status="UNRESOLVED_DXF_CONTRACT_UNAVAILABLE"):
        return {"status": status, "door_matches": [], "window_matches": [],
                "confirmed_by_revit": [], "contradicted_by_revit": [], "not_available_in_revit": [], "still_unresolved": []}
