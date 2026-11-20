from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ConstraintKind(str, Enum):
    HARD = "HARD"
    SOFT = "SOFT"
    PROJECT = "PROJECT"
    JURISDICTION = "JURISDICTION"


@dataclass(frozen=True)
class Rect:
    x1: float; y1: float; x2: float; y2: float
    @property
    def width(self): return self.x2 - self.x1
    @property
    def depth(self): return self.y2 - self.y1
    @property
    def area(self): return self.width * self.depth
    @property
    def center(self): return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)
    def intersects(self, other: "Rect", clearance: float = 0.0) -> bool:
        return not (self.x2 + clearance <= other.x1 or other.x2 + clearance <= self.x1 or self.y2 + clearance <= other.y1 or other.y2 + clearance <= self.y1)
    def contains(self, other: "Rect", tol: float = 1e-6) -> bool:
        return self.x1-tol <= other.x1 and self.y1-tol <= other.y1 and self.x2+tol >= other.x2 and self.y2+tol >= other.y2
    def shared_boundary(self, other: "Rect", tol: float = 1e-6):
        if abs(self.x2-other.x1)<tol or abs(other.x2-self.x1)<tol:
            fixed = self.x2 if abs(self.x2-other.x1)<tol else self.x1
            lo, hi = max(self.y1,other.y1), min(self.y2,other.y2)
            if hi-lo > tol: return ("V",fixed,lo,hi)
        if abs(self.y2-other.y1)<tol or abs(other.y2-self.y1)<tol:
            fixed = self.y2 if abs(self.y2-other.y1)<tol else self.y1
            lo, hi = max(self.x1,other.x1), min(self.x2,other.x2)
            if hi-lo > tol: return ("H",fixed,lo,hi)
        return None
    def to_list(self): return [self.x1,self.y1,self.x2,self.y2]


@dataclass
class Space:
    id: str; role: str; zone: str; rect: Rect | None = None
    label_fa: str = ""; habitable: bool = False; min_area: float = 0.0
    furniture_ids: list[str] = field(default_factory=list)


@dataclass
class DaylightSource:
    id: str; kind: str; rect: Rect; open_to_sky: bool = True; legal: bool = True


@dataclass
class OpeningIntent:
    id: str; kind: str; space_a: str; space_b_or_source: str
    host: tuple | None = None; geometry: tuple | None = None


@dataclass
class FurnitureUseZone:
    id: str; space_id: str; kind: str; rect: Rect; clearance_rect: Rect


@dataclass
class ConstraintResult:
    id: str; kind: str; status: str; severity: str; affected_spaces: list[str]
    evidence_geometry: list[Any]; source: str; suggested_repair_action_class: str; reason: str


QUALITY_FIELDS = ["access_validity","circulation_efficiency","public_private_separation","guest_privacy",
"bedroom_privacy","daylight_legality","daylight_quality","window_source_consistency","furniture_feasibility",
"room_proportion_quality","wet_core_efficiency","kitchen_functionality","entrance_legibility",
"parking_maneuver","courtyard_utility","corridor_penalty","mechanical_grid_penalty","wall_realization_quality"]


@dataclass
class ArchitecturalQualityVector:
    components: dict[str,float] = field(default_factory=lambda:{k:0.0 for k in QUALITY_FIELDS})
    reasons: dict[str,list[str]] = field(default_factory=dict)
    @property
    def aggregate(self): return round(sum(self.components.values())/len(self.components),2)


@dataclass
class ArchitecturalDesignState:
    candidate_id: str; revision: int = 1
    site_geometry: Rect = field(default_factory=lambda:Rect(0,0,10,20))
    legal_open_edges: list[str] = field(default_factory=list)
    street_access_edges: list[str] = field(default_factory=list)
    setbacks_yards_courtyards: dict[str,DaylightSource] = field(default_factory=dict)
    building_footprint_candidates: list[Rect] = field(default_factory=list)
    spaces: dict[str,Space] = field(default_factory=dict)
    adjacency_graph: set[tuple[str,str]] = field(default_factory=set)
    circulation_graph: set[tuple[str,str]] = field(default_factory=set)
    daylight_source_graph: dict[str,str] = field(default_factory=dict)
    opening_intents: list[OpeningIntent] = field(default_factory=list)
    furniture_use_zones: list[FurnitureUseZone] = field(default_factory=list)
    wall_graph: list[dict] = field(default_factory=list)
    free_space_navigation_graph: dict[str,list[str]] = field(default_factory=dict)
    navigation_paths: dict[str,list[tuple[float,float]]] = field(default_factory=dict)
    level_datums: dict[str,float] = field(default_factory=dict)
    rules: dict[str,Any] = field(default_factory=dict)
    pattern_provenance: list[str] = field(default_factory=list)
    unresolved_constraints: list[str] = field(default_factory=list)
    constraint_results: list[ConstraintResult] = field(default_factory=list)
    quality_vector: ArchitecturalQualityVector = field(default_factory=ArchitecturalQualityVector)
    trace: list[dict] = field(default_factory=list)
    drawing_scene: Any = None
    reviewed_revision: int | None = None
    def add_trace(self, stage, decision, evidence=None): self.trace.append({"stage":stage,"decision":decision,"evidence":evidence or []})
    def edge(self,a,b): return tuple(sorted((a,b)))
    def to_dict(self):
        raw=asdict(self); raw["adjacency_graph"]=sorted([list(x) for x in self.adjacency_graph]); raw["circulation_graph"]=sorted([list(x) for x in self.circulation_graph]); raw["drawing_scene"]=self.drawing_scene.to_dict() if hasattr(self.drawing_scene,"to_dict") else self.drawing_scene; raw["quality_vector"]["aggregate"]=self.quality_vector.aggregate; return raw
