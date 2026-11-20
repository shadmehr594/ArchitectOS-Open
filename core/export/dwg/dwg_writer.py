import os
import math
import ezdxf


class DWGWriter:

    VERSION = "1.1"

    SPACE_LABELS = {
        "living": "نشیمن / LIVING",
        "living_room": "نشیمن / LIVING",
        "reception": "پذیرایی / RECEPTION",
        "dining": "ناهارخوری / DINING",
        "kitchen": "آشپزخانه / KITCHEN",
        "bedroom": "اتاق خواب / BEDROOM",
        "master_bedroom": "اتاق خواب مستر / MASTER BEDROOM",
        "corridor": "راهرو / CORRIDOR",
        "hallway": "راهرو / CORRIDOR",
        "stairs": "راه پله / STAIRS",
        "stair": "راه پله / STAIRS",
        "bathroom": "حمام / BATHROOM",
        "guest_wc": "سرویس مهمان / GUEST WC",
        "toilet": "سرویس / WC",
        "entrance": "ورودی / ENTRANCE",
        "yard": "حیاط / YARD",
        "courtyard": "حیاط مرکزی / COURTYARD",
    }


    def __init__(self):

        print(
            f"📐 DWG/DXF Writer v{self.VERSION} ACTIVE"
        )

    # ==========================================
    # LAYER MANAGEMENT
    # ==========================================

    def setup_layers(
        self,
        doc
    ):

        layers = [

            "SITE",

            "F1_WALLS",
            "F1_DOORS",
            "F1_WINDOWS",
            "F1_ROOMS",
            "F1_TEXT",

            "F2_WALLS",
            "F2_DOORS",
            "F2_WINDOWS",
            "F2_ROOMS",
            "F2_TEXT",

            "F3_WALLS",
            "F3_DOORS",
            "F3_WINDOWS",
            "F3_ROOMS",
            "F3_TEXT",

            "EXTERNAL_SPACE"

            ,"STRUCT_COLUMNS"
            ,"STRUCT_BEAMS"
            ,"ARCH_STAIRS"
            ,"STAIR"
            ,"STAIR_FLIGHT"
            ,"STAIR_LANDING"
            ,"STAIR_DIRECTION"
            ,"STAIR_TEXT"
            ,"ARCH_FURNITURE"
            ,"ARCH_CIRCULATION"
            ,"SITE_ROAD"
            ,"SITE_VEHICLE_ACCESS"
            ,"SITE_PEDESTRIAN_ACCESS"
            ,"SITE_LANDSCAPE"
            ,"SITE_BOUNDARY_WALL"
            ,"SITE_LEVELS"
            ,"SITE_SEPARATION_JOINT"
            ,"VEHICLE_ENTRANCE"
            ,"DRIVEWAY"
            ,"VEHICLE_RAMP"
            ,"EXTERIOR_PLATFORM"
            ,"ENTRANCE_STEPS"
            ,"ENTRANCE_LEVELS"
            ,"ARCH_DIMENSIONS"
            ,"ARCH_LEVELS"
            ,"PARKING_AISLE"
            ,"PARKING_STALLS"
            ,"PARKING_PEDESTRIAN"
            ,"RAMP_CLEARANCE"
            ,"SLAB_OPENINGS"
            ,"ARCH_SECTION"
            ,"SECTION_LEVELS"
            ,"SECTION_RAMP"
            ,"SECTION_HEADROOM"
            ,"SECTION_STAIR"
            ,"SECTION_SLAB_OPENING"

        ]


        for layer in layers:

            if layer not in doc.layers:

                doc.layers.add(
                    layer
                )


    # ==========================================
    # HELPERS
    # ==========================================

    def point2d(
        self,
        p
    ):

        if isinstance(p, dict):

            return (
                float(p.get("x", 0)),
                float(p.get("y", 0))
            )


        return (
            float(p[0]),
            float(p[1])
        )


    def ensure_layer(self, doc, name, color=7, linetype="CONTINUOUS"):
        if name not in doc.layers:
            doc.layers.add(name, color=color, linetype=linetype)
        return name


    def level_of(self, item):
        return str(item.get("level", item.get("floor", "F1")))


    def space_label(self, room):
        requirements = room.get("requirements", room.get("design_requirements", {}))
        role = requirements.get("role") if isinstance(requirements, dict) else None
        key = str(role or room.get("name") or room.get("type") or "SPACE").lower()
        return self.SPACE_LABELS.get(key, str(room.get("name") or role or "SPACE").upper())


    def footprint_points(self, item):
        footprint = item.get("footprint", {})
        if isinstance(footprint, dict):
            points = footprint.get("points", footprint.get("source_points", []))
        else:
            points = footprint
        if not points and isinstance(item.get("points"), list):
            points = item.get("points")
        return [self.point2d(point) for point in points] if points else []


    def add_vehicle_access(self, doc, vehicle_access, ramps):
        if not isinstance(vehicle_access, dict):
            vehicle_access = {}
        entrance = vehicle_access.get("entrance", {})
        if isinstance(entrance, dict) and entrance.get("entrance_start") and entrance.get("entrance_end"):
            doc.modelspace().add_line(
                self.point2d(entrance["entrance_start"]),
                self.point2d(entrance["entrance_end"]),
                dxfattribs={"layer": "VEHICLE_ENTRANCE"},
            )
        driveway = vehicle_access.get("driveway", {})
        if isinstance(driveway, dict):
            polygon = driveway.get("polygon", [])
            if polygon:
                doc.modelspace().add_lwpolyline(
                    [self.point2d(point) for point in polygon], close=True,
                    dxfattribs={"layer": "DRIVEWAY"},
                )
            centerline = driveway.get("centerline", [])
            if centerline:
                doc.modelspace().add_lwpolyline(
                    [self.point2d(point) for point in centerline],
                    dxfattribs={"layer": "DRIVEWAY"},
                )
        for ramp in ramps:
            if not isinstance(ramp, dict):
                continue
            polygon = ramp.get("polygon", [])
            if polygon:
                doc.modelspace().add_lwpolyline(
                    [self.point2d(point) for point in polygon], close=True,
                    dxfattribs={"layer": "VEHICLE_RAMP"},
                )
            centerline = ramp.get("centerline", [])
            if centerline:
                doc.modelspace().add_lwpolyline(
                    [self.point2d(point) for point in centerline],
                    dxfattribs={"layer": "VEHICLE_RAMP"},
                )
            if centerline:
                start = centerline[0]
                annotations = [
                    f"{float(ramp.get('start_z', 0)):+.2f}",
                    f"{float(ramp.get('end_z', 0)):+.2f}",
                ]
                if isinstance(ramp.get("slope"), (int, float)):
                    annotations.append(f"RAMP {float(ramp['slope']) * 100:.0f}%")
                if isinstance(ramp.get("required_run"), (int, float)):
                    annotations.append(f"RUN {float(ramp['required_run']):.2f}m")
                text = doc.modelspace().add_text(
                    "  ".join(annotations),
                    dxfattribs={"layer": "VEHICLE_RAMP", "height": 0.20},
                )
                text.set_placement(self.point2d(start))

    def add_architectural_drawing_contract(self, doc, geometry):
        site=geometry.get("site_geometry",{})
        parking=site.get("parking_layout",{}) if isinstance(site,dict) else {}
        aisle=parking.get("parking_aisle",{}) if isinstance(parking,dict) else {}
        if aisle.get("geometry_status")=="resolved" and aisle.get("polygon"):
            doc.modelspace().add_lwpolyline([self.point2d(p) for p in aisle["polygon"]],close=True,dxfattribs={"layer":"PARKING_AISLE"})
        for stall in parking.get("parking_stalls",[]) if isinstance(parking,dict) else []:
            if stall.get("geometry_status")=="resolved":
                doc.modelspace().add_lwpolyline([self.point2d(p) for p in stall["polygon"]],close=True,dxfattribs={"layer":"PARKING_STALLS"})
                text=doc.modelspace().add_text(stall["stall_id"],dxfattribs={"layer":"PARKING_STALLS","height":0.18})
                p=stall["polygon"];text.set_placement((sum(x[0] for x in p)/len(p),sum(x[1] for x in p)/len(p)))
        pedestrian=site.get("parking_pedestrian_connection",{}) if isinstance(site,dict) else {}
        if pedestrian.get("geometry_status")=="resolved":
            for polygon in pedestrian.get("path_corridor",[]):
                if polygon:doc.modelspace().add_lwpolyline([self.point2d(p) for p in polygon],close=True,dxfattribs={"layer":"PARKING_PEDESTRIAN"})
            centerline=pedestrian.get("path_centerline",[])
            if centerline:doc.modelspace().add_lwpolyline([self.point2d(p) for p in centerline],dxfattribs={"layer":"PARKING_PEDESTRIAN"})
        clearance=geometry.get("ramp_clearance",{})
        if isinstance(clearance,dict) and clearance.get("geometry_status")=="resolved":
            for key,layer in (("slab_opening_polygon","SLAB_OPENINGS"),("open_to_sky_zone","RAMP_CLEARANCE")):
                polygon=clearance.get(key)
                if polygon:doc.modelspace().add_lwpolyline([self.point2d(p) for p in polygon],close=True,dxfattribs={"layer":layer})
        contract=geometry.get("cad_drawing_contract",{})
        for marker in contract.get("level_markers",[]) if isinstance(contract,dict) else []:
            if marker.get("geometry_status")!="resolved":continue
            anchor,label=self.point2d(marker["anchor"]),self.point2d(marker["label_point"])
            doc.modelspace().add_line(anchor,label,dxfattribs={"layer":"ARCH_LEVELS"})
            text=doc.modelspace().add_text(f"{marker['level']} {marker['value']:+.2f}",dxfattribs={"layer":"ARCH_LEVELS","height":0.2});text.set_placement(label)
        for dim in contract.get("dimensions",[]) if isinstance(contract,dict) else []:
            if dim.get("geometry_status")!="resolved":continue
            p1,p2=self.point2d(dim["p1"]),self.point2d(dim["p2"])
            dx,dy=p2[0]-p1[0],p2[1]-p1[1];length=math.hypot(dx,dy)
            if length<=1e-9:continue
            nx,ny=-dy/length,dx/length
            base=((p1[0]+p2[0])/2+nx*0.5,(p1[1]+p2[1])/2+ny*0.5)
            entity=doc.modelspace().add_linear_dim(base=base,p1=p1,p2=p2,
                angle=math.degrees(math.atan2(dy,dx)),dxfattribs={"layer":"ARCH_DIMENSIONS"})
            entity.render()

    def add_architectural_section(self,doc,geometry):
        section=geometry.get("architectural_section",{})
        if not isinstance(section,dict) or section.get("geometry_status")!="resolved":return
        floor_points=[self.footprint_points(f) for f in geometry.get("floor_geometry",[])];floor_points=[p for p in floor_points if p]
        origin_x=max((point[0] for points in floor_points for point in points),default=0)+5.0
        origin_y=min((point[1] for points in floor_points for point in points),default=0)
        def pt(p):return (origin_x+float(p[0]),origin_y+float(p[1]))
        for slab in section.get("slab_profiles",[]):
            doc.modelspace().add_line(pt(slab["line"][0]),pt(slab["line"][1]),dxfattribs={"layer":"ARCH_SECTION"})
            text=doc.modelspace().add_text(f"{slab['level']} {float(slab['z']):+.2f}",dxfattribs={"layer":"SECTION_LEVELS","height":0.18});text.set_placement(pt(slab["line"][0]))
        for key,layer in (("ramp_profile","SECTION_RAMP"),("headroom_profile","SECTION_HEADROOM"),("stair_profile","SECTION_STAIR")):
            profile=section.get(key)
            if profile:doc.modelspace().add_lwpolyline([pt(p) for p in profile],dxfattribs={"layer":layer})
        for opening in section.get("slab_openings",[]):
            if isinstance(opening.get("z"),(int,float)):
                text=doc.modelspace().add_text(f"VOID {opening.get('type')}",dxfattribs={"layer":"SECTION_SLAB_OPENING","height":0.16});text.set_placement(pt([0,opening["z"]]))

    def add_entrance_transition(self, doc, transition):
        """Draw only spatially resolved entrance-transition evidence."""
        if not isinstance(transition, dict):
            return
        platform = transition.get(
            "exterior_platform_geometry",
            transition.get("entrance_platform", {}),
        )
        if isinstance(platform, dict) and platform.get("geometry_generation_allowed"):
            polygon = platform.get("polygon", [])
            if isinstance(polygon, list) and len(polygon) >= 3:
                points = [self.point2d(point) for point in polygon]
                doc.modelspace().add_lwpolyline(
                    points, close=True, dxfattribs={"layer": "EXTERIOR_PLATFORM"}
                )
                elevation = platform.get("elevation")
                if isinstance(elevation, (int, float)):
                    text = doc.modelspace().add_text(
                        f"PLATFORM {float(elevation):+.2f}",
                        dxfattribs={"layer": "ENTRANCE_LEVELS", "height": 0.20},
                    )
                    text.set_placement(points[0])

        steps = transition.get(
            "entrance_steps_geometry",
            transition.get("exterior_steps", {}),
        )
        if not isinstance(steps, dict) or not steps.get("geometry_generation_allowed"):
            return
        start, end = steps.get("start_point"), steps.get("end_point")
        if not start or not end:
            return
        start, end = self.point2d(start), self.point2d(end)
        step_edges = steps.get("step_edges", [])
        if isinstance(step_edges, list) and step_edges:
            for edge in step_edges:
                if isinstance(edge, list) and len(edge) >= 2:
                    doc.modelspace().add_line(
                        self.point2d(edge[0]), self.point2d(edge[1]),
                        dxfattribs={"layer": "ENTRANCE_STEPS"},
                    )
        else:
            doc.modelspace().add_line(start, end, dxfattribs={"layer": "ENTRANCE_STEPS"})
        label = (
            f"STEPS {steps.get('riser_count')} x {float(steps.get('riser_height')):.2f}  "
            f"{float(steps.get('start_z')):+.2f} -> {float(steps.get('end_z')):+.2f}"
        )
        text = doc.modelspace().add_text(
            label, dxfattribs={"layer": "ENTRANCE_LEVELS", "height": 0.20}
        )
        text.set_placement(start)


    # ==========================================
    # WALL
    # ==========================================

    def add_wall(
        self,
        doc,
        wall
    ):

        level = self.level_of(wall)


        layer = (
            level
            +
            "_WALLS"
        )


        msp = doc.modelspace()


        self.ensure_layer(doc, layer, color=7)
        thickness = float(wall.get("thickness", 0.2) or 0.2)
        segments = wall.get("solid_segments")
        if not isinstance(segments, list):
            segments = [{"start": wall.get("start"), "end": wall.get("end")}]
        for segment in segments:
            start = self.point2d(segment.get("start"))
            end = self.point2d(segment.get("end"))
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy)
            if length <= 1e-9:
                continue
            ox, oy = -dy / length * thickness / 2.0, dx / length * thickness / 2.0
            for sign in (-1.0, 1.0):
                msp.add_line(
                    (start[0] + sign * ox, start[1] + sign * oy),
                    (end[0] + sign * ox, end[1] + sign * oy),
                    dxfattribs={"layer": layer},
                )


    # ==========================================
    # FLOOR
    # ==========================================

    def add_floor(
        self,
        doc,
        floor
    ):

        points = self.footprint_points(floor)

        if points:

            level = self.level_of(floor)
            layer = self.ensure_layer(doc, level + "_FLOOR", color=9)
            doc.modelspace().add_lwpolyline(
                points,
                close=True,
                dxfattribs={"layer": layer},
            )
            for opening in floor.get("physical_openings", []) or []:
                if opening.get("geometry_status") != "resolved":
                    continue
                void_points = [self.point2d(point) for point in opening.get("polygon", [])]
                if len(void_points) >= 3:
                    doc.modelspace().add_lwpolyline(
                        void_points, close=True,
                        dxfattribs={"layer": self.ensure_layer(doc, level + "_SLAB_OPENINGS", color=1)},
                    )


    # ==========================================
    # ROOM
    # ==========================================

    def add_room(
        self,
        doc,
        room
    ):


        level = self.level_of(room)


        layer = (
            level
            +
            "_ROOMS"
        )


        self.ensure_layer(doc, layer, color=8)
        text_layer = self.ensure_layer(doc, level + "_TEXT", color=2)
        points = self.footprint_points(room)
        if not points:
            geo = room.get("geometry", {})
            x = float(geo.get("x", room.get("x", 0)) or 0)
            y = float(geo.get("y", room.get("y", 0)) or 0)
            w = float(geo.get("width", room.get("width", 0)) or 0)
            h = float(geo.get("height", room.get("depth", 0)) or 0)
            points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        if len(points) < 3:
            return
        doc.modelspace().add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
        cx = sum(point[0] for point in points) / len(points)
        cy = sum(point[1] for point in points) / len(points)
        label = self.space_label(room)
        text = doc.modelspace().add_mtext(
            label,
            dxfattribs={"layer": text_layer, "char_height": 0.25},
        )
        text.set_location((cx, cy), attachment_point=5)

    # ==========================================
    # DOOR EXPORT
    # ==========================================

    def add_door(
        self,
        doc,
        door
    ):

        level = self.level_of(door)
        layer = self.ensure_layer(doc, level + "_DOORS", color=1)
        start = self.point2d(door.get("symbol_start", door.get("start", [door.get("x", 0), door.get("y", 0)])))
        end = self.point2d(door.get("symbol_end", door.get("end", [start[0] + float(door.get("width", 1) or 1), start[1]])))
        width = math.hypot(end[0] - start[0], end[1] - start[1])
        if width <= 1e-9:
            return
        angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
        operation = str(door.get("operation", "hinged")).lower()
        if operation in ("sliding", "automatic_sliding", "rolling_shutter", "sectional_overhead"):
            dx, dy = end[0]-start[0], end[1]-start[1]
            length = math.hypot(dx, dy)
            nx, ny = -dy/length, dx/length
            doc.modelspace().add_line(start, end, dxfattribs={"layer": layer})
            doc.modelspace().add_line(
                (start[0]+nx*0.08, start[1]+ny*0.08),
                (end[0]+nx*0.08, end[1]+ny*0.08),
                dxfattribs={"layer": layer},
            )
        else:
            swing = str(door.get("swing_direction", "inward")).lower()
            sweep = -90.0 if "outward" in swing else 90.0
            doc.modelspace().add_line(start, end, dxfattribs={"layer": layer})
            doc.modelspace().add_arc(
                start, width, min(angle, angle+sweep), max(angle, angle+sweep),
                dxfattribs={"layer": layer},
            )

    # ==========================================
    # WINDOW EXPORT
    # ==========================================

    def add_window(
        self,
        doc,
        window
    ):

        level = self.level_of(window)
        layer = self.ensure_layer(doc, level + "_WINDOWS", color=4)
        start = self.point2d(window.get("symbol_start", window.get("start", [window.get("x", 0), window.get("y", 0)])))
        end = self.point2d(window.get("symbol_end", window.get("end", [start[0] + float(window.get("width", 1) or 1), start[1]])))
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return
        nx, ny = -dy / length, dx / length
        for offset in (-0.05, 0.0, 0.05):
            doc.modelspace().add_line(
                (start[0] + nx * offset, start[1] + ny * offset),
                (end[0] + nx * offset, end[1] + ny * offset),
                dxfattribs={"layer": layer},
            )


    def resolve_opening_symbol(self, opening, walls_by_id):
        result = dict(opening)
        if opening.get("geometry_status") != "resolved":
            return None
        wall_id = opening.get("host_wall_id")
        wall = walls_by_id.get(wall_id)
        if not isinstance(wall, dict):
            return None
        start = opening.get("opening_start") or opening.get("symbol_start")
        end = opening.get("opening_end") or opening.get("symbol_end")
        if start is None or end is None:
            return None
        result["symbol_start"] = self.point2d(start)
        result["symbol_end"] = self.point2d(end)
        result["level"] = opening.get("floor", wall.get("floor", "F1"))
        return result


    def add_external_space(self, doc, space):
        points = self.footprint_points(space)
        if len(points) < 3:
            boundary = space.get("parcel_boundary", space.get("boundary", []))
            points = [self.point2d(point) for point in boundary] if boundary else []
        if len(points) < 3:
            return
        layer = self.ensure_layer(doc, "EXTERNAL_SPACE", color=3)
        doc.modelspace().add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
        cx = sum(point[0] for point in points) / len(points)
        cy = sum(point[1] for point in points) / len(points)
        label = self.SPACE_LABELS.get(
            str(space.get("type", space.get("name", "yard"))).lower(),
            str(space.get("name", "حیاط / YARD")),
        )
        text = doc.modelspace().add_mtext(
            label,
            dxfattribs={"layer": layer, "char_height": 0.35},
        )
        text.set_location((cx, cy), attachment_point=5)


    def add_site_plan(self, doc, site_plan):
        if not isinstance(site_plan, dict):
            return
        road = site_plan.get("road", {})
        if isinstance(road, dict) and road.get("start") and road.get("end"):
            layer = self.ensure_layer(doc, "SITE_ROAD", color=8)
            start, end = self.point2d(road["start"]), self.point2d(road["end"])
            doc.modelspace().add_line(start, end, dxfattribs={"layer": layer, "lineweight": 35})
            mid = ((start[0]+end[0])/2, (start[1]+end[1])/2)
            label = f"ROAD / معبر  W={road.get('width', '?')}m"
            text = doc.modelspace().add_text(label, dxfattribs={"layer": layer, "height": 0.30})
            text.set_placement(mid)
        for key, layer_name, label in (
            ("vehicle_access", "SITE_VEHICLE_ACCESS", "VEHICLE ACCESS"),
            ("pedestrian_access", "SITE_PEDESTRIAN_ACCESS", "PEDESTRIAN ACCESS"),
        ):
            access = site_plan.get(key, {})
            points = access.get("points", []) if isinstance(access, dict) else []
            if len(points) >= 2:
                pts = [self.point2d(p) for p in points]
                layer = self.ensure_layer(doc, layer_name, color=1 if key == "vehicle_access" else 3)
                doc.modelspace().add_lwpolyline(pts, dxfattribs={"layer": layer, "lineweight": 30})
                text = doc.modelspace().add_text(label, dxfattribs={"layer": layer, "height": 0.20})
                text.set_placement(pts[0])
        for landscape in site_plan.get("landscape", []) or []:
            points = self.footprint_points(landscape) if isinstance(landscape, dict) else []
            if len(points) >= 3:
                layer = self.ensure_layer(doc, "SITE_LANDSCAPE", color=3)
                doc.modelspace().add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
        for wall in site_plan.get("boundary_walls", []) or []:
            if isinstance(wall, dict):
                item = dict(wall)
                item["floor"] = "SITE_BOUNDARY"
                self.add_wall(doc, item)
        for marker in site_plan.get("elevation_markers", []) or []:
            if not isinstance(marker, dict) or not marker.get("point"):
                continue
            point = self.point2d(marker["point"])
            layer = self.ensure_layer(doc, "SITE_LEVELS", color=2)
            elevation = marker.get("elevation", marker.get("z", 0))
            label = marker.get("label", f"± {float(elevation):.2f}")
            doc.modelspace().add_circle(point, 0.15, dxfattribs={"layer": layer})
            text = doc.modelspace().add_text(str(label), dxfattribs={"layer": layer, "height": 0.20})
            text.set_placement((point[0]+0.2, point[1]+0.2))

        boundary = site_plan.get("parcel_boundary", [])
        joints = site_plan.get("separation_joints", {})
        if isinstance(boundary, list) and len(boundary) >= 3 and isinstance(joints, dict):
            pts = [self.point2d(point) for point in boundary]
            min_x, max_x = min(p[0] for p in pts), max(p[0] for p in pts)
            min_y, max_y = min(p[1] for p in pts), max(p[1] for p in pts)
            application = site_plan.get("separation_joint_application", {})
            buildable = (
                application.get("buildable_boundary", [])
                if isinstance(application, dict)
                and application.get("status") == "resolved"
                else []
            )
            buildable_pts = (
                [self.point2d(point) for point in buildable]
                if isinstance(buildable, list) and len(buildable) >= 3
                else []
            )
            if buildable_pts:
                buildable_min_x = min(p[0] for p in buildable_pts)
                buildable_max_x = max(p[0] for p in buildable_pts)
                buildable_min_y = min(p[1] for p in buildable_pts)
                buildable_max_y = max(p[1] for p in buildable_pts)
            layer = self.ensure_layer(doc, "SITE_SEPARATION_JOINT", color=1, linetype="DASHED")
            for side, data in joints.items():
                gap = data.get("joint", data.get("width", 0)) if isinstance(data, dict) else data
                try:
                    gap = float(gap)
                except (TypeError, ValueError):
                    continue
                if gap <= 0:
                    continue
                lines = (
                    {
                        "north": ((buildable_min_x, buildable_max_y), (buildable_max_x, buildable_max_y)),
                        "south": ((buildable_min_x, buildable_min_y), (buildable_max_x, buildable_min_y)),
                        "east": ((buildable_max_x, buildable_min_y), (buildable_max_x, buildable_max_y)),
                        "west": ((buildable_min_x, buildable_min_y), (buildable_min_x, buildable_max_y)),
                    }
                    if buildable_pts
                    else {
                        "north": ((min_x, max_y-gap), (max_x, max_y-gap)),
                        "south": ((min_x, min_y+gap), (max_x, min_y+gap)),
                        "east": ((max_x-gap, min_y), (max_x-gap, max_y)),
                        "west": ((min_x+gap, min_y), (min_x+gap, max_y)),
                    }
                )
                if side in lines:
                    start, end = lines[side]
                    doc.modelspace().add_line(start, end, dxfattribs={"layer": layer})
                    text = doc.modelspace().add_text(
                        f"SEPARATION {side.upper()} = {gap:.2f}m",
                        dxfattribs={"layer": layer, "height": 0.18},
                    )
                    text.set_placement(((start[0]+end[0])/2, (start[1]+end[1])/2))


    # ==========================================
    # COLUMN
    # ==========================================

    def add_column(
        self,
        doc,
        column
    ):

        layer = self.ensure_layer(doc, "STRUCT_COLUMNS", color=1)
        x = float(column.get("x", 0) or 0)
        y = float(column.get("y", 0) or 0)
        width = float(column.get("width", column.get("size", 0.30)) or 0.30)
        depth = float(column.get("depth", column.get("size", width)) or width)
        doc.modelspace().add_lwpolyline(
            [(x-width/2, y-depth/2), (x+width/2, y-depth/2),
             (x+width/2, y+depth/2), (x-width/2, y+depth/2)],
            close=True, dxfattribs={"layer": layer},
        )


    # ==========================================
    # BEAM
    # ==========================================

    def add_beam(
        self,
        doc,
        beam
    ):

        layer = self.ensure_layer(doc, "STRUCT_BEAMS", color=6)
        doc.modelspace().add_line(

            self.point2d(
                beam.get(
                    "start",
                    [0,0]
                )
            ),

            self.point2d(
                beam.get(
                    "end",
                    [0,0]
                )
            ), dxfattribs={"layer": layer}

        )


    def add_stair(self, doc, stair):
        if stair.get("geometry_status") == "resolved" and stair.get("flights"):
            msp = doc.modelspace()
            polygon = stair.get("polygon") or []
            if polygon:
                msp.add_lwpolyline(
                    [self.point2d(point) for point in polygon], close=True,
                    dxfattribs={"layer": "STAIR"},
                )
            for flight in stair.get("flights", []):
                flight_polygon = flight.get("polygon") or []
                if flight_polygon:
                    msp.add_lwpolyline(
                        [self.point2d(point) for point in flight_polygon], close=True,
                        dxfattribs={"layer": "STAIR_FLIGHT"},
                    )
                for tread_line in flight.get("tread_lines", []):
                    if len(tread_line) >= 2:
                        msp.add_line(
                            self.point2d(tread_line[0]), self.point2d(tread_line[1]),
                            dxfattribs={"layer": "STAIR_FLIGHT"},
                        )
            for landing in stair.get("landings", []):
                landing_polygon = landing.get("polygon") or []
                if landing_polygon:
                    msp.add_lwpolyline(
                        [self.point2d(point) for point in landing_polygon], close=True,
                        dxfattribs={"layer": "STAIR_LANDING"},
                    )
            centerline = stair.get("walking_line") or stair.get("centerline") or []
            if len(centerline) >= 2:
                msp.add_lwpolyline(
                    [self.point2d(point) for point in centerline],
                    dxfattribs={"layer": "STAIR_DIRECTION"},
                )
                end = self.point2d(centerline[-1])
                before = self.point2d(centerline[-2])
                angle = math.atan2(end[1] - before[1], end[0] - before[0])
                arrow = 0.3
                for offset in (-0.45, 0.45):
                    msp.add_line(
                        end,
                        (end[0] - arrow * math.cos(angle + offset),
                         end[1] - arrow * math.sin(angle + offset)),
                        dxfattribs={"layer": "STAIR_DIRECTION"},
                    )
            labels = [
                ("UP" if stair.get("direction") == "up" else "DN", stair.get("start_point")),
                (f"START {float(stair['start_z']):+.2f}", stair.get("start_point")),
                (f"END {float(stair['end_z']):+.2f}", stair.get("end_point")),
            ]
            for label, point in labels:
                if point:
                    text = msp.add_text(label, dxfattribs={"layer": "STAIR_TEXT", "height": 0.18})
                    text.set_placement(self.point2d(point))
            return

        points = self.footprint_points(stair)
        if len(points) < 3:
            return
        layer = self.ensure_layer(doc, "ARCH_STAIRS", color=2)
        doc.modelspace().add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        count = int(stair.get("riser_count", stair.get("steps", 16)) or 16)
        count = max(2, min(count, 40))
        for index in range(1, count):
            y = min_y + (max_y-min_y) * index / count
            doc.modelspace().add_line((min_x, y), (max_x, y), dxfattribs={"layer": layer})
        doc.modelspace().add_line(
            ((min_x+max_x)/2, min_y), ((min_x+max_x)/2, max_y),
            dxfattribs={"layer": layer},
        )
        for label, y in (("UP / START", min_y), ("END", max_y)):
            text = doc.modelspace().add_text(label, dxfattribs={"layer": layer, "height": 0.18})
            text.set_placement(((min_x+max_x)/2, y))


    def add_furniture(self, doc, item):
        points = self.footprint_points(item)
        if len(points) < 3:
            return
        layer = self.ensure_layer(doc, "ARCH_FURNITURE", color=8)
        doc.modelspace().add_lwpolyline(points, close=True, dxfattribs={"layer": layer})


    def add_circulation_relation(self, doc, relation, spaces_by_id):
        if isinstance(relation, dict):
            source = relation.get("from") or relation.get("source")
            target = relation.get("to") or relation.get("target")
        elif isinstance(relation, (list, tuple)) and len(relation) >= 2:
            source, target = relation[0], relation[1]
        else:
            return
        a, b = spaces_by_id.get(source), spaces_by_id.get(target)
        if not a or not b:
            return
        def center(space):
            pts = self.footprint_points(space)
            return (sum(p[0] for p in pts)/len(pts), sum(p[1] for p in pts)/len(pts)) if pts else None
        pa, pb = center(a), center(b)
        if pa and pb:
            layer = self.ensure_layer(doc, "ARCH_CIRCULATION", color=3, linetype="DASHED")
            doc.modelspace().add_line(pa, pb, dxfattribs={"layer": layer})


    # ==========================================
    # EXPORT
    # ==========================================

    def export(
        self,
        geometry,
        structure,
        output="exports/ArchitectOS_Project.dxf"
    ):


        print("\n====== DWG WRITER CLEAN EXPORT ======")

        print(
            "OUTPUT:",
            output
        )

        print(
            "WALLS:",
            len(
                geometry.get(
                    "walls",
                    []
                )
            )
        )

        print(
            "ROOMS:",
            len(
                geometry.get(
                    "rooms",
                    []
                )
            )
        )

        print(
            "STRUCTURE INCLUDED:",
            bool(structure)
        )

        print(
            "===================================="
        )


        doc = ezdxf.new(
            "R2018"
        )

        self.setup_layers(
            doc
        )


        # ONLY ARCHITECTURAL GEOMETRY


        walls = geometry.get("physical_walls") or geometry.get("walls", [])
        rooms = geometry.get("spaces") or geometry.get("rooms", [])
        openings = geometry.get("openings", [])
        # ArchitecturalGeometry.openings is the canonical, all-storey source.
        # Legacy doors/windows collections may contain only the first floor.
        doors = [opening for opening in openings if opening.get("type") == "door"]
        windows = [opening for opening in openings if opening.get("type") == "window"]
        if not doors:
            doors = geometry.get("doors", []) or []
        if not windows:
            windows = geometry.get("windows", []) or []
        walls_by_id = {
            wall.get("wall_id", wall.get("id")): wall
            for wall in walls
            if isinstance(wall, dict)
        }

        for wall in walls:

            self.add_wall(
                doc,
                wall
            )


        for floor in geometry.get("slabs") or geometry.get("floors", []):

            self.add_floor(
                doc,
                floor
            )


        for room in rooms:

            self.add_room(
                doc,
                room
            )

        for door in doors:
            symbol = self.resolve_opening_symbol(door, walls_by_id)
            if symbol is not None:
                self.add_door(doc, symbol)


        for window in windows:
            symbol = self.resolve_opening_symbol(window, walls_by_id)
            if symbol is not None:
                self.add_window(doc, symbol)

        spaces_by_id = {
            room.get("space_id", room.get("id", room.get("name"))): room
            for room in rooms if isinstance(room, dict)
        }
        for relation in geometry.get("circulation", geometry.get("connections", [])) or []:
            self.add_circulation_relation(doc, relation, spaces_by_id)

        stairs = list(geometry.get("stairs", []) or [])
        stair_keys = {
            stair.get("stair_id", stair.get("id", stair.get("name")))
            for stair in stairs if isinstance(stair, dict)
        }
        for vertical in geometry.get("vertical_geometry", []) or []:
            if not isinstance(vertical, dict) or vertical.get("type") != "stair_geometry":
                continue
            stair = dict(vertical)
            parameters = vertical.get("parameters", {})
            if isinstance(parameters, dict):
                stair.update({key: value for key, value in parameters.items() if key not in stair or stair[key] in (None, [], {})})
            flights = vertical.get("flights", [])
            if flights and "riser_count" not in stair:
                stair["riser_count"] = flights[0].get("riser_count")
            stair_key = stair.get("stair_id", stair.get("id", stair.get("name")))
            if stair_key is None or stair_key not in stair_keys:
                stairs.append(stair)
                stair_keys.add(stair_key)
        for stair in stairs:
            if isinstance(stair, dict):
                self.add_stair(doc, stair)

        site_access = geometry.get("site_geometry", {})
        vehicle_access = site_access.get("vehicle_access", {}) if isinstance(site_access, dict) else {}
        vehicle_ramps = [
            item for item in geometry.get("vertical_geometry", []) or []
            if isinstance(item, dict) and "vehicle_ramp" in str(item.get("type", "")).lower()
        ]
        self.add_vehicle_access(doc, vehicle_access, vehicle_ramps)
        self.add_architectural_drawing_contract(doc, geometry)
        self.add_architectural_section(doc, geometry)
        entrance_transition = (
            site_access.get("exterior_entrance", {})
            if isinstance(site_access, dict)
            else {}
        )
        self.add_entrance_transition(doc, entrance_transition)

        for item in geometry.get("furniture", []) or []:
            if isinstance(item, dict):
                self.add_furniture(doc, item)

        for column in (structure or {}).get("columns", []) or []:
            if isinstance(column, dict):
                self.add_column(doc, column)

        for beam in (structure or {}).get("beams", []) or []:
            if isinstance(beam, dict):
                self.add_beam(doc, beam)

        external_spaces = geometry.get("external_spaces", [])
        site_geometry = geometry.get("site_geometry", [])
        if isinstance(site_geometry, dict):
            site_geometry = [site_geometry]
        for external_space in list(external_spaces) + list(site_geometry or []):
            if isinstance(external_space, dict):
                self.add_external_space(doc, external_space)

        site_plan = geometry.get("site_plan", {}) or (
            geometry.get("site_geometry", {}) if isinstance(geometry.get("site_geometry"), dict) else {}
        )
        site_plan = dict(site_plan) if isinstance(site_plan, dict) else {}
        if not site_plan.get("elevation_markers"):
            markers = []
            for index, slab in enumerate(geometry.get("slabs", []) or []):
                if not isinstance(slab, dict) or slab.get("bottom") is None:
                    continue
                points = self.footprint_points(slab)
                if not points:
                    # Architecture-first CAD must not fabricate an origin-based
                    # level marker when the slab/site position is unresolved.
                    continue
                point = points[0]
                markers.append({
                    "point": point,
                    "elevation": slab["bottom"],
                    "label": f"{self.level_of(slab)}  {float(slab['bottom']):+.2f}",
                })
            site_plan["elevation_markers"] = markers
        self.add_site_plan(doc, site_plan)


        # doors/windows
        # next step


        folder = os.path.dirname(
            output
        )

        if folder:

            os.makedirs(
                folder,
                exist_ok=True
            )


        print(
            "\n====== FINAL DXF ENTITY COUNT ======"
        )

        print(
            len(
                doc.modelspace()
            )
        )

        print(
            "===================================="
        )


        doc.saveas(
            output
        )


        return {

            "status":
                "exported",

            "file":
                output,

            "format":
                "DXF",

            "dwg_ready":
                True,

            "version":
                self.VERSION

        }
