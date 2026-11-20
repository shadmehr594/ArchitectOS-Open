"""
ArchitectOS Semantic BIM Intelligence v45.0

BIM Geometry
      |
      v
Semantic Understanding

Room
 |
 +-- living_room
 +-- kitchen
 +-- bedroom
 +-- circulation
 +-- terrace
 +-- parking


Element
 |
 +-- structural
 +-- architectural
 +-- opening


Output:
semantic BIM intelligence model

"""


class SemanticBIMEngine:


    VERSION = "45.0"



    def __init__(self):

        print(
            f"🧠 Semantic BIM Engine v{self.VERSION} ACTIVE"
        )



    # ======================================================
    # BUILD
    # ======================================================

    def build(
        self,
        rooms=None,
        objects=None,
        elements=None
    ):


        print(
            "▶️ BUILD SEMANTIC BIM v45"
        )


        rooms = rooms or {}
        objects = objects or {}
        elements = elements or {}



        semantic = {


            "engine":

                f"semantic_bim_v{self.VERSION}",


            "rooms":[],

            "objects":[],

            "elements":[],

            "relations":[]

        }



        # ==============================
        # ROOMS
        # ==============================

        room_list = self._extract_rooms(
            rooms
        )



        for room in room_list:


            item = dict(room)


            item["semantic_type"] = (
                self._classify_room(
                    room
                )
            )


            item["intelligence_tags"] = (
                self._room_tags(
                    item["semantic_type"]
                )
            )


            semantic["rooms"].append(
                item
            )



        # ==============================
        # OBJECTS
        # ==============================

        object_list = self._extract_objects(
            objects
        )


        for obj in object_list:


            item = dict(obj)


            item["semantic_type"] = (
                self._classify_object(
                    obj
                )
            )


            semantic["objects"].append(
                item
            )



        # ==============================
        # ELEMENTS
        # ==============================


        element_list = self._extract_elements(
            elements
        )


        for element in element_list:


            item = dict(element)


            item["semantic_type"] = (
                self._classify_element(
                    element
                )
            )


            item["functional_role"] = (
                self._functional_role(
                    element
                )
            )


            item["system_role"] = (
                self._system_role(
                    element
                )
            )


            semantic["elements"].append(
                item
            )



        # ==============================
        # RELATIONS
        # ==============================


        semantic["relations"] = (
            self._build_relations(
                semantic
            )
        )



        print(
            f"🧠 SEMANTIC ROOMS: {len(semantic['rooms'])}"
        )


        print(
            f"🧠 SEMANTIC OBJECTS: {len(semantic['objects'])}"
        )


        print(
            f"🧠 SEMANTIC ELEMENTS: {len(semantic['elements'])}"
        )


        print(
            f"🔗 SEMANTIC RELATIONS: {len(semantic['relations'])}"
        )



        return semantic



    # ======================================================
    # ROOM EXTRACTION
    # ======================================================

    def _extract_rooms(
        self,
        rooms
    ):


        result=[]


        if isinstance(
            rooms,
            list
        ):

            return rooms



        if not isinstance(
            rooms,
            dict
        ):

            return result



        # format:
        # {"rooms":[...]}

        if "rooms" in rooms:


            return rooms.get(
                "rooms",
                []
            )



        # format:
        # F1,F2,F3

        for level, data in rooms.items():


            if not isinstance(
                data,
                dict
            ):
                continue



            for room in data.get(
                "rooms",
                []
            ):


                item = dict(room)


                item["level"] = level



                # ======================================
                # GEOMETRY NORMALIZATION v46
                # Support DesignGeometryAdapter v2.1
                # ======================================

                if "geometry" in item:

                    geo = item.get(
                        "geometry",
                        {}
                    )

                    item["x"] = geo.get(
                        "x",
                        0
                    )

                    item["y"] = geo.get(
                        "y",
                        0
                    )

                    item["width"] = geo.get(
                        "width",
                        0
                    )

                    item["height"] = geo.get(
                        "height",
                        0
                    )


                result.append(
                    item
                )



        return result



    # ======================================================
    # ELEMENT EXTRACTION
    # ======================================================

    def _extract_elements(
        self,
        elements
    ):


        if isinstance(
            elements,
            list
        ):

            return elements



        if isinstance(
            elements,
            dict
        ):

            return elements.get(
                "elements",
                []
            )


        return []



    # ======================================================
    # OBJECT EXTRACTION
    # ======================================================

    def _extract_objects(
        self,
        objects
    ):


        if isinstance(
            objects,
            list
        ):

            return objects


        if isinstance(
            objects,
            dict
        ):

            return objects.get(
                "objects",
                []
            )


        return []



    # ======================================================
    # ROOM CLASSIFICATION
    # ======================================================

    def _classify_room(
        self,
        room
    ):


        text = (

            str(
                room.get("id","")
            )

            +

            str(
                room.get("name","")
            )

        ).lower()



        rules={

            "living":
                "living_room",

            "kitchen":
                "kitchen",

            "bedroom":
                "bedroom",

            "bath":
                "bathroom",

            "circulation":
                "circulation",

            "stair":
                "vertical_circulation",

            "terrace":
                "terrace",

            "parking":
                "parking"

        }



        for key,value in rules.items():


            if key in text:

                return value



        return "generic_room"



    # ======================================================
    # ELEMENT CLASSIFICATION
    # ======================================================

    def _classify_element(
        self,
        element
    ):


        return {

            "IfcWall":
                "wall",

            "IfcColumn":
                "structural_column",

            "IfcBeam":
                "structural_beam",

            "IfcSlab":
                "floor_slab",

            "IfcDoor":
                "door",

            "IfcWindow":
                "window"

        }.get(

            element.get(
                "ifc_type"
            ),

            "generic_element"

        )



    # ======================================================
    # FUNCTION ROLE
    # ======================================================

    def _functional_role(
        self,
        element
    ):


        return {


            "IfcWall":
                "space_boundary",

            "IfcColumn":
                "vertical_load_support",

            "IfcBeam":
                "horizontal_load_transfer",

            "IfcSlab":
                "horizontal_surface",

            "IfcDoor":
                "access",

            "IfcWindow":
                "environment_interface"


        }.get(

            element.get(
                "ifc_type"
            ),

            "unknown"

        )



    # ======================================================
    # SYSTEM ROLE
    # ======================================================

    def _system_role(
        self,
        element
    ):


        return element.get(
            "system",
            "unknown"
        )



    # ======================================================
    # ROOM TAGS
    # ======================================================

    def _room_tags(
        self,
        semantic_type
    ):


        return {


            "living_room":
                [
                    "social",
                    "public"
                ],


            "kitchen":
                [
                    "service",
                    "wet_zone"
                ],


            "bedroom":
                [
                    "private",
                    "night_zone"
                ],


            "circulation":
                [
                    "movement"
                ],


            "parking":
                [
                    "vehicle"
                ]


        }.get(

            semantic_type,
            []

        )



    # ======================================================
    # RELATIONS v46
    # ROOM <-> ELEMENT INTELLIGENCE
    # ======================================================

    def _build_relations(
        self,
        semantic
    ):


        relations = []


        for room in semantic.get(
            "rooms",
            []
        ):


            room_id = room.get(
                "id"
            )


            room_level = room.get(
                "level"
            )


            # ======================================
            # ROOM GEOMETRY NORMALIZATION v46
            # ======================================

            room_geometry = room.get(
                "geometry",
                {}
            )


            room_x = room.get(
                "x",
                room_geometry.get(
                    "x",
                    0
                )
            )


            room_y = room.get(
                "y",
                room_geometry.get(
                    "y",
                    0
                )
            )


            room_w = room.get(
                "width",
                room_geometry.get(
                    "width",
                    room.get(
                        "w",
                        0
                    )
                )
            )


            # ======================================
            # PLAN DEPTH RESOLUTION
            #
            # Architectural contract distinguishes:
            #
            # width  = plan X dimension
            # depth  = plan Y dimension
            # height = vertical Z dimension
            #
            # Semantic spatial ownership must use
            # width/depth, never vertical height.
            # ======================================

            room_depth = room.get(
                "depth"
            )


            if room_depth is None:

                room_depth = room_geometry.get(
                    "depth"
                )


            if room_depth is None:

                room_depth = room.get(
                    "h"
                )


            if room_depth is None:

                # Legacy semantic-room fallback only.
                room_depth = room_geometry.get(
                    "height",
                    room.get(
                        "height",
                        0
                    )
                )

            # Architecture-first spaces may intentionally remain unresolved
            # (for example a site pool without authoritative dimensions).
            # Such a space is evidence, not geometry: do not invent a zero-size
            # semantic room and do not attempt spatial ownership arithmetic.
            if room_w is None or room_depth is None:
                continue


            relation = {

                "type":
                    "room_intelligence",

                "room":
                    room_id,

                "semantic":
                    room.get(
                        "semantic_type"
                    ),

                "elements":[]

            }



            xmin = room_x
            xmax = room_x + room_w

            ymin = room_y
            ymax = room_y + room_depth


            for element in semantic.get(
                "elements",
                []
            ):


                print(
                    "\nRELATION CHECK:",
                    element.get("id"),
                    element.get("ifc_type")
                )


                data = element.get(
                    "data",
                    {}
                )


                print(
                    "ELEMENT DATA CHECK:",
                    element.get("id"),
                    data
                )


                # ======================================
                # ARCHITECTURAL LEVEL IDENTITY
                #
                # Prefer the BIM element's architectural
                # level identity.
                #
                # data.level may later be normalized by
                # IFC/export compatibility layers.
                # ======================================

                element_level = element.get(
                    "level"
                )


                if element_level is None:

                    element_level = data.get(
                        "level"
                    )


                if (
                    element_level
                    !=
                    room_level
                ):

                    continue



                ifc_type = element.get(
                    "ifc_type"
                )



                # -----------------------
                # WALL
                # -----------------------

                if ifc_type == "IfcWall":


                    start = data.get(
                        "start",
                        []
                    )


                    end = data.get(
                        "end",
                        []
                    )


                    if len(start)==2 and len(end)==2:


                        if (

                            xmin <= start[0] <= xmax

                            or

                            xmin <= end[0] <= xmax

                        ) and (

                            ymin <= start[1] <= ymax

                            or

                            ymin <= end[1] <= ymax

                        ):


                            relation["elements"].append(

                                {

                                    "id":
                                        element.get(
                                            "id"
                                        ),

                                    "ifc_type":
                                        ifc_type,

                                    "relation":
                                        "boundary"

                                }

                            )


                            print(
                                "\nCOLUMN OWNED:",
                                element.get("id"),
                                "ROOM:",
                                room_id
                            )


                elif ifc_type == "IfcColumn":

                    data = element.get(
                        "data",
                        {}
                    )


                    x = data.get("x")
                    y = data.get("y")


                    print(
                        "COLUMN CHECK:",
                        element.get("id"),
                        "LEVEL:",
                        data.get("level"),
                        "POS:",
                        x,
                        y,
                        "ROOM:",
                        room_id,
                        "BOX:",
                        xmin,
                        xmax,
                        ymin,
                        ymax
                    )


                    if x is None or y is None:
                        continue


                    if (
                        xmin <= x <= xmax
                        and
                        ymin <= y <= ymax
                    ):

                        relation["elements"].append(

                            {
                                "id":
                                    element.get("id"),

                                "ifc_type":
                                    "IfcColumn",

                                "relation":
                                    "structural_support"

                            }

                        )

                # -----------------------
                # DOOR / WINDOW
                # -----------------------

                elif ifc_type in [

                    "IfcDoor",
                    "IfcWindow"

                ]:


                    x = data.get(
                        "x"
                    )


                    y = data.get(
                        "y"
                    )


                    if x is None or y is None:
                        continue



                    if (

                        xmin <= x <= xmax

                        and

                        ymin <= y <= ymax

                    ):


                        relation["elements"].append(

                            {

                                "id":
                                    element.get(
                                        "id"
                                    ),

                                "ifc_type":
                                    ifc_type,

                                "relation":

                                    (
                                        "access_point"

                                        if ifc_type=="IfcDoor"

                                        else

                                        "environment_interface"
                                    )

                            }

                        )



            relations.append(
                relation
            )

        # ======================================================
        # ELEMENT OWNERSHIP MAPPING v47
        # ======================================================

        print("\n====== RELATION COLUMN DEBUG ======")

        for rel in relations:

            for item in rel.get("elements", []):

                if item.get("ifc_type") == "IfcColumn":

                    print(
                        "COLUMN RELATION:",
                        item.get("id"),
                        "ROOM:",
                        rel.get("room"),
                        "TYPE:",
                        item.get("relation")
                    )

        for relation in relations:

            room_id = relation.get(
                "room"
            )


            for item in relation.get(
                "elements",
                []
            ):


                element_id = item.get(
                    "id"
                )


                for element in semantic.get(
                    "elements",
                    []
                ):


                    if element.get(
                        "id"
                    ) == element_id:


                        if (
                            "belongs_to_rooms"
                            not in element
                        ):

                            element["belongs_to_rooms"] = []


                        if room_id not in [
                            r["room"]
                            for r in element["belongs_to_rooms"]
                        ]:

                            element["belongs_to_rooms"].append(

                                {
                                    "room": room_id,

                                    "relation":
                                        item.get(
                                            "relation"
                                        ),

                                    "semantic":
                                        relation.get(
                                            "semantic"
                                        )

                                }

                        )


        print("\n====== COLUMN RELATION CHECK ======")

        for rel in relations:

            for item in rel.get("elements", []):

                if item.get("ifc_type") == "IfcColumn":

                    print(
                        item.get("id"),
                        "=>",
                        rel.get("room"),
                        item.get("relation")
                    )

        return relations
