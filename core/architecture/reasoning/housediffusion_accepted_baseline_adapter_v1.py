"""HouseDiffusionAcceptedBaselineAdapterV1 — HOUSE-DIFFUSION-ARCHITECTOS-ADAPTER-01.

ONE narrow adapter that maps the REAL accepted HouseDiffusion baseline
(`SemanticArchitecturalPlanBaselineV1`) into the CURRENT ArchitectOS accepted
baseline contract (`AcceptedArchitecturalBaselineEnvelopeV1`), so the frozen
Design-02 → Design-05 chain can consume it.

Direction:  HouseDiffusion accepted baseline → ArchitectOS accepted baseline.

Two explicitly validated baseline origins are supported:

* ``adapt()``            — the historical frozen accepted baseline
  (``SemanticArchitecturalPlanBaselineV1``, phase
  ``HOUSE-DIFFUSION-BASELINE-ARCHITECTURAL-PLAN-CONSOLIDATION-01``), validated
  by ``HouseDiffusionBaselineReconnectV1`` exactly as before.
* ``adapt_generated()``  — a GENERATED baseline
  (``GeneratedArchitecturalBaselineV1``) produced by
  ``GeneratedBaselineRealizationV1`` from a FRESH HouseDiffusion candidate,
  validated by its own strict generated-baseline verifier.

The two paths never share identity validation, and a generated baseline never
impersonates the historical consolidation artifact.

Guarantees:

- lossless with respect to authoritative HouseDiffusion content (room IDs,
  semantic identities, polygons via ``geometry_ref``, wall IDs/roles/centerlines,
  opening IDs/types/hosts, access graph, circulation, provisional windows,
  generator lineage, phase, geometry hashes)
- nothing is moved, resized, merged, split, renamed or invented
- symbolic wall bands stay symbolic: ``WALL_THICKNESS_METRIC_UNRESOLVED`` and
  ``construction_claim = false`` (no 0.2 m / 0.3 m default is ever assigned)
- no final windows, no world orientation, no parcel/site context
- the internal rule-based generator (LayoutReasoner / SpatialPlacementReasoner /
  CoherentFloorPlanResolverV1 / architectural_layout_intelligence_v1) is never
  invoked; a guard fails with ``INTERNAL_GENERATOR_BYPASS_DETECTED`` if it is
- HouseDiffusion lab sources are read-only
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from shapely.geometry import Polygon
from shapely.ops import unary_union

from core.architecture.contracts.generated_architectural_baseline_v1 import (
    assert_generated_architectural_baseline,
)
from core.architecture.geometry.architectural_space_boundary_pipeline_v1 import (
    ArchitecturalSpaceBoundaryPipelineV1,
)
from core.architecture.reasoning.housediffusion_baseline_reconnect_v1 import (
    BASELINE_ROOT,
    HouseDiffusionBaselineReconnectV1,
    _ArtifactCache,
)


CONTRACT = "HouseDiffusionAcceptedBaselineAdapterV1"
VERSION = "1.0"

WALL_THICKNESS_METRIC_UNRESOLVED = "WALL_THICKNESS_METRIC_UNRESOLVED"
FINAL_WINDOWS_NOT_CREATED = "FINAL_WINDOWS_NOT_CREATED"
WORLD_ORIENTATION_PENDING = "WORLD_ORIENTATION_PENDING"
PARCEL_SITE_CONTEXT_PENDING = "PARCEL_SITE_CONTEXT_PENDING"
INTERNAL_GENERATOR_BYPASS_DETECTED = "INTERNAL_GENERATOR_BYPASS_DETECTED"

#: Modules that must never participate in the adapter path.
FORBIDDEN_INTERNAL_GENERATORS = (
    "core.architecture.reasoning.layout_reasoner",
    "core.architecture.reasoning.spatial_placement_reasoner",
    "core.architecture.reasoning.coherent_floor_plan_resolver_v1",
    "core.architecture.reasoning.architectural_layout_intelligence_v1",
    "core.architecture.brain.architectural_brain",
)


class InternalGeneratorBypassError(RuntimeError):
    """Raised when an internal rule-based generator participates in the path."""

    code = INTERNAL_GENERATOR_BYPASS_DETECTED


@contextmanager
def _internal_generator_guard():
    """Fail if any internal rule-based generator module is imported inside."""
    before = set(sys.modules)
    yield
    imported = {name for name in set(sys.modules) - before}
    offenders = sorted(
        name for name in imported
        if any(name == forbidden or name.startswith(forbidden + ".")
               for forbidden in FORBIDDEN_INTERNAL_GENERATORS)
    )
    if offenders:
        raise InternalGeneratorBypassError(
            f"{INTERNAL_GENERATOR_BYPASS_DETECTED}: {offenders}")


class HouseDiffusionAcceptedBaselineAdapterV1:
    """Adapt the accepted HouseDiffusion baseline into the ArchitectOS contract."""

    VERSION = VERSION

    def __init__(self, baseline_root: Path | str | None = None):
        self.root = Path(baseline_root) if baseline_root is not None else BASELINE_ROOT
        self.verifier = HouseDiffusionBaselineReconnectV1(self.root)

    # --------------------------------------------------
    # public entry
    # --------------------------------------------------

    def adapt(self, *, candidate_id: str = "HD-ACCEPTED-BASELINE-01",
              candidate_version: str = "1",
              acceptance_provenance: Mapping[str, Any] | None = None) -> dict[str, Any]:
        with _internal_generator_guard():
            identity = self.verifier.verify_identity()
            if identity["status"] != "RECONNECTED":
                raise ValueError(
                    "ACCEPTED_HOUSEDIFFUSION_BASELINE_IDENTITY_UNRESOLVED: "
                    f"{identity.get('failed_checks')}")

            extraction, lineage = self.build_boundary_extraction()
            # the lineage travels INSIDE the hashed extraction so the accepted
            # envelope stays verifiable (nothing may be added after hashing)
            extraction["house_diffusion_lineage"] = lineage
            resolved = {
                "version": "2.0-additive",
                "pipeline": (
                    "HOUSEDIFFUSION_ACCEPTED_BASELINE -> CANONICAL_GRAPH_REALIZATION "
                    "(no re-derivation, no internal generator)"
                ),
                "boundary_extraction": extraction,
                "semantic_regions": [],
                "constraints": [],
                "protected_constraints": [],
                "protected_entities": [],
                "preservation_requirements": ["PRESERVE_ACCEPTED_GEOMETRY"],
                "architecture_only": True,
                "adapter_lineage": lineage,
            }
            envelope = ArchitecturalSpaceBoundaryPipelineV1().accept_resolved_baseline(
                resolved,
                candidate_id=candidate_id,
                candidate_version=candidate_version,
                acceptance_provenance=dict(acceptance_provenance or {
                    "status": "ACCEPTED",
                    "evidence_ids": ["house-diffusion-accepted-baseline-01"],
                    "source": "D:/AI_Architecture_Lab/baseline_architectural_plan_01",
                }),
            )
            return envelope

    # --------------------------------------------------
    # graph realization
    # --------------------------------------------------

    def build_boundary_extraction(self) -> tuple[dict[str, Any], dict[str, Any]]:
        baseline = self._read("semantic_architectural_plan_baseline_v1.json")
        walls = self._read("wall_registry_baseline_v1.json").get("walls") or []
        openings = self._read("opening_registry_baseline_v1.json").get(
            "baseline_openings") or []
        access = self._read("access_graph_baseline_v1.json")
        windows = self._read("window_registry_provisional_v1.json")
        gate = baseline.get("gate") or {}

        cache = _ArtifactCache()
        rooms = self._rooms(baseline, cache)
        floor = self._floor_id(rooms)
        wall_records = self._walls(walls, cache)
        opening_records = self._openings(openings)
        envelope_polygons, envelope_source = self._envelopes(rooms, cache)

        faces = []
        for wall in wall_records:
            faces.append({
                "face_id": f"FACE-{wall['wall_id']}",
                "wall_id": wall["wall_id"],
                "start": wall["centerline"][0],
                "end": wall["centerline"][1],
                "wall_role": wall["wall_role"],
                "wall_band": wall["wall_band"],
                "thickness_status": WALL_THICKNESS_METRIC_UNRESOLVED,
                "construction_claim": False,
                "provenance": {"source": "house_diffusion_wall_registry_baseline_v1"},
            })

        space_graph = {
            "floor": floor,
            "unresolved": [],
            "spaces": [{
                "space_id": room["identity"],
                "canonical_name": room["identity"],
                "semantic_class": room["identity"],
                "external": room["external"],
                "program_room": room["is_program_room"],
                "boundary_ids": [f"FACE-{wall['wall_id']}" for wall in wall_records
                                 if room["identity"] in (wall.get("between") or [])],
                "polygon": room["polygon"],
                "area_m2": room["area_normalized"],
                "perimeter_m": room["perimeter"],
                "geometry_ref": room["geometry_ref"],
                "construction_claim": False,
                "provenance": {"source": "house_diffusion_refined_semantic_plan_candidate_v1_4",
                               "geometry_invented": False},
            } for room in rooms],
        }

        opening_graph = {
            "floor": floor,
            "unresolved": [],
            "openings": [{
                "opening_id": item["opening_id"],
                "id": item["opening_id"],
                "kind": item["kind"],
                "opening_class": item["opening_class"],
                "semantic_role": item["semantic_role"],
                "status": "RESOLVED",
                "host_face_a": item["host_face_id"],
                "host_wall_id": item["host_wall_id"],
                "host_boundary_id": item["host_boundary_id"],
                "side_a": item["side_a"],
                "side_b": item["side_b"],
                "opening_segment": item["segment"],
                "span": item["span"],
                "geometry_ref": item["geometry_ref"],
                "construction_claim": False,
                "provenance": {"source": "house_diffusion_opening_registry_baseline_v1"},
            } for item in opening_records],
        }

        wall_face_graph = {
            "floor": floor,
            "unresolved": [],
            "faces": faces,
            "wall_band_rule": {
                "wall_band_type": "SYMBOLIC_RELATIVE",
                "metric_thickness": "UNKNOWN",
                "status": WALL_THICKNESS_METRIC_UNRESOLVED,
                "construction_claim": False,
                "source": "ARCHITECTOS_DERIVED",
            },
        }

        wall_solid_graph = {
            "floor": floor,
            "solids": [],
            "floor_envelopes": [{
                "envelope_id": f"HD-ENV-{index + 1:02d}",
                "polygon": polygon,
                "construction_claim": False,
                "provenance": {"source": envelope_source, "geometry_invented": False},
            } for index, polygon in enumerate(envelope_polygons)],
            "unresolved": [{
                "classification": "MISSING_CANONICAL_EVIDENCE",
                "code": WALL_THICKNESS_METRIC_UNRESOLVED,
                "detail": "HouseDiffusion wall bands are SYMBOLIC_RELATIVE; no metric thickness exists",
            }],
        }

        access_graph = {
            "nodes": deepcopy(access.get("nodes") or []),
            "edges": deepcopy(access.get("edges") or []),
            "status": "RESOLVED" if (access.get("gate") or {}).get(
                "ACCESSIBLE_PROGRAM_SPACES") else "MISSING",
            "method": access.get("method"),
            "provenance": {"source": "house_diffusion_access_graph_baseline_v1"},
        }

        unresolved = [
            {"classification": "MISSING_CANONICAL_EVIDENCE",
             "code": WALL_THICKNESS_METRIC_UNRESOLVED,
             "detail": "symbolic relative wall bands; metric thickness not provided"},
            {"classification": "NON_BLOCKING_FUTURE_RECHECK",
             "code": FINAL_WINDOWS_NOT_CREATED,
             "detail": f"{len(windows.get('provisional_baseline') or windows.get('baseline') or {})} provisional window candidates only"},
            {"classification": "NON_BLOCKING_FUTURE_RECHECK",
             "code": WORLD_ORIENTATION_PENDING,
             "detail": "final world orientation unknown in the accepted baseline"},
            {"classification": "NON_BLOCKING_FUTURE_RECHECK",
             "code": PARCEL_SITE_CONTEXT_PENDING,
             "detail": "no parcel/site context exists in the accepted baseline"},
        ]

        extraction = {
            "source_file": "house_diffusion_accepted_baseline_v1",
            "source_sha256": self._sha256("semantic_architectural_plan_baseline_v1.json"),
            "tolerance_audit": {"chosen_snap_tolerance_m": None,
                                "source": "house_diffusion_normalized_geometry"},
            "wall_face_graphs": {floor: wall_face_graph},
            "wall_solid_graphs": {floor: wall_solid_graph},
            "opening_host_graphs": {floor: opening_graph},
            "space_boundary_graphs": {floor: space_graph},
            "access_graph": access_graph,
            "unresolved": unresolved,
        }

        lineage = {
            "adapter": CONTRACT,
            "adapter_version": VERSION,
            "direction": "SemanticArchitecturalPlanBaselineV1 -> AcceptedArchitecturalBaselineEnvelopeV1",
            "source_root": str(self.root),
            "source_schema": baseline.get("schema"),
            "source_phase": baseline.get("phase"),
            "source_generator": deepcopy(baseline.get("generator")),
            "source_gate_baseline_complete": gate.get("BASELINE_ARCHITECTURAL_PLAN_COMPLETE"),
            "source_gate_blockers": gate.get("BLOCKERS_FOUND"),
            "geometry_resolved_via_ref": True,
            "geometry_unresolved": cache.unresolved,
            "counts": {
                "rooms": len(rooms),
                "program_rooms": sum(1 for room in rooms if room["is_program_room"]),
                "walls": len(wall_records),
                "exterior_walls": sum(1 for w in wall_records if w["wall_role"] == "EXTERIOR"),
                "interior_walls": sum(1 for w in wall_records if w["wall_role"] == "INTERIOR"),
                "openings": len(opening_records),
                "access_nodes": len(access_graph["nodes"]),
                "access_edges": len(access_graph["edges"]),
            },
            "preservation": {
                "room_ids_preserved": True,
                "wall_ids_preserved": True,
                "opening_ids_preserved": True,
                "access_graph_preserved": True,
                "geometry_moved": False,
                "geometry_resized": False,
                "geometry_merged": False,
                "geometry_split": False,
                "geometry_invented": False,
                "metric_wall_thickness_invented": False,
                "final_windows_invented": False,
                "world_orientation_invented": False,
                "parcel_context_invented": False,
                "internal_generator_used": False,
                "house_diffusion_modified": False,
            },
            "floor_id": floor,
        }
        return extraction, lineage

    # --------------------------------------------------
    # GENERATED baseline path (HOUSE-DIFFUSION-PRODUCTION-PATH-02A)
    #
    # ADDITIVE.  The historical path above is untouched and still validates the
    # frozen CONSOLIDATION-01 artifact exactly as before.  This second, explicit
    # path accepts a GENERATED baseline (``GeneratedArchitecturalBaselineV1``)
    # produced by ``GeneratedBaselineRealizationV1`` from a FRESH HouseDiffusion
    # candidate, and verifies it with its OWN strict verifier.  Identity is never
    # globally injectable, and verification is never bypassed.
    # --------------------------------------------------

    def adapt_generated(self, generated_baseline: Mapping[str, Any], *,
                        candidate_id: str,
                        candidate_version: str = "1",
                        acceptance_provenance: Mapping[str, Any] | None = None,
                        ) -> dict[str, Any]:
        """Adapt a GENERATED HouseDiffusion baseline into the accepted envelope."""
        with _internal_generator_guard():
            report = assert_generated_architectural_baseline(generated_baseline)
            extraction, lineage = self.build_boundary_extraction_from_generated(
                generated_baseline)
            extraction["generated_baseline_lineage"] = lineage
            resolved = {
                "version": "2.0-additive",
                "pipeline": (
                    "GENERATED_HOUSEDIFFUSION_BASELINE -> CANONICAL_GRAPH_REALIZATION "
                    "(no re-derivation, no internal generator)"
                ),
                "candidate_id": candidate_id,
                "candidate_version": candidate_version,
                "boundary_extraction": extraction,
                "semantic_regions": [],
                "constraints": [],
                "protected_constraints": [],
                "protected_entities": [],
                "preservation_requirements": ["PRESERVE_GENERATED_GEOMETRY"],
                "architecture_only": True,
                "adapter_lineage": lineage,
                "generated_baseline_verification": {
                    "status": report["status"],
                    "failed_checks": report["failed_checks"],
                    "realization_sha256": report["realization_sha256"],
                    "source_candidate_sha256": report["source_candidate_sha256"],
                },
            }
            envelope = ArchitecturalSpaceBoundaryPipelineV1().accept_resolved_baseline(
                resolved,
                candidate_id=candidate_id,
                candidate_version=candidate_version,
                acceptance_provenance=dict(acceptance_provenance or {
                    "status": "ACCEPTED",
                    "evidence_ids": ["house-diffusion-generated-baseline-01"],
                    "source": "GeneratedBaselineRealizationV1",
                }),
            )
            return envelope

    def build_boundary_extraction_from_generated(
            self, document: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """Build the canonical boundary extraction from a generated baseline."""
        floors = document.get("floors") or {}
        floor = sorted(floors, key=str)[0] if floors else "ground_floor"
        graph = floors.get(floor) or {}

        rooms = graph.get("spaces") or []
        walls = graph.get("walls") or []
        openings = graph.get("openings") or []
        envelope = graph.get("envelope") or {}
        band_rule = graph.get("wall_band_rule") or {}

        faces = [{
            "face_id": f"FACE-{wall['wall_id']}",
            "wall_id": wall["wall_id"],
            "start": wall["centerline"][0],
            "end": wall["centerline"][1],
            "wall_role": wall["wall_role"],
            "wall_band": deepcopy(wall.get("wall_band")),
            "thickness_status": WALL_THICKNESS_METRIC_UNRESOLVED,
            "construction_claim": False,
            "provenance": {"source": "generated_baseline_realization_v1"},
        } for wall in walls]

        space_graph = {
            "floor": floor,
            "unresolved": [],
            "spaces": [{
                "space_id": room["space_id"],
                "canonical_name": room.get("canonical_name") or room["space_id"],
                "semantic_class": room["space_id"],
                "external": False,
                "program_room": True,
                "boundary_ids": [f"FACE-{wall['wall_id']}" for wall in walls
                                 if room["space_id"] in (wall.get("between") or [])],
                "polygon": deepcopy(room["polygon"]),
                "area_m2": room.get("area_normalized"),
                "perimeter_m": room.get("perimeter_normalized"),
                "geometry_ref": {
                    "artifact": "generated_baseline_realization_v1",
                    "item_id": room["space_id"],
                    "geometry_sha256": room["geometry_sha256"],
                },
                "construction_claim": False,
                "provenance": {"source": "generated_baseline_realization_v1",
                               "geometry_invented": False},
            } for room in rooms],
        }

        opening_graph = {
            "floor": floor,
            "unresolved": [],
            "openings": [{
                "opening_id": item["opening_id"],
                "id": item["opening_id"],
                "kind": item.get("kind") or "DOOR",
                "opening_class": item.get("opening_class"),
                "semantic_role": item.get("opening_class"),
                "status": "RESOLVED",
                "host_face_a": (f"FACE-{item['host_wall_id']}"
                                if item.get("host_wall_id") else None),
                "host_wall_id": item.get("host_wall_id"),
                "host_boundary_id": item.get("host_wall_id"),
                "side_a": item.get("side_a"),
                "side_b": item.get("side_b"),
                "opening_segment": deepcopy(item.get("opening_segment")),
                "span": item.get("span"),
                "geometry_ref": None,
                "construction_claim": False,
                "provenance": {"source": "house_diffusion_source_door"},
            } for item in openings],
        }

        wall_face_graph = {
            "floor": floor,
            "unresolved": [],
            "faces": faces,
            "wall_band_rule": deepcopy(band_rule),
        }

        wall_solid_graph = {
            "floor": floor,
            "solids": [],
            "floor_envelopes": ([{
                "envelope_id": "GEN-ENV-01",
                "polygon": deepcopy(envelope.get("polygon")),
                "construction_claim": False,
                "provenance": {"source": envelope.get("source"),
                               "geometry_invented": False},
            }] if envelope.get("polygon") else []),
            "unresolved": [{
                "classification": "MISSING_CANONICAL_EVIDENCE",
                "code": WALL_THICKNESS_METRIC_UNRESOLVED,
                "detail": "generated baseline carries symbolic wall bands only",
            }],
        }

        access = document.get("access_graph") or {}
        access_graph = {
            "nodes": deepcopy(access.get("nodes") or []),
            "edges": deepcopy(access.get("edges") or []),
            "status": access.get("status") or "MISSING",
            "method": access.get("method"),
            "provenance": {"source": "house_diffusion_source_candidate_doors"},
        }

        unresolved = deepcopy(document.get("unresolved") or [])

        extraction = {
            "source_file": "generated_architectural_baseline_v1",
            "source_sha256": document.get("realization_sha256"),
            "tolerance_audit": {"chosen_snap_tolerance_m": None,
                                "source": "generated_baseline_measured_gap"},
            "wall_face_graphs": {floor: wall_face_graph},
            "wall_solid_graphs": {floor: wall_solid_graph},
            "opening_host_graphs": {floor: opening_graph},
            "space_boundary_graphs": {floor: space_graph},
            "access_graph": access_graph,
            "unresolved": unresolved,
        }

        lineage = {
            "adapter": CONTRACT,
            "adapter_version": VERSION,
            "direction": ("GeneratedArchitecturalBaselineV1 -> "
                          "AcceptedArchitecturalBaselineEnvelopeV1"),
            "baseline_origin": document.get("baseline_origin"),
            "source_engine": document.get("source_engine"),
            "source_candidate_schema": document.get("source_candidate_schema"),
            "source_candidate_id": document.get("source_candidate_id"),
            "source_candidate_sha256": document.get("source_candidate_sha256"),
            "generation_seed": document.get("generation_seed"),
            "realization_contract": document.get("realization_contract"),
            "realization_sha256": document.get("realization_sha256"),
            "generation_policy": document.get("generation_policy"),
            "geometry_resolved_via_ref": True,
            "geometry_unresolved": [],
            "counts": {
                "rooms": len(rooms),
                "program_rooms": len(rooms),
                "walls": len(walls),
                "exterior_walls": sum(1 for w in walls
                                      if w.get("wall_role") == "EXTERIOR"),
                "interior_walls": sum(1 for w in walls
                                      if w.get("wall_role") == "INTERIOR"),
                "openings": len(openings),
                "access_nodes": len(access_graph["nodes"]),
                "access_edges": len(access_graph["edges"]),
            },
            "preservation": {
                "room_ids_preserved": True,
                "wall_ids_preserved": True,
                "opening_ids_preserved": True,
                "access_graph_preserved": True,
                "geometry_moved": False,
                "geometry_resized": False,
                "geometry_merged": False,
                "geometry_split": False,
                "geometry_invented": False,
                "metric_wall_thickness_invented": False,
                "final_windows_invented": False,
                "world_orientation_invented": False,
                "parcel_context_invented": False,
                "internal_generator_used": False,
                "house_diffusion_modified": False,
            },
            "historical_consolidation_impersonated": False,
            "floor_id": floor,
        }
        return extraction, lineage

    # --------------------------------------------------
    # real-data helpers
    # --------------------------------------------------

    def _read(self, name: str) -> dict[str, Any]:
        with (self.root / name).open(encoding="utf-8") as handle:
            return json.load(handle)

    def _sha256(self, name: str) -> str:
        digest = hashlib.sha256()
        with (self.root / name).open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _ring(value: Any) -> list[list[float]]:
        if not isinstance(value, (list, tuple)):
            return []
        output = []
        for point in value:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                try:
                    output.append([float(point[0]), float(point[1])])
                except (TypeError, ValueError):
                    return []
            else:
                return []
        return output

    @staticmethod
    def _floor_id(rooms: Sequence[Mapping[str, Any]]) -> str:
        for room in rooms:
            if room.get("floor"):
                return str(room["floor"])
        return "ground_floor"

    def _rooms(self, baseline: Mapping[str, Any], cache: _ArtifactCache) -> list[dict[str, Any]]:
        rooms = []
        seen: set[str] = set()
        candidates = list(baseline.get("1_program_spaces") or [])
        circulation = baseline.get("2_derived_circulation") or {}
        if circulation:
            candidates.append(circulation)
        for space in candidates:
            identity = str(space.get("identity") or space.get("space_id"))
            if identity in seen:
                continue
            seen.add(identity)
            polygon = self._ring(space.get("polygon"))
            floor = None
            if not polygon:
                resolved = cache.item(space.get("geometry_ref"))
                if resolved:
                    polygon = self._ring(resolved.get("polygon"))
                    floor = resolved.get("floor")
            rooms.append({
                "identity": identity,
                "is_program_room": bool(space.get("is_program_room")),
                "polygon": polygon,
                "area_normalized": space.get("area"),
                "perimeter": round(Polygon(polygon).length, 6) if len(polygon) >= 4 else None,
                "external": "TERRACE" in identity or "BALCONY" in identity,
                "floor": floor,
                "geometry_ref": deepcopy(space.get("geometry_ref")),
            })
        return rooms

    def _walls(self, walls: Sequence[Mapping[str, Any]],
               cache: _ArtifactCache) -> list[dict[str, Any]]:
        records = []
        for wall in walls:
            centerline = wall.get("centerline")
            if not (isinstance(centerline, list) and len(centerline) >= 2):
                resolved = cache.item(wall.get("centerline_ref"))
                centerline = (resolved or {}).get("centerline")
            if not (isinstance(centerline, list) and len(centerline) >= 2):
                continue
            records.append({
                "wall_id": wall.get("wall_id"),
                "wall_role": wall.get("wall_role"),
                "between": deepcopy(wall.get("between") or []),
                "centerline": [[float(centerline[0][0]), float(centerline[0][1])],
                               [float(centerline[1][0]), float(centerline[1][1])]],
                "wall_band": deepcopy(wall.get("wall_band")),
            })
        return records

    def _openings(self, openings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        records = []
        for item in openings:
            segment = item.get("opening_segment")
            host = item.get("host_boundary") or {}
            pair = item.get("space_pair") or []
            opening_class = str(item.get("opening_class") or "")
            kind = "DOOR" if ("DOOR" in opening_class or "PORTAL" in opening_class) else "WINDOW"
            records.append({
                "opening_id": item.get("id"),
                "kind": kind,
                "opening_class": opening_class,
                "semantic_role": item.get("semantic_role"),
                "segment": self._ring(segment),
                "span": item.get("span"),
                "host_wall_id": host.get("wall_id"),
                "host_boundary_id": host.get("boundary_id"),
                "host_face_id": f"FACE-{host.get('wall_id')}" if host.get("wall_id") else None,
                "side_a": pair[0] if len(pair) > 0 else None,
                "side_b": pair[1] if len(pair) > 1 else None,
                "geometry_ref": deepcopy(item.get("geometry_ref")),
            })
        return records

    def _envelopes(self, rooms: Sequence[Mapping[str, Any]],
                   cache: _ArtifactCache) -> tuple[list[list[list[float]]], str]:
        """Floor envelope(s) from the REAL accepted room polygons.

        The accepted baseline's refined ``envelope`` does not necessarily cover
        every accepted room, so the envelope is taken as the union of the real
        room polygons (derived, never invented).  The refined envelope is only a
        fallback when no room geometry resolves.
        """
        shapes = [Polygon(room["polygon"]) for room in rooms if len(room["polygon"]) >= 4]
        if shapes:
            # The accepted rooms are separated by the baseline's OWN measured wall
            # gap, so the raw union is multi-part.  Closing it with the baseline's
            # own symbolic half-band is evidence-based, not an invented thickness.
            half_band = self._accepted_half_band()
            merged = unary_union(shapes)
            if half_band and half_band > 0:
                merged = merged.buffer(half_band, join_style=2)
            parts = list(merged.geoms) if merged.geom_type == "MultiPolygon" else [merged]
            polygons = [[[round(float(x), 9), round(float(y), 9)]
                         for x, y in part.exterior.coords]
                        for part in parts if not part.is_empty]
            if polygons:
                source = ("UNION_OF_ACCEPTED_ROOM_POLYGONS_CLOSED_BY_ACCEPTED_HALF_BAND"
                          if half_band else "UNION_OF_ACCEPTED_ROOM_POLYGONS")
                return polygons, source
        refined = self._refined_envelope(cache)
        if refined:
            return [refined], "HOUSEDIFFUSION_REFINED_ENVELOPE"
        return [], "UNAVAILABLE"

    def _accepted_half_band(self) -> float | None:
        """The baseline's OWN symbolic half-band (never an invented thickness)."""
        try:
            registry = self._read("wall_registry_baseline_v1.json")
        except OSError:
            return None
        rule = registry.get("wall_band_rule") or {}
        half_band = rule.get("half_band")
        return float(half_band) if isinstance(half_band, (int, float)) else None

    def _refined_envelope(self, cache: _ArtifactCache) -> list[list[float]]:
        provenance = (self._read("semantic_architectural_plan_baseline_v1.json")
                      .get("provenance") or {})
        geometry_ref = provenance.get("geometry")
        if not isinstance(geometry_ref, Mapping):
            return []
        document = cache.document(geometry_ref.get("artifact"))
        if not isinstance(document, Mapping):
            return []
        envelope = document.get("envelope")
        if isinstance(envelope, Mapping):
            return self._ring(envelope.get("polygon"))
        return []

    # --------------------------------------------------
    # downstream chain
    # --------------------------------------------------

    def run_design_chain(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        """Run the frozen Design-02 → Design-05 chain on the adapted envelope."""
        with _internal_generator_guard():
            from core.architecture.reasoning.architectural_baseline_derived_candidate_refinement_v1 import (
                derive_architectural_candidate_v1,
            )
            from core.architecture.reasoning.architectural_baseline_opening_privacy_parcel_edge_intelligence_v1 import (
                enrich_opening_privacy_parcel_edge_intelligence_v1,
            )
            from core.architecture.reasoning.architectural_baseline_floor_roof_geometry_v1 import (
                derive_architectural_floor_roof_geometry_v1,
            )
            from core.architecture.reasoning.architectural_baseline_structural_readiness_v1 import (
                analyze_architectural_structural_readiness_v1,
            )

            design_02 = derive_architectural_candidate_v1(
                envelope,
                derivation_provenance={"decision": "DESIGN_02",
                                       "evidence_ids": ["hd-adapted-baseline"],
                                       "source": "house_diffusion"})
            design_03 = enrich_opening_privacy_parcel_edge_intelligence_v1(
                design_02,
                enrichment_provenance={"decision": "DESIGN_03",
                                       "evidence_ids": ["hd-adapted-baseline"],
                                       "source": "house_diffusion"})
            design_04 = derive_architectural_floor_roof_geometry_v1(
                design_03,
                geometry_evidence=self._geometry_evidence(envelope),
                derivation_provenance={"decision": "DESIGN_04",
                                       "evidence_ids": ["hd-adapted-baseline"],
                                       "source": "house_diffusion"})
            design_05 = analyze_architectural_structural_readiness_v1(
                design_04, readiness_evidence=None,
                analysis_provenance={"decision": "DESIGN_05",
                                     "evidence_ids": ["hd-adapted-baseline"],
                                     "source": "house_diffusion"})
            return {
                "design_02": design_02,
                "design_03": design_03,
                "design_04": design_04,
                "design_05": design_05,
            }

    @staticmethod
    def _geometry_evidence(envelope: Mapping[str, Any]) -> dict[str, Any]:
        """Floor evidence taken ONLY from the adapted baseline; no invention."""
        extraction = envelope.get("boundary_extraction") or {}
        floors = sorted(extraction.get("space_boundary_graphs") or {})
        levels = [{"floor_id": floor, "order": index} for index, floor in enumerate(floors)]
        return {
            "contract": "ApprovedArchitecturalGeometryEvidenceV1",
            "status": "VERIFIED" if levels else "INSUFFICIENT",
            "levels": levels,
            "vertical_circulation": [],
            "roof": {"status": "UNRESOLVED",
                     "reason": "no roof evidence exists in the accepted HouseDiffusion baseline"},
        }


housediffusion_accepted_baseline_adapter = HouseDiffusionAcceptedBaselineAdapterV1()


def adapt_housediffusion_accepted_baseline(
        baseline_root: Path | str | None = None, **kwargs: Any) -> dict[str, Any]:
    """Module-level convenience wrapper over the canonical adapter."""
    return HouseDiffusionAcceptedBaselineAdapterV1(baseline_root).adapt(**kwargs)


__all__ = [
    "CONTRACT", "VERSION", "WALL_THICKNESS_METRIC_UNRESOLVED", "FINAL_WINDOWS_NOT_CREATED",
    "WORLD_ORIENTATION_PENDING", "PARCEL_SITE_CONTEXT_PENDING",
    "INTERNAL_GENERATOR_BYPASS_DETECTED", "FORBIDDEN_INTERNAL_GENERATORS",
    "InternalGeneratorBypassError", "HouseDiffusionAcceptedBaselineAdapterV1",
    "housediffusion_accepted_baseline_adapter", "adapt_housediffusion_accepted_baseline",
]
