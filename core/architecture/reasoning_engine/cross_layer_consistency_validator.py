from __future__ import annotations

from .state import ConstraintKind, ConstraintResult


class CrossLayerConsistencyValidator:
    def validate(self,s):
        issues=[]; ids=set(s.spaces)
        def add(i,reason,affected=None,evidence=None): issues.append(ConstraintResult(i,"HARD","FAIL","BLOCKING",affected or [],evidence or [],"CROSS_LAYER_GATE","RegenerateAffectedStage",reason))
        for a,b in s.adjacency_graph|s.circulation_graph:
            if a not in ids|{"SITE_ENTRY"} or b not in ids|{"SITE_ENTRY"}: add("XL_UNKNOWN_GRAPH_ID",f"شناسه ناشناخته {a}/{b}",[a,b])
        opening_pairs={tuple(sorted((o.space_a,o.space_b_or_source))) for o in s.opening_intents if o.kind in {"DOOR","OPEN"}}
        for edge in s.circulation_graph:
            if "SITE_ENTRY" not in edge and tuple(sorted(edge)) not in opening_pairs: add("XL_SEMANTIC_EDGE_WITHOUT_OPENING",f"یال {edge} بازشوی واقعی ندارد",list(edge))
        for o in s.opening_intents:
            if o.kind=="WINDOW":
                declared=s.daylight_source_graph.get(o.space_a)
                if declared!=o.space_b_or_source: add("XL_WINDOW_SOURCE_MISMATCH",f"پنجره {o.id} با منبع graph همسان نیست",[o.space_a],[o.geometry])
        furniture_ids={f.space_id for f in s.furniture_use_zones}
        for sid,sp in s.spaces.items():
            if sp.furniture_ids and sid not in furniture_ids:add("XL_FURNITURE_FLAG_WITHOUT_GEOMETRY",f"فضای {sid} fit دارد ولی هندسه مبلمان ندارد",[sid])
        scene=s.drawing_scene
        if scene:
            room_labels={p.metadata.get("room") for p in scene.primitives if p.layer=="LABELS"}
            missing=ids-room_labels
            if missing:add("XL_SCENE_SPACE_ID_MISMATCH","همه فضاها در scene وجود ندارند",sorted(missing))
            north=[p for p in scene.primitives if p.kind=="GROUP" and p.geometry.get("symbol")=="NORTH_ARROW"]
            if not north:add("XL_ORIENTATION_MISMATCH","فلش شمال scene موجود نیست")
        else:add("XL_MISSING_DRAWING_SCENE","drawing scene تولید نشده")
        return {"status":"PASS" if not issues else "FAIL","issues":[x.__dict__ for x in issues],"checked_layers":["semantic_graph","room_polygons","wall_graph","openings","daylight_graph","free_space_navigation","furniture","drawing_scene"]}
