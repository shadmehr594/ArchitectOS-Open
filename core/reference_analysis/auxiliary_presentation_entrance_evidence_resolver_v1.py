"""Fail-closed pedestrian-yard-entrance evidence from presentation scenes."""

import json
import math
from pathlib import Path


class AuxiliaryPresentationEntranceEvidenceResolverV1:
    VERSION = "1.0"
    EVIDENCE_STATUS = "AUXILIARY_PRESENTATION_EVIDENCE"

    def resolve(self, scene, revit_contract, source_3ds=None):
        scene = self._load(scene)
        revit = self._load(revit_contract)
        source_3ds_evidence = self._load(source_3ds) if source_3ds and str(source_3ds).lower().endswith(".json") else None
        gates = [self._candidate(item) for item in scene.get("objects", []) if self._discover_gate(item)]
        gates = [item for item in gates if item is not None]
        transform = self._coordinate_correspondence(scene, revit)
        if transform["canonical_dxf_transform_status"] == "PROVEN":
            dx, dy = transform["revit_minus_dxf_translation"]
            for item in gates:
                item["canonical_dxf_center_candidate"] = [item["center"][0] - dx, item["center"][1] - dy, item["center"][2]]
        pedestrian = self._pedestrian_selection(gates)
        selected = pedestrian.get("selected_candidate")
        canonical = None
        if selected and transform["canonical_dxf_transform_status"] == "PROVEN":
            dx, dy = transform["revit_minus_dxf_translation"]
            center = selected["center"]
            canonical = [center[0] - dx, center[1] - dy, center[2]]
        approach = self._approach(gates, selected, transform, revit)
        result = {
            "contract": "dxf_max_auxiliary_pedestrian_entrance_evidence_v1",
            "version": self.VERSION,
            "source": scene.get("source"),
            "source_file": scene.get("source_file"),
            "source_3ds": source_3ds_evidence.get("source_file") if source_3ds_evidence else (str(source_3ds) if source_3ds else None),
            "source_3ds_correspondence": self._source_3ds_correspondence(gates, source_3ds_evidence),
            "scope": "REFERENCE_ANALYSIS_ONLY",
            "evidence_status": self.EVIDENCE_STATUS,
            "candidate_objects": gates,
            "pedestrian_entrance": pedestrian,
            "coordinate_correspondence": transform,
            "canonical_dxf_entrance_point": canonical,
            "approach_evidence": approach,
            "door_correspondence": None,
            "main_entrance_status": "UNRESOLVED",
            "publication_to_production_allowed": False,
            "unresolved_items": self._unresolved(gates, pedestrian, transform, approach),
        }
        if selected and approach["unique_door_status"] == "RESOLVED":
            result["door_correspondence"] = approach["selected_door"]
            result["main_entrance_status"] = "RESOLVED_BY_AUXILIARY_EVIDENCE"
        return result

    def _source_3ds_correspondence(self, gates, evidence):
        if not evidence:
            return {"status": "UNRESOLVED_NO_3DS_METADATA_CONTRACT", "matching_node_names": []}
        node_names = {item.get("name") for item in evidence.get("keyframe_nodes", [])}
        matches = [item["name"] for item in gates if item["name"] in node_names]
        return {
            "status": "CONFIRMED_BY_3DS_KEYFRAME_NODE_NAMES" if len(matches) == len(gates) and matches else "PARTIAL_OR_UNRESOLVED",
            "matching_node_names": matches,
            "geometry_status": "FBX_ONLY_3DS_KEYFRAME_NODES_HAVE_NO_PARSED_MESH_BINDING",
            "evidence_status": self.EVIDENCE_STATUS,
        }

    def resolve_files(self, scene_path, revit_path, output_path, source_3ds=None):
        result = self.resolve(scene_path, revit_path, source_3ds)
        Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    @staticmethod
    def _load(value):
        if isinstance(value, (str, Path)):
            return json.loads(Path(value).read_text(encoding="utf-8"))
        return value

    @staticmethod
    def _discover_gate(obj):
        name = (obj.get("name") or "").casefold()
        # Names are candidate-discovery evidence only; geometry validation follows.
        return any(token in name for token in ("gate", "pedestrian", "entrance", "ورود", "درب"))

    def _candidate(self, obj):
        bbox = obj.get("world_bbox")
        mesh = obj.get("mesh_statistics")
        if obj.get("type") != "MESH" or not bbox or not mesh or mesh.get("polygon_count", 0) <= 0:
            return None
        low, high = bbox["min"], bbox["max"]
        extents = [high[index] - low[index] for index in range(3)]
        if min(extents[:2]) <= 0 or extents[2] <= 0:
            return None
        horizontal_axis = 0 if extents[0] >= extents[1] else 1
        normal_axis = 1 - horizontal_axis
        center = [(low[index] + high[index]) / 2 for index in range(3)]
        return {
            "object_id": obj["object_id"],
            "name": obj.get("name"),
            "world_bbox": bbox,
            "world_matrix": obj.get("world_matrix"),
            "location": obj.get("location"),
            "rotation_euler": obj.get("rotation_euler"),
            "scale": obj.get("scale"),
            "center": center,
            "horizontal_span": extents[horizontal_axis],
            "depth": extents[normal_axis],
            "height": extents[2],
            "plane_axis": "X" if horizontal_axis == 0 else "Y",
            "normal_axis": "Y" if normal_axis == 1 else "X",
            "projected_envelope_span": (
                [[low[0], center[1], low[2]], [high[0], center[1], low[2]]]
                if horizontal_axis == 0 else [[center[0], low[1], low[2]], [center[0], high[1], low[2]]]
            ),
            "passage_segment": None,
            "passage_status": "UNRESOLVED_OBJECT_BBOX_IS_NOT_OPENING_PROOF",
            "geometry_validation": "VALID_NONEMPTY_WORLD_SPACE_MESH",
            "semantic_role": "GATE_CANDIDATE_NAME_NOT_DECISIVE",
            "evidence_status": self.EVIDENCE_STATUS,
        }

    def _pedestrian_selection(self, gates):
        explicit = [item for item in gates if any(token in item["name"].casefold() for token in ("pedestrian", "yard entrance", "نفر", "ورودی نفر"))]
        if len(gates) == 1 and len(explicit) == 1:
            return {"status": "RESOLVED_UNIQUE_GEOMETRIC_GATE_CANDIDATE", "selected_candidate_id": gates[0]["object_id"], "selected_candidate": gates[0]}
        return {
            "status": "UNRESOLVED_MULTIPLE_GATE_CANDIDATES" if gates else "UNRESOLVED_NO_GATE_CANDIDATE",
            "selected_candidate_id": None,
            "selected_candidate": None,
            "reason": "Object name and relative width do not prove pedestrian semantic role",
        }

    def _coordinate_correspondence(self, scene, revit):
        mesh_points = [obj.get("location") for obj in scene.get("objects", []) if obj.get("type") == "MESH" and obj.get("location")]
        anchors = []
        for door in revit.get("doors", []):
            point = door.get("location")
            if not point:
                continue
            matches = [candidate for candidate in mesh_points if math.hypot(candidate[0] - point["x"], candidate[1] - point["y"]) <= 0.01]
            if matches:
                anchors.append({"revit_element_id": door["element_id"], "revit_xy": [point["x"], point["y"]], "scene_xy": matches[0][:2], "residual": [matches[0][0] - point["x"], matches[0][1] - point["y"]]})
        proven = len(anchors) >= 3 and max((math.hypot(*item["residual"]) for item in anchors), default=999) <= 0.01
        translation = revit.get("dxf_comparison", {}).get("translation_revit_minus_dxf")
        return {
            "max_fbx_to_revit_status": "PROVEN_IDENTITY_XY" if proven else "UNRESOLVED",
            "anchor_count": len(anchors),
            "anchors": anchors,
            "canonical_dxf_transform_status": "PROVEN" if proven and translation else "UNRESOLVED",
            "revit_minus_dxf_translation": translation,
            "evidence_status": self.EVIDENCE_STATUS,
        }

    def _approach(self, gates, selected, transform, revit):
        result = {"status": "UNRESOLVED", "direction": None, "unique_door_status": "UNRESOLVED", "selected_door": None, "evidence_status": self.EVIDENCE_STATUS}
        if not selected or transform["max_fbx_to_revit_status"] != "PROVEN_IDENTITY_XY":
            return result
        result["axis"] = [0.0, 1.0] if selected["normal_axis"] == "Y" else [1.0, 0.0]
        result["status"] = "AXIS_ONLY_SIGN_UNRESOLVED_NO_PATH_GEOMETRY"
        return result

    @staticmethod
    def _unresolved(gates, pedestrian, transform, approach):
        items = []
        if pedestrian["selected_candidate_id"] is None: items.append("unique pedestrian gate")
        if any(item["passage_status"].startswith("UNRESOLVED") for item in gates): items.append("physical passage/opening segment")
        if transform["canonical_dxf_transform_status"] != "PROVEN": items.append("Max/Revit/DXF coordinate correspondence")
        if approach["status"] != "RESOLVED": items.append("signed pedestrian approach direction")
        items.extend(["unique approach-to-building-door association", "main entrance"])
        return items
