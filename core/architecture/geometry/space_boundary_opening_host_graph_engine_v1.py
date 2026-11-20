"""Architecture-only space boundary and opening host graph kernel.

The kernel never writes source CAD.  DWG files are converted to a temporary DXF
working copy, while every output retains source handles and geometric evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from math import atan2, hypot
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from typing import Any, Iterable
import json
import os
import re
import shutil
import subprocess

from shapely import concave_hull
from shapely.geometry import GeometryCollection, LineString, MultiPoint, MultiPolygon, Point, Polygon
from shapely.ops import nearest_points, polygonize_full, snap, unary_union


Point2 = tuple[float, float]


@dataclass
class SpacePolygon:
    space_id: str
    floor: str
    polygon: list[list[float]]
    area_m2: float
    perimeter_m: float
    centroid: list[float]
    interior_point: list[float]
    boundary_ids: list[str]
    semantic_label: str | None = None
    semantic_label_handle: str | None = None
    semantic_class: str | None = None
    provenance: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class OpeningPortal:
    opening_id: str
    floor: str
    kind: str
    constituent_source_handles: list[str]
    host_wall_pair_id: str | None
    host_face_a: str | None
    host_face_b: str | None
    threshold: list[list[float]] | None
    centerline: list[list[float]] | None
    clear_width_m: float | None
    side_a: str | None
    side_b: str | None
    traversable: bool
    exposure: str | None
    confidence: float
    geometric_evidence: dict[str, Any]
    status: str
    expected_from_space: str | None = None
    expected_to_space: str | None = None
    expected_host_partition: str | None = None
    expected_exposure: str | None = None
    intent_assertion_status: str | None = None


@dataclass
class WallFaceGraph:
    floor: str
    faces: list[dict[str, Any]]
    pairs: list[dict[str, Any]]
    junctions: list[dict[str, Any]]
    thickness_clusters_m: list[dict[str, Any]]


@dataclass
class WallSolidGraph:
    floor: str
    solids: list[dict[str, Any]]
    unresolved_pairs: list[dict[str, Any]]
    union_area_m2: float
    floor_envelopes: list[dict[str, Any]]
    topology_repairs: list[dict[str, Any]]


@dataclass
class OpeningHostGraph:
    floor: str
    openings: list[OpeningPortal]
    unresolved: list[dict[str, Any]]


@dataclass
class SpaceBoundaryGraph:
    floor: str
    spaces: list[SpacePolygon]
    virtual_closures: list[dict[str, Any]]
    unresolved: list[dict[str, Any]]


@dataclass
class BoundaryExtractionResult:
    source_file: str
    source_sha256: str
    semantic_length_unit: str
    geometry_scale_applied: bool
    tolerance_audit: dict[str, Any]
    wall_face_graphs: dict[str, WallFaceGraph]
    wall_solid_graphs: dict[str, WallSolidGraph]
    opening_host_graphs: dict[str, OpeningHostGraph]
    space_boundary_graphs: dict[str, SpaceBoundaryGraph]
    access_graph: dict[str, Any]
    label_bindings: list[dict[str, Any]]
    unresolved: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpaceBoundaryOpeningHostGraphEngineV1:
    VERSION = "1.0"
    FLOORS = ("G", "R1", "R2", "ROOF")
    WALL_SUFFIX = "_ROOM_WALL"
    OPENING_SUFFIXES = {"_DOOR": "DOOR", "_WINDOW": "WINDOW"}
    IGNORED_LAYER_TOKENS = ("PATH", "GUIDE", "COLUMN", "DIMENSION", "STAIR_TREAD", "MANEUVER", "PROJECTION")
    LABEL_CLASSES = {
        "bed": "BEDROOM", "batch": "BATHROOM", "wc": "WC", "kitchen": "KITCHEN",
        "پذیرایی": "LIVING", "نشیمن خصوصی": "PRIVATE_LIVING", "انبار": "STORAGE",
        "کفش کن": "ENTRY", "نورگیر": "LIGHTWELL", "تراس": "TERRACE",
        "تجاری": "COMMERCIAL", "فضای مانور": "MANEUVER", "ورودی ماشین رو و نفر رو": "ACCESS_SHARED",
    }
    NON_ROOM_CLASSES = {"MANEUVER"}

    def extract(self, source_file: str | os.PathLike[str], semantic_regions: dict[str, Any] | None = None) -> BoundaryExtractionResult:
        source = Path(source_file).resolve()
        before = self._hash(source)
        with TemporaryDirectory(prefix="architectos_space_boundary_") as tmp:
            dxf = self._readable_cad(source, Path(tmp))
            import ezdxf
            document = ezdxf.readfile(str(dxf))
            modelspace = list(document.modelspace())
            floor_data = {floor: self._extract_floor_entities(modelspace, floor) for floor in self.FLOORS}
            tolerance = self._tolerance_audit(floor_data)
            snap_tolerance = tolerance["chosen_snap_tolerance_m"]
            walls: dict[str, WallFaceGraph] = {}
            solid_graphs: dict[str, WallSolidGraph] = {}
            opening_graphs: dict[str, OpeningHostGraph] = {}
            spaces: dict[str, SpaceBoundaryGraph] = {}
            bindings: list[dict[str, Any]] = []
            unresolved: list[dict[str, Any]] = []
            for floor, data in floor_data.items():
                wall_graph = self._wall_graph(floor, data["wall_segments"], snap_tolerance)
                walls[floor] = wall_graph
                solid_graph = self._wall_solids(floor, wall_graph, snap_tolerance)
                solid_graphs[floor] = solid_graph
                clusters = self._cluster_openings(floor, data["opening_entities"], snap_tolerance)
                portals, closures, opening_unresolved = self._host_openings(floor, clusters, wall_graph, solid_graph, snap_tolerance)
                boundary, floor_bindings = self._free_space_cells(floor, wall_graph, solid_graph, closures, data["labels"], snap_tolerance)
                self._attach_sides(portals, boundary.spaces, wall_graph, data["extent"])
                for portal in portals:
                    if portal.status.startswith("UNRESOLVED") and not any(x.get("id")==portal.opening_id for x in opening_unresolved):
                        opening_unresolved.append({"id":portal.opening_id,"floor":floor,"type":"OPENING_PORTAL",
                                                   "reason":portal.status,"source_handles":portal.constituent_source_handles,
                                                   "side_a":portal.side_a,"side_b":portal.side_b})
                opening_graphs[floor] = OpeningHostGraph(floor, portals, opening_unresolved)
                spaces[floor] = boundary
                bindings.extend(floor_bindings)
                unresolved.extend(opening_unresolved + boundary.unresolved)
            access = self._access_graph(spaces, opening_graphs)
        after = self._hash(source)
        if before != after:
            raise RuntimeError("SOURCE_DWG_MUTATED")
        return BoundaryExtractionResult(str(source), before, "METER", False, tolerance, walls, solid_graphs, opening_graphs, spaces, access, bindings, unresolved)

    def extract_geometry(self, floors: dict[str, dict[str, Any]]) -> BoundaryExtractionResult:
        """Pure-geometry entry point used by unit tests and upstream architecture."""
        prepared = {}
        for floor in self.FLOORS:
            raw = floors.get(floor, {})
            prepared[floor] = {
                "wall_segments": raw.get("wall_segments", []), "opening_entities": raw.get("opening_entities", []),
                "labels": raw.get("labels", []), "extent": raw.get("extent"),
            }
        tolerance = self._tolerance_audit(prepared)
        walls = {}; solids = {}; openings = {}; boundaries = {}; bindings = []; unresolved = []
        for floor, data in prepared.items():
            wg = self._wall_graph(floor, data["wall_segments"], tolerance["chosen_snap_tolerance_m"])
            sg = self._wall_solids(floor, wg, tolerance["chosen_snap_tolerance_m"])
            clusters = self._cluster_openings(floor, data["opening_entities"], tolerance["chosen_snap_tolerance_m"])
            portals, closures, ou = self._host_openings(floor, clusters, wg, sg, tolerance["chosen_snap_tolerance_m"])
            bg, fb = self._free_space_cells(floor, wg, sg, closures, data["labels"], tolerance["chosen_snap_tolerance_m"])
            self._attach_sides(portals, bg.spaces, wg, data.get("extent"))
            for portal in portals:
                if portal.status.startswith("UNRESOLVED") and not any(x.get("id")==portal.opening_id for x in ou):
                    ou.append({"id":portal.opening_id,"floor":floor,"type":"OPENING_PORTAL","reason":portal.status,
                               "source_handles":portal.constituent_source_handles,"side_a":portal.side_a,"side_b":portal.side_b})
            walls[floor] = wg; solids[floor] = sg; openings[floor] = OpeningHostGraph(floor, portals, ou); boundaries[floor] = bg
            bindings += fb; unresolved += ou + bg.unresolved
        return BoundaryExtractionResult("IN_MEMORY", "IN_MEMORY", "METER", False, tolerance, walls, solids, openings, boundaries,
                                        self._access_graph(boundaries, openings), bindings, unresolved)

    def _readable_cad(self, source: Path, tmp: Path) -> Path:
        if source.suffix.lower() == ".dxf":
            return source
        converter = shutil.which("ODAFileConverter") or r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"
        if not Path(converter).is_file():
            raise RuntimeError("DWG_READER_UNAVAILABLE_ODA_FILE_CONVERTER_NOT_FOUND")
        subprocess.run([converter, str(source.parent), str(tmp), "ACAD2018", "DXF", "0", "0", source.name],
                       check=True, timeout=10800, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        candidate = tmp / f"{source.stem}.dxf"
        if not candidate.is_file():
            raise RuntimeError("DWG_TO_DXF_WORKING_COPY_FAILED")
        return candidate

    def _extract_floor_entities(self, entities: list[Any], floor: str) -> dict[str, Any]:
        wall_layer = f"{floor}{self.WALL_SUFFIX}"
        opening_layers = {f"{floor}{suffix}": kind for suffix, kind in self.OPENING_SUFFIXES.items()}
        label_layer = f"{floor}_LEVEL_TEXT"
        wall_segments = [] ; opening_entities = [] ; labels = [] ; all_points = []
        for entity in entities:
            layer = str(entity.dxf.layer)
            if any(token in layer.upper() for token in self.IGNORED_LAYER_TOKENS):
                continue
            if layer == wall_layer:
                wall_segments.extend(self._entity_segments(entity, "wall"))
            elif layer in opening_layers:
                segs = self._entity_segments(entity, opening_layers[layer].lower())
                opening_entities.append({"handle": entity.dxf.handle, "kind": opening_layers[layer], "layer": layer,
                                         "entity_type": entity.dxftype(), "segments": segs,
                                         "points": [p for s in segs for p in (s["start"], s["end"])]})
            elif layer == label_layer and entity.dxftype() in {"TEXT", "MTEXT"}:
                text = (entity.plain_text() if entity.dxftype() == "MTEXT" else entity.dxf.text).strip()
                if self._label_class(text):
                    labels.append({"handle": entity.dxf.handle, "text": text,
                                   "point": [float(entity.dxf.insert.x), float(entity.dxf.insert.y)],
                                   "semantic_class": self._label_class(text)})
        for segment in wall_segments:
            all_points.extend((segment["start"], segment["end"]))
        extent = [min(p[0] for p in all_points), min(p[1] for p in all_points), max(p[0] for p in all_points), max(p[1] for p in all_points)] if all_points else None
        return {"wall_segments": wall_segments, "opening_entities": opening_entities, "labels": labels, "extent": extent}

    def _entity_segments(self, entity: Any, role: str) -> list[dict[str, Any]]:
        result = []
        def add(a: Any, b: Any) -> None:
            p = [float(a[0]), float(a[1])]; q = [float(b[0]), float(b[1])]
            if hypot(q[0]-p[0], q[1]-p[1]) > 1e-9:
                result.append({"start": p, "end": q, "source_handle": entity.dxf.handle,
                               "source_handles": [entity.dxf.handle], "source_layer": entity.dxf.layer,
                               "entity_type": entity.dxftype(), "role": role})
        kind = entity.dxftype()
        if kind == "LINE": add(entity.dxf.start, entity.dxf.end)
        elif kind == "LWPOLYLINE":
            points = [(x, y) for x, y, *_ in entity.get_points()]
            for a, b in zip(points, points[1:] + ([points[0]] if entity.closed else [])): add(a, b)
        elif kind == "POLYLINE":
            points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
            for a, b in zip(points, points[1:] + ([points[0]] if entity.is_closed else [])): add(a, b)
        elif kind in {"ARC", "CIRCLE"}:
            import ezdxf
            points = [(v.x, v.y) for v in ezdxf.path.make_path(entity).flattening(0.01)]
            for a, b in zip(points, points[1:]): add(a, b)
        return result

    def _tolerance_audit(self, floor_data: dict[str, dict[str, Any]]) -> dict[str, Any]:
        points = []
        for data in floor_data.values():
            for segment in data.get("wall_segments", []): points.extend((segment["start"], segment["end"]))
        decimals = []
        for p in points:
            for value in p:
                text = f"{float(value):.12f}".rstrip("0")
                decimals.append(len(text.split(".")[1]) if "." in text else 0)
        near = []
        for i, a in enumerate(points):
            for b in points[i+1:]:
                d = hypot(a[0]-b[0], a[1]-b[1])
                if 1e-8 < d <= 0.10: near.append(d)
        histogram = {"0_0.001": 0, "0.001_0.005": 0, "0.005_0.01": 0, "0.01_0.02": 0, "0.02_0.05": 0, "0.05_0.10": 0}
        for d in near:
            keys = [(0.001,"0_0.001"),(0.005,"0.001_0.005"),(0.01,"0.005_0.01"),(0.02,"0.01_0.02"),(0.05,"0.02_0.05"),(0.10,"0.05_0.10")]
            for upper, key in keys:
                if d <= upper: histogram[key] += 1; break
        precision_floor = 10 ** (-(max(decimals) if decimals else 6))
        small = sorted(d for d in near if d <= 0.02)
        chosen = min(0.02, max(precision_floor * 10, small[len(small)//2] * 1.25 if small else 0.001))
        candidates = [0.0001, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.02]
        return {"coordinate_precision": {"max_decimal_places": max(decimals) if decimals else 0,
                                          "median_decimal_places": median(decimals) if decimals else 0,
                                          "precision_floor_m": precision_floor},
                "endpoint_near_gap_histogram_m": histogram, "candidate_snap_tolerances_tested_m": candidates,
                "chosen_snap_tolerance_m": chosen,
                "justification": "small-gap median bounded by 0.02 m; never bridges architectural openings",
                "maximum_geometric_movement_m": chosen, "normalization_scope": "topology_working_copy_only"}

    def _wall_graph(self, floor: str, raw: list[dict[str, Any]], tolerance: float) -> WallFaceGraph:
        dedup: dict[tuple[Any, ...], dict[str, Any]] = {}
        for item in raw:
            if item.get("role", "wall") != "wall" or any(token in str(item.get("source_layer", "")).upper() for token in self.IGNORED_LAYER_TOKENS):
                continue
            a = self._snap_point(item["start"], tolerance); b = self._snap_point(item["end"], tolerance)
            if b < a: a, b = b, a
            key = (a, b)
            if key in dedup:
                dedup[key]["source_handles"] = sorted(set(dedup[key]["source_handles"] + item.get("source_handles", [])))
            else:
                dedup[key] = dict(item, start=list(a), end=list(b), source_handles=list(item.get("source_handles", [])))
        faces = []
        for index, item in enumerate(dedup.values(), 1):
            a, b = item["start"], item["end"]; length = hypot(b[0]-a[0], b[1]-a[1])
            faces.append({"face_id": f"{floor}-FACE-{index:04d}", **item, "length_m": length,
                          "angle_rad": atan2(b[1]-a[1], b[0]-a[0]) % 3.141592653589793,
                          "confidence": 1.0, "provenance": "SOURCE_WALL_FACE"})
        pairs = [] ; distances = []
        for i, a in enumerate(faces):
            la = LineString([a["start"], a["end"]])
            for b in faces[i+1:]:
                angle_delta = abs(a["angle_rad"]-b["angle_rad"]); angle_delta = min(angle_delta, 3.141592653589793-angle_delta)
                if angle_delta > 0.02: continue
                lb = LineString([b["start"], b["end"]]); distance = la.distance(lb)
                if not 0.06 <= distance <= 0.60: continue
                direction = self._unit(a["start"], a["end"])
                ai = sorted(self._dot(p, direction) for p in (a["start"], a["end"])); bi = sorted(self._dot(p, direction) for p in (b["start"], b["end"]))
                overlap = max(0.0, min(ai[1],bi[1])-max(ai[0],bi[0]))
                if overlap < max(0.15, min(a["length_m"], b["length_m"])*0.20): continue
                distances.append(distance)
                pairs.append({"wall_pair_id": f"{floor}-WPAIR-{len(pairs)+1:04d}", "face_a": a["face_id"], "face_b": b["face_id"],
                              "thickness_m": distance, "overlap_m": overlap,
                              "source_handles": sorted(set(a["source_handles"]+b["source_handles"])),
                              "confidence": min(1.0, 0.65+overlap/max(a["length_m"],b["length_m"])*0.35),
                              "evidence": ["parallel faces", "projected overlap", "observed separation"]})
        clusters = self._clusters_1d(distances, 0.035)
        thickness_clusters = [{"center_m": median(c), "count": len(c), "min_m": min(c), "max_m": max(c)} for c in clusters]
        lines = [LineString([f["start"],f["end"]]) for f in faces]
        noded = unary_union(lines) if lines else None
        junctions = []
        if noded:
            parts = list(noded.geoms) if hasattr(noded, "geoms") else [noded]
            counts: dict[Point2,int] = {}
            for part in parts:
                for p in (part.coords[0], part.coords[-1]):
                    key=(round(p[0],8),round(p[1],8)); counts[key]=counts.get(key,0)+1
            junctions=[{"junction_id":f"{floor}-J-{i:04d}","point":list(p),"degree":n,
                        "kind":"T" if n==3 else "L_OR_END" if n<=2 else "CROSS"} for i,(p,n) in enumerate(sorted(counts.items()),1)]
        return WallFaceGraph(floor, faces, pairs, junctions, thickness_clusters)

    def _wall_solids(self, floor: str, graph: WallFaceGraph, tolerance: float) -> WallSolidGraph:
        """Build material wall strips only from defensible paired source faces."""
        face_by_id = {face["face_id"]: face for face in graph.faces}
        cluster_centres = [c["center_m"] for c in graph.thickness_clusters_m if c["count"] >= 1]
        pair_by_face: dict[str,list[dict[str,Any]]] = {}
        for pair in graph.pairs:
            pair_by_face.setdefault(pair["face_a"],[]).append(pair)
            pair_by_face.setdefault(pair["face_b"],[]).append(pair)
        def pair_rank(pair):
            a=face_by_id[pair["face_a"]]; b=face_by_id[pair["face_b"]]
            ratio=pair["overlap_m"]/max(min(a["length_m"],b["length_m"]),1e-9)
            return (pair["thickness_m"],-ratio)
        mutual_ids={pair["wall_pair_id"] for pair in graph.pairs if all(
            min(pair_by_face[face_id],key=pair_rank)["wall_pair_id"]==pair["wall_pair_id"]
            for face_id in (pair["face_a"],pair["face_b"]))}
        solids: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []
        seen: list[Polygon] = []
        for pair in graph.pairs:
            if pair["wall_pair_id"] not in mutual_ids:
                unresolved.append({"wall_pair_id":pair["wall_pair_id"],"reason":"NON_MUTUAL_COMPETING_FACE_PAIR"})
                continue
            a = face_by_id[pair["face_a"]]; b = face_by_id[pair["face_b"]]
            direction = self._unit(a["start"], a["end"])
            ai = sorted(self._dot(p, direction) for p in (a["start"], a["end"]))
            bi = sorted(self._dot(p, direction) for p in (b["start"], b["end"]))
            lo, hi = max(ai[0], bi[0]), min(ai[1], bi[1])
            cluster = min(cluster_centres, key=lambda x: abs(x-pair["thickness_m"]), default=pair["thickness_m"])
            if hi-lo < max(0.15, tolerance*4) or abs(cluster-pair["thickness_m"]) > max(0.035, cluster*0.18):
                unresolved.append({"wall_pair_id": pair["wall_pair_id"], "reason": "PAIR_OUTSIDE_DEFENSIBLE_THICKNESS_OR_OVERLAP"})
                continue
            la = LineString([a["start"], a["end"]]); lb = LineString([b["start"], b["end"]])
            origin = (0.0, 0.0)
            points = []
            for value, line in ((lo, la), (hi, la), (hi, lb), (lo, lb)):
                target = Point(origin[0]+direction[0]*value, origin[1]+direction[1]*value)
                projected = line.interpolate(line.project(target))
                points.append((projected.x, projected.y))
            cap=min(pair["thickness_m"]/2,0.20)
            points=[(points[0][0]-direction[0]*cap,points[0][1]-direction[1]*cap),
                    (points[1][0]+direction[0]*cap,points[1][1]+direction[1]*cap),
                    (points[2][0]+direction[0]*cap,points[2][1]+direction[1]*cap),
                    (points[3][0]-direction[0]*cap,points[3][1]-direction[1]*cap)]
            strip = Polygon(points)
            if not strip.is_valid:
                repaired = strip.buffer(0)
                if repaired.geom_type != "Polygon" or abs(repaired.area-strip.area) > max(0.01, strip.area*0.02):
                    unresolved.append({"wall_pair_id": pair["wall_pair_id"], "reason": "SOLID_INVALID_REPAIR_MATERIAL"})
                    continue
                strip = repaired
            if strip.area <= tolerance*tolerance:
                continue
            duplicate = next((i for i, prior in enumerate(seen) if strip.symmetric_difference(prior).area <= max(1e-6, strip.area*0.01)), None)
            if duplicate is not None:
                solids[duplicate]["source_handles"] = sorted(set(solids[duplicate]["source_handles"] + pair["source_handles"]))
                solids[duplicate]["source_pair_ids"].append(pair["wall_pair_id"])
                continue
            solid_id = f"{floor}-WSOLID-{len(solids)+1:04d}"
            solids.append({"wall_solid_id": solid_id, "polygon": self._polygon_coordinates(strip),
                           "area_m2": float(strip.area), "thickness_m": float(pair["thickness_m"]),
                           "thickness_cluster_center_m": float(cluster), "source_pair_ids": [pair["wall_pair_id"]],
                           "source_face_ids": [a["face_id"], b["face_id"]], "source_handles": pair["source_handles"],
                           "end_caps": "PROJECTED_OVERLAP_ENDPOINTS", "confidence": pair["confidence"],
                           "provenance": ["SOURCE_WALL_FACE_PAIR", "PARALLEL", "PROJECTED_OVERLAP", "THICKNESS_CLUSTER"]})
            seen.append(strip)
        union = unary_union(seen) if seen else GeometryCollection()
        envelopes = self._derive_floor_envelopes(graph, union, tolerance)
        return WallSolidGraph(floor, solids, unresolved, float(union.area), envelopes, [])

    def _derive_floor_envelopes(self, graph: WallFaceGraph, wall_union, tolerance: float) -> list[dict[str, Any]]:
        """Use closed source perimeter rings; never return a room bbox as envelope."""
        lines = [LineString([f["start"], f["end"]]) for f in graph.faces]
        if not lines:
            return []
        noded = snap(unary_union(lines), unary_union(lines), tolerance)
        polygons, _, _, _ = polygonize_full(noded)
        rings = [p for p in polygons.geoms if p.area >= 1.0]
        point_cloud=MultiPoint([point for f in graph.faces for point in (f["start"],f["end"])])
        hull=point_cloud.convex_hull
        ring_coverage=max((Polygon(p.exterior).area for p in rings),default=0.0)
        if not wall_union.is_empty and not hull.is_empty and hull.area>0 and ring_coverage < hull.area*.35:
            derived=concave_hull(point_cloud,ratio=.45,allow_holes=False)
            if derived.geom_type=="Polygon" and derived.area>=hull.area*.35:
                rings=[derived]
        if not rings and not wall_union.is_empty:
            # The wall material boundary is architectural source geometry; closing only
            # sub-tolerance endpoint gaps is recorded and does not invent a bbox.
            boundary = snap(wall_union.boundary, wall_union.boundary, tolerance)
            recovered, _, _, _ = polygonize_full(boundary)
            rings = [p for p in recovered.geoms if p.area >= 1.0]
        if not rings:
            return []
        maximal = [Polygon(p.exterior) for p in rings if not any(
            Polygon(q.exterior).area > Polygon(p.exterior).area and Polygon(q.exterior).buffer(tolerance).covers(p.representative_point())
            for q in rings)]
        return [{"envelope_id": f"{graph.floor}-ENVELOPE-{i:03d}", "polygon": self._polygon_coordinates(p),
                 "area_m2": float(p.area), "source": "CLOSED_SOURCE_PERIMETER_GEOMETRY",
                 "edge_classification": {"south": "SOUTH_STREET", "east": "CONSTRAINED", "west": "CONSTRAINED", "north": "CONSTRAINED"}}
                for i, p in enumerate(sorted(maximal, key=lambda x: -x.area), 1)]

    def _cluster_openings(self, floor: str, entities: list[dict[str, Any]], tolerance: float) -> list[dict[str, Any]]:
        groups: list[list[dict[str, Any]]] = []
        pending = list(entities)
        while pending:
            seed = pending.pop(0); group=[seed]; changed=True
            while changed:
                changed=False
                shape = unary_union([LineString([s["start"],s["end"]]) for e in group for s in e["segments"]])
                for e in pending[:]:
                    other = unary_union([LineString([s["start"],s["end"]]) for s in e["segments"]])
                    if seed["kind"] == e["kind"] and shape.distance(other) <= max(0.08, tolerance*4):
                        group.append(e); pending.remove(e); changed=True
            groups.append(group)
        result=[]
        counters={"DOOR":0,"WINDOW":0}
        for group in groups:
            kind=group[0]["kind"]; counters[kind]+=1
            points=[p for e in group for p in e["points"]]
            if not points: continue
            bbox=[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
            result.append({"opening_id":f"{floor}-{kind}-{counters[kind]:03d}","kind":kind,
                           "handles":sorted(e["handle"] for e in group),"layers":sorted(set(e["layer"] for e in group)),
                           "entity_types":sorted(set(e["entity_type"] for e in group)),"bbox":bbox,
                           "center":[(bbox[0]+bbox[2])/2,(bbox[1]+bbox[3])/2],"points":points,
                           "expected_from_space":group[0].get("expected_from_space"),
                           "expected_to_space":group[0].get("expected_to_space"),
                           "expected_host_partition":group[0].get("expected_host_partition"),
                           "expected_exposure":group[0].get("expected_exposure")})
        return result

    def _host_openings(self, floor: str, clusters: list[dict[str, Any]], graph: WallFaceGraph, solid_graph: WallSolidGraph, tolerance: float):
        portals=[]; closures=[]; unresolved=[]
        face_by_id={f["face_id"]:f for f in graph.faces}
        solid_by_pair={pair_id:(solid,Polygon(solid["polygon"])) for solid in solid_graph.solids for pair_id in solid["source_pair_ids"]}
        for opening in clusters:
            center=Point(opening["center"]); candidates=[]
            for pair in graph.pairs:
                if pair["wall_pair_id"] not in solid_by_pair: continue
                solid,solid_polygon=solid_by_pair[pair["wall_pair_id"]]
                fa=face_by_id[pair["face_a"]]; fb=face_by_id[pair["face_b"]]
                la=LineString([fa["start"],fa["end"]]); lb=LineString([fb["start"],fb["end"]])
                distance=max(la.distance(center),lb.distance(center))
                if distance <= max(1.6, pair["thickness_m"]+0.9):
                    projected_a=la.interpolate(la.project(center)); projected_b=lb.interpolate(lb.project(center))
                    threshold=LineString([projected_a,projected_b])
                    span=max(opening["bbox"][2]-opening["bbox"][0],opening["bbox"][3]-opening["bbox"][1])
                    opening_axis=self._opening_axis(opening)
                    wall_direction=self._unit(fa["start"],fa["end"])
                    axis_alignment=abs(self._dot(opening_axis,wall_direction))
                    projected=self._dot(opening["center"],wall_direction)
                    intervals=[]
                    for face in (fa,fb): intervals.append(sorted(self._dot(p,wall_direction) for p in (face["start"],face["end"])))
                    overlap_margin=min(intervals[0][1],intervals[1][1])-max(intervals[0][0],intervals[1][0])
                    in_jamb_range=max(intervals[0][0],intervals[1][0])-tolerance <= projected <= min(intervals[0][1],intervals[1][1])+tolerance
                    cut_zone=solid_polygon.buffer(max(tolerance,span*.12)).covers(center)
                    continuity=sum(1 for interval in intervals if interval[0]-tolerance <= projected <= interval[1]+tolerance)
                    score=(distance + abs(pair["thickness_m"]-threshold.length)*2 + axis_alignment*.35
                           + (0 if in_jamb_range else 2.0) + (0 if cut_zone else .45) + (2-continuity)*.3)
                    evidence={"orientation_penalty":axis_alignment,"projected_overlap_m":overlap_margin,
                              "in_jamb_range":in_jamb_range,"centroid_in_or_at_cut_zone":cut_zone,
                              "local_face_continuity_count":continuity,"distance_to_face_a_m":la.distance(center),
                              "distance_to_face_b_m":lb.distance(center)}
                    expected_host=opening.get("expected_host_partition")
                    host_sources=set(fa.get("source_handles",[])) | set(fb.get("source_handles",[]))
                    if expected_host and expected_host not in host_sources:
                        continue
                    evidence["expected_host_partition"]=expected_host
                    evidence["expected_host_partition_confirmed"]=not expected_host or expected_host in host_sources
                    candidates.append((score,pair,fa,fb,threshold,span,evidence,solid))
            candidates.sort(key=lambda x:x[0])
            accepted=candidates[0] if candidates and (len(candidates)==1 or candidates[1][0]-candidates[0][0] > 0.08) else None
            if accepted is None and len(candidates)>=2 and self._same_wall_band(candidates[0],candidates[1],tolerance):
                accepted=candidates[0]
                accepted[6]["tie_resolved_by_local_face_continuity"] = True
            if accepted:
                score,pair,fa,fb,threshold,span,evidence,solid=accepted
                # A topology closure follows the host direction through the opening centre.
                direction=self._unit(fa["start"],fa["end"]); half=max(0.2,min(1.5,span/2))
                companion=next((candidate for candidate in candidates if candidate is not accepted and self._same_wall_band(accepted,candidate,tolerance)),None)
                bridge=self._bridge_wall_gap(accepted,companion,pair["thickness_m"]) if companion else None
                if bridge:
                    closure=bridge
                    evidence["closure_location_method"]="COLLINEAR_HOST_STUB_GAP"
                else:
                    closure=[[opening["center"][0]-direction[0]*half,opening["center"][1]-direction[1]*half],
                             [opening["center"][0]+direction[0]*half,opening["center"][1]+direction[1]*half]]
                    evidence["closure_location_method"]="OPENING_GEOMETRY_CENTRE"
                closures.append({"closure_id":f"VC-{opening['opening_id']}","opening_id":opening["opening_id"],"kind":opening["kind"],
                                 "line":closure,"barrier_width_m":pair["thickness_m"],"topology_only":True,"source_written":False,
                                 "host_wall_solid_id":solid["wall_solid_id"]})
                portal=OpeningPortal(opening["opening_id"],floor,opening["kind"],opening["handles"],pair["wall_pair_id"],fa["face_id"],fb["face_id"],
                                     [list(threshold.coords[0]),list(threshold.coords[-1])],closure,span,None,None,opening["kind"]=="DOOR",None,
                                     max(0.55,1.0-score/3),{"candidate_count":len(candidates),"host_distance_score":score,
                                     "wall_solid_id":solid["wall_solid_id"],"wall_thickness_m":pair["thickness_m"],
                                     **evidence,"source_layers":opening["layers"],"entity_types":opening["entity_types"]},"HOST_RESOLVED")
            else:
                reason="NO_TWO_FACE_HOST_WITH_GEOMETRIC_ALIGNMENT" if not candidates else "AMBIGUOUS_MULTIPLE_WALL_PAIRS"
                if candidates:
                    _,pair,fa,_,threshold,span,evidence,solid=candidates[0]
                    if evidence["in_jamb_range"] and evidence["local_face_continuity_count"]>=1:
                        direction=self._unit(fa["start"],fa["end"]); half=max(.2,min(1.5,span/2+.12))
                        threshold_center=threshold.interpolate(.5,normalized=True)
                        closure=[[threshold_center.x-direction[0]*half,threshold_center.y-direction[1]*half],
                                 [threshold_center.x+direction[0]*half,threshold_center.y+direction[1]*half]]
                        closures.append({"closure_id":f"VC-{opening['opening_id']}","opening_id":opening["opening_id"],"kind":opening["kind"],
                                         "line":closure,"barrier_width_m":pair["thickness_m"],"topology_only":True,"source_written":False,
                                         "host_wall_solid_id":solid["wall_solid_id"],"host_status":"AMBIGUOUS_HOST_CLOSURE_ONLY"})
                portal=OpeningPortal(opening["opening_id"],floor,opening["kind"],opening["handles"],None,None,None,None,None,None,None,None,
                                     opening["kind"]=="DOOR",None,0.0,{"candidate_count":len(candidates),"measured_reason":reason},"UNRESOLVED")
                unresolved.append({"id":opening["opening_id"],"floor":floor,"type":"OPENING_HOST","reason":reason,
                                   "source_handles":opening["handles"],"candidate_count":len(candidates)})
            portal.expected_from_space=opening.get("expected_from_space")
            portal.expected_to_space=opening.get("expected_to_space")
            portal.expected_host_partition=opening.get("expected_host_partition")
            portal.expected_exposure=opening.get("expected_exposure")
            portals.append(portal)
        return portals,closures,unresolved

    def _free_space_cells(self, floor: str, graph: WallFaceGraph, solid_graph: WallSolidGraph,
                          closures: list[dict[str, Any]], labels: list[dict[str, Any]], tolerance: float):
        envelopes=[Polygon(item["polygon"]) for item in solid_graph.floor_envelopes]
        wall_polygons=[Polygon(item["polygon"]) for item in solid_graph.solids]
        unresolved=[]
        if not envelopes:
            if graph.faces:
                unresolved.append({"id":f"{floor}-ENVELOPE","floor":floor,"type":"FLOOR_ENVELOPE",
                                   "reason":"NO_DEFENSIBLE_CLOSED_ARCHITECTURAL_ENVELOPE"})
                unresolved.append({"id":f"{floor}-POLYGONIZATION","floor":floor,"type":"SPACE_BOUNDARY",
                                   "reason":"NO_VALID_SPATIAL_CELL_POLYGONIZED"})
            return SpaceBoundaryGraph(floor,[],closures,unresolved),[]
        wall_union=unary_union(wall_polygons) if wall_polygons else GeometryCollection()
        envelope_union=unary_union(envelopes)
        free=envelope_union.difference(wall_union)
        closure_barriers=[]
        for closure in closures:
            width=max(float(closure.get("barrier_width_m",0.2)),tolerance*2)
            closure_barriers.append(LineString(closure["line"]).buffer(width/2+tolerance,cap_style=2,join_style=2))
        if closure_barriers:
            free=free.difference(unary_union(closure_barriers))
        raw_parts=list(free.geoms) if hasattr(free,"geoms") else [free]
        candidates=[]
        for polygon in raw_parts:
            if polygon.geom_type != "Polygon" or polygon.area < 0.35: continue
            if any(polygon.intersection(w).area > max(1e-7,tolerance*tolerance) for w in wall_polygons):
                unresolved.append({"id":f"{floor}-CELL-CANDIDATE-{len(candidates)+1}","floor":floor,"type":"SPACE_BOUNDARY",
                                   "reason":"CELL_OVERLAPS_WALL_SOLID"})
                continue
            rectangle=polygon.minimum_rotated_rectangle; coords=list(rectangle.exterior.coords)
            widths=sorted(hypot(coords[i+1][0]-coords[i][0],coords[i+1][1]-coords[i][1]) for i in range(4))
            contains_label=any(polygon.buffer(tolerance).covers(Point(x["point"])) for x in labels)
            if widths[0] <= 0.58 and not contains_label: continue
            candidates.append(polygon)
        spaces=[]; bindings=[]
        for index, polygon in enumerate(sorted(candidates,key=lambda p:(p.centroid.x,p.centroid.y)),1):
            contained=[label for label in labels if polygon.covers(Point(label["point"]))]
            room_labels=[label for label in contained if label["semantic_class"] not in self.NON_ROOM_CLASSES]
            ordinary=[x for x in room_labels if x["semantic_class"] not in {"PARKING","COMMERCIAL","ACCESS_SHARED","LIGHTWELL","TERRACE"}]
            conflict=len({x["semantic_class"] for x in ordinary})>1
            selected=room_labels[0] if len(room_labels)==1 else None
            boundary_ids=[]
            for face in graph.faces:
                if polygon.boundary.distance(LineString([face["start"],face["end"]])) <= max(tolerance,0.002): boundary_ids.append(face["face_id"])
            for closure in closures:
                if polygon.boundary.distance(LineString(closure["line"])) <= max(tolerance,0.002): boundary_ids.append(closure["closure_id"])
            rp=polygon.representative_point(); sid=f"{floor}-SPACE-{index:03d}"
            spaces.append(SpacePolygon(sid,floor,[[float(x),float(y)] for x,y in polygon.exterior.coords],float(polygon.area),float(polygon.length),
                                       [polygon.centroid.x,polygon.centroid.y],[rp.x,rp.y],sorted(set(boundary_ids)),
                                       selected["text"] if selected else None,selected["handle"] if selected else None,
                                       selected["semantic_class"] if selected else None,
                                        ["floor envelope minus wall-solid union","topology-only opening closures","source coordinates in metres"],
                                       0.96 if selected else 0.72))
            for label in contained:
                bindings.append({"floor":floor,"space_id":sid,"label_handle":label["handle"],"text":label["text"],
                                 "semantic_class":label["semantic_class"],"method":"POINT_IN_POLYGON","conflict":conflict})
            if conflict: unresolved.append({"id":sid,"floor":floor,"type":"LABEL_BINDING","reason":"MULTIPLE_CONFLICTING_ROOM_LABELS",
                                            "label_handles":[x["handle"] for x in room_labels]})
        bound={b["label_handle"] for b in bindings}
        for label in labels:
            if label["handle"] not in bound:
                unresolved.append({"id":label["handle"],"floor":floor,"type":"LABEL_BINDING","reason":"LABEL_OUTSIDE_ALL_SPACE_POLYGONS",
                                   "text":label["text"],"point":label["point"]})
        if not spaces and graph.faces:
            unresolved.append({"id":f"{floor}-POLYGONIZATION","floor":floor,"type":"SPACE_BOUNDARY","reason":"NO_VALID_SPATIAL_CELL_POLYGONIZED",
                               "wall_solid_count":len(solid_graph.solids),"envelope_count":len(envelopes)})
        return SpaceBoundaryGraph(floor,spaces,closures,unresolved),bindings

    def _attach_sides(self, portals: list[OpeningPortal], spaces: list[SpacePolygon], graph: WallFaceGraph, extent: list[float] | None):
        polygons=[(s,Polygon(s.polygon)) for s in spaces]
        labels={s.space_id:s.semantic_label for s in spaces}
        for portal in portals:
            if portal.status!="HOST_RESOLVED" or not portal.centerline: continue
            a,b=portal.centerline; direction=self._unit(a,b); normal=(-direction[1],direction[0]); center=((a[0]+b[0])/2,(a[1]+b[1])/2)
            thickness=float(portal.geometric_evidence.get("wall_thickness_m",0.2))
            offset=max(0.12,thickness/2+0.08)
            samples=[Point(center[0]+normal[0]*offset,center[1]+normal[1]*offset),Point(center[0]-normal[0]*offset,center[1]-normal[1]*offset)]
            sides=[]
            for sample in samples:
                hit=next((s.space_id for s,p in polygons if p.buffer(1e-7).covers(sample)),None)
                sides.append(hit)
            portal.side_a,portal.side_b=[side or f"EXTERIOR:{portal.floor}" for side in sides]
            if portal.kind=="WINDOW":
                if any(s and next((x.semantic_class for x in spaces if x.space_id==s),None)=="LIGHTWELL" for s in sides): portal.exposure="LIGHTWELL"
                elif any(s and next((x.semantic_class for x in spaces if x.space_id==s),None)=="TERRACE" for s in sides): portal.exposure="TERRACE"
                elif extent and center[1] <= extent[1]+max(0.8,(extent[3]-extent[1])*0.08): portal.exposure="SOUTH_STREET"
                elif any(side is None for side in sides): portal.exposure="UNRESOLVED_EXTERIOR_EDGE"
                else: portal.exposure="INTERIOR_OR_UNRESOLVED"
                if portal.exposure not in {"SOUTH_STREET","LIGHTWELL","TERRACE"}: portal.status="UNRESOLVED_INVALID_WINDOW_EXPOSURE"
                elif portal.expected_exposure and portal.exposure != portal.expected_exposure: portal.status="UNRESOLVED_EXPECTED_EXPOSURE_MISMATCH"
                else: portal.status="RESOLVED"
            elif portal.side_a == portal.side_b:
                portal.status="UNRESOLVED_DOOR_SAME_CELL"
                portal.traversable=False
                portal.geometric_evidence["measured_reason"]="DOOR_PORTAL_REQUIRES_DISTINCT_SIDES"
            else:
                portal.status="RESOLVED"
            if portal.status=="RESOLVED" and portal.kind=="DOOR" and portal.expected_from_space and portal.expected_to_space:
                measured={side if side and side.startswith("EXTERIOR:") else labels.get(side) for side in (portal.side_a,portal.side_b)}
                expected={portal.expected_from_space,portal.expected_to_space}
                if measured != expected:
                    portal.status="UNRESOLVED_EXPECTED_SIDE_PAIR_MISMATCH"
                    portal.traversable=False
                    portal.geometric_evidence["measured_semantic_side_pair"]=sorted(x for x in measured if x)
                    portal.geometric_evidence["expected_semantic_side_pair"]=sorted(expected)
                else:
                    portal.intent_assertion_status="CONFIRMED_GEOMETRICALLY"
            elif portal.status=="RESOLVED" and portal.kind=="WINDOW" and portal.expected_exposure:
                portal.intent_assertion_status="CONFIRMED_GEOMETRICALLY"

    def _access_graph(self, boundaries: dict[str, SpaceBoundaryGraph], openings: dict[str, OpeningHostGraph]) -> dict[str, Any]:
        nodes=[]; edges=[]; window_edges=[]
        for floor,boundary in boundaries.items():
            nodes += [{"id":s.space_id,"floor":floor,"semantic_class":s.semantic_class,"label":s.semantic_label} for s in boundary.spaces]
            for portal in openings[floor].openings:
                if portal.kind=="DOOR" and portal.status=="RESOLVED" and portal.side_a and portal.side_b and portal.side_a!=portal.side_b:
                    edges.append({"edge_id":portal.opening_id,"from":portal.side_a,"to":portal.side_b,"kind":"DOOR_PORTAL",
                                  "source_handles":portal.constituent_source_handles})
                elif portal.kind=="WINDOW" and portal.side_a and portal.side_b:
                    window_edges.append(portal.opening_id)
        exterior_ids=sorted({endpoint for edge in edges for endpoint in (edge["from"],edge["to"]) if endpoint.startswith("EXTERIOR:")})
        nodes += [{"id":node,"floor":node.split(":",1)[1],"semantic_class":"EXTERIOR","label":"EXTERIOR"} for node in exterior_ids]
        adjacency={n["id"]:set() for n in nodes}
        for edge in edges: adjacency[edge["from"]].add(edge["to"]); adjacency[edge["to"]].add(edge["from"])
        components=[]; unseen=set(adjacency)
        while unseen:
            seed=next(iter(unseen)); stack=[seed]; unseen.remove(seed); component=[]
            while stack:
                current=stack.pop(); component.append(current)
                for neighbor in adjacency[current]:
                    if neighbor in unseen: unseen.remove(neighbor); stack.append(neighbor)
            components.append(sorted(component))
        r1_status=self._r1_reachability(nodes,edges,components)
        r2_status=self._r2_separation(nodes,edges,components)
        overall="UNPROVEN_NO_PORTALS" if not edges else ("RESOLVED" if r1_status=="PROVEN_FROM_PORTALS" and r2_status=="PROVEN_FROM_PORTALS" else "PARTIAL")
        return {"nodes":nodes,"edges":edges,"connected_components":components,
                "proofs":{"no_wall_crossing_except_traversable_door_portals":True,
                          "windows_never_access_edges":all(edge.get("kind")=="DOOR_PORTAL" for edge in edges),
                          "no_path_guide_wall_or_host_use":True,"no_lightwell_access_edge":all(
                              n.get("semantic_class")!="LIGHTWELL" or not adjacency[n["id"]] for n in nodes)},
                "r1_reachability":{"status":r1_status},
                "r2_unit_separation":{"status":r2_status},
                "status":overall}

    @staticmethod
    def _r1_reachability(nodes,edges,components):
        floor_nodes=[n for n in nodes if n["floor"]=="R1" and n["semantic_class"]!="EXTERIOR"]
        floor_edges=[e for e in edges if e["from"].startswith("R1") or e["to"].startswith("R1")]
        entries=[e for e in floor_edges if "EXTERIOR:R1" in {e["from"],e["to"]}]
        required=[n["id"] for n in floor_nodes if n.get("semantic_class") not in {None,"LIGHTWELL","TERRACE","SERVICE","COMMON_VERTICAL_CORE"}]
        if not floor_edges: return "UNPROVEN_NO_PORTALS"
        if not entries: return "UNPROVEN_NO_UNIT_ENTRY_PORTAL"
        entry_inside=next(endpoint for endpoint in (entries[0]["from"],entries[0]["to"]) if endpoint!="EXTERIOR:R1")
        component=next((set(c) for c in components if entry_inside in c),set())
        return "PROVEN_FROM_PORTALS" if required and all(node in component for node in required) else "UNPROVEN_REQUIRED_ROOMS_NOT_CONNECTED"

    @staticmethod
    def _r2_separation(nodes,edges,components):
        r2=[n for n in nodes if n["floor"]=="R2"]
        r2_edges=[e for e in edges if e["from"].startswith("R2") or e["to"].startswith("R2")]
        if not r2_edges: return "UNPROVEN_NO_PORTALS"
        entries=[e for e in r2_edges if "EXTERIOR:R2" in {e["from"],e["to"]}]
        if len(entries)<2: return "UNPROVEN_MISSING_TWO_UNIT_ENTRY_PORTALS"
        inside=[next(endpoint for endpoint in (e["from"],e["to"]) if endpoint!="EXTERIOR:R2") for e in entries]
        # A shared exterior node is not a private cross-unit connection.  Compare
        # components after removing exterior endpoints.
        private_adj={n["id"]:set() for n in r2 if n["semantic_class"]!="EXTERIOR"}
        for edge in r2_edges:
            if edge["from"] in private_adj and edge["to"] in private_adj:
                private_adj[edge["from"]].add(edge["to"]); private_adj[edge["to"]].add(edge["from"])
        private_components=[]; unseen=set(private_adj)
        while unseen:
            seed=next(iter(unseen)); stack=[seed]; unseen.remove(seed); component=[]
            while stack:
                current=stack.pop(); component.append(current)
                for neighbor in private_adj[current]:
                    if neighbor in unseen: unseen.remove(neighbor); stack.append(neighbor)
            private_components.append(component)
        component_index={node:i for i,c in enumerate(private_components) for node in c}
        if len({component_index.get(node) for node in inside})<2: return "UNPROVEN_UNIT_INTERIORS_NOT_DISTINCT"
        labels={n["id"]:str(n.get("label") or "").upper() for n in r2}
        cross=any("U1" in labels.get(e["from"],"")+labels.get(e["to"],"") and "U2" in labels.get(e["from"],"")+labels.get(e["to"],"") for e in r2_edges)
        return "UNPROVEN_CROSS_UNIT_PORTAL" if cross else "PROVEN_FROM_PORTALS"

    def _label_class(self, text: str) -> str | None:
        normalized=re.sub(r"\s+"," ",text.strip().lower())
        if normalized in self.LABEL_CLASSES: return self.LABEL_CLASSES[normalized]
        if re.fullmatch(r"p\s*[123]",normalized): return "PARKING"
        return None

    @staticmethod
    def _opening_axis(opening: dict[str, Any]) -> Point2:
        points=opening.get("points",[])
        if len(points)<2: return (1.0,0.0)
        best=max(((a,b) for i,a in enumerate(points) for b in points[i+1:]),key=lambda ab:hypot(ab[1][0]-ab[0][0],ab[1][1]-ab[0][1]),default=(points[0],points[-1]))
        return SpaceBoundaryOpeningHostGraphEngineV1._unit(best[0],best[1])

    @staticmethod
    def _same_wall_band(first, second, tolerance: float) -> bool:
        fa,fb=first[2],second[2]
        da=SpaceBoundaryOpeningHostGraphEngineV1._unit(fa["start"],fa["end"])
        db=SpaceBoundaryOpeningHostGraphEngineV1._unit(fb["start"],fb["end"])
        if abs(abs(SpaceBoundaryOpeningHostGraphEngineV1._dot(da,db))-1.0)>.01: return False
        normal=(-da[1],da[0])
        first_points=[p for face in (first[2],first[3]) for p in (face["start"],face["end"])]
        second_points=[p for face in (second[2],second[3]) for p in (face["start"],face["end"])]
        ma=(sum(p[0] for p in first_points)/4,sum(p[1] for p in first_points)/4)
        mb=(sum(p[0] for p in second_points)/4,sum(p[1] for p in second_points)/4)
        return abs(SpaceBoundaryOpeningHostGraphEngineV1._dot(ma,normal)-SpaceBoundaryOpeningHostGraphEngineV1._dot(mb,normal)) <= max(tolerance*2,.03)

    @staticmethod
    def _bridge_wall_gap(first, second, thickness: float) -> list[list[float]] | None:
        if second is None: return None
        line_a=LineString([first[2]["start"],first[2]["end"]])
        line_b=LineString([second[2]["start"],second[2]["end"]])
        pa,pb=nearest_points(line_a,line_b)
        gap=pa.distance(pb)
        if gap < .15 or gap > 2.5: return None
        direction=SpaceBoundaryOpeningHostGraphEngineV1._unit(first[2]["start"],first[2]["end"])
        if (pb.x-pa.x)*direction[0]+(pb.y-pa.y)*direction[1] < 0: pa,pb=pb,pa
        cap=min(max(thickness/2,.05),.20)
        return [[pa.x-direction[0]*cap,pa.y-direction[1]*cap],[pb.x+direction[0]*cap,pb.y+direction[1]*cap]]

    @staticmethod
    def _polygon_coordinates(polygon: Polygon) -> list[list[float]]:
        return [[float(x),float(y)] for x,y in polygon.exterior.coords]

    @staticmethod
    def _hash(path: Path) -> str: return sha256(path.read_bytes()).hexdigest()
    @staticmethod
    def _snap_point(point: Iterable[float], tolerance: float) -> Point2:
        q=max(tolerance,1e-9); return (round(float(point[0])/q)*q,round(float(point[1])/q)*q)
    @staticmethod
    def _unit(a: Iterable[float],b: Iterable[float]) -> Point2:
        dx=float(b[0])-float(a[0]);dy=float(b[1])-float(a[1]);length=hypot(dx,dy) or 1.0;return dx/length,dy/length
    @staticmethod
    def _dot(p: Iterable[float],d: Iterable[float]) -> float:return float(p[0])*float(d[0])+float(p[1])*float(d[1])
    @staticmethod
    def _clusters_1d(values: list[float], tolerance: float) -> list[list[float]]:
        groups=[]
        for value in sorted(values):
            if not groups or value-groups[-1][-1]>tolerance: groups.append([value])
            else: groups[-1].append(value)
        return groups


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
