"""HouseDiffusionBaselineReconnectV1 — HOUSE-DIFFUSION-PRODUCTION-BASELINE-RECONNECT-01.

READ-ONLY reconnection and verification of the PREVIOUSLY ACCEPTED real
HouseDiffusion architectural baseline.

This module does NOT generate a plan.  It:

1. locates the accepted baseline artifacts,
2. proves their identity/lineage against the frozen checkpoint,
3. probes whether the CURRENT ArchitectOS contracts can consume them and
   records the exact outcome,
4. exports a human-readable plan from the REAL baseline geometry (no invention),
5. reports the production-routing status.

HouseDiffusion remains the PRIMARY PLAN GENERATOR.  The internal rule-based
layout branch (01A / 01A2) is diagnostic only and is never used as a candidate
source here.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
from typing import Any

from shapely.geometry import Polygon


CONTRACT = "HouseDiffusionBaselineReconnectV1"
VERSION = "1.0"

BASELINE_ROOT = Path(r"D:\AI_Architecture_Lab\baseline_architectural_plan_01")

EXPECTED_SCHEMA = "SemanticArchitecturalPlanBaselineV1"
EXPECTED_PHASE = "HOUSE-DIFFUSION-BASELINE-ARCHITECTURAL-PLAN-CONSOLIDATION-01"
EXPECTED_PRIMARY_GENERATOR = "HouseDiffusion"
EXPECTED_GENERATION_POLICY = "HOUSE_DIFFUSION_GENERATION_POLICY_V1"

REQUIRED_ARTIFACTS = (
    "semantic_architectural_plan_baseline_v1.json",
    "wall_registry_baseline_v1.json",
    "opening_registry_baseline_v1.json",
    "window_registry_provisional_v1.json",
    "access_graph_baseline_v1.json",
    "plan_completeness_gate_v1.json",
)

#: The graphs the CURRENT ArchitectOS baseline envelope requires.
ARCHITECTOS_REQUIRED_GRAPHS = (
    "boundary_extraction",
    "wall_face_graphs",
    "wall_solid_graphs",
    "opening_host_graphs",
    "space_boundary_graphs",
    "access_graph",
)

# ---- classifications --------------------------------------------------------
STATUS_RECONNECTED = "RECONNECTED"
STATUS_IDENTITY_UNRESOLVED = "ACCEPTED_HOUSEDIFFUSION_BASELINE_IDENTITY_UNRESOLVED"
STATUS_ARTIFACTS_MISSING = "ACCEPTED_HOUSEDIFFUSION_BASELINE_ARTIFACTS_MISSING"
STATUS_CONSUMER_INCOMPATIBLE = "CURRENT_CONTRACTS_CANNOT_CONSUME_BASELINE"
STATUS_ADAPTER_UNREACHABLE = "HOUSEDIFFUSION_ADAPTER_NOT_REACHABLE_FROM_ARCHITECTOS"

CLASS_DIAGNOSTIC_BRANCH = "DIAGNOSTIC_BRANCH"
CLASS_FALLBACK_BRANCH = "FALLBACK_BRANCH"
CLASS_TEST_ONLY_BRANCH = "TEST_ONLY_BRANCH"
CLASS_LEGACY_INTERNAL_GENERATOR_BRANCH = "LEGACY_INTERNAL_GENERATOR_BRANCH"

PLAN_SVG_BACKGROUND = "#ffffff"
PLAN_SVG_PADDING = 0.06
PLAN_SVG_UNITS = 2400.0
PLAN_SVG_FONT = "monospace"


def _read(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


class _ArtifactCache:
    """Resolve geometry through the baseline's ``geometry_ref`` contract.

    The accepted baseline deliberately does NOT copy coordinates; every item
    carries ``geometry_ref {artifact, item_id, geometry_sha256}`` and readers
    resolve the geometry from the source artifact.  Nothing is invented here.
    """

    def __init__(self):
        self._documents: dict[str, Any] = {}
        self.unresolved: list[dict[str, Any]] = []

    def document(self, artifact: Any) -> dict[str, Any] | None:
        if not isinstance(artifact, str) or not artifact:
            return None
        if artifact not in self._documents:
            path = Path(artifact)
            self._documents[artifact] = _read(path) if path.is_file() else None
        return self._documents[artifact]

    def item(self, geometry_ref: Any) -> Mapping[str, Any] | None:
        if not isinstance(geometry_ref, Mapping):
            return None
        document = self.document(geometry_ref.get("artifact"))
        if not isinstance(document, Mapping):
            self.unresolved.append({"geometry_ref": dict(geometry_ref),
                                    "reason": "source_artifact_missing"})
            return None
        item_id = geometry_ref.get("item_id")
        # some derived items (e.g. the derived circulation) live as top-level keys
        direct = document.get(str(item_id))
        if isinstance(direct, Mapping):
            return direct
        for key in ("spaces", "walls", "openings", "rooms", "items"):
            collection = document.get(key)
            if not isinstance(collection, list):
                continue
            for entry in collection:
                if not isinstance(entry, Mapping):
                    continue
                for identity_key in ("space_id", "architectos_identity", "wall_id",
                                     "opening_id", "item_id", "id"):
                    if str(entry.get(identity_key)) == str(item_id):
                        return entry
        self.unresolved.append({"geometry_ref": dict(geometry_ref),
                                "reason": "item_not_found_in_source_artifact"})
        return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class HouseDiffusionBaselineReconnectV1:
    """Locate, verify, probe and export the accepted HouseDiffusion baseline."""

    VERSION = VERSION

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root is not None else BASELINE_ROOT

    # --------------------------------------------------
    # 1 / 2 — locate
    # --------------------------------------------------

    def locate(self) -> dict[str, Any]:
        present = self.root.is_dir()
        artifacts = {}
        if present:
            for name in REQUIRED_ARTIFACTS:
                path = self.root / name
                artifacts[name] = {
                    "present": path.is_file(),
                    "bytes": path.stat().st_size if path.is_file() else None,
                    "sha256": _sha256(path) if path.is_file() else None,
                }
        return {
            "root": str(self.root),
            "root_present": present,
            "artifacts": artifacts,
            "all_required_present": bool(present) and all(
                item["present"] for item in artifacts.values()),
        }

    # --------------------------------------------------
    # 3 — identity
    # --------------------------------------------------

    def verify_identity(self) -> dict[str, Any]:
        located = self.locate()
        if not located["all_required_present"]:
            return {"status": STATUS_ARTIFACTS_MISSING, "located": located}

        baseline = _read(self.root / "semantic_architectural_plan_baseline_v1.json")
        gate = baseline.get("gate") or {}
        generator = baseline.get("generator") or {}
        provenance = baseline.get("provenance") or {}
        checks = {
            "schema": baseline.get("schema") == EXPECTED_SCHEMA,
            "phase": baseline.get("phase") == EXPECTED_PHASE,
            "primary_generator": generator.get("PRIMARY_PLAN_GENERATOR")
            == EXPECTED_PRIMARY_GENERATOR,
            "generation_policy_locked": EXPECTED_GENERATION_POLICY
            in str(generator.get("GENERATION_POLICY")),
            "baseline_complete": gate.get("BASELINE_ARCHITECTURAL_PLAN_COMPLETE") == "YES",
            "blockers_zero": gate.get("BLOCKERS_FOUND") == 0,
            "program_identities_8_8": gate.get("PROGRAM_IDENTITIES") == "8/8",
            "accessible_spaces_8_8": gate.get("ACCESSIBLE_PROGRAM_SPACES") == "8/8",
            "sealed_zero": gate.get("SEALED_PROGRAM_SPACES") == 0,
            "orphan_zero": gate.get("ORPHAN_PROGRAM_SPACES") == 0,
            "daylight_4_4": gate.get("HABITABLE_ROOMS_WITH_PROVISIONAL_DAYLIGHT") == "4/4",
            "wet_ventilation_2_2": gate.get("WET_SPACES_WITH_VENTILATION_STRATEGY") == "2/2",
            "door_window_overlap_zero": gate.get("DOOR_WINDOW_OVERLAPS") == 0,
            "polygon_overlap_zero": gate.get("POLYGON_OVERLAPS") == 0,
            "final_windows_not_created": gate.get("FINAL_WINDOWS_CREATED") == "NO",
            "site_orientation_pending": gate.get("FINAL_WORLD_ORIENTATION_KNOWN") == "NO",
            "house_diffusion_not_modified": gate.get("HOUSE_DIFFUSION_MODIFIED") == "NO",
            "checkpoint_not_modified": gate.get("CHECKPOINT_MODIFIED") == "NO",
            "no_structure": gate.get("NO_STRUCTURE") == "YES",
            "no_bim_ifc": gate.get("NO_BIM_IFC") == "YES",
            "geometry_refs_present": all(
                isinstance(item.get("geometry_ref"), Mapping)
                for item in baseline.get("1_program_spaces") or []
            ),
            "no_duplicated_geometry": (baseline.get("no_duplicated_geometry") or {}).get(
                "GEOMETRY_DUPLICATED") is False,
        }
        geometry_source = ((provenance.get("geometry") or {}).get("artifact"))
        source_path = Path(geometry_source) if geometry_source else None
        source_ok = bool(source_path and source_path.is_file())
        if source_ok:
            checks["geometry_source_sha256_matches"] = _sha256(source_path) == (
                (provenance.get("geometry") or {}).get("sha256"))

        return {
            "status": STATUS_RECONNECTED if all(checks.values()) else STATUS_IDENTITY_UNRESOLVED,
            "checks": checks,
            "failed_checks": sorted(key for key, ok in checks.items() if not ok),
            "schema": baseline.get("schema"),
            "phase": baseline.get("phase"),
            "generator": generator,
            "status_line": baseline.get("status"),
            "gate": gate,
            "provenance_geometry": provenance.get("geometry"),
            "geometry_source_present": source_ok,
        }

    # --------------------------------------------------
    # 4 — ArchitectOS consumption probe
    # --------------------------------------------------

    def probe_architectos_consumption(self) -> dict[str, Any]:
        baseline = _read(self.root / "semantic_architectural_plan_baseline_v1.json")
        missing = [name for name in ARCHITECTOS_REQUIRED_GRAPHS if name not in baseline]
        outcome = "not_attempted"
        error = None
        try:
            from core.architecture.geometry.architectural_space_boundary_pipeline_v1 import (
                ArchitecturalSpaceBoundaryPipelineV1,
            )

            ArchitecturalSpaceBoundaryPipelineV1().accept_resolved_baseline(
                baseline, candidate_id="HD-RECONNECT-01", candidate_version="1",
                acceptance_provenance={"status": "ACCEPTED", "evidence_ids": ["hd-reconnect"]})
            outcome = "accepted"
        except Exception as exc:  # fail closed; the incompatibility is the finding
            outcome = "rejected"
            error = f"{type(exc).__name__}: {exc}"

        return {
            "status": STATUS_CONSUMER_INCOMPATIBLE if outcome != "accepted" else STATUS_RECONNECTED,
            "architectos_required_graphs": list(ARCHITECTOS_REQUIRED_GRAPHS),
            "missing_from_baseline": missing,
            "consumption_outcome": outcome,
            "consumption_error": error,
            "adapter_present_in_architectos": self._adapter_present_in_architectos(),
            "note": (
                "SemanticArchitecturalPlanBaselineV1 and "
                "AcceptedArchitecturalBaselineEnvelopeV1 are different contracts; no "
                "adapter between them exists in the ArchitectOS repository."
            ),
        }

    @staticmethod
    def _adapter_present_in_architectos() -> bool:
        """True only if some OTHER ArchitectOS module integrates HouseDiffusion.

        This verifier module itself is excluded, so it cannot report its own
        docstring as an integration.
        """
        repo = Path(__file__).resolve().parents[3]
        itself = Path(__file__).resolve()
        for base in (repo / "core", repo / "app.py"):
            if not base.exists():
                continue
            targets = base.rglob("*.py") if base.is_dir() else [base]
            for path in targets:
                try:
                    if path.resolve() == itself:
                        continue
                    text = path.read_text(encoding="utf-8", errors="ignore").lower()
                except OSError:
                    continue
                if "housediffusion" in text or "house_diffusion" in text:
                    return True
        return False

    # --------------------------------------------------
    # 6 — export the REAL baseline plan
    # --------------------------------------------------

    def export_plan(self) -> dict[str, Any]:
        baseline = _read(self.root / "semantic_architectural_plan_baseline_v1.json")
        walls = _read(self.root / "wall_registry_baseline_v1.json").get("walls") or []
        openings = _read(self.root / "opening_registry_baseline_v1.json").get(
            "baseline_openings") or []
        windows = _read(self.root / "window_registry_provisional_v1.json")
        access = _read(self.root / "access_graph_baseline_v1.json")

        cache = _ArtifactCache()
        rooms = []
        seen_identities: set[str] = set()
        candidates = list(baseline.get("1_program_spaces") or [])
        circulation = baseline.get("2_derived_circulation") or {}
        if circulation:
            candidates.append(circulation)
        for space in candidates:
            identity = str(space.get("identity") or space.get("space_id"))
            if identity in seen_identities:
                continue
            seen_identities.add(identity)
            polygon = self._space_polygon(space)
            if not polygon:
                resolved = cache.item(space.get("geometry_ref"))
                polygon = self._space_polygon(resolved) if resolved else []
            rooms.append({
                "space_id": space.get("space_id"),
                "identity": space.get("identity"),
                "display_label": str(space.get("identity") or "").replace("_", " "),
                "is_program_room": bool(space.get("is_program_room")),
                "polygon": polygon,
                "area_normalized": space.get("area"),
                "geometry_ref": space.get("geometry_ref"),
                "provenance_source": (space.get("provenance") or {}).get("source"),
            })

        wall_records = []
        for wall in walls:
            centerline = wall.get("centerline")
            if not (isinstance(centerline, list) and len(centerline) >= 2):
                resolved = cache.item(wall.get("centerline_ref"))
                centerline = (resolved or {}).get("centerline")
            if not (isinstance(centerline, list) and len(centerline) >= 2):
                continue
            wall_records.append({
                "wall_id": wall.get("wall_id"),
                "wall_role": wall.get("wall_role"),
                "between": wall.get("between"),
                "centerline": centerline,
                "length_normalized": wall.get("length_normalized"),
                "wall_band": wall.get("wall_band"),
                "status": wall.get("status"),
            })

        opening_records = [{
            "opening_id": item.get("id"),
            "opening_class": item.get("opening_class"),
            "semantic_role": item.get("semantic_role"),
            "space_pair": item.get("space_pair"),
            "segment": item.get("opening_segment"),
            "host_boundary": item.get("host_boundary"),
            "geometry_ref": item.get("geometry_ref"),
        } for item in openings]

        window_source = windows.get("provisional_baseline")
        if not isinstance(window_source, Mapping):
            window_source = (baseline.get("6_provisional_windows") or {}).get("baseline")
        if not isinstance(window_source, Mapping):
            window_source = {}
        final_windows = windows.get("FINAL_WINDOWS_CREATED") or (
            baseline.get("6_provisional_windows") or {}).get("FINAL_WINDOWS_CREATED")
        window_records = []
        for name, item in window_source.items():
            if isinstance(item, Mapping):
                window_records.append({
                    "space": name,
                    "window_candidate_id": item.get("window_candidate_id"),
                    "segment_class": item.get("segment_class"),
                    "usable_frontage": item.get("usable_frontage"),
                    "span": item.get("span"),
                    "final_window_created": final_windows,
                })

        return {
            "contract": CONTRACT, "version": VERSION,
            "plan_kind": "ACCEPTED_HOUSEDIFFUSION_BASELINE_READ_ONLY_EXPORT",
            "source": {
                "root": str(self.root),
                "schema": baseline.get("schema"),
                "phase": baseline.get("phase"),
                "generator": baseline.get("generator"),
                "status": baseline.get("status"),
            },
            "rooms": rooms,
            "walls": wall_records,
            "openings": opening_records,
            "windows": window_records,
            "circulation": [circulation.get("identity")] if circulation else [],
            "access_graph": {
                "nodes": len(access.get("nodes") or []),
                "edges": len(access.get("edges") or []),
                "accessible_program_spaces": access.get("ACCESSIBLE_PROGRAM_SPACES"),
            },
            "geometry_resolution": {
                "resolved_via_geometry_ref": True,
                "unresolved": cache.unresolved,
            },
            "counts": {
                "rooms": len(rooms),
                "program_rooms": sum(1 for room in rooms if room["is_program_room"]),
                "walls": len(wall_records),
                "exterior_walls": sum(1 for w in wall_records if w["wall_role"] == "EXTERIOR"),
                "interior_walls": sum(1 for w in wall_records if w["wall_role"] == "INTERIOR"),
                "openings": len(opening_records),
                "provisional_windows": len(window_records),
            },
            "provenance": {
                "exported_from": "accepted_baseline_artifacts",
                "geometry_invented": False,
                "internal_layout_engine_used": False,
                "plan_generated": False,
            },
        }

    @staticmethod
    def _space_polygon(space: Mapping[str, Any]) -> list[list[float]]:
        polygon = space.get("polygon")
        if not isinstance(polygon, (list, tuple)):
            return []
        output = []
        for point in polygon:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                try:
                    output.append([float(point[0]), float(point[1])])
                except (TypeError, ValueError):
                    return []
        return output

    # --------------------------------------------------
    # SVG
    # --------------------------------------------------

    def render_plan_svg(self, plan: Mapping[str, Any], *, with_openings: bool = False,
                        diagnostic: bool = False) -> str:
        points: list[list[float]] = []
        for room in plan["rooms"]:
            points.extend(room["polygon"])
        for wall in plan["walls"]:
            points.extend(wall["centerline"])
        if not points:
            return self._empty_svg("no baseline geometry")

        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)
        pad = PLAN_SVG_PADDING
        scale = PLAN_SVG_UNITS
        width = (max_x - min_x + 2 * pad) * scale
        height = (max_y - min_y + 2 * pad) * scale + 30.0

        def px(value):
            return (float(value) - min_x + pad) * scale

        def py(value):
            return (max_y - float(value) + pad) * scale + 30.0

        def attr(ring):
            return " ".join(f"{px(p[0]):.2f},{py(p[1]):.2f}" for p in ring)

        title = "ACCEPTED HOUSE-DIFFUSION BASELINE — ARCHITECTURAL PLAN"
        if with_openings:
            title += " (WITH OPENINGS)"
        if diagnostic:
            title += " (DIAGNOSTIC)"

        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.2f}" height="{height:.2f}" '
            f'viewBox="0 0 {width:.2f} {height:.2f}">',
            f'<rect x="0" y="0" width="{width:.2f}" height="{height:.2f}" '
            f'fill="{PLAN_SVG_BACKGROUND}"/>',
            f'<text x="10.000" y="18.000" font-family="{PLAN_SVG_FONT}" font-size="13" '
            f'fill="#111111">{self._escape(title)}</text>',
        ]

        parts.append('<g id="rooms">')
        for room in plan["rooms"]:
            if not room["polygon"]:
                continue
            external = "TERRACE" in str(room["identity"]) or "BALCONY" in str(room["identity"])
            derived = not room["is_program_room"]
            stroke = "#2f8f6b" if external else ("#7a4fbf" if derived else "#111111")
            fill = "#2f8f6b" if external else ("#7a4fbf" if derived else "#ffffff")
            opacity = 0.12 if external else (0.08 if derived else 0.0)
            parts.append(
                f'<polygon points="{attr(room["polygon"])}" fill="{fill}" '
                f'fill-opacity="{opacity}" stroke="{stroke}" stroke-width="2.0"/>')
        parts.append("</g>")

        parts.append('<g id="walls">')
        for wall in plan["walls"]:
            if not with_openings and not diagnostic:
                width_px = 3.4 if wall["wall_role"] == "EXTERIOR" else 1.8
            else:
                width_px = 2.6 if wall["wall_role"] == "EXTERIOR" else 1.2
            colour = "#111111" if wall["wall_role"] == "EXTERIOR" else "#666666"
            (x1, y1), (x2, y2) = wall["centerline"]
            parts.append(
                f'<line x1="{px(x1):.2f}" y1="{py(y1):.2f}" x2="{px(x2):.2f}" '
                f'y2="{py(y2):.2f}" stroke="{colour}" stroke-width="{width_px}"/>')
        parts.append("</g>")

        if with_openings or diagnostic:
            parts.append('<g id="openings">')
            for opening in plan["openings"]:
                segment = opening.get("segment")
                if not segment or len(segment) < 2:
                    continue
                (x1, y1), (x2, y2) = segment[0], segment[1]
                colour = "#b5561f" if "DOOR" in str(opening.get("opening_class")) else "#1f6fb5"
                parts.append(
                    f'<line x1="{px(x1):.2f}" y1="{py(y1):.2f}" x2="{px(x2):.2f}" '
                    f'y2="{py(y2):.2f}" stroke="{colour}" stroke-width="6.0"/>')
            parts.append("</g>")

        if diagnostic:
            parts.append('<g id="diagnostics">')
            lines = [
                f"walls={plan['counts']['walls']} "
                f"(ext {plan['counts']['exterior_walls']} / int {plan['counts']['interior_walls']})",
                f"openings={plan['counts']['openings']} "
                f"provisional_windows={plan['counts']['provisional_windows']}",
                "wall_band=SYMBOLIC_RELATIVE metric_thickness=UNKNOWN",
                "final_windows=NOT_CREATED site_orientation=PENDING",
            ]
            for index, line in enumerate(lines):
                parts.append(
                    f'<text x="10.000" y="{height - 10.0 - index * 12.0:.2f}" '
                    f'font-family="{PLAN_SVG_FONT}" font-size="9" fill="#b02020">'
                    f'{self._escape(line)}</text>')
            parts.append("</g>")

        parts.append('<g id="labels">')
        for room in plan["rooms"]:
            if not room["polygon"]:
                continue
            anchor = self._anchor(room["polygon"])
            if anchor is None:
                continue
            parts.append(
                f'<text x="{px(anchor[0]):.2f}" y="{py(anchor[1]):.2f}" text-anchor="middle" '
                f'font-family="{PLAN_SVG_FONT}" font-size="10" fill="#111111">'
                f'{self._escape(room["display_label"])}</text>')
        parts.append("</g>")
        parts.append("</svg>")
        return "".join(parts)

    @staticmethod
    def _anchor(ring):
        if len(ring) < 4:
            return None
        try:
            point = Polygon(ring).representative_point()
        except (ValueError, TypeError):
            return None
        return [float(point.x), float(point.y)]

    @staticmethod
    def _empty_svg(message: str) -> str:
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="360.000" height="80.000" '
                'viewBox="0 0 360.000 80.000">'
                f'<rect x="0" y="0" width="360.000" height="80.000" fill="{PLAN_SVG_BACKGROUND}"/>'
                f'<text x="10.000" y="40.000" font-family="{PLAN_SVG_FONT}" font-size="11" '
                f'fill="#b02020">'
                f'{HouseDiffusionBaselineReconnectV1._escape(message)}</text></svg>')

    @staticmethod
    def _escape(value: Any) -> str:
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # --------------------------------------------------
    # report
    # --------------------------------------------------

    def report(self) -> dict[str, Any]:
        located = self.locate()
        identity = self.verify_identity() if located["root_present"] else {
            "status": STATUS_ARTIFACTS_MISSING}
        consumption = self.probe_architectos_consumption() if located["root_present"] else {}
        plan = self.export_plan() if located["root_present"] else {}
        return {
            "contract": CONTRACT, "version": VERSION,
            "located": located,
            "identity": identity,
            "architectos_consumption": consumption,
            "plan_counts": plan.get("counts") if plan else None,
            "production_routing": {
                "primary_plan_generator": "HouseDiffusion",
                "generation_policy": EXPECTED_GENERATION_POLICY,
                "house_diffusion_primary_path_restored": False,
                "internal_generator_role": "DIAGNOSTIC_ONLY_NOT_A_CANDIDATE_SOURCE",
                "bypass_point": (
                    "ArchitecturalBrain.design -> LayoutReasoner/SpatialPlacementReasoner "
                    "(internal rule-based generator). No HouseDiffusion call site exists in "
                    "core/ or app.py."
                ),
            },
            "branch_classification": {
                "ArchitecturalHumanReadablePlanV1": CLASS_DIAGNOSTIC_BRANCH,
                "CoherentArchitecturalFloorPlanV1": CLASS_DIAGNOSTIC_BRANCH,
                "architectural_layout_intelligence_v1 (01A2B)": CLASS_DIAGNOSTIC_BRANCH,
                "treemap_zone_band_partition": CLASS_LEGACY_INTERNAL_GENERATOR_BRANCH,
                "retained": True,
                "modified": False,
                "continued": False,
            },
        }


housediffusion_baseline_reconnect = HouseDiffusionBaselineReconnectV1()


def reconnect_housediffusion_baseline(root: Path | str | None = None) -> dict[str, Any]:
    """Module-level convenience wrapper over the canonical reconnect verifier."""
    return HouseDiffusionBaselineReconnectV1(root).report()


__all__ = [
    "CONTRACT", "VERSION", "BASELINE_ROOT", "EXPECTED_SCHEMA", "EXPECTED_PHASE",
    "EXPECTED_PRIMARY_GENERATOR", "EXPECTED_GENERATION_POLICY", "REQUIRED_ARTIFACTS",
    "ARCHITECTOS_REQUIRED_GRAPHS", "STATUS_RECONNECTED", "STATUS_IDENTITY_UNRESOLVED",
    "STATUS_ARTIFACTS_MISSING", "STATUS_CONSUMER_INCOMPATIBLE",
    "STATUS_ADAPTER_UNREACHABLE", "CLASS_DIAGNOSTIC_BRANCH", "CLASS_FALLBACK_BRANCH",
    "CLASS_TEST_ONLY_BRANCH", "CLASS_LEGACY_INTERNAL_GENERATOR_BRANCH",
    "HouseDiffusionBaselineReconnectV1", "housediffusion_baseline_reconnect",
    "reconnect_housediffusion_baseline",
]
