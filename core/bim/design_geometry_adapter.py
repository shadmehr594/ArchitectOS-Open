"""
ArchitectOS Design Geometry Adapter v2.1

Converts Architectural Spatial Output
into BIM Geometry Contract

v2.1
----------------------------------
✔ Single Source Room Geometry
✔ Spatial Contract Compatible
✔ Room → Wall Generation
✔ Interior Door Detection
✔ Interior Window Generation
✔ External Space Protection
✔ BIM Ready Geometry
"""

from collections import defaultdict
from copy import deepcopy


class DesignGeometryAdapter:

    VERSION = "2.1"

    FLOOR_HEIGHT = 3.20

    DEFAULT_DOOR_WIDTH = 1.00
    DEFAULT_DOOR_HEIGHT = 2.20

    DEFAULT_WINDOW_WIDTH = 2.00
    DEFAULT_WINDOW_HEIGHT = 1.50


    def __init__(self):

        print(
            f"📐 Design Geometry Adapter v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # MAIN CONVERTER
    # ==================================================

    def convert(
        self,
        project=None
    ):

        project = project or {}

        authoritative = project.get("architectural_geometry")
        if not isinstance(authoritative, dict):
            candidate = project.get("geometry")
            if isinstance(candidate, dict) and (
                candidate.get("architectural_authority")
                or candidate.get("physical_walls")
                or candidate.get("floor_geometry")
            ):
                authoritative = candidate

        if isinstance(authoritative, dict) and authoritative:
            geometry = deepcopy(authoritative)
            geometry["architectural_authority"] = True
            geometry["geometry_source"] = "ArchitecturalGeometryEngineV2"
            return {
                "adapter": f"DesignGeometryAdapter_v{self.VERSION}",
                "geometry": geometry,
                "authoritative_passthrough": True,
            }


        spatial = project.get(
            "spatial",
            {}
        )


        print(
            "\n====== RAW SPATIAL INPUT TO DESIGN ADAPTER ======"
        )


        if isinstance(spatial, dict):

            for level, data in spatial.items():

                print(
                    "LEVEL:",
                    level
                )

                print(data)



        # ======================================
        # OUTPUT GEOMETRY CONTRACT
        # ======================================

        geometry = {


            "rooms": [],

            "floors": [],

            "levels": [],

            "walls": [],

            "floor_walls": [],

            "doors": [],

            "windows": [],

            "parcel": [],

            "spaces": [],

            "parking": [],

            "landscape": [],

            "access": []

        }



        print(
            "\n====== ADAPTER SPATIAL DEBUG ======"
        )


        print(
            "SPATIAL TYPE:",
            type(spatial)
        )


        print(
            "SPATIAL KEYS:",
            spatial.keys()
            if isinstance(spatial, dict)
            else None
        )



        # ======================================
        # NORMALIZE SPATIAL INPUT
        # ======================================

        if (

            isinstance(spatial, dict)

            and

            "floors" not in spatial

        ):

            spatial = {

                "floors": spatial

            }



        floors = spatial.get(
            "floors",
            {}
        )


        print(
            "FLOOR COUNT:",
            len(floors)
        )



        # ======================================
        # GLOBAL CACHE
        # ======================================

        floor_polygons = defaultdict(list)


        wall_cache = defaultdict(set)


        door_cache = set()


        window_cache = set()



        # ======================================
        # GLOBAL ROOM EXTRACTION
        # SINGLE SOURCE OF TRUTH
        # ======================================

        print(
            "\n====== BUILD GLOBAL ROOMS ======"
        )



        for level_name, level_data in floors.items():


            if not isinstance(
                level_data,
                dict
            ):

                continue



            spaces = level_data.get(
                "spaces",
                []
            )

            # ======================================
            # SPATIAL NODES -> SPACE CONTRACT
            # ======================================

            if not spaces:

                nodes = level_data.get(
                    "nodes",
                    {}
                )

                if isinstance(
                    nodes,
                    dict
                ):

                    spaces = []

                    for node_id, node_data in nodes.items():

                        if not isinstance(
                            node_data,
                            dict
                        ):

                            continue

                        semantic = node_data.get(
                            "semantic",
                            {}
                        )

                        if not isinstance(
                            semantic,
                            dict
                        ):

                            semantic = {}

                        node_type = node_data.get(
                            "type"
                        )

                        if node_type:

                            semantic = {
                                **semantic,
                                "type":
                                    semantic.get(
                                        "type",
                                        node_type
                                    )
                            }

                        spaces.append(
                            {
                                "name":
                                    node_data.get(
                                        "name",
                                        node_id
                                    ),

                                "x":
                                    node_data.get(
                                        "x",
                                        0
                                    ),

                                "y":
                                    node_data.get(
                                        "y",
                                        0
                                    ),

                                "width":
                                    node_data.get(
                                        "width",
                                        node_data.get(
                                            "w",
                                            4
                                        )
                                    ),

                                "height":
                                    node_data.get(
                                        "height",
                                        node_data.get(
                                            "h",
                                            4
                                        )
                                    ),

                                "semantic":
                                    semantic
                            }
                        )

                    print(
                        "NODE CONTRACT NORMALIZED:",
                        level_name,
                        "NODE COUNT:",
                        len(
                            nodes
                        ),
                        "SPACE COUNT:",
                        len(
                            spaces
                        )
                    )


            print(
                "LEVEL:",
                level_name,
                "SPACE COUNT:",
                len(spaces)
            )



            for space in spaces:


                if not isinstance(
                    space,
                    dict
                ):

                    continue



                room_id = space.get(
                    "name"
                )



                if not room_id:

                    continue



                semantic = space.get(
                    "semantic",
                    {}
                )



                geometry_data = {


                    "x":
                        space.get(
                            "x",
                            0
                        ),


                    "y":
                        space.get(
                            "y",
                            0
                        ),


                    "width":
                        space.get(
                            "width",
                            space.get(
                                "w",
                                4
                            )
                        ),


                    "height":
                        space.get(
                            "height",
                            space.get(
                                "h",
                                4
                            )
                        )

                }



                room = {


                    "id":
                        room_id,


                    "type":
                        "space",


                    "level":
                        level_name,


                    "semantic":
                        semantic,


                    "geometry":
                        geometry_data

                }



                duplicate = any(

                    r["id"] == room_id

                    and

                    r["level"] == level_name

                    for r in geometry["rooms"]

                )



                if duplicate:

                    print(
                        "ROOM DUPLICATE SKIP:",
                        room_id,
                        level_name
                    )

                    continue



                geometry["rooms"].append(
                    room
                )


                print(
                    "ROOM CREATED:",
                    room
                )



        print(
            "\nGLOBAL ROOM COUNT:",
            len(
                geometry["rooms"]
            )
        )


        print(
            "GLOBAL ROOM IDS:",
            [
                r["id"]
                for r in geometry["rooms"]
            ]
        )


        print(
            "GLOBAL ROOM LEVELS:",
            [
                r["level"]
                for r in geometry["rooms"]
            ]
        )
        # ======================================
        # FLOOR STRUCTURE DEBUG
        # ======================================

        print(
            "\n====== SPATIAL FLOOR STRUCTURE DEBUG ======"
        )


        for level_name, level_data in floors.items():


            print(
                "\nLEVEL:",
                level_name
            )


            print(
                "TYPE:",
                type(level_data)
            )


            if isinstance(
                level_data,
                dict
            ):

                print(
                    "KEYS:",
                    level_data.keys()
                )


        print(
            "=========================================="
        )



        print(
            "\n====== BEFORE FLOOR LOOP ======"
        )


        for room in geometry["rooms"]:

            print(
                room["id"],
                room["level"],
                room["geometry"]
            )


        print(
            "=============================="
        )



        # ==================================================
        # FLOOR PROCESSING LOOP
        # ==================================================

        for floor_name, floor_data in floors.items():


            print(
                "\nPROCESS FLOOR:",
                floor_name
            )


            # ======================================
            # FLOOR LEVEL REGISTER
            # ======================================

            if not any(
                l["name"] == floor_name
                for l in geometry["levels"]
            ):

                geometry["levels"].append(
                    {
                        "name": floor_name
                    }
                )



            # ======================================
            # LOCAL FLOOR CONTEXT
            # ======================================


            floor_rooms = [

                r for r in geometry["rooms"]

                if r.get("level") == floor_name

            ]


            floor_walls = []



            print(
                "\n====== FLOOR ROOM SOURCE ======"
            )


            print(
                "CURRENT FLOOR:",
                floor_name
            )


            print(
                "ROOMS:",
                [
                    r["id"]
                    for r in floor_rooms
                ]
            )


            print(
                "==============================="
            )



            # ======================================
            # SKIP EMPTY FLOOR
            # ======================================

            if not floor_rooms:

                print(
                    "NO ROOMS ON FLOOR:",
                    floor_name
                )

                continue



            # ======================================
            # WALL GENERATION
            # ROOM GEOMETRY SOURCE
            # ======================================


            for room in floor_rooms:


                room_id = room["id"]


                semantic = room.get(
                    "semantic",
                    {}
                )


                geo = room.get(
                    "geometry",
                    {}
                )



                # ----------------------------------
                # EXTERNAL SPACE PROTECTION
                # ----------------------------------

                zone = semantic.get(
                    "zone"
                )


                if zone == "external":


                    print(
                        "SKIP EXTERNAL WALL:",
                        room_id
                    )


                    continue



                x = geo.get(
                    "x"
                )


                y = geo.get(
                    "y"
                )


                w = geo.get(
                    "width"
                )


                h = geo.get(
                    "height"
                )



                if None in [
                    x,
                    y,
                    w,
                    h
                ]:


                    print(
                        "INVALID ROOM GEOMETRY:",
                        room_id,
                        geo
                    )


                    continue



                print(
                    "\nROOM WALL SOURCE:",
                    room_id,
                    x,
                    y,
                    w,
                    h
                )



                # polygon cache

                floor_polygons[floor_name].append(

                    [

                        [x, y],

                        [x + w, y],

                        [x + w, y + h],

                        [x, y + h]

                    ]

                )



                edges = [

                    (
                        (x, y),
                        (x + w, y)
                    ),

                    (
                        (x + w, y),
                        (x + w, y + h)
                    ),

                    (
                        (x + w, y + h),
                        (x, y + h)
                    ),

                    (
                        (x, y + h),
                        (x, y)
                    )

                ]



                for p1, p2 in edges:



                    key = (

                        floor_name,

                        tuple(

                            sorted(

                                [

                                    tuple(p1),

                                    tuple(p2)

                                ]

                            )

                        )

                    )



                    if key in wall_cache[floor_name]:

                        continue



                    wall_cache[floor_name].add(
                        key
                    )



                    wall = {


                        "start":
                            list(p1),


                        "end":
                            list(p2),


                        "height":
                            self.FLOOR_HEIGHT,


                        "level":
                            floor_name

                    }



                    floor_walls.append(
                        wall
                    )


                    print(
                        "WALL CREATED:",
                        wall
                    )



            print(
                "\n====== FLOOR WALL RESULT ======"
            )


            print(
                "FLOOR:",
                floor_name
            )


            print(
                "LOCAL WALL COUNT:",
                len(floor_walls)
            )


            print(
                "==============================="
            )
            # ======================================
            # FLOOR GEOMETRY
            # ======================================

            if floor_polygons[floor_name]:


                xs = []

                ys = []


                for polygon in floor_polygons[floor_name]:

                    for point in polygon:

                        xs.append(
                            point[0]
                        )

                        ys.append(
                            point[1]
                        )



                geometry["floors"].append(

                    {

                        "level":
                            floor_name,


                        "points":

                            [

                                [
                                    min(xs),
                                    min(ys)
                                ],

                                [
                                    max(xs),
                                    min(ys)
                                ],

                                [
                                    max(xs),
                                    max(ys)
                                ],

                                [
                                    min(xs),
                                    max(ys)
                                ]

                            ],


                        "height":
                            0

                    }

                )



            print(
                "FLOOR GENERATED:",
                floor_name
            )


            print(
                "FLOOR COUNT:",
                len(
                    geometry["floors"]
                )
            )



            # ======================================
            # DOOR GENERATION
            # INTERIOR ROOM ADJACENCY
            # ======================================


            print(
                "\n====== DOOR DETECTION ======"
            )


            door_candidates = []



            for index_a, room_a in enumerate(floor_rooms):


                semantic_a = room_a.get(
                    "semantic",
                    {}
                )


                if semantic_a.get(
                    "zone"
                ) == "external":

                    continue



                geo_a = room_a.get(
                    "geometry",
                    {}
                )


                ax1 = geo_a.get(
                    "x"
                )

                ay1 = geo_a.get(
                    "y"
                )

                ax2 = ax1 + geo_a.get(
                    "width",
                    0
                )

                ay2 = ay1 + geo_a.get(
                    "height",
                    0
                )



                for room_b in floor_rooms[index_a + 1:]:



                    semantic_b = room_b.get(
                        "semantic",
                        {}
                    )


                    if semantic_b.get(
                        "zone"
                    ) == "external":

                        continue



                    geo_b = room_b.get(
                        "geometry",
                        {}
                    )



                    bx1 = geo_b.get(
                        "x"
                    )

                    by1 = geo_b.get(
                        "y"
                    )

                    bx2 = bx1 + geo_b.get(
                        "width",
                        0
                    )

                    by2 = by1 + geo_b.get(
                        "height",
                        0
                    )



                    # --------------------------
                    # Horizontal adjacency
                    # --------------------------

                    if ax2 == bx1 or bx2 == ax1:


                        overlap = min(
                            ay2,
                            by2
                        ) - max(
                            ay1,
                            by1
                        )



                        if overlap > 0:


                            door_candidates.append(

                                {

                                    "from":
                                        room_a["id"],


                                    "to":
                                        room_b["id"],


                                    "type":
                                        "horizontal",


                                    "length":
                                        overlap

                                }

                            )



                    # --------------------------
                    # Vertical adjacency
                    # --------------------------

                    if ay2 == by1 or by2 == ay1:


                        overlap = min(
                            ax2,
                            bx2
                        ) - max(
                            ax1,
                            bx1
                        )



                        if overlap > 0:


                            door_candidates.append(

                                {

                                    "from":
                                        room_a["id"],


                                    "to":
                                        room_b["id"],


                                    "type":
                                        "vertical",


                                    "length":
                                        overlap

                                }

                            )



            print(
                "DOOR CANDIDATES:",
                door_candidates
            )



            for door in door_candidates:


                key = tuple(

                    sorted(

                        [

                            door["from"],

                            door["to"]

                        ]

                    )

                )



                if key in door_cache:

                    continue



                door_cache.add(
                    key
                )



                geometry["doors"].append(

                    {


                        "id":

                            (
                                f"DOOR_"
                                f"{door['from']}_"
                                f"{door['to']}"
                            ),


                        "from":

                            door["from"],


                        "to":

                            door["to"],


                        "level":

                            floor_name,


                        "type":

                            door["type"],


                        "width":

                            min(
                                door["length"],
                                self.DEFAULT_DOOR_WIDTH
                            )

                    }

                )



            print(
                "DOORS CREATED:",
                len(
                    geometry["doors"]
                )
            )
            # ======================================
            # WINDOW GENERATION
            # EXTERIOR WALL BASED
            # ======================================


            print(
                "\n====== WINDOW GENERATION ======"
            )


            for room in floor_rooms:


                room_id = room["id"]


                semantic = room.get(
                    "semantic",
                    {}
                )


                # external spaces do not get windows

                if semantic.get(
                    "zone"
                ) == "external":

                    print(
                        "SKIP EXTERNAL WINDOW:",
                        room_id
                    )

                    continue



                geo = room.get(
                    "geometry",
                    {}
                )



                x = geo.get(
                    "x"
                )

                y = geo.get(
                    "y"
                )

                w = geo.get(
                    "width"
                )

                h = geo.get(
                    "height"
                )



                if None in [
                    x,
                    y,
                    w,
                    h
                ]:


                    print(
                        "INVALID WINDOW ROOM:",
                        room_id
                    )


                    continue



                key = (

                    room_id,

                    floor_name

                )



                if key in window_cache:

                    continue



                window_cache.add(
                    key
                )



                geometry["windows"].append(

                    {


                        "id":

                            f"WIN_{room_id}",



                        "x":

                            x + (
                                w / 2
                            ),



                        "y":

                            y + h,



                        "width":

                            self.DEFAULT_WINDOW_WIDTH,



                        "height":

                            self.DEFAULT_WINDOW_HEIGHT,



                        "level":

                            floor_name

                    }

                )



            print(
                "WINDOW COUNT:",
                len(
                    geometry["windows"]
                )
            )



            # ======================================
            # MERGE LOCAL WALLS
            # ======================================


            print(
                "\n====== FLOOR WALL MERGE ======"
            )


            print(
                "CURRENT FLOOR:",
                floor_name
            )


            print(
                "LOCAL WALLS:",
                len(floor_walls)
            )



            geometry["walls"].extend(

                floor_walls

            )


            geometry["floor_walls"].extend(

                floor_walls

            )



            print(
                "GLOBAL WALL COUNT:",
                len(
                    geometry["walls"]
                )
            )


            print(
                "=============================="
            )



            # ======================================
            # FLOOR RESULT
            # ======================================


            print(
                "\n====== FLOOR RESULT CHECK ======"
            )


            print(
                "LEVEL:",
                floor_name
            )


            print(
                "ROOMS:",
                len(floor_rooms)
            )


            print(
                "WALLS:",
                len(floor_walls)
            )


            print(
                "DOORS TOTAL:",
                len(
                    geometry["doors"]
                )
            )


            print(
                "WINDOWS TOTAL:",
                len(
                    geometry["windows"]
                )
            )


            print(
                "================================"
            )



        # ======================================
        # GLOBAL GEOMETRY VALIDATION
        # ======================================


        print(
            "\n====== GLOBAL GEOMETRY VALIDATION ======"
        )


        print(
            "ROOM COUNT:",
            len(
                geometry["rooms"]
            )
        )


        print(
            "LEVEL COUNT:",
            len(
                geometry["levels"]
            )
        )


        print(
            "FLOOR COUNT:",
            len(
                geometry["floors"]
            )
        )


        print(
            "WALL COUNT:",
            len(
                geometry["walls"]
            )
        )


        print(
            "DOOR COUNT:",
            len(
                geometry["doors"]
            )
        )


        print(
            "WINDOW COUNT:",
            len(
                geometry["windows"]
            )
        )


        print(
            "========================================="
        )
        # ======================================
        # ROOM GEOMETRY CHECK
        # ======================================


        print(
            "\n====== ROOM GEOMETRY CHECK ======"
        )


        for room in geometry["rooms"]:


            print(

                room["id"],

                room["level"],

                room["geometry"]

            )


        print(
            "================================="
        )



        # ======================================
        # WALL GEOMETRY CHECK
        # ======================================


        print(
            "\n====== WALL GEOMETRY CHECK ======"
        )


        for wall in geometry["walls"][:10]:


            print(

                wall["start"],

                wall["end"],

                wall["level"]

            )


        print(
            "================================="
        )



        # ======================================
        # FINAL ADAPTER OUTPUT DEBUG
        # ======================================


        print(
            "\n====== FINAL ADAPTER OUTPUT ======"
        )


        print(
            "ADAPTER:",
            f"DesignGeometryAdapter_v{self.VERSION}"
        )


        print(
            "ROOMS:",
            len(
                geometry["rooms"]
            )
        )


        print(
            "WALLS:",
            len(
                geometry["walls"]
            )
        )


        print(
            "FLOORS:",
            len(
                geometry["floors"]
            )
        )


        print(
            "DOORS:",
            len(
                geometry["doors"]
            )
        )


        print(
            "WINDOWS:",
            len(
                geometry["windows"]
            )
        )


        print(
            "================================="
        )



        # ======================================
        # SAMPLE OUTPUT CHECK
        # ======================================


        if geometry["rooms"]:


            print(
                "\nFIRST ROOM:"
            )


            print(
                geometry["rooms"][0]
            )



        if geometry["walls"]:


            print(
                "\nFIRST WALL:"
            )


            print(
                geometry["walls"][0]
            )



        if geometry["doors"]:


            print(
                "\nFIRST DOOR:"
            )


            print(
                geometry["doors"][0]
            )



        if geometry["windows"]:


            print(
                "\nFIRST WINDOW:"
            )


            print(
                geometry["windows"][0]
            )



        # ======================================
        # ROOM WALL CONSISTENCY CHECK
        # ======================================


        print(
            "\n====== ROOM WALL CONSISTENCY ======"
        )

        # DEBUG ONLY

        all_room_levels = set(

            r["level"]

            for r in geometry["rooms"]

        )


        wall_levels = set(

            w["level"]

            for w in geometry["walls"]

        )


        print(
            "ALL ROOM LEVELS:",
            all_room_levels
        )



        # ======================================
        # EXCLUDE NON BUILDING LEVELS
        # ======================================

        architectural_room_levels = set(

            r["level"]

            for r in geometry["rooms"]

            if r.get("semantic", {}).get("zone")
            !=
            "external"

        )


        wall_levels = set(

            w["level"]

            for w in geometry["walls"]

        )

        print(
            "ARCHITECTURAL ROOM LEVELS:",
            architectural_room_levels
        )


        print(
            "WALL LEVELS:",
            wall_levels
        )


        missing_levels = (

            architectural_room_levels

            -

            wall_levels

        )



        if missing_levels:


            print(

                "⚠️ LEVELS WITHOUT WALLS:",

                missing_levels

            )


        else:


            print(

                "✅ ALL ARCHITECTURAL ROOM LEVELS HAVE WALLS"

            )



        print(
            "=================================="
        )



        # ======================================
        # RETURN CONTRACT
        # ======================================


        return {


            "adapter":

                f"DesignGeometryAdapter_v{self.VERSION}",


            "geometry":

                geometry

        }
