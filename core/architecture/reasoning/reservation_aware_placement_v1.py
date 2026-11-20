"""Reservation-aware, resource-sensitive placement for envelope-level architecture."""
from __future__ import annotations

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union


def _poly(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type != "Polygon":
        parts = [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]
        if not parts:
            return []
        g = max(parts, key=lambda p: p.area)
    return [[round(float(x), 6), round(float(y), 6)] for x, y in list(g.exterior.coords)[:-1]]


class ReservationAwarePlacementV1:
    """Search legal placements before geometry is admitted to a candidate."""
    EPS = 1e-7

    @staticmethod
    def resource_and_demand_maps(parcel, site, family, demand_bias=None):
        x0, y0, x1, y1 = parcel.bounds
        depth = y1 - y0
        neighbors = site.get("neighbors", {})
        frontages = site.get("frontages", [])
        public_edges = {str(f.get("edge", "")).lower() for f in frontages if "public" in str(f.get("role", "")).lower()}
        for edge, relation in neighbors.items():
            if any(k in str(relation).lower() for k in ("road", "open", "public")):
                public_edges.add(str(edge).lower())
        if not public_edges:
            public_edges.add("south")
        private_edges = {str(e).lower() for e, r in neighbors.items()
                         if any(k in str(r).lower() for k in ("private", "closed", "privacy", "neighbor"))}
        # Demand zones represent principal-space regions least served by public edges.
        bands = {
            "north": box(x0, y0 + depth * .52, x1, y1),
            "south": box(x0, y0, x1, y0 + depth * .48),
            "west": box(x0, y0, x0 + (x1-x0) * .48, y1),
            "east": box(x0 + (x1-x0) * .52, y0, x1, y1),
        }
        targets = []
        if demand_bias:
            targets = [str(x).lower() for x in demand_bias]
        else:
            targets = [e for e in ("north", "west", "east", "south") if e not in public_edges][:2]
        demand = unary_union([bands[e] for e in targets if e in bands]).intersection(parcel) if targets else parcel
        low_value = parcel.difference(unary_union([bands[e].intersection(parcel).buffer(-min(x1-x0, depth)*.08) for e in public_edges]))
        return {"public_edges": sorted(public_edges), "private_edges": sorted(private_edges),
                "demand_targets": targets, "daylight_demand_geometry": _poly(demand),
                "low_resource_geometry": _poly(low_value),
                "frontage_value": {e: (1.0 if e in public_edges else .15 if e in private_edges else .45)
                                   for e in ("north", "east", "south", "west")}}

    def place_core(self, parcel, size, forbidden, resource_map, requirements):
        w, d = map(float, size); x0, y0, x1, y1 = parcel.bounds
        obstacle = unary_union([g for g in forbidden if g is not None and not g.is_empty])
        step = max(.4, float(requirements.get("placement_search_step", .6)))
        pedestrian_side = str(requirements.get("pedestrian_access_edge", "south")).lower()
        preferred = str(requirements.get("core_preferred_edge", "")).lower()
        candidates = []
        y = y0
        while y + d <= y1 + self.EPS:
            x = x0
            while x + w <= x1 + self.EPS:
                core = box(x, y, x+w, y+d)
                if parcel.buffer(self.EPS).covers(core) and core.intersection(obstacle).area <= self.EPS:
                    frontage_penalty = core.distance(LineString([[x0,y0],[x1,y0]]))
                    if pedestrian_side == "south": access = y-y0
                    elif pedestrian_side == "north": access = y1-(y+d)
                    elif pedestrian_side == "west": access = x-x0
                    else: access = x1-(x+w)
                    demand = Polygon(resource_map["daylight_demand_geometry"]) if resource_map.get("daylight_demand_geometry") else Polygon()
                    demand_penalty = core.intersection(demand).area
                    edge_distance={"north":y1-(y+d),"south":y-y0,"west":x-x0,"east":x1-(x+w)}.get(preferred,0)
                    score = access * 1.2 + demand_penalty * 3.0 - frontage_penalty * .15 + edge_distance * 2.0
                    candidates.append((score, core))
                x += step
            y += step
        if not candidates:
            return {"status":"not_feasible", "polygon":[], "searched_count":0, "accepted_count":0}
        candidates.sort(key=lambda item: (item[0], item[1].bounds[1], item[1].bounds[0]))
        core = candidates[0][1]
        minx,miny,maxx,maxy=core.bounds
        lobby_d=min(d*.28,1.5); stair_w=w*.58
        lobby=box(minx,miny,maxx,miny+lobby_d)
        stair=box(minx,miny+lobby_d,minx+stair_w,maxy)
        elevator=box(minx+stair_w,miny+lobby_d,maxx,maxy)
        return {"status":"placed_in_feasible_region", "polygon":_poly(core), "searched_count":len(candidates),
                "accepted_count":len(candidates), "selection_score":round(candidates[0][0],6),
                "stair":_poly(stair), "elevator":_poly(elevator), "lobby":_poly(lobby),
                "constraints":["vertical_alignment","pedestrian_accessibility","vehicle_exclusion",
                               "frontage_preservation","low_daylight_preference"]}

    def place_court(self, parcel, size, forbidden, demand_map, requirements):
        w,d=map(float,size);x0,y0,x1,y1=parcel.bounds
        obstacle=unary_union([g for g in forbidden if g is not None and not g.is_empty])
        demand=Polygon(demand_map["daylight_demand_geometry"]) if demand_map.get("daylight_demand_geometry") else parcel
        step=max(.4,float(requirements.get("placement_search_step",.6))); margin=float(requirements.get("court_maintenance_clearance",.3))
        trials=[];y=y0+margin
        while y+d<=y1-margin+self.EPS:
            x=x0+margin
            while x+w<=x1-margin+self.EPS:
                court=box(x,y,x+w,y+d)
                if parcel.buffer(self.EPS).covers(court) and court.buffer(margin).intersection(obstacle).area<=self.EPS:
                    benefit=court.buffer(max(w,d)*1.2).intersection(demand).area
                    privacy_penalty=sum(court.distance(LineString([[x0,y1],[x1,y1]])) < margin for _ in [0] if "north" in demand_map.get("private_edges",[]))
                    trials.append((-(benefit-privacy_penalty),court,benefit))
                x+=step
            y+=step
        if not trials:return {"status":"not_feasible","polygon":[],"searched_count":0,"accepted_count":0,"useful_daylight_benefit":0}
        trials.sort(key=lambda t:(t[0],t[1].bounds[1],t[1].bounds[0]));court=trials[0][1]
        return {"status":"placed_from_daylight_demand","polygon":_poly(court),"searched_count":len(trials),
                "accepted_count":len(trials),"useful_daylight_benefit":round(trials[0][2],6),
                "demand_targets":demand_map.get("demand_targets",[]),"maintenance_clearance":margin}

    def terrace_alternatives(self, unit, parcel, forbidden, demand_map, requirements):
        depth=float(requirements.get("terrace_depth",1.5));min_area=float(requirements.get("terrace_min_area",2.0))
        x0,y0,x1,y1=parcel.bounds; forbidden_shape=unary_union([g for g in forbidden if g is not None and not g.is_empty])
        bands={"south":box(x0,y0,x1,y0+depth),"east":box(x1-depth,y0,x1,y1),
               "north":box(x0,y1-depth,x1,y1),"west":box(x0,y0,x0+depth,y1)}
        court = forbidden[1] if len(forbidden) > 1 else Polygon()
        if court is not None and not court.is_empty:
            bands["daylight_court"] = court.buffer(depth, join_style=2).difference(court)
        private=set(demand_map.get("private_edges",[]));values={**demand_map.get("frontage_value",{}),"daylight_court":.78}
        alternatives=[]
        for edge,band in bands.items():
            if edge in private:continue
            geom=unit.intersection(band).difference(forbidden_shape)
            parts=[geom] if geom.geom_type=="Polygon" else list(getattr(geom,"geoms",[]))
            for part in parts:
                if part.area>=min_area:alternatives.append((-(values.get(edge,.4)*part.area),edge,part))
        alternatives.sort(key=lambda a:(a[0],a[1]))
        return {"searched_edges":sorted(set(bands)-private),"alternative_count":len(alternatives),
                "selected_edge":alternatives[0][1] if alternatives else None,
                "polygon":_poly(alternatives[0][2]) if alternatives else []}
