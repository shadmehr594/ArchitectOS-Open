"""
ArchitectOS Opening Reasoner V2

Parametric architectural door and window intelligence.

Handles:
- residential openings
- commercial doors
- basement windows
- accessibility
- facade connection
- functional dimensions
"""


class OpeningReasonerV2:


    VERSION = "2.0"



    def __init__(self):

        print(
            "🪟 OPENING REASONER V2 ONLINE"
        )

    def resolve_connections(self, connections, physical_walls, existing_openings=None, protected_zones=None):
        """Create interior opening intents only from resolved connection interfaces."""
        existing_openings = existing_openings if isinstance(existing_openings, list) else []
        protected_zones = protected_zones if isinstance(protected_zones, list) else []
        intents=[];seen=set()
        for connection in connections if isinstance(connections,list) else []:
            if not isinstance(connection,dict):continue
            pair=tuple(sorted((str(connection.get("from_space_id") or connection.get("from")),str(connection.get("to_space_id") or connection.get("to")))))
            identity=connection.get("connection_id") or pair
            if identity in seen:continue
            seen.add(identity)
            if connection.get("door_required") is not True and connection.get("required") is not True:continue
            base={"opening_id":f"INTERIOR-{connection.get('connection_id')}","id":f"INTERIOR-{connection.get('connection_id')}",
                  "connection_id":connection.get("connection_id"),"from_space_id":pair[0],"to_space_id":pair[1],
                  "connects_from":connection.get("from_space_id") or connection.get("from"),"connects_to":connection.get("to_space_id") or connection.get("to"),
                  "from_floor":connection.get("from_floor"),"to_floor":connection.get("to_floor"),"floor":connection.get("from_floor"),
                  "opening_role":"interior_connection","opening_type":"door","type":"door","category":"interior_door",
                  "door_required":connection.get("door_required") is True,"privacy_role":connection.get("privacy_class"),
                  "circulation_role":connection.get("circulation_role"),"shared_boundary_reference":connection.get("shared_boundary"),
                  "preferred_interface_segment":connection.get("shared_boundary"),"width":connection.get("required_clear_width"),
                  "height":connection.get("required_clear_height"),"source":"resolved_spatial_connection_contract",
                  "evidence_status":connection.get("evidence_status"),"semantic_scope":"interior_opening",
                  "geometry_status":"pending","geometry_generation_allowed":False}
            if connection.get("privacy_violation") is True:
                base["opening_resolution_status"]="not_feasible_privacy_violation";intents.append(base);continue
            if connection.get("geometry_status")!="resolved_shared_boundary" or connection.get("from_floor")!=connection.get("to_floor"):
                base["opening_resolution_status"]="shared_boundary_pending";intents.append(base);continue
            if not self._positive(base["width"]) or not self._positive(base["height"]):
                base["opening_resolution_status"]="opening_dimensions_pending";intents.append(base);continue
            segment=connection.get("shared_boundary") or {};a=segment.get("start");b=segment.get("end")
            hosts=[w for w in physical_walls if isinstance(w,dict) and w.get("floor")==base["floor"]
                   and set(pair).issubset(set(map(str,w.get("spaces",[])))) and self._same_segment(w,a,b)]
            base["candidate_wall_ids"]=[w.get("wall_id") for w in hosts]
            if len(hosts)!=1:
                base["opening_resolution_status"]="pending_multiple_hosts" if len(hosts)>1 else "host_unresolved";intents.append(base);continue
            points=[]
            if self._point(connection.get("preferred_opening_point")):points=[self._point(connection["preferred_opening_point"])]
            else:points=[self._point(p) for p in connection.get("opening_point_candidates",[]) if self._point(p)]
            feasible=[p for p in points if self._on_segment(p,a,b) and self._fits(p,a,b,float(base["width"]),connection.get("end_clearance"))]
            if len(feasible)!=1:
                base["host_wall_id"]=hosts[0].get("wall_id")
                base["opening_resolution_status"]="pending_tie" if len(feasible)>1 else "placement_pending";intents.append(base);continue
            center=feasible[0]
            if self._overlaps_existing(center,float(base["width"]),hosts[0],existing_openings):
                base["opening_resolution_status"]="not_feasible_opening_overlap";intents.append(base);continue
            if self._conflicts_protected_zone(center,float(base["width"]),hosts[0],protected_zones):
                base["opening_resolution_status"]="not_feasible_protected_zone";intents.append(base);continue
            base.update({"host_wall_id":hosts[0].get("wall_id"),"opening_center":center,
                         "end_clearance":connection.get("end_clearance"),"opening_resolution_status":"resolved_interface_host_and_point"})
            intents.append(base)
        return intents

    def resolve_exterior_exposure(self, spaces, physical_walls):
        """Derive room exposure only from topologically exterior physical walls."""
        contracts=[]
        for space in spaces if isinstance(spaces,list) else []:
            if not isinstance(space,dict):continue
            sid=space.get("space_id") or space.get("id") or space.get("name");floor=space.get("floor")
            walls=[w for w in physical_walls if isinstance(w,dict) and w.get("floor")==floor
                   and w.get("is_exterior") is True and sid in w.get("spaces",[])]
            segments=[{"wall_id":w.get("wall_id"),"start":w.get("start"),"end":w.get("end"),
                       "solid_segments":w.get("solid_segments",[])} for w in walls]
            contracts.append({"space_id":sid,"floor":floor,
              "exterior_exposure_status":"resolved" if walls else "interior_only",
              "exterior_wall_ids":[w.get("wall_id") for w in walls],"exterior_boundary_segments":segments,
              "orientation":None,"privacy_class":space.get("privacy_level") or space.get("privacy_requirements"),
              "daylight_requirement":space.get("daylight_requirement"),"ventilation_requirement":space.get("ventilation_requirement"),
              "source":"physical_wall_boundary_topology","evidence_status":"authoritative_geometry",
              "unresolved_evidence":[] if walls else ["exterior_physical_boundary"]})
        return contracts

    def resolve_windows(self, exposures, requirements, physical_walls, existing_openings=None, protected_zones=None):
        existing_openings=existing_openings if isinstance(existing_openings,list) else []
        protected_zones=protected_zones if isinstance(protected_zones,list) else []
        exposure_by={(e.get("space_id"),e.get("floor")):e for e in exposures if isinstance(e,dict)}
        intents=[];seen=set()
        for index,req in enumerate(requirements if isinstance(requirements,list) else []):
            if not isinstance(req,dict):continue
            sid=req.get("space_id");floor=req.get("floor");identity=req.get("window_id") or (sid,floor,req.get("role","exterior_window"))
            if identity in seen:continue
            seen.add(identity);exposure=exposure_by.get((sid,floor))
            base={"id":req.get("window_id") or f"WINDOW-{index+1:03d}","opening_id":req.get("window_id") or f"WINDOW-{index+1:03d}",
                  "type":"window","category":req.get("role","exterior_window"),"space":sid,"served_space_id":sid,"floor":floor,
                  "width":req.get("clear_width",req.get("width")),"height":req.get("clear_height",req.get("height")),
                  "sill_height":req.get("sill_height"),"head_height":req.get("head_height"),
                  "daylight_requirement":req.get("daylight_requirement"),
                  "ventilation_requirement":req.get("ventilation_requirement"),
                  "privacy_requirement":req.get("privacy_requirement",req.get("privacy_control")),
                  "source":req.get("source","project_window_requirement"),"evidence_status":req.get("evidence_status"),
                  "geometry_status":"pending","geometry_generation_allowed":False,"exterior_host_status":"pending",
                  "daylight_feasibility_status":"unresolved" if req.get("daylight_requirement") is not None else "requirement_not_numeric",
                  "privacy_status":"pending"}
            if not exposure or exposure.get("exterior_exposure_status")!="resolved":
                base["window_resolution_status"]="forbidden_interior_only" if exposure else "exterior_exposure_pending";intents.append(base);continue
            if req.get("privacy_conflict") is True:
                base["window_resolution_status"]="not_feasible_privacy_conflict";intents.append(base);continue
            if not self._positive(base["width"]) or not self._positive(base["height"]):
                base["window_resolution_status"]="window_dimensions_pending";intents.append(base);continue
            hosts=[w for w in physical_walls if isinstance(w,dict) and w.get("wall_id") in exposure["exterior_wall_ids"]
                   and w.get("is_exterior") is True and sid in w.get("spaces",[]) and w.get("floor")==floor
                   and self._wall_usable_for_window(w,float(base["width"]),float(base["height"]),base.get("sill_height"),base.get("head_height"))]
            base["candidate_wall_ids"]=[w.get("wall_id") for w in hosts]
            if len(hosts)!=1:
                base["window_resolution_status"]="pending_multiple_hosts" if len(hosts)>1 else "no_usable_exterior_host";intents.append(base);continue
            points=[self._point(req.get("preferred_opening_point"))] if self._point(req.get("preferred_opening_point")) else [self._point(p) for p in req.get("opening_point_candidates",[]) if self._point(p)]
            wall=hosts[0];a,b=wall.get("start"),wall.get("end")
            feasible=[p for p in points if self._on_segment(p,a,b) and self._fits(p,a,b,float(base["width"]),req.get("end_clearance"))]
            if len(feasible)!=1:
                base["host_wall_id"]=wall.get("wall_id");base["window_resolution_status"]="pending_tie" if len(feasible)>1 else "placement_pending";intents.append(base);continue
            center=feasible[0]
            if self._overlaps_existing(center,float(base["width"]),wall,existing_openings):
                base["window_resolution_status"]="not_feasible_opening_overlap";intents.append(base);continue
            if self._conflicts_protected_zone(center,float(base["width"]),wall,protected_zones):
                base["window_resolution_status"]="not_feasible_protected_zone";intents.append(base);continue
            base.update({"host_wall_id":wall.get("wall_id"),"opening_center":center,"end_clearance":req.get("end_clearance"),
                         "window_resolution_status":"resolved_exterior_host_and_point","exterior_host_status":"resolved",
                         "privacy_status":"resolved_from_requirement","daylight_feasibility_status":"exterior_opening_supported"})
            intents.append(base)
        return intents

    @classmethod
    def _wall_usable_for_window(cls,w,width,height,sill,head):
        import math
        a,b=cls._point(w.get("start")),cls._point(w.get("end"))
        if not a or not b or math.hypot(b[0]-a[0],b[1]-a[1])+1e-7<width:return False
        wall_height=w.get("height")
        if isinstance(wall_height,(int,float)):
            if height>wall_height+1e-7:return False
            if isinstance(sill,(int,float)) and sill+height>wall_height+1e-7:return False
            if isinstance(head,(int,float)) and head>wall_height+1e-7:return False
        return True

    @staticmethod
    def _positive(v):return isinstance(v,(int,float)) and v>0
    @staticmethod
    def _point(v):return [float(v[0]),float(v[1])] if isinstance(v,(list,tuple)) and len(v)>=2 else None
    @classmethod
    def _same_segment(cls,w,a,b):return cls._on_segment(cls._point(w.get("start")),a,b) and cls._on_segment(cls._point(w.get("end")),a,b) or cls._on_segment(a,w.get("start"),w.get("end")) and cls._on_segment(b,w.get("start"),w.get("end"))
    @classmethod
    def _on_segment(cls,p,a,b):
        p,a,b=cls._point(p),cls._point(a),cls._point(b)
        if not p or not a or not b:return False
        cross=abs((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))
        return cross<=1e-6 and min(a[0],b[0])-1e-7<=p[0]<=max(a[0],b[0])+1e-7 and min(a[1],b[1])-1e-7<=p[1]<=max(a[1],b[1])+1e-7
    @classmethod
    def _fits(cls,p,a,b,width,clearance):
        import math
        c=float(clearance) if isinstance(clearance,(int,float)) else 0.0
        length=math.hypot(b[0]-a[0],b[1]-a[1]);along=math.hypot(p[0]-a[0],p[1]-a[1])
        return along-width/2>=c-1e-7 and along+width/2<=length-c+1e-7
    @classmethod
    def _overlaps_existing(cls,p,width,wall,openings):
        import math
        a=cls._point(wall.get("start"));b=cls._point(wall.get("end"));L=math.hypot(b[0]-a[0],b[1]-a[1]);ux=(b[0]-a[0])/L;uy=(b[1]-a[1])/L
        center=(p[0]-a[0])*ux+(p[1]-a[1])*uy;lo,hi=center-width/2,center+width/2
        for o in openings:
            if o.get("host_wall_id")!=wall.get("wall_id") or o.get("geometry_status")!="resolved":continue
            q=cls._point(o.get("opening_center"));ow=o.get("resolved_width",o.get("width"))
            if q and cls._positive(ow):
                oc=(q[0]-a[0])*ux+(q[1]-a[1])*uy
                if min(hi,oc+ow/2)-max(lo,oc-ow/2)>1e-7:return True
        return False

    @classmethod
    def _conflicts_protected_zone(cls,center,width,wall,zones):
        import math
        a,b=cls._point(wall.get("start")),cls._point(wall.get("end"))
        if not a or not b:return True
        length=math.hypot(b[0]-a[0],b[1]-a[1])
        if length<=1e-9:return True
        ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
        p=[center[0]-ux*width/2,center[1]-uy*width/2];q=[center[0]+ux*width/2,center[1]+uy*width/2]
        for zone in zones:
            poly=zone.get("polygon",zone.get("points")) if isinstance(zone,dict) else zone
            if not isinstance(poly,list) or len(poly)<3:continue
            if cls._inside(p,poly) or cls._inside(q,poly) or any(cls._intersects(p,q,poly[i],poly[(i+1)%len(poly)]) for i in range(len(poly))):return True
        return False

    @staticmethod
    def _inside(p,poly):
        inside=False;j=len(poly)-1
        for i in range(len(poly)):
            xi,yi=poly[i][:2];xj,yj=poly[j][:2]
            if (yi>p[1])!=(yj>p[1]) and p[0]<(xj-xi)*(p[1]-yi)/(yj-yi)+xi:inside=not inside
            j=i
        return inside
    @staticmethod
    def _intersects(a,b,c,d):
        def orient(p,q,r):return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
        return orient(a,b,c)*orient(a,b,d)<=0 and orient(c,d,a)*orient(c,d,b)<=0



    def resolve(
        self,
        space,
        context=None
    ):


        context = context or {}


        name = space.get(
            "name",
            ""
        )


        zone = space.get(
            "zone"
        )


        role = space.get(
            "role"
        )


        building_type = context.get(
            "building_type",
            "residential"
        )


        floor = context.get(
            "floor",
            "F1"
        )


        level_condition = context.get(
            "level_condition",
            "above_grade"
        )

        # ==============================================
        # PARCEL / PRIVACY EDGE INTELLIGENCE v1.0
        #
        # Consume confirmed site-edge evidence.
        #
        # IMPORTANT:
        # This does not invent a regulatory prohibition.
        # It only marks privacy-sensitive conditions.
        # ==============================================

        preferred_edge_index = space.get(
            "preferred_edge_index"
        )

        edge_relation = space.get(
            "edge_relation"
        )

        site_context = context.get(
            "site_context",
            {}
        )


        if not isinstance(
            site_context,
            dict
        ):

            site_context = {}


        parcel_edge_roles = site_context.get(
            "parcel_edge_roles"
        )


        if not isinstance(
            parcel_edge_roles,
            list
        ):

            parcel_edge_roles = context.get(
                "parcel_edge_roles",
                []
            )


        if not isinstance(
            parcel_edge_roles,
            list
        ):

            parcel_edge_roles = []


        selected_edge_role = None


        for edge_role in parcel_edge_roles:

            if not isinstance(
                edge_role,
                dict
            ):

                continue


            if (
                preferred_edge_index is not None
                and
                edge_role.get(
                    "edge_index"
                ) == preferred_edge_index
            ):

                selected_edge_role = edge_role

                break


        privacy_edge = False


        if isinstance(
            selected_edge_role,
            dict
        ):

            privacy_edge = bool(
                selected_edge_role.get(
                    "privacy_constraint",
                    False
                )
            )


            if not edge_relation:

                edge_relation = selected_edge_role.get(
                    "relation"
                )

        # ==============================================
        # SITE / FACADE EVIDENCE STATUS v1.0
        #
        # Opening geometry may still be generated from
        # typology knowledge while parcel-edge approval
        # remains unresolved.
        #
        # Do not confuse design intent with confirmed
        # facade placement.
        # ==============================================

        edge_decision_status = space.get(
            "edge_decision_status"
        )


        if edge_decision_status is None:

            edge_decision_status = context.get(
                "edge_decision_status"
            )


        site_evidence_status = "unresolved"

        facade_approval_status = "pending"


        if isinstance(
            selected_edge_role,
            dict
        ):

            selected_edge_status = (
                selected_edge_role.get(
                    "decision_status"
                )
            )


            selected_edge_confirmed = bool(
                selected_edge_role.get(
                    "confirmed",
                    False
                )
            )


            if (
                selected_edge_status == "resolved"
                or
                selected_edge_confirmed
            ):

                site_evidence_status = (
                    "resolved_from_parcel"
                )

                facade_approval_status = (
                    "edge_evidence_available"
                )


            elif selected_edge_status == "pending":

                site_evidence_status = (
                    "parcel_edge_pending"
                )

                facade_approval_status = (
                    "pending"
                )


        elif not parcel_edge_roles:

            site_evidence_status = (
                "site_evidence_unavailable"
            )

            facade_approval_status = (
                "pending"
            )


        if edge_decision_status == "pending":

            facade_approval_status = (
                "pending"
            )


        openings = []


        openings = []



        # ==================================
        # BASEMENT INTELLIGENCE
        # ==================================

        if level_condition == "below_grade":


            openings.append(

                self.create_basement_window()

            )



        # ==================================
        # COMMERCIAL
        # ==================================

        elif building_type in [

            "shop",
            "commercial",
            "retail",
            "mixed_use_commercial_residential"

        ] and name in ("shop", "store", "commercial", "retail"):


            openings.extend(

                self.resolve_commercial(
                    space
                )

            )



        # ==================================
        # RESIDENTIAL
        # ==================================

        else:


            openings.extend(

                self.resolve_residential(
                    name,
                    zone,
                    role,
                    privacy_edge=privacy_edge,
                    edge_relation=edge_relation,
                    selected_edge_role=selected_edge_role
                )

            )

        # ==============================================
        # ATTACH SITE DECISION EVIDENCE
        # ==============================================

        for opening in openings:

            if not isinstance(
                opening,
                dict
            ):

                continue

            if opening.get("type") == "door" and opening.get("category") != "main_entrance":
                adjacent = space.get("adjacent_to", [])
                adjacent = adjacent if isinstance(adjacent, list) else []
                preferences = {
                    "bedroom": ("corridor", "hallway", "night_hall"),
                    "master_bedroom": ("corridor", "night_hall", "hallway"),
                    "guest_room": ("corridor", "hallway", "living"),
                    "bathroom": ("corridor", "bedroom", "hallway"),
                    "guest_wc": ("corridor", "hallway", "entrance"),
                    "toilet": ("corridor", "hallway"),
                    "stairs": ("corridor", "hallway", "lobby"),
                    "stair": ("corridor", "hallway", "lobby"),
                    "stair_landing": ("corridor", "hallway", "lobby"),
                    "vertical_core": ("corridor", "hallway", "lobby"),
                }
                preferred = preferences.get(name, ())
                target = next((item for item in preferred if item in adjacent), None)
                if target is None and adjacent:
                    target = adjacent[0]
                opening["connects_from"] = name
                opening["connects_to"] = target
                opening["connection_status"] = (
                    "resolved_from_space_adjacency" if target else "adjacency_pending"
                )


            opening[
                "preferred_edge_index"
            ] = preferred_edge_index

            opening[
                "edge_decision_status"
            ] = edge_decision_status

            opening[
                "site_evidence_status"
            ] = site_evidence_status

            opening[
                "facade_approval_status"
            ] = facade_approval_status


            if opening.get(
                "edge_relation"
            ) is None:

                opening[
                    "edge_relation"
                ] = edge_relation



        return {


            "space":
                name,


            "floor":
                floor,


            "openings":
                openings,


            "design_logic":[

                "opening_size_based_on_space_function",

                "window_height_based_on_usage",

                "privacy_controls_opening_ratio",

                "facade_relation_controls_position"

            ]

        }





    # ==================================
    # RESIDENTIAL
    # ==================================

    def resolve_residential(
        self,
        name,
        zone,
        role,
        privacy_edge=False,
        edge_relation=None,
        selected_edge_role=None
    ):


        if name in [

            "entrance",
            "main_entrance"

        ]:


            return [

                {

                    "type":
                        "door",

                    "category":
                        "main_entrance",

                    "width":
                        1400,

                    "height":
                        2400,

                    "material":
                        "glass_aluminum",

                    "operation":
                        "pivot",

                    "swing_direction":
                        "outward",

                    "egress_role":
                        "primary_exit",

                    "reason":
                        "main_access"

                }

            ]



        if name in [

            "living",
            "family_room"

        ]:


            if privacy_edge:

                return [

                    {

                        "type":
                            "window",

                        "category":
                            "controlled_living_window",

                        "width":
                            1800,

                        "height":
                            1500,

                        "sill_height":
                            900,

                        "head_height":
                            2400,

                        "material":
                            "glass_aluminum",

                        "operation":
                            "sliding",

                        "privacy":
                            "controlled",

                        "privacy_control_required":
                            True,

                        "edge_relation":
                            edge_relation,

                        "edge_role":
                            selected_edge_role.get(
                                "primary_role"
                            )
                            if isinstance(
                                selected_edge_role,
                                dict
                            )
                            else None,

                        "reason":
                            "daylight_with_neighbor_privacy_control"

                    }

                ]


            return [

                {

                    "type":
                        "window",

                    "category":
                        "living_room_glazing",

                    "width":
                        3000,

                    "height":
                        2400,

                    "sill_height":
                        300,

                    "head_height":
                        2700,

                    "material":
                        "glass_aluminum",

                    "operation":
                        "sliding",

                    "privacy_control_required":
                        False,

                    "edge_relation":
                        edge_relation,

                    "reason":
                        "daylight_and_view"

                }

            ]



        if name in [

            "bedroom",
            "master_bedroom",
            "guest_room"

        ]:


            return [

                {
                    "type": "door",
                    "category": "bedroom_door",
                    "width": 900,
                    "height": 2100,
                    "material": "wood",
                    "operation": "hinged",
                    "swing_direction": "inward",
                    "reason": "private_room_access"
                },

                {

                    "type":
                        "window",

                    "category":
                        "bedroom_window",

                    "width":
                        1500,

                    "height":
                        1500,

                    "sill_height":
                        900,

                    "head_height":
                        2400,

                    "material":
                        "glass_aluminum",

                    "operation":
                        "sliding",

                    "privacy":
                        "high",

                    "privacy_control_required":
                        bool(
                            privacy_edge
                        ),

                    "edge_relation":
                        edge_relation,

                    "edge_role":
                        selected_edge_role.get(
                            "primary_role"
                        )
                        if isinstance(
                            selected_edge_role,
                            dict
                        )
                        else None,

                    "reason":
                        (
                            "controlled_daylight_with_neighbor_privacy"
                            if privacy_edge
                            else "controlled_daylight"
                        )

                }

            ]



        if name in [

            "bathroom",
            "guest_wc",
            "toilet",
            "wc",
            "service"

        ]:


            return [

                {
                    "type": "door",
                    "category": "wet_room_door",
                    "width": 800,
                    "height": 2100,
                    "material": "moisture_resistant_wood",
                    "operation": "hinged",
                    "swing_direction": "inward",
                    "reason": "wet_room_access"
                },

                {

                    "type":
                        "window",

                    "category":
                        "high_level_window",

                    "width":
                        600,

                    "height":
                        600,

                    "sill_height":
                        1800,

                    "head_height":
                        2400,

                    "material":
                        "obscure_glass",

                    "privacy":
                        "high",

                    "privacy_control_required":
                        bool(
                            privacy_edge
                        ),

                    "edge_relation":
                        edge_relation,

                    "edge_role":
                        selected_edge_role.get(
                            "primary_role"
                        )
                        if isinstance(
                            selected_edge_role,
                            dict
                        )
                        else None,

                    "reason":
                        (
                            "ventilation_privacy_with_neighbor_edge_control"
                            if privacy_edge
                            else "ventilation_privacy"
                        )

                }

            ]



        if name == "terrace":


            return [

                {

                    "type":
                        "door",

                    "category":
                        "sliding_terrace_door",

                    "width":
                        2400,

                    "height":
                        2400,

                    "sill_height":
                        0,

                    "material":
                        "glass_aluminum",

                    "operation":
                        "sliding",

                    "reason":
                        "indoor_outdoor_connection"

                }

            ]

        if name in ("stairs", "stair", "staircase", "stair_landing", "vertical_core"):
            return [{
                "type": "door", "category": "stair_enclosure_door",
                "width": 1000, "height": 2100, "material": "fire_rated_steel",
                "operation": "hinged", "swing_direction": "outward_egress",
                "fire_rating_minutes": 90, "egress_role": "protected_escape_route",
                "reason": "protected_stair_access"
            }]

        if name in ("roof_stair", "roof_access", "penthouse_stair", "kharposhteh"):
            return [{
                "type": "door", "category": "roof_access_door",
                "width": 900, "height": 2100, "material": "weatherproof_steel",
                "operation": "hinged", "swing_direction": "outward",
                "reason": "roof_exit"
            }]

        if name in ("garage", "parking_entrance", "vehicle_access"):
            garage_operation = "rolling_shutter"
            return [{
                "type": "door", "category": "garage_vehicle_door",
                "width": 3000, "height": 2400, "material": "steel",
                "operation": garage_operation, "swing_direction": "none",
                "motorized": True, "reason": "vehicle_access"
            }]



        return []





    # ==================================
    # COMMERCIAL
    # ==================================

    def resolve_commercial(
        self,
        space
    ):


        name = space.get(
            "name"
        )


        if name in [

            "shop",
            "store",
            "commercial"

        ]:


            return [

                {

                    "type":
                        "door",

                    "category":
                        "storefront_entry",

                    "width":
                        1800,

                    "height":
                        2800,

                    "material":
                        "glass_aluminum",

                    "operation":
                        "automatic_sliding",

                    "swing_direction":
                        "none",

                    "glass_type":
                        "tempered_safety_glass",

                    "egress_role":
                        "commercial_exit",

                    "reason":
                        "customer_access"

                }

            ]



        return []





    # ==================================
    # BASEMENT
    # ==================================

    def create_basement_window(
        self
    ):


        return {


            "type":
                "window",


            "category":
                "basement_window",


            "width":
                1200,


            "height":
                600,


            "sill_height":
                1200,


            "head_height":
                1800,


            "window_well":
                True,


            "reason":
                "below_grade_daylight"

        }
