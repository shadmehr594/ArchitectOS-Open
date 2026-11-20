import json


class IFCRevitExporter:


    VERSION = "1.1"



    def __init__(self):

        print(
            f"🏗️ IFC Revit Exporter v{self.VERSION} ACTIVE"
        )



    # =====================================
    # EXPORT BIM → IFC SEMANTIC MODEL
    # =====================================

    def export(
        self,
        geometry,
        structure
    ):

        print(
            "\n====== IFC REVIT EXPORT INPUT DEBUG ======"
        )

        print(
            "GEOMETRY KEYS:",
            geometry.keys()
        )

        print(
            "STRUCTURE KEYS:",
            structure.keys()
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
            "FLOORS:",
            len(
                geometry.get(
                    "floors",
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

        print(
            "COLUMNS:",
            len(
                structure.get(
                    "columns",
                    []
                )
            )
        )

        print(
            "BEAMS:",
            len(
                structure.get(
                    "beams",
                    []
                )
            )
        )


        ifc_model = {


            "project":

                "ArchitectOS BIM Export",



            "schema":

                "IFC4",



            "elements":

                []

        }



        element_id = 1




        # ======================
        # WALLS → IFC WALLS
        # ======================

        for wall in geometry.get(
            "walls",
            []
        ):


            ifc_model["elements"].append({

                "id":

                    f"wall_{element_id:03}",


                "ifc_type":

                    "IfcWall",


                "type":

                    "IfcWall",


                "data":

                    {

                        "start":

                            wall.get(
                                "start"
                            ),


                        "end":

                            wall.get(
                                "end"
                            ),


                        "height":

                            wall.get(
                                "height",
                                3
                            )

                    }

            })


            element_id += 1





        # ======================
        # FLOORS → IFC SLABS
        # ======================

        for floor in geometry.get(
            "floors",
            []
        ):


            ifc_model["elements"].append({

                "id":

                    f"slab_{element_id:03}",


                "ifc_type":

                    "IfcSlab",


                "type":

                    "IfcSlab",


                "data":

                    {

                        "floor":

                            floor.get(
                                "floor"
                            ),


                        "thickness":

                            floor.get(
                                "thickness",
                                0.25
                            )

                    }

            })


            element_id += 1





        # ======================
        # ROOMS → IFC SPACES
        # ======================

        for room in geometry.get(
            "rooms",
            []
        ):


            ifc_model["elements"].append({

                "id":

                    f"space_{element_id:03}",


                "ifc_type":

                    "IfcSpace",


                "type":

                    "IfcSpace",


                "data":

                    {

                        "name":

                            room.get(
                                "name"
                            ),


                        "location":

                            {

                                "x":

                                    room.get(
                                        "x",
                                        0
                                    ),


                                "y":

                                    room.get(
                                        "y",
                                        0
                                    ),


                                "z":

                                    room.get(
                                        "z",
                                        0
                                    )

                            },


                        "dimensions":

                            {

                                "width":

                                    room.get(
                                        "w",
                                        0
                                    ),


                                "depth":

                                    room.get(
                                        "h",
                                        0
                                    ),


                                "height":

                                    room.get(
                                        "height",
                                        3
                                    )

                            }

                    }

            })


            element_id += 1






        # ======================
        # STRUCTURE → COLUMNS
        # ======================

        for col in structure.get(
            "columns",
            []
        ):


            ifc_model["elements"].append({

                "id":

                    f"column_{element_id:03}",


                "ifc_type":

                    "IfcColumn",


                "type":

                    "IfcColumn",


                "data":

                    {

                        "location":

                            {

                                "x":

                                    col.get(
                                        "x",
                                        0
                                    ),


                                "y":

                                    col.get(
                                        "y",
                                        0
                                    ),


                                "z":

                                    col.get(
                                        "z",
                                        0
                                    )

                            },


                        "height":

                            col.get(
                                "height",
                                3
                            )

                    }

            })


            element_id += 1






        # ======================
        # STRUCTURE → BEAMS
        # ======================

        for beam in structure.get(
            "beams",
            []
        ):


            ifc_model["elements"].append({

                "id":

                    f"beam_{element_id:03}",


                "ifc_type":

                    "IfcBeam",


                "type":

                    "IfcBeam",


                "data":

                    {

                        "start":

                            beam.get(
                                "start"
                            ),


                        "end":

                            beam.get(
                                "end"
                            ),


                        "level":

                            beam.get(
                                "level"
                            )

                    }

            })


            element_id += 1






        # ======================
        # OPENINGS → DOORS
        # ======================

        for door in geometry.get(
            "doors",
            []
        ):


            ifc_model["elements"].append({

                "id":

                    f"door_{element_id:03}",


                "ifc_type":

                    "IfcDoor",


                "type":

                    "IfcDoor",


                "data":

                    door

            })


            element_id += 1





        # ======================
        # OPENINGS → WINDOWS
        # ======================

        for window in geometry.get(
            "windows",
            []
        ):


            ifc_model["elements"].append({

                "id":

                    f"window_{element_id:03}",


                "ifc_type":

                    "IfcWindow",


                "type":

                    "IfcWindow",


                "data":

                    window

            })


            element_id += 1





        # ======================
        # STATISTICS
        # ======================

        counts = {}


        for element in ifc_model["elements"]:

            t = element["ifc_type"]

            counts[t] = counts.get(
                t,
                0
            ) + 1



        ifc_model["statistics"] = counts



        return ifc_model






    # =====================================
    # SAVE JSON IFC REPRESENTATION
    # =====================================

    def save(
        self,
        ifc_model,
        filename="export.ifc.json"
    ):


        with open(
            filename,
            "w",
            encoding="utf-8"
        ) as f:


            json.dump(

                ifc_model,

                f,

                indent=2,

                ensure_ascii=False

            )



        print(
            "✅ IFC JSON SAVED:",
            filename
        )


        return filename