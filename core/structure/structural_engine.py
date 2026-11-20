from collections import Counter


print("######## STRUCTURE ENGINE DEBUG VERSION LOADED ########")


class StructureEngine:


    def __init__(
        self,
        grid_spacing=4,
        level_config=None
    ):

        self.grid_spacing = grid_spacing
        self.level_config = level_config or {}



    # ======================
    # LEVEL TO Z
    # ======================

    def level_to_z(
        self,
        level
    ):

        if not level:
            return 0


        level = level.upper()


        data = self.level_config.get(
            level,
            {}
        )


        return data.get(
            "base_z",
            0
        )



    # ======================
    # MAIN ENTRY
    # ======================

    def build_structure(
        self,
        geometry
    ):

        print("\n!!!!!!!! BUILD_STRUCTURE CALLED !!!!!!!!")


        print(
            "LEVEL CONFIG DEBUG:",
            self.level_config
        )


        print("\n====== STRUCTURE ENGINE BUILD START ======")

        print(
            "SPATIAL LEVELS:",
            geometry.get("spatial", {}).keys()
        )

        print(
            "STRUCTURAL GRID LEVELS:",
            geometry.get("structural_grid", {}).keys()
        )

        print(
            "==========================================")


        # ==========================================
        # STRUCTURAL GRID INPUT TRACE
        # ==========================================

        print("\n====== STRUCTURAL GRID INPUT TO ENGINE ======")

        print(
            geometry.get(
                "structural_grid",
                {}
            )
        )

        print("============================================")


        # ==========================================
        # STRUCTURE LEVEL DEBUG
        # ==========================================

        spatial_levels = geometry.get(
            "spatial",
            {}
        ).get(
            "floors",
            {}
        )

        structural_grid = geometry.get(
            "structural_grid",
            {}
        )


        for floor_name in spatial_levels:

            print(
                "\nPROCESSING STRUCTURE LEVEL:",
                floor_name
            )


            print(
                "LEVEL GRID:",
                structural_grid.get(
                    floor_name,
                    {}
                )
            )


        print("\n====== STRUCTURE ROOM LEVEL TRACE ======")

        for room in geometry.get("rooms", []):

            print(
                {
                    "id": room.get("id"),
                    "level": room.get("level"),
                    "x": room.get("x"),
                    "y": room.get("y"),
                    "w": room.get("w"),
                    "h": room.get("h")
                }
            )

        print("========================================")


        print("\n====== BEFORE COLUMN GENERATION ======")

        print(
            "GRID:",
            geometry.get(
                "structural_grid",
                {}
            )
        )

        print("======================================")



        columns = self._generate_columns(
            geometry
        )


        columns = self._generate_columns(
            geometry
        )


        print(
            "\nGENERATED COLUMNS:",
            len(columns)
        )


        for floor_name in spatial_levels:

            level_columns = [
                c for c in columns
                if c.get("level") == floor_name
            ]

            print(
                "GENERATED COLUMNS:",
                floor_name,
                len(level_columns)
            )

        print("\n====== COLUMN OUTPUT CHECK ======")

        for c in columns[:10]:
            print(
                c
            )

        print(
            "TOTAL COLUMNS:",
            len(columns)
        )


        print("\n====== COLUMN LEVEL DISTRIBUTION BEFORE BEAMS ======")

        for level in ["F1", "F2", "F3"]:

            cols = [
                c
                for c in columns
                if c.get("level") == level
            ]

            print(level, len(cols))

        print("====================================================")


        beams = self._generate_beams(
            columns
        )


        print(
            "\nGENERATED BEAMS:",
            len(beams)
        )


        for floor_name in spatial_levels:

            level_beams = [
                b for b in beams
                if b.get("level") == floor_name
            ]

            print(
                "GENERATED BEAMS:",
                floor_name,
                len(level_beams)
            )


        slabs = geometry.get(
            "floors",
            []
        )


        walls = geometry.get(
            "walls",
            []
        )


        print(
            "STRUCTURE LEVEL SUMMARY"
        )


        print(
            "COLUMNS:",
            Counter(
                c.get("level")
                for c in columns
            )
        )


        print(
            "BEAMS:",
            Counter(
                b.get("level")
                for b in beams
            )
        )


        print(
            "\n====== STRUCTURE FINAL Z CHECK ======"
        )

        print("\nLAST STRUCTURE Z CHECK")


        for c in columns[-20:]:

            print(
                "COLUMN",
                c["level"],
                "X",
                c["x"],
                "Y",
                c["y"],
                "Z",
                c.get("z")
            )


        for b in beams[-20:]:

            print(
                "BEAM",
                b["level"],
                "START",
                b["start"],
                "END",
                b["end"],
                "Z",
                b.get("z")
            )


        print(
            "===================================="
        )


        return {

            "columns": columns,

            "beams": beams,

            "slabs": slabs,

            "walls": walls

        }



    # ======================
    # COLUMNS
    # ======================

    def _generate_columns(
        self,
        geometry
    ):


        columns = []

        rooms = geometry.get(
            "rooms",
            []
        )


        structural_grid = geometry.get(
            "structural_grid",
            {}
        )

        print("\n========== RAW STRUCTURAL GRID ==========")

        for level, grid in structural_grid.items():

            print(
                "LEVEL:",
                level
            )

            print(
                "GRID DATA:",
                grid
            )

        print("=========================================\n")
        

        print("\n====== COLUMN ENGINE GRID TRACE ======")

        for level, grid in structural_grid.items():

            print(
                "LEVEL:",
                level
            )

            print(
                "X:",
                grid.get("columns_x")
            )

            print(
                "Y:",
                grid.get("columns_y")
            )

            print(
                "EXPECTED:",
                len(grid.get("columns_x", []))
                *
                len(grid.get("columns_y", []))
            )

        print("======================================")

        # ==================================
        # 1) GRID BASED COLUMNS
        # ==================================

        for level, grid in structural_grid.items():


            x_lines = grid.get(
                "columns_x",
                []
            )


            y_lines = grid.get(
                "columns_y",
                []
            )


            column_z = self.level_to_z(
                level
            )

            level_height = self.level_config.get(
                level,
                {}
            ).get(
                "height",
                3.2
            )

            print(
                "GRID COLUMN SOURCE:",
                {
                    "level": level,
                    "columns_x": x_lines,
                    "columns_y": y_lines,
                    "count": len(x_lines) * len(y_lines)
                }
            )


            for x in x_lines:

                for y in y_lines:

                    columns.append({

                        "type":
                            "column",


                        "source": 
                            "grid",


                        "x":
                            x,


                        "y":
                            y,


                        "z":
                            column_z,


                        "base_z":
                            column_z,


                        "top_z":
                            column_z + level_height,


                        "height":
                            level_height,


                        "level":
                            level

                    })

        # ==================================
        # 2) ROOM CORNER COLUMNS
        # ==================================

        for room in rooms:


            x = room.get(
                "x",
                0
            )

            y = room.get(
                "y",
                0
            )


            w = room.get(
                "w",
                0
            )


            h = room.get(
                "h",
                0
            )


            floor_level = room.get(
                "level",
                "F1"
            )


            height = room.get(
                "height",
                self.level_config.get(
                    floor_level,
                    {}
                ).get(
                    "height",
                    3.2
                )
            )


            column_z = self.level_to_z(
                floor_level
            )


            points = [

                (x, y),

                (x + w, y),

                (x + w, y + h),

                (x, y + h)

            ]



            for px, py in points:


                columns.append({

                    "type":
                        "column",


                    "source": 
                        "room_corner",


                    "x":
                        px,


                    "y":
                        py,


                    "z":
                        column_z,


                    "base_z":
                        column_z,


                    "top_z":
                        column_z + height,


                    "height":
                        height,


                    "level":
                        floor_level

                })

        # ==================================
        # COLUMN SOURCE NORMALIZATION
        # REMOVE DUPLICATES
        # ==================================

        print("\n====== COLUMN RAW SOURCE COUNT ======")

        print(
            "TOTAL RAW COLUMNS:",
            len(columns)
        )

        print("====================================")

        print("\n====== COLUMN NORMALIZATION ======")

        unique_columns = []

        seen = set()


        for column in columns:

            key = (

                column.get("level"),

                column.get("x"),

                column.get("y")

            )


            if key in seen:
                continue


            seen.add(key)

            unique_columns.append(
                column
            )


        print(
            "COLUMNS BEFORE:",
            len(columns)
        )


        print(
            "COLUMNS AFTER:",
            len(unique_columns)
        )


        print(
            "REMOVED:",
            len(columns) - len(unique_columns)
        )


        print(
            "================================="
        )


        print("\n====== COLUMN SOURCE TYPES ======")

        for c in unique_columns:

            print(
                {
                    "level": c["level"],
                    "x": c["x"],
                    "y": c["y"],
                    "z": c["z"]
                }
            )

        print("================================")


        columns = unique_columns

        print("\n====== COLUMN LEVEL Z CHECK ======")

        for level in ["F1","F2","F3"]:
            items = [
                c for c in unique_columns
                if c["level"] == level
            ]

            print(
                level,
                "COUNT:",
                len(items),
                "Z:",
                sorted(set(
                    c["z"] for c in items
                ))
            )

        print("==================================")


        return columns



    # ======================
    # BEAMS
    # ======================

    def _generate_beams(
        self,
        columns
    ):

        beams = []

        seen = set()

        print("\n====== BEAM SOURCE COLUMN LEVEL TRACE ======")

        for c in columns:

            print(
                c["level"],
                c["x"],
                c["y"]
            )

        print("==========================================")


        for a in columns:

            for b in columns:


                if a is b:
                    continue

                if (
                    a["x"] == b["x"]
                    and
                    a["y"] == b["y"]
                ):
                    continue


                if a["level"] != b["level"]:
                    continue


                if (
                    a["source"] != "grid"
                    or
                    b["source"] != "grid"
                ):
                    continue


                dx = abs(
                    a["x"] - b["x"]
                )

                dy = abs(
                    a["y"] - b["y"]
                )


                # فقط هم محورهای واقعی شبکه


                print(
                    "COLUMN PAIR CHECK:",
                    {
                        "A": (
                            a["x"],
                            a["y"],
                            a["level"]
                        ),
                        "B": (
                            b["x"],
                            b["y"],
                            b["level"]
                        ),
                        "dx": dx,
                        "dy": dy
                    }
                )


                if (
                    dy == 0
                    and dx in [4,8]
                ):


                    print(
                        "VALID HORIZONTAL BEAM:",
                        {
                            "A": (a["x"], a["y"]),
                            "B": (b["x"], b["y"]),
                            "dx": dx,
                            "dy": dy
                        }
                    )

                    key = tuple(sorted([
                        (
                            a["x"],
                            a["y"]
                        ),
                        (
                            b["x"],
                            b["y"]
                        )
                    ]))


                    if key in seen:
                        continue


                    seen.add(key)


                    print(
                        "FINAL BEAM BEFORE APPEND:",
                        {
                            "level": a["level"],
                            "start": (
                                a["x"],
                                a["y"]
                            ),
                            "end": (
                                b["x"],
                                b["y"]
                            ),
                            "a_z": a["z"],
                            "column_height": a["height"],
                            "beam_z": a["z"] + a["height"]
                        }
                    )


                    print(
                        "APPENDING BEAM:",
                        {
                            "level": a["level"],
                            "start": (
                                a["x"],
                                a["y"]
                            ),
                            "end": (
                                b["x"],
                                b["y"]
                            ),
                            "z": a["z"] + a["height"]
                        }
                    )



                    beams.append({

                        "type":
                            "beam",


                        "start":
                            (
                                a["x"],
                                a["y"]
                            ),


                        "end":
                            (
                                b["x"],
                                b["y"]
                            ),


                        "level":
                            a["level"],


                        "z":
                            a["z"]
                            +
                            a["height"],


                        "elevation":
                            a["z"]
                            +
                            a["height"],
                            

                        "height":
                            0.4,


                        "depth":
                            0.4

                    })



                if (
                    dx == 0
                    and dy in [4,8]
                ):


                    print(
                        "VALID VERTICAL BEAM:",
                        {
                            "A": (a["x"], a["y"]),
                            "B": (b["x"], b["y"]),
                            "dx": dx,
                            "dy": dy
                        }
                    )


                    key = tuple(sorted([
                        (
                            a["x"],
                            a["y"]
                        ),
                        (
                            b["x"],
                            b["y"]
                        )
                    ]))


                    if key in seen:
                        continue


                    seen.add(key)


                    print(
                        "BEAM SOURCE INPUT TRACE:",
                        {
                            "level": a["level"],
                            "a_z": a["z"],
                            "x": a["x"],
                            "y": a["y"],
                            "height": 0.4
                        }
                    )


                    print(
                        "FINAL BEAM BEFORE APPEND:",
                        {
                            "level": a["level"],
                            "start": (
                                a["x"],
                                a["y"]
                            ),
                            "end": (
                                b["x"],
                                b["y"]
                            ),
                            "a_z": a["z"],
                            "column_height": a["height"],
                            "beam_z": a["z"] + a["height"]
                        }
                    )


                    print(
                        "APPENDING BEAM:",
                        {
                            "level": a["level"],
                            "start": (
                                a["x"],
                                a["y"]
                            ),
                            "end": (
                                b["x"],
                                b["y"]
                            ),
                            "z": a["z"] + a["height"]
                        }
                    )



                    beams.append({

                        "type":
                            "beam",


                        "start":
                            (
                                a["x"],
                                a["y"]
                            ),


                        "end":
                            (
                                b["x"],
                                b["y"]
                            ),


                        "level":
                            a["level"],


                        "z":
                            a["z"]
                            +
                            a["height"],


                        "elevation":
                            a["z"]
                            +
                            a["height"],


                        "height":
                            0.4,


                        "depth":
                            0.4

                    })


            if beams:
                print(
                    "STRUCTURE BEAM CREATED:",
                    beams[-1]
                )
            else:
                print(
                    "NO BEAM CREATED FOR COLUMN:",
                    a
                )

        print("\n====== BEAM LEVEL Z CHECK ======")

        for level in ["F1","F2","F3"]:
            items = [
                b for b in beams
                if b["level"] == level
            ]

            print(
                level,
                "COUNT:",
                len(items),
                "Z:",
                sorted(set(
                    b["z"] for b in items
                ))
            )

        print("=================================")

        return beams