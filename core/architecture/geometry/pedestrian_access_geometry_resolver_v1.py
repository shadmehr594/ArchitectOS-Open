class PedestrianAccessGeometryResolverV1:
    """Validate explicit site-to-building pedestrian approach geometry."""

    VERSION = "1.0"
    TOLERANCE = 1e-7

    def resolve(self, site_geometry, floor_geometry):
        site = site_geometry if isinstance(site_geometry, dict) else {}
        candidates = site.get("pedestrian_access_candidates", [])
        candidates = candidates if isinstance(candidates, list) else []
        parcel = site.get("parcel_boundary")
        building = self._building_footprint(floor_geometry)
        valid = []

        for candidate in candidates:
            normalized = self._validate_candidate(candidate, site, parcel, building)
            if normalized is not None:
                valid.append(normalized)

        if len(valid) == 1:
            return valid[0]
        return {
            "type": "pedestrian_access",
            "access_id": None,
            "parcel_edge_reference": None,
            "access_point": None,
            "approach_start": None,
            "approach_end": None,
            "approach_line": None,
            "geometry_status": "pending",
            "resolution_reason": (
                "multiple_valid_pedestrian_access_candidates"
                if len(valid) > 1
                else "complete_authoritative_site_access_geometry_required"
            ),
            "valid_candidate_ids": [item["access_id"] for item in valid],
            "source_evidence": [],
            "source": self.__class__.__name__,
        }

    def _validate_candidate(self, candidate, site, parcel, building):
        if not isinstance(candidate, dict) or candidate.get("geometry_status") not in {
            "resolved", "candidate"
        }:
            return None
        access_id = candidate.get("access_id", candidate.get("id"))
        edge_reference = candidate.get(
            "parcel_edge_reference", candidate.get("edge_index")
        )
        access_point = self._point(candidate.get("access_point"))
        start = self._point(candidate.get("approach_start"))
        end = self._point(candidate.get("approach_end"))
        line = candidate.get("approach_line")
        if (start is None or end is None) and self._valid_line(line):
            start, end = self._point(line[0]), self._point(line[1])
        if access_point is None and start is not None:
            access_point = list(start)
        if edge_reference is None and access_point is not None:
            matches = self._matching_parcel_edges(site, parcel, access_point)
            if len(matches) == 1:
                edge_reference = matches[0]
        edge = self._parcel_edge(site, parcel, edge_reference)
        if not access_id or edge is None or access_point is None or start is None or end is None:
            return None
        if not self._same_point(access_point, start):
            return None
        if not self._point_on_segment(access_point, edge[0], edge[1]):
            return None
        if building is None or not self._point_on_boundary(end, building):
            return None
        if self._same_point(start, end):
            return None
        evidence = candidate.get("source_evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        if not isinstance(evidence, list) or not evidence:
            return None
        return {
            "type": "pedestrian_access",
            "access_id": access_id,
            "parcel_edge_reference": edge_reference,
            "access_point": access_point,
            "approach_start": start,
            "approach_end": end,
            "approach_line": [start, end],
            "geometry_status": "resolved",
            "resolution_reason": "unique_complete_authoritative_site_access_candidate",
            "source_evidence": list(evidence),
            "source": self.__class__.__name__,
        }

    def _matching_parcel_edges(self, site, parcel, point):
        matches = []
        for edge in site.get("parcel_edges", []):
            if not isinstance(edge, dict) or not self._valid_line([edge.get("start"), edge.get("end")]):
                continue
            if self._point_on_segment(point, edge["start"], edge["end"]):
                matches.append(edge.get("id", edge.get("edge_index")))
        if matches:
            return [reference for reference in matches if reference is not None]
        if self._valid_polygon(parcel):
            return [
                index for index in range(len(parcel))
                if self._point_on_segment(point, parcel[index], parcel[(index + 1) % len(parcel)])
            ]
        return []

    def _parcel_edge(self, site, parcel, reference):
        for edge in site.get("parcel_edges", []):
            if not isinstance(edge, dict):
                continue
            identities = {edge.get("id"), edge.get("edge_index")}
            if reference in identities and self._valid_line([edge.get("start"), edge.get("end")]):
                return [self._point(edge["start"]), self._point(edge["end"])]
        if isinstance(reference, int) and self._valid_polygon(parcel):
            if 0 <= reference < len(parcel):
                return [self._point(parcel[reference]), self._point(parcel[(reference + 1) % len(parcel)])]
        return None

    def _building_footprint(self, floor_geometry):
        footprints = []
        for item in floor_geometry if isinstance(floor_geometry, list) else []:
            if not isinstance(item, dict):
                continue
            footprint = item.get("footprint", {})
            points = footprint.get("points") if isinstance(footprint, dict) else None
            if self._valid_polygon(points):
                footprints.append([self._point(point) for point in points])
        return footprints[0] if len(footprints) == 1 else None

    def _point_on_boundary(self, point, polygon):
        return any(
            self._point_on_segment(point, polygon[index], polygon[(index + 1) % len(polygon)])
            for index in range(len(polygon))
        )

    def _point_on_segment(self, point, start, end):
        point, start, end = self._point(point), self._point(start), self._point(end)
        cross = (point[0] - start[0]) * (end[1] - start[1]) - (point[1] - start[1]) * (end[0] - start[0])
        return abs(cross) <= self.TOLERANCE and (
            min(start[0], end[0]) - self.TOLERANCE <= point[0] <= max(start[0], end[0]) + self.TOLERANCE
            and min(start[1], end[1]) - self.TOLERANCE <= point[1] <= max(start[1], end[1]) + self.TOLERANCE
        )

    def _same_point(self, first, second):
        return abs(first[0] - second[0]) <= self.TOLERANCE and abs(first[1] - second[1]) <= self.TOLERANCE

    def _valid_line(self, value):
        return isinstance(value, (list, tuple)) and len(value) == 2 and all(self._point(item) is not None for item in value)

    def _valid_polygon(self, value):
        return isinstance(value, list) and len(value) >= 3 and all(self._point(item) is not None for item in value)

    @staticmethod
    def _point(value):
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                return [float(value[0]), float(value[1])]
            except (TypeError, ValueError):
                return None
        return None
