class GeometryAdapter:

    VERSION = "2.0"

    def level_to_elevation(self, level):
        if not level:
            return 0

        if level.startswith("F"):
            try:
                floor_number = int(level[1:])
                return (floor_number - 1) * 3.0
            except:
                return 0

        return 0

    """
    ArchitectOS Unified Geometry Adapter v2.0
    """

    ENTITY_MAP = {

        "columns": "IfcColumn",

        "beams": "IfcBeam",

        "slabs": "IfcSlab",

        "walls": "IfcWall",

        "doors": "IfcDoor",

        "windows": "IfcWindow",

        "openings": "IfcOpening",

        "stairs": "IfcStair",

        "ramps": "IfcRamp",

        "site_accesses": "IfcBuildingElementProxy",

        "elevators": "IfcTransportElement",

        "cores": "IfcBuildingElementProxy",

        "roofs": "IfcRoof",

        "railings": "IfcRailing",

    }


    def __init__(self):

        print(
            "📐 Unified Geometry Adapter v2.0 ACTIVE"
        )



    def build(
        self,
        structure,
        geometry=None
    ):

        elements = []

        counters = {}


        if not isinstance(structure, dict):

            structure = {}


        if not isinstance(geometry, dict):

            geometry = {}


        print(
            "\n========== GEOMETRY ADAPTER VERSION CHECK =========="
        )

        print(
            "FILE:",
            __file__
        )

        print(
            "VERSION:",
            self.VERSION
        )

        print(
            "===================================================="
        )



        print(
            "📐 GEOMETRY ADAPTER BUILD v2"
        )


        print(
            "STRUCTURE KEYS:",
            structure.keys()
        )


        print(
            "GEOMETRY KEYS:",
            geometry.keys()
        )


        print("\n====== ADAPTER SOURCE FULL CHECK ======")

        for key in [
            "walls",
            "slabs",
            "doors",
            "windows"
        ]:

            print(
                key.upper(),
                "STRUCTURE:",
                len(structure.get(key, []))
            )

            print(
                key.upper(),
                "GEOMETRY:",
                len(geometry.get(key, []))
            )


        print("======================================")



        for group_name, ifc_type in self.ENTITY_MAP.items():


            counters.setdefault(
                group_name,
                1
            )


            # =========================
            # SOURCE RESOLUTION
            # =========================

            if geometry.get("architectural_authority") and geometry.get(group_name):
                source = geometry.get(group_name, [])
            else:
                source = structure.get(group_name, [])
                if not source:
                    source = geometry.get(group_name, [])


                print(
                    "\n====== OPENING SOURCE DEBUG ======"
                )

                if group_name in [
                    "doors",
                    "windows"
                ]:

                    print(
                        "GROUP:",
                        group_name
                    )

                    print(
                        "COUNT:",
                        len(source)
                    )

                    if source:
                        print(
                        source[0]
                    )

                    print(
                        "=================================="
                    )


            if not isinstance(source, list):

                continue



            print(
                f"{group_name.upper()} SOURCE COUNT:",
                len(source)
            )



            for obj in source:


                if group_name == "walls":
                    print(
                        "\n====== WALL ADAPTER FINAL DIRECTION ======"
                    )

                    print(
                        {
                            "id": obj.get("id"),
                            "start": obj.get("start"),
                            "end": obj.get("end"),
                            "level": obj.get("level")
                        }
                    )

                    print(
                        "=========================================="
                    )


                print(
                    "\n====== ADAPTER GROUP DEBUG ======"
                )

                print(
                    {
                        "group_name": group_name,
                        "source_type": type(source),
                        "source_count": len(source)
                        if hasattr(source, "__len__")
                        else None
                    }
                )

                print(
                    "================================="
                )


                if group_name == "walls":

                    print(
                        "\n====== WALL SOURCE DIRECTION SUMMARY ======"
                    )

                    print(
                        {
                            "id": obj.get("id"),
                            "start": obj.get("start"),
                            "end": obj.get("end"),
                            "is_vertical":
                                (
                                    obj.get("start")[0] == obj.get("end")[0]
                                    if obj.get("start") and obj.get("end")
                                    else None
                                )
                        }
                    )

                print(
                    "============================================"
                )


                print(
                    "\n========== ADAPTER RAW OBJECT =========="
                )

                print(
                    obj
                )

                if group_name in [
                    "walls",
                    "slabs"
                ]:

                    print(
                        "\n====== ARCH SOURCE DEBUG ======"
                    )

                    print(
                        {
                            "type": group_name,
                            "id": obj.get("id"),
                            "level": obj.get("level"),
                            "z": obj.get("z"),
                            "start": obj.get("start"),
                            "end": obj.get("end"),
                            "x": obj.get("x"),
                            "y": obj.get("y"),
                            "width": obj.get("width"),
                            "depth": obj.get("depth")
                        }
                    )

                    print(
                        "=============================="
                    )


                idx = counters[group_name]


                level = None

                if isinstance(obj, dict):

                    level = (
                        obj.get("level")
                        or obj.get("floor")
                        or obj.get("source_level")
                    )

                    served_levels = obj.get("served_levels")

                    if (
                        not level
                        and isinstance(served_levels, list)
                        and served_levels
                    ):

                        level = served_levels[0]

                # Retained only for genuinely legacy elements with no level
                # evidence. Authoritative elements resolve above from their
                # own floor/source/served-level contract.
                level = level or "F1"



                element = {


                    "id":

                    f"{group_name[:-1]}_{obj.get('id') or obj.get('access_id') or obj.get('name') or idx}",



                    "type":

                    group_name[:-1],



                    "ifc_type":

                    ifc_type,



                    "system":

                    self._resolve_system(
                        group_name
                    ),



                    "data":

                    dict(obj)

                }

                # Keep level evidence at both contract layers. Exporters read
                # the element-level field, while semantic/BIM consumers read
                # data.level.
                element["level"] = level



                # =========================
                # LEVEL INJECTION
                # =========================

                if isinstance(
                    element["data"],
                    dict
                ):

                    element["data"]["level"] = level



                    if "id" in obj:

                        element["data"]["source_id"] = obj.get(
                            "source_id",
                            obj.get("id")
                        )



                # =========================
                # BIM CONTRACT NORMALIZATION
                # =========================

                if group_name == "beams":

                    element["start"] = obj.get(
                        "start"
                    )

                    element["end"] = obj.get(
                        "end"
                    )

                    element["z"] = obj.get(
                        "z"
                    )

                    element["level"] = obj.get(
                        "level"
                    )


                # =========================
                # WALL CONTRACT NORMALIZATION
                # =========================

                if group_name == "walls":

                    element["start"] = obj.get(
                        "start"
                    )

                    element["end"] = obj.get(
                        "end"
                    )

                    element["z"] = obj.get(
                        "z"
                    ) 

                    element["level"] = obj.get(
                        "level"
                    )


                if group_name == "beams":

                    print(
                        "\n====== BEAM ELEMENT FULL DEBUG ======"
                    )


                if group_name == "beams":

                    print(
                        "\n====== BEAM ELEMENT FULL DEBUG ======"
                    )

                    print(
                        element
                    )

                    print(
                        "====================================="
                    )


                elif group_name == "columns":


                    element["x"] = obj.get(
                        "x"
                    )

                    element["y"] = obj.get(
                        "y"
                    )

                    element["z"] = obj.get(
                        "z"
                    )

                    element["level"] = obj.get(
                        "level"
                    )


                elif group_name == "doors":

                    element["x"] = obj.get(
                        "x"
                    )

                    element["y"] = obj.get(
                        "y"
                    )

                    element["z"] = obj.get(
                        "z",
                        obj.get("level_bottom", obj.get("bottom", obj.get("elevation")))
                    )

                    if (
                        element["z"] is None
                        and not geometry.get("architectural_authority")
                    ):

                        element["z"] = self.level_to_elevation(level)

                    element["level"] = level


                elif group_name == "windows":

                    element["x"] = obj.get(
                        "x"
                    )

                    element["y"] = obj.get(
                        "y"
                    )

                    okb = obj.get(
                        "okb",
                        0.9
                    )

                    opening_base = obj.get(
                        "z",
                        obj.get("level_bottom", obj.get("bottom", obj.get("elevation")))
                    )
                    element["z"] = (
                        opening_base + okb
                        if isinstance(opening_base, (int, float))
                        else None
                    )

                    if (
                        element["z"] is None
                        and not geometry.get("architectural_authority")
                    ):

                        element["z"] = self.level_to_elevation(level) + okb

                    element["level"] = level


                if element.get("ifc_type") in [
                    "IfcWall",
                    "IfcSlab"
                ]:

                    print(
                        "\n====== ARCH BIM ELEMENT DEBUG ======"
                    )

                    print(
                        {
                            "id": element.get("id"),
                            "ifc_type": element.get("ifc_type"),
                            "level": element.get("data", {}).get("level"),
                            "data": element.get("data")
                        }
                    )

                    print(
                        "===================================="
                    )

                    print(
                        "\n====== WALL BEFORE APPEND FULL ======"
                    )

                    print(element)

                    print(
                        "======================================"
                    )



                print(
                    "\n========== BIM ELEMENT CREATED =========="
                )


                print(
                    {
                        "id":
                        element.get("id"),

                        "ifc_type":
                        element.get("ifc_type"),

                        "level":
                        element.get("data",{}).get("level"),

                        "x":
                        element.get("x"),

                        "y":
                        element.get("y"),

                        "z":
                        element.get("z"),

                        "start":
                        element.get("start"),

                        "end":
                        element.get("end"),

                        "data":
                        element.get("data")

                    }
                )


                if element.get("ifc_type") == "IfcBeam":

                    print(
                        "\n====== BIM ID GENERATION DEBUG ======"
                    )

                    print(
                        {
                            "bim_id": element.get("id"),
                            "source_id":
                                element.get("data", {}).get("id"),
                            "start":
                                element.get("data", {}).get("start"),
                            "end":
                                element.get("data", {}).get("end"),
                            "level":
                                element.get("data", {}).get("level")
                        }
                    )

                    print(
                        "======================================"
                    )


                print(
                    "\n====== BIM ELEMENT BEFORE APPEND ======"
                )

                print(
                    {
                        "id": element.get("id"),
                        "type": element.get("type"),
                        "ifc": element.get("ifc_type"),
                        "level": element.get("level"),
                        "z": element.get("z")
                    }
                )

                print(
                    "======================================"
                )


                if element.get("ifc_type") in [
                    "IfcDoor",
                    "IfcWindow"
                ]:

                    print(
                        "\n====== OPENING BIM ELEMENT DEBUG ======"
                    )

                    print(
                        element
                    )

                    print(
                        "========================================"
                    )


                elements.append(
                    element
                )

                print(
                    "WALL ELEMENT FULL:",
                    element
                )
   

                counters[group_name] += 1
                

                if element.get("ifc_type") == "IfcBeam":

                    beam_data = element.get(
                        "data",
                        {}
                    )

                    print(
                        "========== ADAPTER BEAM FINAL =========="
                    )

                    print(
                        {
                            "id": element.get("id"),
                            "level": beam_data.get("level"),
                            "z": beam_data.get("z"),
                            "start": beam_data.get("start"),
                            "end": beam_data.get("end")
                        }
                    )


        print(
            "\n📦 ADAPTER ELEMENT COUNT:",
            len(elements)
        )



        from collections import Counter


        print(
            "IFC TYPE COUNTS:",
            Counter(
                e.get("ifc_type")
                for e in elements
            )
        )

        print(
            "\n====== FINAL ARCHITECTURAL OUTPUT ======"
        )

        for e in elements:

            if e.get("ifc_type") in [
                "IfcWall",
                "IfcSlab",
                "IfcDoor",
                "IfcWindow"
            ]:

                print(
                    {
                        "id": e.get("id"),
                        "type": e.get("ifc_type"),
                        "level": e.get("data",{}).get("level")
                    }
                )


        print(
            "========================================"
        )



        print(
            "\n====== FINAL ADAPTER OUTPUT DEBUG ======"
        )


        for e in elements:


            if e.get("ifc_type") in [

                "IfcColumn",

                "IfcBeam"

            ]:

                print(

                    {

                        "id":
                        e.get("id"),

                        "type":
                        e.get("ifc_type"),

                        "level":
                        e.get("data",{}).get("level"),

                        "x":
                        e.get("x"),

                        "y":
                        e.get("y"),

                        "z":
                        e.get("z"),

                        "start":
                        e.get("start"),

                        "end":
                        e.get("end")

                    }

                )



        print(
            "========================================"
        )

        beam_ids = [
            e.get("id")
            for e in elements
            if e.get("ifc_type") == "IfcBeam"
        ]

        print(
            "\n====== ADAPTER RETURN BEAMS ======"
        )

        print(
            "COUNT:",
            len(beam_ids)
        )

        print(
            beam_ids
        )

        print(
            "=================================="
        )



        return elements





    def _resolve_system(
        self,
        group_name
    ):


        architectural = [

            "walls",

            "doors",

            "windows",

            "openings",

            "stairs",

            "roofs",

            "railings"

            ,"ramps"
            ,"site_accesses"

        ]



        structural = [

            "columns",

            "beams",

            "slabs"

        ]



        if group_name in structural:

            return "structural"



        if group_name in architectural:

            return "architectural"


        return "unknown"
