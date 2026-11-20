from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Primitive:
    kind: str
    layer: str
    geometry: dict[str, Any]
    style: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArchitecturalDrawingScene:
    candidate_id: str
    sheet: dict[str, Any] = field(default_factory=lambda: {"size": "A3", "orientation": "LANDSCAPE", "scale": 50})
    primitives: list[Primitive] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add(self, kind: str, layer: str, geometry: dict[str, Any], style: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> Primitive:
        item = Primitive(kind, layer, geometry, style or {}, metadata or {})
        self.primitives.append(item)
        return item

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for item in self.primitives:
            result[item.kind] = result.get(item.kind, 0) + 1
        return result

    def layer_counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for item in self.primitives:
            result[item.layer] = result.get(item.layer, 0) + 1
        return result

    def to_dict(self) -> dict[str, Any]:
        return {"candidate_id": self.candidate_id, "sheet": self.sheet, "metadata": self.metadata,
                "counts": self.counts(), "layer_counts": self.layer_counts(),
                "primitives": [asdict(p) for p in self.primitives]}
