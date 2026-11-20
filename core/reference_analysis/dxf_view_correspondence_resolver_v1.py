import collections
import math
import statistics


class DXFViewCorrespondenceResolverV1:
    """Read-only correspondence proof for two already-clustered DXF views."""

    VERSION = "1.0"
    PRECISION = 5

    def resolve(self, file_path, scope_contract, view_a_id="VIEW-001", view_b_id="VIEW-002"):
        import ezdxf

        views = {view["view_id"]: view for view in scope_contract.get("views", [])}
        view_a, view_b = views.get(view_a_id), views.get(view_b_id)
        if not view_a or not view_b:
            return self._pending(view_a_id, view_b_id, "requested_views_unavailable")

        document = ezdxf.readfile(str(file_path))
        entities = {entity.dxf.handle: entity for entity in document.modelspace()}
        a_entities = [entities[handle] for handle in view_a["source_handles"] if handle in entities]
        b_entities = [entities[handle] for handle in view_b["source_handles"] if handle in entities]
        translation, support = self._translation(a_entities, b_entities)
        if translation is None or support < 4:
            return self._pending(view_a_id, view_b_id, "stable_translation_correspondence_unavailable")

        rotation_delta = self._rotation_delta(a_entities, b_entities)
        scale_ratio = (
            view_b["scale_value"] / view_a["scale_value"]
            if view_a.get("scale_value") and view_b.get("scale_value")
            else self._scale_ratio(a_entities, b_entities)
        )
        categories = {
            "walls": lambda entity: entity.dxftype() == "LINE" and entity.dxf.layer == "A-WALL",
            "openings": lambda entity: entity.dxftype() == "INSERT" and entity.dxf.layer in {"A-DOOR-FRAM", "A-GLAZ"},
            "doors": lambda entity: entity.dxftype() == "INSERT" and entity.dxf.layer == "A-DOOR-FRAM",
            "windows": lambda entity: entity.dxftype() == "INSERT" and entity.dxf.layer == "A-GLAZ",
            "dimensions": lambda entity: entity.dxftype() == "DIMENSION",
            "levels": lambda entity: entity.dxftype() in {"TEXT", "MTEXT"} and self._is_level(self._text(entity)),
            "blocks": lambda entity: entity.dxftype() == "INSERT" and entity.dxf.layer not in {"0"},
            "floor": lambda entity: entity.dxf.layer == "A-FLOR",
            "geometry": lambda entity: entity.dxftype() in {"LINE", "LWPOLYLINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE", "INSERT"},
        }
        comparisons = {
            name: self._compare(a_entities, b_entities, predicate, translation)
            for name, predicate in categories.items()
        }
        wall_score = comparisons["walls"]["score"]
        opening_score = comparisons["openings"]["score"]
        dimension_score = comparisons["dimensions"]["score"]
        level_score = comparisons["levels"]["score"]
        block_score = comparisons["blocks"]["score"]
        geometry_score = (
            0.40 * wall_score + 0.25 * opening_score + 0.15 * level_score
            + 0.10 * block_score + 0.10 * dimension_score
        )
        transform_consistent = (
            abs(rotation_delta) <= 1e-6 and abs(scale_ratio - 1.0) <= 1e-6
        )
        architectural_difference = wall_score < 0.95 or opening_score < 0.95 or level_score < 0.95
        enough = support >= 4 and min(wall_score, opening_score, level_score) >= 0.95
        equivalent = transform_consistent and enough and not architectural_difference
        equivalence_status = "equivalent" if equivalent else "not_equivalent" if architectural_difference else "unresolved"
        canonical_id = min(view_a_id, view_b_id) if equivalent else None
        canonical_view = views.get(canonical_id) if canonical_id else None

        unmatched = comparisons["walls"]["unmatched"] + comparisons["openings"]["unmatched"]
        floor_a = comparisons["floor"]["a_count"]
        floor_b = comparisons["floor"]["b_count"]
        presentation = {
            "category": "A-FLOR",
            "view_a_count": floor_a,
            "view_b_count": floor_b,
            "matched_signature_count": comparisons["floor"]["matched_count"],
            "additional_count": abs(floor_b - floor_a),
            "classification": (
                "presentation_enrichment_or_duplicate_drafting_linework"
                if equivalent and floor_a != floor_b else "no_material_presentation_difference"
            ),
        }
        presentation_differences = [presentation]
        if comparisons["dimensions"]["a_count"] != comparisons["dimensions"]["b_count"] or dimension_score < 1.0:
            presentation_differences.append({
                "category": "DIMENSION",
                "view_a_count": comparisons["dimensions"]["a_count"],
                "view_b_count": comparisons["dimensions"]["b_count"],
                "matched_signature_count": comparisons["dimensions"]["matched_count"],
                "classification": "presentation_annotation_set_difference",
            })
        return {
            "version": self.VERSION,
            "relation_status": "resolved" if equivalence_status != "unresolved" else "pending",
            "relation": "equivalent_presentation_views" if equivalent else equivalence_status,
            "view_a": view_a_id,
            "view_b": view_b_id,
            "translation_vector": translation,
            "translation_support_count": support,
            "rotation_delta": rotation_delta,
            "scale_ratio": scale_ratio,
            "geometry_match_score": geometry_score,
            "wall_match_score": wall_score,
            "opening_match_score": opening_score,
            "door_match_score": comparisons["doors"]["score"],
            "window_match_score": comparisons["windows"]["score"],
            "dimension_match_score": dimension_score,
            "level_annotation_match_score": level_score,
            "block_match_score": block_score,
            "unmatched_authoritative_geometry": unmatched,
            "presentation_only_entities": presentation_differences,
            "architectural_difference_detected": architectural_difference,
            "equivalence_status": equivalence_status,
            "evidence_used": [
                "translation_normalized_handle_independent_signatures",
                "wall_line_correspondence", "door_window_block_correspondence",
                "dimension_correspondence", "level_annotation_correspondence",
                "entity_category_correspondence",
            ],
            "unresolved_evidence": [] if equivalent else ["architectural_correspondence_threshold_not_met"],
            "primary_view_id": None,
            "canonical_analysis_view_id": canonical_id,
            "canonicalization_allowed": equivalent,
            "canonicalization_reason": (
                "equivalent_views_normalized_for_reference_analysis" if equivalent else None
            ),
            "canonical_scope": self._canonical_scope(canonical_view) if equivalent else None,
            "provenance": [str(file_path), view_a.get("title_handle"), view_b.get("title_handle")],
        }

    def _translation(self, first, second):
        first_anchors = self._anchors(first)
        second_anchors = self._anchors(second)
        votes = collections.Counter()
        samples = collections.defaultdict(list)
        for key in first_anchors.keys() & second_anchors.keys():
            for a in first_anchors[key]:
                for b in second_anchors[key]:
                    delta = (b[0] - a[0], b[1] - a[1])
                    bucket = (round(delta[0], 3), round(delta[1], 3))
                    votes[bucket] += 1
                    samples[bucket].append(delta)
        if not votes:
            return None, 0
        bucket, support = votes.most_common(1)[0]
        vector = samples[bucket]
        return [statistics.median(item[0] for item in vector), statistics.median(item[1] for item in vector)], support

    def _anchors(self, entities):
        result = collections.defaultdict(list)
        for entity in entities:
            if entity.dxftype() == "INSERT":
                point = entity.dxf.insert
                key = ("INSERT", entity.dxf.layer, entity.dxf.name)
                result[key].append((float(point.x), float(point.y)))
            elif entity.dxftype() in {"TEXT", "MTEXT"}:
                point = entity.dxf.insert
                key = ("TEXT", entity.dxf.layer, self._text(entity))
                result[key].append((float(point.x), float(point.y)))
        return result

    def _compare(self, first, second, predicate, translation):
        a = collections.Counter(self._signature(entity, [0.0, 0.0]) for entity in first if predicate(entity))
        b = collections.Counter(self._signature(entity, translation) for entity in second if predicate(entity))
        matched = a & b
        matched_count = sum(matched.values())
        denominator = max(sum(a.values()), sum(b.values()), 1)
        unmatched = []
        for signature, count in (a - b).items():
            unmatched.append({"view": "a", "signature": repr(signature), "count": count})
        for signature, count in (b - a).items():
            unmatched.append({"view": "b", "signature": repr(signature), "count": count})
        return {
            "score": matched_count / denominator,
            "matched_count": matched_count,
            "a_count": sum(a.values()), "b_count": sum(b.values()),
            "unmatched": unmatched,
        }

    def _signature(self, entity, translation):
        dx, dy = translation
        kind, layer = entity.dxftype(), entity.dxf.layer

        def point(value):
            return (round(float(value.x) - dx, self.PRECISION), round(float(value.y) - dy, self.PRECISION))

        if kind == "LINE":
            return kind, layer, tuple(sorted((point(entity.dxf.start), point(entity.dxf.end))))
        if kind == "LWPOLYLINE":
            points = tuple((round(x - dx, self.PRECISION), round(y - dy, self.PRECISION)) for x, y, *_ in entity.get_points())
            return kind, layer, self._canonical_cycle(points, bool(entity.closed))
        if kind == "INSERT":
            return kind, layer, entity.dxf.name, point(entity.dxf.insert), round(float(entity.dxf.rotation), 5), round(float(entity.dxf.xscale), 5), round(float(entity.dxf.yscale), 5)
        if kind in {"TEXT", "MTEXT"}:
            return "TEXT", layer, self._text(entity), point(entity.dxf.insert), round(float(getattr(entity.dxf, "rotation", 0.0)), 5)
        if kind == "DIMENSION":
            points = []
            for name in ("defpoint", "defpoint2", "defpoint3", "defpoint4"):
                value = getattr(entity.dxf, name, None)
                if value is not None:
                    points.append(point(value))
            try:
                measurement = round(float(entity.get_measurement()), 5)
            except Exception:
                measurement = None
            if points:
                origin = points[0]
                relative = tuple(
                    (round(item[0] - origin[0], self.PRECISION), round(item[1] - origin[1], self.PRECISION))
                    for item in points
                )
            else:
                relative = ()
            return kind, layer, relative, measurement, int(entity.dxf.dimtype) & 15
        if kind in {"ARC", "CIRCLE"}:
            return kind, layer, point(entity.dxf.center), round(float(entity.dxf.radius), 5), round(float(getattr(entity.dxf, "start_angle", 0.0)), 5), round(float(getattr(entity.dxf, "end_angle", 0.0)), 5)
        try:
            return kind, layer, point(entity.dxf.insert)
        except Exception:
            return kind, layer

    @staticmethod
    def _canonical_cycle(points, closed):
        if not closed or not points:
            return points
        rotations = [points[index:] + points[:index] for index in range(len(points))]
        reversed_points = tuple(reversed(points))
        rotations += [reversed_points[index:] + reversed_points[:index] for index in range(len(points))]
        return min(rotations)

    def _rotation_delta(self, first, second):
        first_by_name = collections.defaultdict(list)
        second_by_name = collections.defaultdict(list)
        for entity in first:
            if entity.dxftype() == "INSERT":
                first_by_name[entity.dxf.name].append(float(entity.dxf.rotation))
        for entity in second:
            if entity.dxftype() == "INSERT":
                second_by_name[entity.dxf.name].append(float(entity.dxf.rotation))
        votes = collections.Counter()
        for name in first_by_name.keys() & second_by_name.keys():
            for a in first_by_name[name]:
                for b in second_by_name[name]:
                    votes[round(((b - a + 180.0) % 360.0) - 180.0, 6)] += 1
        return float(votes.most_common(1)[0][0]) if votes else 0.0

    def _scale_ratio(self, first, second):
        a = [float(entity.dxf.xscale) for entity in first if entity.dxftype() == "INSERT"]
        b = [float(entity.dxf.xscale) for entity in second if entity.dxftype() == "INSERT"]
        if not a or not b:
            return 1.0
        return round((sum(b) / len(b)) / (sum(a) / len(a)), 6)

    def _canonical_scope(self, view):
        doors = [item for item in view.get("inserts", []) if item.get("layer") == "A-DOOR-FRAM"]
        windows = [item for item in view.get("inserts", []) if item.get("layer") == "A-GLAZ"]
        levels = view.get("level_annotations", [])
        texts = [item.get("text") for item in view.get("texts", [])]
        return {
            "view_id": view["view_id"], "bbox": view["bbox"],
            "source_handles": view["source_handles"],
            "door_candidate_count": len(doors), "window_candidate_count": len(windows),
            "dimension_count": len(view.get("dimensions", [])),
            "level_evidence_count": len(levels),
            "level_annotations": levels,
            "level_040_evidence_count": sum(1 for text in texts if text == "+0.40" or text == "0.40m"),
            "riser_count_annotation_count": sum(1 for text in texts if text == "n:2"),
            "riser_height_annotation_count": sum(1 for text in texts if text == "h:0.20"),
            "level_040_geometry_binding_status": "UNRESOLVED",
            "riser_geometry_binding_status": "UNRESOLVED",
            "building_footprint_status": "UNRESOLVED",
            "yard_open_space_status": "UNRESOLVED",
            "entrance_door_status": "UNRESOLVED",
            "platform_step_binding_status": "UNRESOLVED",
            "parcel_status": "UNRESOLVED",
            "pedestrian_access_status": "UNRESOLVED",
        }

    @staticmethod
    def _text(entity):
        try:
            return (entity.plain_text() if entity.dxftype() == "MTEXT" else entity.dxf.text).strip()
        except Exception:
            return ""

    @staticmethod
    def _is_level(text):
        normalized = (text or "").replace(" ", "").lower().rstrip("m")
        try:
            float(normalized)
            return "." in normalized or normalized.startswith(("+", "-"))
        except ValueError:
            return False

    def _pending(self, view_a, view_b, reason):
        return {
            "version": self.VERSION, "relation_status": "pending",
            "view_a": view_a, "view_b": view_b, "translation_vector": None,
            "rotation_delta": None, "scale_ratio": None, "geometry_match_score": 0.0,
            "wall_match_score": 0.0, "opening_match_score": 0.0,
            "door_match_score": 0.0, "window_match_score": 0.0,
            "dimension_match_score": 0.0, "level_annotation_match_score": 0.0,
            "block_match_score": 0.0, "unmatched_authoritative_geometry": [],
            "presentation_only_entities": [], "architectural_difference_detected": False,
            "equivalence_status": "unresolved", "evidence_used": [],
            "unresolved_evidence": [reason], "primary_view_id": None,
            "canonical_analysis_view_id": None, "canonicalization_allowed": False,
            "canonical_scope": None,
        }
