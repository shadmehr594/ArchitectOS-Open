from collections import Counter
from copy import deepcopy

from core.structure.architecture_structure_handoff_v1 import (
    ArchitectureStructureHandoffV1,
)


print("######## USING GRID STRUCTURE ENGINE ########")
print("######## STRUCTURAL ELEMENT ENGINE DEBUG VERSION LOADED ########")


class StructuralElementEngine:


    def __init__(
        self,
        grid_data,
        level_config=None
    ):

        self.grid = grid_data

        supplied_level_config = (
            level_config
            if isinstance(level_config, dict)
            else {}
        )

        architecture_handoff = (
            grid_data.get("architecture_handoff", {})
            if isinstance(grid_data, dict)
            else {}
        )

        ArchitectureStructureHandoffV1.require_ready(
            architecture_handoff,
            consumer="structural_elements",
        )

        handoff_levels = {}

        if (
            isinstance(architecture_handoff, dict)
            and architecture_handoff.get("status") == "ready"
            and isinstance(
                architecture_handoff.get("levels_by_name"),
                dict
            )
        ):

            handoff_levels = architecture_handoff.get(
                "levels_by_name",
                {}
            )

        if handoff_levels:

            self.level_config = deepcopy(
                supplied_level_config
            )

            for level_name, architectural_level in handoff_levels.items():

                if not isinstance(architectural_level, dict):

                    continue

                merged_level = self.level_config.get(
                    level_name,
                    {}
                )

                if not isinstance(merged_level, dict):

                    merged_level = {}

                merged_level = deepcopy(merged_level)
                merged_level.update(
                    deepcopy(architectural_level)
                )

                self.level_config[level_name] = merged_level

            self.level_config_source = (
                "architecture_handoff_levels_by_name"
            )

        else:

            self.level_config = deepcopy(
                supplied_level_config
            )

            self.level_config_source = "supplied_level_config"


        print("\n====== STRUCTURAL ENGINE GRID INPUT ======")

        print(
            self.grid
        )

        print("==========================================")


        print("\n====== LEVEL CONFIG INPUT ======")

        print(
            self.level_config
        )

        print("================================")

        print("\n====== REAL STRUCTURAL ELEMENT ENGINE LOADED ======")

        print(
            "GRID INPUT:",
            self.grid
        )

        print("==================================================")


    # ======================
    # LEVEL CONFIG LOOKUP
    # ======================

    def _get_level_config(
        self,
        level
    ):

        if not level:

            return {}


        # --------------------------------------
        # 1. EXACT CONTRACT KEY
        # --------------------------------------

        if level in self.level_config:

            data = self.level_config.get(
                level
            )

            return (
                data
                if isinstance(
                    data,
                    dict
                )
                else {}
            )


        normalized_level = str(
            level
        ).lower()


        # --------------------------------------
        # 2. CASE-INSENSITIVE CONTRACT LOOKUP
        # --------------------------------------

        for config_level, data in (
            self.level_config.items()
        ):

            if (
                str(
                    config_level
                ).lower()
                ==
                normalized_level
            ):

                return (
                    data
                    if isinstance(
                        data,
                        dict
                    )
                    else {}
                )


        return {}


    # ======================
    # LEVEL TO Z
    # ======================

    def _level_to_z(
        self,
        level
    ):

        if not level:

            return None


        data = self._get_level_config(
            level
        )


        for key in (
            "bottom",
            "base_z",
            "elevation"
        ):

            if isinstance(data.get(key), (int, float)):

                return data.get(key)

        return None



    # ======================
    # LEVEL HEIGHT
    # ======================

    def _get_column_height(
        self,
        level
    ):

        data = self._get_level_config(
            level
        )


        for key in (
            "height",
            "column_height"
        ):

            if isinstance(data.get(key), (int, float)):

                return data.get(key)

        return None


    # ======================
    # LEVEL TOP
    # ======================

    def _get_level_top(
        self,
        level
    ):

        data = self._get_level_config(
            level
        )

        for key in (
            "top",
            "top_z",
            "beam_top_z"
        ):

            if isinstance(data.get(key), (int, float)):

                return data.get(key)

        # Legacy level contracts sometimes carry only base + height.  Keep
        # that compatibility here; architecture-first contracts always carry
        # their authoritative explicit ``top`` and return above.
        base_z = self._level_to_z(level)
        height = self._get_column_height(level)

        if (
            isinstance(base_z, (int, float))
            and isinstance(height, (int, float))
        ):

            return base_z + height

        return None



    # ======================
    # BEAM LEVEL
    # ======================

    def _get_beam_z(
        self,
        level,
        beam_depth
    ):

        data = self._get_level_config(
            level
        )


        level_top = self._get_level_top(
            level
        )

        beam_z = (
            level_top - beam_depth
            if isinstance(level_top, (int, float))
            and isinstance(beam_depth, (int, float))
            else None
        )

        print(
            "\n====== GET BEAM Z DEBUG ======"
        )

        print(
            {
                "level": level,
                "level_top": level_top,
                "beam_depth": beam_depth,
                "beam_bottom_z": beam_z
            }
        )

        print(
            "================================"
        )


        return beam_z



    # ======================
    # MAIN ENTRY
    # ======================

    def build(
        self,
        spatial_data
    ):


        print(
            "\n===== STRUCTURAL ENGINE START ====="
        )


        print(
            "GRID DATA:",
            self.grid
        )


        print(
            "SPATIAL FLOORS:",
            spatial_data.keys()
        )


        result = {}


        for floor_name, floor_data in spatial_data.items():

            # Spatial v19 wraps floor records with metadata.  Structural
            # generation must only consume actual floor dictionaries.
            if not isinstance(floor_data, dict):
                continue


            print(
                "\n========== BUILD FLOOR ==========",
                floor_name
            )


            print(
                "FLOOR DATA KEYS:",
                floor_data.keys()
            )


            nodes = floor_data.get(
                "nodes",
                {}
            )


            print(
                "\n====== SPATIAL NODE COLUMN DECISION DEBUG ======"
            )


            print(
                "LEVEL:",
                floor_name
            )


            print(
                "NODE COUNT:",
                len(nodes)
            )


            print(
                "=============================================="
            )



            columns = self._generate_columns(
                floor_name
            )


            beams = self._generate_beams(
                nodes,
                floor_name
            )


            print(
                "\n====== STRUCTURAL GENERATED GEOMETRY DEBUG ======"
            )

            print(
                "LEVEL:",
                floor_name
            )

            for c in columns[:3]:
                print(
                    "COLUMN:",
                    {
                        "id": c.get("id"),
                        "level": c.get("level"),
                        "x": c.get("x"),
                        "y": c.get("y"),
                        "z": c.get("z"),
                        "width": c.get("width"),
                        "depth": c.get("depth"),
                        "height": c.get("height")
                    }
                )


            for b in beams[:3]:
                print(
                    "BEAM:",
                    {
                        "id": b.get("id"),
                        "level": b.get("level"),
                        "start": b.get("start"),
                        "end": b.get("end"),
                        "z": b.get("z"),
                        "depth": b.get("depth"),
                        "height": b.get("height")
                    }
                )

            print(
                "=============================================="
            )



            print(
                "STRUCTURAL Z CHECK:",
                floor_name,
                "COLUMN Z:",
                [
                    c.get("z")
                    for c in columns[:3]
                ],
                "BEAM Z:",
                [
                    b.get("z")
                    for b in beams[:3]
                ]
            )



            walls = self._generate_walls(
                nodes,
                floor_name
            )



            print(
                "FLOOR:",
                floor_name,
                "| NODES:",
                len(nodes),
                "| COLUMNS:",
                len(columns),
                "| BEAMS:",
                len(beams),
                "| WALLS:",
                len(walls)
            )


            print(
                "\n====== COLUMN FINAL SOURCE XY DEBUG ======"
            )

            for c in columns[:12]:

                print(
                    c["id"],
                    "X=",
                    c["x"],
                    "Y=",
                    c["y"],
                    "LEVEL=",
                    c["level"]
                )

            print(
                "=========================================="
            )



            result[floor_name] = {

                "columns": columns,

                "beams": beams,

                "walls": walls

            }



        print(
            "\n====== STRUCTURAL SOURCE LEVEL DEBUG ======"
        )


        for level, data in result.items():


            for item in data.get("columns", [])[:5]:

                print(
                    item.get("id"),
                    item.get("type"),
                    item.get("level"),
                    item.get("z"),
                    item
                )



            for item in data.get("beams", [])[:5]:

                print(
                    item.get("id"),
                    item.get("type"),
                    item.get("level"),
                    item.get("z"),
                    item
                )


        print(
            "=========================================="
        )


        return result

    # ======================
    # COLUMNS
    # ======================

    def _generate_columns(
        self,
        floor_name
    ):

        print(
            "\n====== ADAPTIVE COLUMN SOURCE ======"
        )

        floor_structural_systems = self.grid.get(
            "floor_structural_systems",
            {}
        )


        if not isinstance(
            floor_structural_systems,
            dict
        ):

            floor_structural_systems = {}


        floor_system = floor_structural_systems.get(
            floor_name,
            {}
        )


        if not isinstance(
            floor_system,
            dict
        ):

            floor_system = {}


        source_columns = floor_system.get(
            "columns"
        )


        if not isinstance(
            source_columns,
            list
        ):

            source_columns = self.grid.get(
                "columns",
                []
            )


        if not isinstance(
            source_columns,
            list
        ):

            source_columns = []


        print(
            "\n====== FLOOR STRUCTURAL COLUMN SOURCE ======"
        )

        print(
            {
                "level":
                    floor_name,

                "source":
                    (
                        "floor_structural_systems"
                        if floor_system
                        else "master_grid_fallback"
                    ),

                "topology_mode":
                    floor_system.get(
                        "topology_mode"
                    ),

                "column_count":
                    len(
                        source_columns
                    )
            }
        )

        print(
            "============================================"
        )

        print(
            "\n====== COLUMN SOURCE ID BEFORE FLOOR BUILD ======"
        )

        print(
            "FLOOR:",
            floor_name
        )

        print(
            "SOURCE IDS:",
            [
                column.get(
                    "id"
                )
                for column in source_columns[:10]
            ]
        )

        print(
            "SOURCE SOURCE_IDS:",
            [
                column.get(
                    "source_id"
                )
                for column in source_columns[:10]
            ]
        )

        print(
            "================================================"
        )

        print(
            {
                "level": floor_name,
                "source_count": len(
                    source_columns
                ),
                "grid_type": self.grid.get(
                    "grid_type"
                )
            }
        )

        print(
            "===================================="
        )

        columns = []

        # ----------------------
        # PRESERVE EXISTING
        # LEVEL / Z LOGIC
        # ----------------------

        base_z = self._level_to_z(
            floor_name
        )

        column_height = self._get_column_height(
            floor_name
        )

        top_z = self._get_level_top(
            floor_name
        )

        print(
            "\n====== COLUMN LEVEL CONFIG DEBUG ======"
        )

        print(
            {
                "level": floor_name,
                "base_z": base_z,
                "column_height": column_height,
                "top_z": top_z
            }
        )

        print(
            "======================================"
        )

        # ----------------------
        # ADAPT FINAL COLUMNS
        # DO NOT REBUILD TOPOLOGY
        # ----------------------

        for index, source_column in enumerate(
            source_columns
        ):

            if not isinstance(
                source_column,
                dict
            ):
                continue

            x = source_column.get(
                "x"
            )

            y = source_column.get(
                "y"
            )

            if x is None or y is None:
                continue

            width = source_column.get(
                "width"
            )

            depth = source_column.get(
                "depth"
            )

            if width is None or depth is None:
                continue

            source_id = source_column.get(
                "id",
                f"C-{index + 1}"
            )

            size = (
                f"{round(width * 100):g}"
                f"x"
                f"{round(depth * 100):g}"
            )

            column = dict(
                source_column
            )

            column.update(
                {
                    "id":
                        f"{source_id}-{floor_name}",

                    "source_id":
                        source_id,

                    "x":
                        x,

                    "y":
                        y,

                    "width":
                        width,

                    "depth":
                        depth,

                    "z":
                        base_z,

                    "base_z":
                        base_z,

                    "top_z":
                        top_z,

                    "height":
                        column_height,

                    "level":
                        floor_name,

                    "type":
                        "RC_COLUMN",

                    "size":
                        size,

                    "reference":
                        source_column.get(
                            "reference",
                            "corner"
                        )
                }
            )


            if index < 3:

                print(
                    "COLUMN IDENTITY OUT:",
                    {
                        "id":
                            column.get(
                                "id"
                            ),

                        "source_id":
                            column.get(
                                "source_id"
                            ),

                        "x":
                            column.get(
                                "x"
                            ),

                        "y":
                            column.get(
                                "y"
                            ),

                        "level":
                            column.get(
                                "level"
                            )
                    }
                )

            columns.append(
                column
            )


        print(
            "\n====== ADAPTIVE COLUMN OUTPUT ======"
        )

        print(
            "LEVEL:",
            floor_name
        )

        print(
            "COUNT:",
            len(
                columns
            )
        )

        for column in columns[:5]:
            print(
                column
            )

        if columns:

            xs = [
                column["x"]
                for column in columns
            ]

            ys = [
                column["y"]
                for column in columns
            ]

            print(
                "EXTENTS:",
                {
                    "min_x": min(xs),
                    "max_x": max(xs),
                    "min_y": min(ys),
                    "max_y": max(ys)
                }
            )

        print(
            "===================================="
        )

        return columns
    # ======================
    # BEAMS
    # ======================

    def _generate_beams(
        self,
        nodes,
        floor_name
    ):

        print(
            "\n====== ADAPTIVE BEAM SOURCE ======"
        )

        floor_structural_systems = self.grid.get(
            "floor_structural_systems",
            {}
        )


        if not isinstance(
            floor_structural_systems,
            dict
        ):

            floor_structural_systems = {}


        floor_system = floor_structural_systems.get(
            floor_name,
            {}
        )


        if not isinstance(
            floor_system,
            dict
        ):

            floor_system = {}


        source_beams = floor_system.get(
            "beams"
        )


        if not isinstance(
            source_beams,
            list
        ):

            source_beams = self.grid.get(
                "beams",
                []
            )


        if not isinstance(
            source_beams,
            list
        ):

            source_beams = []


        print(
            "\n====== FLOOR STRUCTURAL BEAM SOURCE ======"
        )

        print(
            {
                "level":
                    floor_name,

                "source":
                    (
                        "floor_structural_systems"
                        if floor_system
                        else "master_grid_fallback"
                    ),

                "topology_mode":
                    floor_system.get(
                        "topology_mode"
                    ),

                "beam_count":
                    len(
                        source_beams
                    )
            }
        )

        print(
            "=========================================="
        )

        print(
            {
                "level": floor_name,
                "source_count": len(
                    source_beams
                ),
                "grid_type": self.grid.get(
                    "grid_type"
                )
            }
        )

        print(
            "=================================="
        )

        beams = []

        # ----------------------
        # ADAPT FINAL BEAMS
        # DO NOT REBUILD TOPOLOGY
        # ----------------------

        for index, source_beam in enumerate(
            source_beams
        ):

            if not isinstance(
                source_beam,
                dict
            ):
                continue

            start = source_beam.get(
                "start"
            )

            end = source_beam.get(
                "end"
            )

            if (
                not start
                or
                not end
                or
                len(start) < 2
                or
                len(end) < 2
            ):
                continue

            width = source_beam.get(
                "width"
            )

            depth = source_beam.get(
                "depth"
            )

            if width is None or depth is None:
                continue

            beam_z = self._get_beam_z(
                floor_name,
                depth
            )

            source_id = source_beam.get(
                "id",
                f"B-{index + 1}"
            )

            beam = dict(
                source_beam
            )

            beam.update(
                {
                    "id":
                        f"{source_id}-{floor_name}",

                    "source_id":
                        source_id,

                    "start":
                        (
                            start[0],
                            start[1]
                        ),

                    "end":
                        (
                            end[0],
                            end[1]
                        ),

                    "width":
                        width,

                    "depth":
                        depth,

                    # Keep downstream geometry
                    # compatibility.
                    "height":
                        depth,

                    "type":
                        "BEAM",

                    "level":
                        floor_name,

                    "z":
                        beam_z,

                    "elevation":
                        beam_z,

                    "top_z":
                        self._get_level_top(
                            floor_name
                        ),

                    "reference":
                        source_beam.get(
                            "reference",
                            "corner"
                        )
                }
            )

            beams.append(
                beam
            )

        print(
            "\n====== ADAPTIVE BEAM OUTPUT ======"
        )

        print(
            "LEVEL:",
            floor_name
        )

        print(
            "COUNT:",
            len(
                beams
            )
        )

        for beam in beams[:5]:

            print(
                {
                    "id":
                        beam.get(
                            "id"
                        ),

                    "start":
                        beam.get(
                            "start"
                        ),

                    "end":
                        beam.get(
                            "end"
                        ),

                    "orientation":
                        beam.get(
                            "orientation"
                        ),

                    "width":
                        beam.get(
                            "width"
                        ),

                    "depth":
                        beam.get(
                            "depth"
                        ),

                    "level":
                        beam.get(
                            "level"
                        ),

                    "z":
                        beam.get(
                            "z"
                        )
                }
            )

        print(
            "=================================="
        )

        return beams
    # ======================
    # WALL SYSTEM
    # ======================

    def _generate_walls(
        self,
        nodes,
        floor_name
    ):

        walls = []


        base_z = self._level_to_z(
            floor_name
        )


        wall_height = self._get_column_height(
            floor_name
        )

        wall_top_z = self._get_level_top(
            floor_name
        )



        print(
            "\n====== WALL LEVEL CONFIG ======"
        )


        print(
            {
                "level": floor_name,
                "base_z": base_z,
                "wall_height": wall_height
            }
        )


        print(
            "==============================="
        )



        for node, props in nodes.items():

            if props.get(
                "external",
                False
            ):

                print(
                    "SKIP EXTERNAL STRUCTURAL WALL:",
                    node
                )

                continue


            x = props.get(
                "x",
                0
            )


            y = props.get(
                "y",
                0
            )


            w = props.get(
                "w",
                0
            )


            h = props.get(
                "h",
                0
            )


            print(
                "====== WALL NODE SOURCE ======"
            )

            print(
                {
                    "node": node,
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "props": props
                }
            )

            print(
                "=============================="
            )


            print(
                "====== STRUCTURAL WALL AXIS DECISION INPUT ======"
            )

            print(
                {
                    "node": node,
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "w_gt_h": w > h,
                    "w_eq_h": w == h,
                    "w_lt_h": w < h
                }
            )

            print(
                "==============================================="
            )

            print(
                "====== WALL AXIS RAW TEST ======"
            )

            print(
                {
                    "node": node,
                    "w": w,
                    "h": h,
                    "w_gt_h": w > h,
                    "h_gt_w": h > w,
                    "w_eq_h": w == h
                }
            )

            print(
                "================================"
            )


            print(
                "====== SQUARE WALL FULL AXIS SOURCE ======"
            )

            print(
                {
                    "node": node,
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "props": props,
                    "connections": props.get("connections"),
                    "external": props.get("external")
                }
            )

            print(
                "==========================================="
            )


            print(
                "====== STRUCTURAL WALL AXIS DECISION ======"
            )

            print(
                {
                    "node": node,
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "connections": props.get("connections"),
                    "CURRENT_RULE": (
                        "X"
                        if w > h
                        else "Y"
                    )
                }
            )

            print(
                "==========================================="
            )

            print(
                "====== STRUCTURAL WALL GEOMETRY SOURCE ======"
            )

            print(
                {
                    "node": node,
                    "props": props,
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "connections": props.get("connections"),
                    "boundary_candidates": {
                        "bottom_X": (
                            (x, y),
                            (x + w, y)
                        ),
                        "right_Y": (
                            (x + w, y),
                            (x + w, y + h)
                        ),
                        "top_X": (
                            (x + w, y + h),
                            (x, y + h)
                        ),
                        "left_Y": (
                            (x, y + h),
                            (x, y)
                        )
                    }
                }
            )

            print(
                "============================================="
            )


            if w > h:

                # X direction wall
                start = (
                    x,
                    y
                )

                end = (
                    x + w,
                    y
                )

                wall_direction = "X"


            elif h > w:

                # Y direction wall
                start = (
                    x,
                    y
                )

                end = (
                    x,
                    y + h
                )

                wall_direction = "Y"


            else:

                # SQUARE — AXIS IS AMBIGUOUS
                print(
                    "⚠️ SQUARE WALL — AXIS UNRESOLVED"
                )

                print(
                    {
                        "node": node,
                        "x": x,
                        "y": y,
                        "w": w,
                        "h": h,
                        "props": props
                    }
                )

                # فعلاً Y برای تست
                start = (
                    x,
                    y
                )

                end = (
                    x,
                    y + h
                )

                wall_direction = "Y"


            print(
                "====== WALL DIRECTION GENERATED ======"
            )

            print(
                {
                    "node": node,
                    "start": start,
                    "end": end,
                    "direction": wall_direction
                }
            )

            print(
                "======================================"
            )


            print(
                "====== STRUCTURAL WALL AXIS DECISION OUTPUT ======"
            )

            print(
                {
                    "node": node,
                    "start": start,
                    "end": end,
                    "direction": wall_direction,
                    "w": w,
                    "h": h
                }
            )

            print(
                "==================================================="
            )

            print(
                "====== FINAL WALL BEFORE APPEND ======"
            )

            print(
                {
                    "id": node,
                    "start": start,
                    "end": end,
                    "dx": end[0]-start[0],
                    "dy": end[1]-start[1],
                    "direction": wall_direction
                }
            )

            print(
                "======================================="
            )

            print(
                "====== X WALL GENERATION TEST ======"
            )

            x_wall_start = (
                x,
                y
            )

            x_wall_end = (
                x + w,
                y
            )

            print(
                {
                    "node": node,
                    "x_wall_start": x_wall_start,
                    "x_wall_end": x_wall_end,
                    "dx": x_wall_end[0] - x_wall_start[0],
                    "dy": x_wall_end[1] - x_wall_start[1],
                    "direction": "X"
                } 
            )

            print(
                "===================================="
            )

            print(
                "====== X WALL APPEND TEST ======"
            )

            x_wall = {
                "id": f"{node}-X",
                "start": x_wall_start,
                "end": x_wall_end,
                "length": w,
                "direction": "X"
            }

            print(
                "X WALL OBJECT:",
                x_wall
            ) 

            walls.append(
                x_wall
            )

            print(
                "====== X WALL APPENDED ======"
            )

            print(
                {
                    "id": walls[-1].get("id"),
                    "start": walls[-1].get("start"),
                    "end": walls[-1].get("end"),
                    "dx": walls[-1]["end"][0] - walls[-1]["start"][0],
                    "dy": walls[-1]["end"][1] - walls[-1]["start"][1],
                    "direction": walls[-1].get("direction")
                }
            )

            print(
                "================================"
            )



            walls.append({

                "id":
                    f"W-{node}",

                
                "start":
                    start,


                "end":
                    end,
                

                "level":
                    floor_name,


                "z":
                    base_z,


                "length":
                    w,


                "height":
                    wall_height,


                "top_z":
                    wall_top_z,


                "thickness":
                    0.2,


                "type":
                    "SHEAR_WALL"

            })



        print(
            "\n====== STRUCTURAL WALL OUTPUT ======"
        )


        print(
            "LEVEL:",
            floor_name
        )


        print(
            "COUNT:",
            len(walls)
        )


        for wall in walls[:3]:

            print(
                wall
            )


        print(
            "===================================="
        )



        return walls
