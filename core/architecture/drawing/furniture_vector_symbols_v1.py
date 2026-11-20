from __future__ import annotations

from .architectural_scene_v1 import ArchitecturalDrawingScene
from .architectural_symbol_library_v1 import SYMBOL_LIBRARY

REGISTRY = {k:tuple(v["nominal_footprint_m"]) for k,v in SYMBOL_LIBRARY.items()}

def add_symbol(scene: ArchitecturalDrawingScene, symbol: str, x: float, y: float, w: float | None = None,
               h: float | None = None, rotation: float = 0, room: str | None = None) -> None:
    w, h = (w or REGISTRY[symbol][0]), (h or REGISTRY[symbol][1])
    spec=SYMBOL_LIBRARY[symbol]
    meta = dict(spec, symbol_id=symbol, nominal_m=[w,h], authority="DESIGN_HEURISTIC", room=room)
    layer={"KITCHEN":"CABINETRY","BATH_WC":"FIXTURES","LANDSCAPE":"LANDSCAPE","ENTRY":"SITE_FEATURES","PARKING":"SITE_FEATURES"}.get(spec["category"],"FURNITURE")
    scene.add("GROUP",layer,{"symbol":symbol,"x":x,"y":y,"w":w,"h":h,"rotation":rotation,"mirror":False,"vector_primitives":spec["vector_primitives"]},metadata=meta)
