"""Architecture-first CAD topology pipeline; deliberately has no BIM/IFC dependency."""
from core.architecture.contracts.accepted_architectural_baseline_envelope_v1 import (
    build_accepted_architectural_baseline_envelope,
)
from core.architecture.geometry.space_boundary_opening_host_graph_engine_v1 import SpaceBoundaryOpeningHostGraphEngineV1


class ArchitecturalSpaceBoundaryPipelineV1:
    VERSION = "2.0-additive"

    def __init__(self):
        self.kernel = SpaceBoundaryOpeningHostGraphEngineV1()

    def resolve(self, cad_file, semantic_regions=None):
        result = self.kernel.extract(cad_file, semantic_regions=semantic_regions)
        payload = result.to_dict()
        return {
            "version": self.VERSION,
            "pipeline": "DWG_INGEST -> WALL_FACES -> WALL_SOLIDS -> FLOOR_FREE_SPACE -> TEMP_OPENING_CLOSURES -> ROOM_CELLS -> OPENING_PORTALS -> ACCESS_GRAPH -> ARCHITECTURAL_VALIDATION",
            "boundary_extraction": payload,
            "semantic_regions": self._consume_real_geometry(semantic_regions or {}, payload),
            "architecture_only": True,
        }

    def accept_resolved_baseline(
        self,
        resolved_baseline,
        *,
        candidate_id,
        candidate_version,
        acceptance_provenance,
    ):
        """Create the sole frozen envelope for a resolved pipeline candidate."""
        return build_accepted_architectural_baseline_envelope(
            resolved_baseline,
            candidate_id=candidate_id,
            candidate_version=candidate_version,
            acceptance_provenance=acceptance_provenance,
        )

    @staticmethod
    def _consume_real_geometry(semantic_regions, payload):
        regions = semantic_regions.get("regions", semantic_regions if isinstance(semantic_regions, list) else [])
        by_floor = payload["space_boundary_graphs"]
        resolved = []
        for region in regions:
            item = dict(region)
            floor = str(item.get("floor", ""))
            point = item.get("interior_reference_point")
            candidates = by_floor.get(floor, {}).get("spaces", [])
            if point:
                from shapely.geometry import Point, Polygon
                hit = next((space for space in candidates if Polygon(space["polygon"]).covers(Point(point))), None)
                if hit:
                    item.update(polygon=hit["polygon"], area_m2=hit["area_m2"], perimeter_m=hit["perimeter_m"],
                                boundary_status="RESOLVED_REAL_GEOMETRY", geometry_source_space_id=hit["space_id"])
            resolved.append(item)
        return resolved
