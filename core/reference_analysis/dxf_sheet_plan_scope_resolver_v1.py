import collections
import math
import re


class DXFSheetPlanScopeResolverV1:
    """Cluster titled DXF views without altering or generating design geometry."""

    VERSION = "1.0"
    TITLE_PATTERN = re.compile(r"\b(FLOOR\s+PLAN|SITE\s+PLAN|ELEVATION|SECTION)\b", re.I)
    SCALE_PATTERN = re.compile(r"\b1\s*:\s*(\d+(?:\.\d+)?)\b")
    LEVEL_PATTERN = re.compile(r"(?<!\d)[+-]?\d+(?:\.\d+)?\s*m?\b", re.I)

    def resolve(self, file_path, metadata=None):
        import ezdxf
        from ezdxf import bbox

        metadata = metadata if isinstance(metadata, dict) else {}
        document = ezdxf.readfile(str(file_path))
        modelspace = document.modelspace()
        cache = bbox.Cache()
        records = [self._record(entity, bbox, cache) for entity in modelspace]
        records = [record for record in records if record is not None]
        titles = [record for record in records if self._view_type(record.get("text"))]

        views = self._clusters(records, titles)
        plan_views = [view for view in views if view["view_type"] in {"architectural_plan", "site_plan"}]
        primary_candidates = [
            view for view in plan_views
            if "PRESENTATION" not in (view.get("title_text") or "").upper()
        ]
        selected = primary_candidates[0] if len(primary_candidates) == 1 else None
        status = "resolved" if selected else "plan_scope_pending"
        reason = (
            "unique_non_presentation_titled_plan_view"
            if selected
            else "multiple_equivalent_plan_views_without_unique_primary_evidence"
            if len(primary_candidates) > 1
            else "unique_titled_plan_view_unavailable"
        )

        result = {
            "version": self.VERSION,
            "source_file": str(file_path),
            "view_count": len(views),
            "views": views,
            "plan_relationships": self._plan_relationships(plan_views),
            "selected_view_id": selected.get("view_id") if selected else None,
            "selected_view_bbox": selected.get("bbox") if selected else None,
            "selected_view_transform": (
                {"type": "identity", "source_coordinate_preserved": True}
                if selected else None
            ),
            "selected_entities": selected.get("entities", []) if selected else [],
            "selected_handles": selected.get("source_handles", []) if selected else [],
            "selected_layers": sorted(selected.get("layer_distribution", {})) if selected else [],
            "selected_inserts": selected.get("inserts", []) if selected else [],
            "selected_dimensions": selected.get("dimensions", []) if selected else [],
            "selected_texts": selected.get("texts", []) if selected else [],
            "selected_level_annotations": selected.get("level_annotations", []) if selected else [],
            "excluded_views": [view["view_id"] for view in views if not selected or view["view_id"] != selected["view_id"]],
            "selection_evidence": [reason],
            "selection_status": status,
            "metadata_use": {
                "building_type": metadata.get("building_type"),
                "storeys": metadata.get("storeys"),
                "purpose": "prevent_multiple_plan_views_from_being_interpreted_as_storeys",
            },
            "downstream_reference_evidence": self._scope_evidence(selected) if selected else self._empty_scope_evidence(),
            "provenance": ["DXF modelspace entities", "explicit view title text", "source entity handles"],
        }
        return result

    def _clusters(self, records, titles):
        if not titles:
            return []
        ordered = sorted(titles, key=lambda item: item["point"][0])
        anchors = [item["point"][0] for item in ordered]
        boundaries = [-math.inf] + [
            (anchors[index] + anchors[index + 1]) / 2.0
            for index in range(len(anchors) - 1)
        ] + [math.inf]
        views = []
        for index, title in enumerate(ordered):
            members = [
                record for record in records
                if boundaries[index] <= record["centroid"][0] < boundaries[index + 1]
            ]
            view_type = self._view_type(title.get("text"))
            texts = [self._public_record(item) for item in members if item.get("text") is not None]
            scales = [item for item in members if self.SCALE_PATTERN.search(item.get("text") or "")]
            scale_text = scales[0]["text"] if len(scales) == 1 else None
            match = self.SCALE_PATTERN.search(scale_text or "")
            bbox_value = self._aggregate_bbox(members)
            layer_distribution = dict(collections.Counter(item["layer"] for item in members))
            inserts = [self._public_record(item) for item in members if item["type"] == "INSERT"]
            dimensions = [self._public_record(item) for item in members if item["type"] == "DIMENSION"]
            level_annotations = [
                self._public_record(item) for item in members
                if item.get("text") and self._is_level_annotation(item["text"])
            ]
            views.append({
                "view_id": f"VIEW-{index + 1:03d}",
                "source_handles": [item["handle"] for item in members],
                "bbox": bbox_value,
                "centroid": self._bbox_centroid(bbox_value),
                "title_text": title.get("text"),
                "title_handle": title["handle"],
                "view_type": view_type,
                "scale_text": scale_text,
                "scale_value": float(match.group(1)) if match else None,
                "entity_count": len(members),
                "layer_distribution": layer_distribution,
                "block_insert_count": len(inserts),
                "dimensions": dimensions,
                "level_annotations": level_annotations,
                "geometry_extent": {
                    "width": bbox_value[1][0] - bbox_value[0][0],
                    "height": bbox_value[1][1] - bbox_value[0][1],
                },
                "confidence": 0.9 if title.get("text") and members else 0.5,
                "evidence_status": "INFERRED",
                "provenance": [
                    f"title_handle:{title['handle']}",
                    "horizontal non-overlap between explicit titled views",
                    "source handles preserved",
                ],
                "entities": [self._public_record(item) for item in members],
                "inserts": inserts,
                "texts": texts,
            })
        return views

    def _plan_relationships(self, plans):
        relationships = []
        for index, first in enumerate(plans):
            for second in plans[index + 1:]:
                first_title = (first.get("title_text") or "").upper()
                second_title = (second.get("title_text") or "").upper()
                if "PRESENTATION" in first_title or "PRESENTATION" in second_title:
                    relation = "presentation_copy"
                elif self._similar_views(first, second):
                    relation = "duplicate_plan_candidate"
                elif self._semantic_plan_match(first, second):
                    relation = "presentation_copy_candidate"
                else:
                    relation = "different_plan_views"
                relationships.append({
                    "view_ids": [first["view_id"], second["view_id"]],
                    "relationship": relation,
                    "evidence_status": "INFERRED",
                })
        return relationships

    def _similar_views(self, first, second):
        a, b = first["geometry_extent"], second["geometry_extent"]
        size_close = (
            abs(a["width"] - b["width"]) <= max(a["width"], b["width"], 1.0) * 0.08
            and abs(a["height"] - b["height"]) <= max(a["height"], b["height"], 1.0) * 0.08
        )
        count_close = abs(first["entity_count"] - second["entity_count"]) <= max(first["entity_count"], second["entity_count"], 1) * 0.08
        return size_close and count_close and first["view_type"] == second["view_type"]

    def _semantic_plan_match(self, first, second):
        a, b = first["geometry_extent"], second["geometry_extent"]
        size_close = (
            abs(a["width"] - b["width"]) <= max(a["width"], b["width"], 1.0) * 0.08
            and abs(a["height"] - b["height"]) <= max(a["height"], b["height"], 1.0) * 0.08
        )
        walls_close = abs(
            first["layer_distribution"].get("A-WALL", 0)
            - second["layer_distribution"].get("A-WALL", 0)
        ) <= 4
        doors_equal = sum(1 for item in first["inserts"] if item.get("layer") == "A-DOOR-FRAM") == sum(
            1 for item in second["inserts"] if item.get("layer") == "A-DOOR-FRAM"
        )
        first_levels = sorted(item.get("text") for item in first["level_annotations"])
        second_levels = sorted(item.get("text") for item in second["level_annotations"])
        return (
            first["view_type"] == second["view_type"] == "architectural_plan"
            and first.get("scale_value") == second.get("scale_value")
            and size_close and walls_close and doors_equal and first_levels == second_levels
        )

    def _scope_evidence(self, view):
        hatches = [item for item in view["entities"] if item["type"] == "HATCH"]
        closed_polylines = [item for item in view["entities"] if item["type"] in {"LWPOLYLINE", "POLYLINE"} and item.get("closed")]
        door_inserts = [item for item in view["inserts"] if item.get("layer") == "A-DOOR-FRAM"]
        return {
            "candidate_parcel_boundaries": hatches + closed_polylines,
            "parcel_status": "UNRESOLVED",
            "building_footprint": None,
            "building_footprint_status": "UNRESOLVED",
            "yard_open_space_geometry": [],
            "entrance_door_candidates": door_inserts,
            "entrance_door_status": "UNRESOLVED",
            "pedestrian_access_evidence": [],
            "platform_step_geometry_evidence": [],
            "level_040_annotations": [item for item in view["level_annotations"] if "+0.40" in (item.get("text") or "") or "0.40m" in (item.get("text") or "")],
            "level_040_value_status": "AUTHORITATIVE" if any("0.40" in (item.get("text") or "") for item in view["level_annotations"]) else "UNRESOLVED",
            "level_040_geometry_binding_status": "UNRESOLVED",
        }

    @staticmethod
    def _empty_scope_evidence():
        return {
            "candidate_parcel_boundaries": [], "parcel_status": "UNRESOLVED",
            "building_footprint": None, "building_footprint_status": "UNRESOLVED",
            "yard_open_space_geometry": [], "entrance_door_candidates": [],
            "entrance_door_status": "UNRESOLVED", "pedestrian_access_evidence": [],
            "platform_step_geometry_evidence": [], "level_040_annotations": [],
            "level_040_value_status": "UNRESOLVED",
            "level_040_geometry_binding_status": "UNRESOLVED",
        }

    def _record(self, entity, bbox_module, cache):
        try:
            extent = bbox_module.extents([entity], cache=cache, fast=True)
            if not extent.has_data:
                return None
            box = [[float(extent.extmin.x), float(extent.extmin.y)], [float(extent.extmax.x), float(extent.extmax.y)]]
        except Exception:
            return None
        text = None
        if entity.dxftype() in {"TEXT", "MTEXT"}:
            try:
                text = entity.plain_text() if entity.dxftype() == "MTEXT" else entity.dxf.text
            except Exception:
                text = None
        point = None
        if entity.dxftype() in {"TEXT", "MTEXT", "INSERT"}:
            point = [float(entity.dxf.insert.x), float(entity.dxf.insert.y)]
        result = {
            "handle": entity.dxf.handle, "type": entity.dxftype(),
            "layer": entity.dxf.layer, "bbox": box,
            "centroid": self._bbox_centroid(box), "point": point,
            "text": text,
        }
        if entity.dxftype() == "INSERT":
            result["block_name"] = entity.dxf.name
        if entity.dxftype() in {"LWPOLYLINE", "POLYLINE"}:
            result["closed"] = bool(entity.closed)
        if entity.dxftype() == "HATCH":
            result["hatch_area"] = (box[1][0] - box[0][0]) * (box[1][1] - box[0][1])
        return result

    @staticmethod
    def _public_record(record):
        return {key: value for key, value in record.items() if key not in {"centroid", "point"} or value is not None}

    @staticmethod
    def _aggregate_bbox(records):
        return [
            [min(item["bbox"][0][0] for item in records), min(item["bbox"][0][1] for item in records)],
            [max(item["bbox"][1][0] for item in records), max(item["bbox"][1][1] for item in records)],
        ]

    @staticmethod
    def _bbox_centroid(box):
        return [(box[0][0] + box[1][0]) / 2.0, (box[0][1] + box[1][1]) / 2.0]

    @staticmethod
    def _view_type(text):
        normalized = (text or "").upper()
        if "SITE PLAN" in normalized:
            return "site_plan"
        if "FLOOR PLAN" in normalized:
            return "architectural_plan"
        if "ELEVATION" in normalized:
            return "elevation"
        if "SECTION" in normalized:
            return "section"
        return None

    def _is_level_annotation(self, text):
        normalized = (text or "").strip()
        return bool(self.LEVEL_PATTERN.fullmatch(normalized)) and (
            "." in normalized or normalized.startswith(("+", "-"))
        )
