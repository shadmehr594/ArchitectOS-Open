"""
ArchitectOS Design → BIM Integration Bridge v1.2

Purpose:
Connect existing DesignTool output
to existing FullBIMPipeline.

No modification to:
- Intent
- Brain
- Chat
- Render
- BIM engines

Only adapter layer.
"""
import math
from copy import deepcopy

from core.structure.architecture_structure_handoff_v1 import (
    ArchitectureStructureHandoffV1,
)

class DesignBIMBridge:

    VERSION = "1.2"


    def __init__(self):

        print(
            f"🔗 Design BIM Bridge v{self.VERSION} ACTIVE"
        )

    # ==================================================
    # PARCEL LOCAL -> ARCHITECTURAL FLOOR LOCAL
    # ==================================================

    def _resolved_point_to_source(
        self,
        point,
        coordinate_frame
    ):

        if not (
            isinstance(
                point,
                (list, tuple)
            )
            and len(
                point
            ) >= 2
        ):

            return None


        if not isinstance(
            coordinate_frame,
            dict
        ):

            return None

        if (
            not coordinate_frame.get("translation_applied")
            and not coordinate_frame.get("rotation_applied")
        ):
            return [float(point[0]), float(point[1])]

        # Translation-only ArchitecturalGeometry already carries resolved
        # parcel-local coordinates.  Rotation pivots do not exist in this
        # mode, so attempting the rotation inverse below would incorrectly
        # discard every physical wall from the BIM handoff.
        if (
            coordinate_frame.get("translation_applied")
            and not coordinate_frame.get("rotation_applied")
        ):
            return [float(point[0]), float(point[1])]


        source_pivot = coordinate_frame.get(
            "source_pivot",
            {}
        ) or {}

        target_pivot = coordinate_frame.get(
            "target_pivot",
            {}
        ) or {}


        try:

            point_x = float(
                point[0]
            )

            point_y = float(
                point[1]
            )


            source_pivot_x = float(
                source_pivot.get(
                    "x"
                )
            )

            source_pivot_y = float(
                source_pivot.get(
                    "y"
                )
            )


            target_pivot_x = float(
                target_pivot.get(
                    "x"
                )
            )

            target_pivot_y = float(
                target_pivot.get(
                    "y"
                )
            )


            rotation_degrees = float(
                coordinate_frame.get(
                    "rotation_degrees",
                    0.0
                )
                or 0.0
            )

        except (
            TypeError,
            ValueError
        ):

            return None


        # Forward architectural placement is:
        #
        # resolved =
        # R(source - source_pivot)
        # + target_pivot
        #
        # Therefore inverse transformation is:
        #
        # source =
        # R^-1(resolved - target_pivot)
        # + source_pivot

        rotation_radians = math.radians(
            rotation_degrees
        )


        rotation_cos = math.cos(
            rotation_radians
        )

        rotation_sin = math.sin(
            rotation_radians
        )


        relative_x = (
            point_x
            -
            target_pivot_x
        )

        relative_y = (
            point_y
            -
            target_pivot_y
        )


        source_x = (
            relative_x
            *
            rotation_cos
            +
            relative_y
            *
            rotation_sin
            +
            source_pivot_x
        )


        source_y = (
            -
            relative_x
            *
            rotation_sin
            +
            relative_y
            *
            rotation_cos
            +
            source_pivot_y
        )


        return [
            source_x,
            source_y
        ]

    # ==================================================
    # ARCHITECTURAL PHYSICAL WALLS -> BIM WALL CONTRACT
    # ==================================================

    def _build_architectural_walls(
        self,
        architectural_geometry
    ):

        if not isinstance(
            architectural_geometry,
            dict
        ):

            return []


        physical_walls = architectural_geometry.get(
            "physical_walls",
            []
        )


        if not isinstance(
            physical_walls,
            list
        ):

            return []


        coordinate_frame = architectural_geometry.get(
            "coordinate_frame",
            {}
        )


        walls = []


        for wall in physical_walls:

            if not isinstance(
                wall,
                dict
            ):

                continue


            start = wall.get(
                "start"
            )

            end = wall.get(
                "end"
            )


            source_start = self._resolved_point_to_source(
                start,
                coordinate_frame
            )

            source_end = self._resolved_point_to_source(
                end,
                coordinate_frame
            )


            if (
                source_start is None
                or
                source_end is None
            ):

                continue


            wall_id = wall.get(
                "wall_id"
            )


            floor = wall.get(
                "floor"
            )


            item = dict(wall)
            item.update(
                {
                    "id":
                        wall_id,

                    "source_id":
                        wall_id,

                    "start":
                        source_start,

                    "end":
                        source_end,

                    "level":
                        floor,

                    "floor":
                        floor,

                    "wall_type":
                        wall.get(
                            "wall_type"
                        ),

                    "is_exterior":
                        wall.get(
                            "is_exterior",
                            False
                        ),

                    "spaces":
                        list(
                            wall.get(
                                "spaces",
                                []
                            )
                            or []
                        ),

                    "coordinate_mode":
                        "architectural_metric_floor_local",

                    "resolved_coordinate_mode":
                        wall.get(
                            "coordinate_mode",
                            "parcel_local"
                        ),

                    "resolved_start":
                        list(
                            start
                        )
                        if isinstance(
                            start,
                            (list, tuple)
                        )
                        else None,

                    "resolved_end":
                        list(
                            end
                        )
                        if isinstance(
                            end,
                            (list, tuple)
                        )
                        else None,

                    "topology_status":
                        wall.get(
                            "topology_status"
                        ),

                    "source":
                        "architectural_physical_wall"
                }
            )
            walls.append(item)


        return walls

    # ==================================================
    # ARCHITECTURAL OPENINGS -> BIM OPENING CONTRACT
    # ==================================================

    def _build_architectural_openings(
        self,
        architectural_geometry
    ):

        if not isinstance(
            architectural_geometry,
            dict
        ):

            return {
                "doors": [],
                "windows": []
            }


        openings = architectural_geometry.get(
            "openings",
            []
        )


        if not isinstance(
            openings,
            list
        ):

            openings = []


        doors = []
        windows = []


        for index, opening in enumerate(
            openings
        ):

            if not isinstance(
                opening,
                dict
            ):

                continue

            # Semantic/pending openings are diagnostic contracts, not physical
            # architecture.  The bridge must never invent a host or placement.
            if (
                opening.get("geometry_status") != "resolved"
                or not opening.get("host_wall_id")
                or opening.get("geometry_generation_allowed") is not True
            ):
                continue


            opening_type = str(
                opening.get(
                    "type",
                    ""
                )
            ).lower()


            floor = opening.get(
                "floor"
            )


            space = opening.get(
                "space"
            )


            item = dict(
                opening
            )


            item.update(
                {
                    "id":
                        opening.get(
                            "id"
                        )
                        or
                        f"{floor}-{opening_type}-{index + 1}",

                    "level":
                        floor,

                    "floor":
                        floor,

                    "space":
                        space,

                    "source":
                        "architectural_opening",

                    "architectural_authority":
                        True
                }
            )


            if opening_type == "door":

                doors.append(
                    item
                )


            elif opening_type == "window":

                windows.append(
                    item
                )


        return {
            "doors":
                doors,

            "windows":
                windows
        }

    # ==================================================
    # ARCHITECTURAL SLABS -> BIM FLOOR CONTRACT
    # ==================================================

    def _build_architectural_slabs(
        self,
        architectural_geometry
    ):

        if not isinstance(
            architectural_geometry,
            dict
        ):

            return []


        slabs = architectural_geometry.get(
            "slabs",
            []
        )


        if not isinstance(
            slabs,
            list
        ):

            return []


        coordinate_frame = architectural_geometry.get(
            "coordinate_frame",
            {}
        )


        result = []


        for index, slab in enumerate(
            slabs
        ):

            if not isinstance(
                slab,
                dict
            ):

                continue


            floor = slab.get(
                "floor"
            )


            footprint = slab.get(
                "footprint",
                {}
            )


            if not isinstance(
                footprint,
                dict
            ):

                footprint = {}


            resolved_points = footprint.get(
                "points",
                []
            )


            source_points = footprint.get(
                "source_points"
            )


            if not isinstance(
                source_points,
                list
            ):

                source_points = []


            if (
                not source_points
                and
                isinstance(
                    resolved_points,
                    list
                )
            ):

                for point in resolved_points:

                    source_point = (
                        self._resolved_point_to_source(
                            point,
                            coordinate_frame
                        )
                    )


                    if source_point is not None:

                        source_points.append(
                            source_point
                        )


            slab_id = slab.get(
                "id"
            ) or f"{floor}-SLAB-{index + 1}"


            item = dict(slab)
            item.update(
                {
                    "id":
                        slab_id,

                    "source_id":
                        slab_id,

                    "type":
                        "SLAB",

                    "level":
                        floor,

                    "floor":
                        floor,

                    "footprint":
                        source_points,

                    "resolved_footprint":
                        list(
                            resolved_points
                        )
                        if isinstance(
                            resolved_points,
                            list
                        )
                        else [],

                    "geometry_type":
                        slab.get(
                            "geometry_type"
                        ),

                    "geometry_status":
                        slab.get(
                            "geometry_status"
                        ),

                    "coordinate_mode":
                        "architectural_metric_floor_local",

                    "resolved_coordinate_mode":
                        slab.get(
                            "coordinate_mode",
                            "parcel_local"
                        ),

                    "source_envelope":
                        slab.get(
                            "source_envelope"
                        ),

                    "source":
                        "architectural_floor_slab",

                    "architectural_authority":
                        True
                }
            )
            result.append(item)


        return result


    # ==================================================
    # NORMALIZE DESIGN OUTPUT
    # ==================================================

    def prepare_bim_project(
        self,
        design_result
    ):

        design_result = design_result or {}


        print(
            "DESIGN RESULT KEYS:",
            design_result.keys()
        )


        print(
            "DESIGN SPATIAL:",
            bool(
                design_result.get(
                    "spatial"
                )
            )
        )


        print(
            "DESIGN GEOMETRY:",
            bool(
                design_result.get(
                    "geometry"
                )
            )
        )

        print("\n====== DESIGN RESULT GEOMETRY SOURCE ======")

        print(
            "DESIGN RESULT KEYS:",
            design_result.keys()
        )

        print(
            "DESIGN RESULT GEOMETRY:",
            design_result.get("geometry")
        )

        print("============================================")


        geometry = design_result.get("architectural_geometry")
        authoritative_available = isinstance(geometry, dict) and any(
            bool(geometry.get(key))
            for key in (
                "spaces", "physical_walls", "openings", "slabs",
                "floor_geometry", "vertical_geometry"
            )
        )
        if not authoritative_available and isinstance(geometry, dict):
            candidate_site = geometry.get("site_geometry", {})
            authoritative_available = (
                isinstance(candidate_site, dict)
                and isinstance(candidate_site.get("vehicle_access"), dict)
                and bool(candidate_site.get("vehicle_access"))
            )
        if not authoritative_available:
            geometry = design_result.get("geometry", {})
        geometry = deepcopy(geometry) if isinstance(geometry, dict) else {}

        architectural_walls = []


        if isinstance(
            geometry,
            dict
        ):

            architectural_walls = self._build_architectural_walls(
                geometry
            )


        if architectural_walls:

            geometry = dict(
                geometry
            )

            geometry[
                "walls"
            ] = architectural_walls


            print(
                "\n====== ARCHITECTURAL PHYSICAL WALL BRIDGE ======"
            )

            print(
                "PHYSICAL WALL SOURCE COUNT:",
                len(
                    geometry.get(
                        "physical_walls",
                        []
                    )
                )
            )

            print(
                "BIM WALL CONTRACT COUNT:",
                len(
                    architectural_walls
                )
            )

            print(
                "FIRST BIM WALL:",
                architectural_walls[
                    0
                ]
                if architectural_walls
                else None
            )

            print(
                "================================================"
            )

        architectural_openings = (
            self._build_architectural_openings(
                geometry
            )
        )


        architectural_doors = (
            architectural_openings.get(
                "doors",
                []
            )
        )


        architectural_windows = (
            architectural_openings.get(
                "windows",
                []
            )
        )


        architectural_slabs = (
            self._build_architectural_slabs(
                geometry
            )
        )


        if (
            architectural_doors
            or
            architectural_windows
            or
            architectural_slabs
        ):

            geometry = dict(
                geometry
            )


        if architectural_doors:

            geometry[
                "doors"
            ] = architectural_doors


        if architectural_windows:

            geometry[
                "windows"
            ] = architectural_windows


        if architectural_slabs:

            geometry[
                "floors"
            ] = architectural_slabs

        vertical_geometry = geometry.get("vertical_geometry", [])
        if isinstance(vertical_geometry, list) and vertical_geometry:
            geometry = dict(geometry)
            geometry.setdefault("stairs", [])
            geometry.setdefault("elevators", [])
            geometry.setdefault("cores", [])
            geometry.setdefault("ramps", [])
            for vertical in vertical_geometry:
                if not isinstance(vertical, dict):
                    continue
                vertical_type = (
                    str(vertical.get("type", ""))
                    + " "
                    + str(vertical.get("name", ""))
                ).lower()
                if "vehicle_ramp" in vertical_type or vertical_type.strip() == "ramp":
                    ramp = dict(vertical)
                    if not ramp.get("level"):
                        start_z = ramp.get("start_z")
                        vertical_section = design_result.get("vertical_section", {})
                        for level_data in vertical_section.get("levels", []) if isinstance(vertical_section, dict) else []:
                            if isinstance(level_data, dict) and level_data.get("bottom") == start_z:
                                ramp["level"] = level_data.get("name")
                                break
                    geometry["ramps"].append(ramp)
                elif "stair" in vertical_type or "پله" in vertical_type:
                    geometry["stairs"].append(dict(vertical))
                elif "elevator" in vertical_type or "lift" in vertical_type or "آسانسور" in vertical_type:
                    geometry["elevators"].append(dict(vertical))
                else:
                    geometry["cores"].append(dict(vertical))

        site_geometry = geometry.get("site_geometry", {})
        if isinstance(site_geometry, dict):
            vehicle_access = site_geometry.get("vehicle_access", {})
            driveway = vehicle_access.get("driveway") if isinstance(vehicle_access, dict) else None
            if isinstance(driveway, dict):
                geometry = dict(geometry)
                driveway_contract = dict(driveway)
                driveway_contract.setdefault("target_level", driveway_contract.get("served_level"))
                driveway_contract.setdefault("level", driveway_contract.get("served_level"))
                geometry["site_accesses"] = [driveway_contract]

        roof_geometry = geometry.get("roof_geometry")
        if isinstance(roof_geometry, dict) and roof_geometry:
            geometry = dict(geometry)
            geometry.setdefault("roofs", [dict(roof_geometry)])

        if geometry and authoritative_available:
            geometry["architectural_authority"] = True
            geometry.setdefault("geometry_source", "ArchitecturalGeometryEngineV2")


        print(
            "\n====== ARCHITECTURAL OPENING / SLAB BRIDGE ======"
        )

        print(
            "OPENING SOURCE COUNT:",
            len(
                geometry.get(
                    "openings",
                    []
                )
            )
        )

        print(
            "BIM DOOR COUNT:",
            len(
                geometry.get(
                    "doors",
                    []
                )
            )
        )

        print(
            "BIM WINDOW COUNT:",
            len(
                geometry.get(
                    "windows",
                    []
                )
            )
        )

        print(
            "ARCHITECTURAL SLAB SOURCE COUNT:",
            len(
                geometry.get(
                    "slabs",
                    []
                )
            )
        )

        print(
            "BIM FLOOR / SLAB CONTRACT COUNT:",
            len(
                geometry.get(
                    "floors",
                    []
                )
            )
        )

        print(
            "================================================="
        )

        print("\n====== BRIDGE GEOMETRY COUNT ======")

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
            "DOORS:",
            len(
                geometry.get(
                    "doors",
                    []
                )
            )
        )

        print(
            "WINDOWS:",
            len(
                geometry.get(
                    "windows",
                    []
                )
            )
        )

        print("==============================")


        print(
            "\n====== BRIDGE GEOMETRY DIMENSION DEBUG ======"
        )

        print(
            {
                "geometry_keys": geometry.keys(),
                "walls_count": len(
                    geometry.get(
                        "walls",
                        []
                    )
                )
            }
        )


        if geometry.get("walls"):

            print(
                "FIRST WALL:",
                geometry["walls"][0]
            )


        print(
            "============================================="
        )


        print(
            "\n====== BRIDGE INPUT ======"
        )


        print(
            "geometry keys:",
            geometry.keys()
        )


        print(
            "walls:",
            len(
                geometry.get(
                    "walls",
                    []
                )
            )
        )


        print(
            "doors:",
            len(
                geometry.get(
                    "doors",
                    []
                )
            )
        )


        print(
            "windows:",
            len(
                geometry.get(
                    "windows",
                    []
                )
            )
        )

        # ==================================================
        # ARCHITECTURAL LEVEL CONFIG CONTRACT
        #
        # Floor heights are authoritative architectural
        # knowledge coming from ArchitecturalGeometryEngine.
        #
        # BIM must consume this contract and must not
        # recreate floor heights from fallback assumptions.
        # ==================================================

        architectural_level_config = {}

        floor_geometry = geometry.get(
            "floor_geometry",
            []
        )

        if not isinstance(
            floor_geometry,
            list
        ):

            floor_geometry = []


        structural_grid = design_result.get(
            "structural_grid",
            {}
        )
        architecture_handoff = (
            structural_grid.get("architecture_handoff", {})
            if isinstance(structural_grid, dict)
            else {}
        )
        ArchitectureStructureHandoffV1.require_ready(
            architecture_handoff,
            consumer="design_bim_bridge",
        )

        handoff_levels = (
            architecture_handoff.get("levels", [])
            if isinstance(architecture_handoff, dict)
            and architecture_handoff.get("status") == "ready"
            else []
        )

        vertical_section = design_result.get("vertical_section", {})
        vertical_section_levels = (
            vertical_section.get("levels", [])
            if isinstance(vertical_section, dict)
            else []
        )

        if isinstance(handoff_levels, list) and handoff_levels:
            level_sources = deepcopy(handoff_levels)
        elif isinstance(vertical_section_levels, list) and vertical_section_levels:
            level_sources = deepcopy(vertical_section_levels)
        else:
            level_sources = floor_geometry


        for floor_data in level_sources:

            if not isinstance(
                floor_data,
                dict
            ):

                continue


            floor_name = floor_data.get("name", floor_data.get("floor"))

            floor_height = floor_data.get(
                "height"
            )

            bottom = floor_data.get("bottom")
            top = floor_data.get("top")


            if (
                not floor_name
                or
                not isinstance(
                    floor_height,
                    (int, float)
                )
                or not isinstance(bottom, (int, float))
                or not isinstance(top, (int, float))
            ):

                continue


            floor_height = float(
                floor_height
            )


            architectural_level_config[
                floor_name
            ] = {

                "base_z":
                    float(bottom),

                "bottom":
                    float(bottom),

                "top":
                    float(top),

                "height":
                    floor_height,

                "column_height":
                    floor_height,

                "floor_height":
                    floor_height,

                "height_status":
                    floor_data.get(
                        "height_status"
                    ),

                "height_source":
                    (
                        "vertical_section.levels"
                        if handoff_levels or vertical_section_levels
                        else "architectural_floor_geometry"
                    ),

                "architectural_authority":
                    True

            }


        print(
            "\n====== ARCHITECTURAL LEVEL CONFIG CONTRACT ======"
        )

        print(
            architectural_level_config
        )

        print(
            "================================================="
        )



        project = {


            "source":
            "ArchitectOS DesignTool",



            # ==========================================
            # SITE CONTRACT
            # ==========================================

            "site":
            design_result.get(
                "site",
                {}
            ),



            # ==========================================
            # SPATIAL CONTRACT
            # ==========================================

            "spatial":
            design_result.get(
                "spatial",
                {}
            ),



            # ==========================================
            # STRUCTURAL CONTRACT
            # ==========================================

            "structural_grid":
            design_result.get(
                "structural_grid",
                {}
            )
            or
            {},



            # ==========================================
            # GRAPH CONTRACT
            # ==========================================

            "graph":
            design_result.get(
                "graph",
                {}
            ),



            # ==========================================
            # DESIGN GEOMETRY CONTRACT
            # ==========================================

            "geometry":
            geometry,

            "architectural_geometry":
            geometry,

            "vertical_section":
            design_result.get(
                "vertical_section",
                geometry.get("vertical_section", {})
            ),

            "geometry_intent":
            design_result.get("geometry_intent", {}),

            "architecture_first":
            bool(
                design_result.get("architecture_first")
                or geometry.get("physical_walls")
                or geometry.get("floor_geometry")
                or geometry.get("vertical_geometry")
                or geometry.get("site_geometry", {}).get("vehicle_access")
            ),

            "run_id":
            design_result.get("run_id", "architecture_first"),

            "export_session":
            design_result.get("export_session", "DEFAULT"),



            # ==========================================
            # ARCHITECTURAL LEVEL CONFIG
            # ==========================================

            "level_config":
            architectural_level_config,



            # ==========================================
            # MATERIAL CONTRACT
            # ==========================================

            "materials":
            design_result.get(
                "materials",
                {}
            ),



            # ==========================================
            # CONSTRAINT CONTRACT
            # ==========================================

            "constraints":
            design_result.get(
                "constraints",
                {}
            ),



            # ==========================================
            # EXECUTED ACTION CONTRACT
            # ==========================================

            "actions":
            design_result.get(
                "applied_actions",
                []
            ),



            # ==========================================
            # STRUCTURE CONTROL FLAG
            # ==========================================

            "generate_structure":
            design_result.get(
                "generate_structure",
                True
            )

        }



        print(
            "\n====== BRIDGE STRUCTURE CONTRACT ======"
        )


        print(
            "generate_structure:",
            project.get(
                "generate_structure"
            )
        )


        print(
            "structural_grid:",
            project.get(
                "structural_grid"
            )
        )

        structural_grid = project.get(
            "structural_grid",
            {}
        )


        print(
            "GRID TYPE:",
            structural_grid.get(
                "grid_type"
            )
        )


        print(
            "ANCHOR OWNERSHIP:",
            structural_grid.get(
                "anchor_ownership"
            )
        )


        print(
            "MASTER X:",
            structural_grid.get(
                "master_x_anchors"
            )
        )


        print(
            "MASTER Y:",
            structural_grid.get(
                "master_y_anchors"
            )
        )


        print(
            "FLOOR STRUCTURAL SYSTEMS:",
            {
                floor: {
                    "topology_mode":
                        data.get(
                            "topology_mode"
                        ),

                    "columns":
                        len(
                            data.get(
                                "columns",
                                []
                            )
                        ),

                    "beams":
                        len(
                            data.get(
                                "beams",
                                []
                            )
                        )
                }

                for floor, data in structural_grid.get(
                    "floor_structural_systems",
                    {}
                ).items()

                if isinstance(
                    data,
                    dict
                )
            }
        )


        print(
            "======================================"
        )



        print(
            "\n====== BRIDGE OUTPUT ======"
        )


        print(
            "walls:",
            len(
                project["geometry"].get(
                    "walls",
                    []
                )
            )
        )


        print(
            "doors:",
            len(
                project["geometry"].get(
                    "doors",
                    []
                )
            )
        )


        print(
            "windows:",
            len(
                project["geometry"].get(
                    "windows",
                    []
                )
            )
        )


        return project



    # ==================================================
    # CONNECT TO BIM PIPELINE
    # ==================================================

    def run_bim(
        self,
        design_result
    ):


        print("\n====== DESIGN RESULT SOURCE DEBUG ======")

        print(
            "DESIGN RESULT KEYS:",
            design_result.keys()
        )

        print( 
            "DESIGN RESULT KEYS:", 
            design_result.keys() 
        )


        print("\n====== DESIGN RESULT FULL TRACE ======")

        print(
            design_result
        )

        print("======================================")

        print(
            "HAS STRUCTURAL GRID:",
            "structural_grid" in design_result
        )

        print(
            "STRUCTURAL GRID VALUE:",
            design_result.get("structural_grid")
        )

        print(
            "HAS SPATIAL:",
            "spatial" in design_result
        )

        print("========================================")


        print("\n====== DESIGN SPATIAL TRACE ======")

        print(
            design_result.get("spatial")
        )

        print("==================================")


        print("\n====== DESIGN GEOMETRY TRACE ======")

        print(
            design_result.get("geometry")
        )

        print("===================================")


        from core.bim.full_bim_pipeline import (
            FullBIMPipeline
        )


        import inspect

        print("\n====== DESIGN RESULT CREATED BY ======")

        for frame in inspect.stack()[1:6]:
            print(
                frame.filename,
                frame.function,
                frame.lineno
            )

        print("======================================")


        project = self.prepare_bim_project(
            design_result
        )


        print(
            "FINAL DESIGN GRID BEFORE BIM:",
            design_result.get("structural_grid")
        )



        print(
            "\n====== FINAL PROJECT BEFORE BIM ======"
        )


        print(
            "PROJECT KEYS:",
            project.keys()
        )


        print(
            "GENERATE STRUCTURE:",
            project.get(
                "generate_structure"
            )
        )


        print(
            "STRUCTURAL GRID:",
            project.get(
                "structural_grid"
            )
        )


        print(
            "======================================"
        )



        pipeline = FullBIMPipeline()



        result = pipeline.generate(
            project
        )



        return {


            "bridge":
            f"DesignBIMBridge_v{self.VERSION}",


            "status":
            "completed",


            "input_project":
            project,


            "bim_result":
            result

        }
