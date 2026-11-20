class BIMRevitFamilyIntelligenceEngine:


    """
    BIM Revit Family Intelligence Engine v55.0


    Responsibilities:

        Object To Family Mapping
        Door Family Generation
        Window Family Generation
        Furniture Family Generation
        MEP Family Generation
        Revit Ready Structure

    """



    def __init__(self):

        print(
            "🏠 BIM Revit Family Intelligence Engine v55.0 ACTIVE"
        )





    def build(
        self,
        graph
    ):


        print(
            "▶️ BUILD BIM REVIT FAMILY INTELLIGENCE v55"
        )



        result = {


            "engine":
                "bim_revit_family_v55.0",


            "families":
                [],


            "statistics":
                {}

        }





        self._extract_rooms(
            graph,
            result
        )


        self._extract_objects(
            graph,
            result
        )


        self._extract_furniture(
            graph,
            result
        )


        self._extract_mep(
            graph,
            result
        )





        result["statistics"] = {


            "families":
                len(
                    result["families"]
                )

        }





        print(
            f"🏠 REVIT FAMILIES GENERATED: {result['statistics']['families']}"
        )



        return result





    # =====================================
    # ROOM FAMILIES
    # =====================================


    def _extract_rooms(
        self,
        graph,
        result
    ):


        rooms = graph.get(
            "rooms",
            {}
        ).get(
            "rooms",
            []
        )


        for room in rooms:


            if isinstance(room, dict):

                result["families"].append(

                    {

                        "category":
                            "Rooms",

                        "family":
                            "Room_Family",

                        "type":
                            room.get(
                                "type",
                                "GenericRoom"
                            ),

                        "source":
                            room.get(
                                "id"
                            )

                    }

                )





    # =====================================
    # OBJECT FAMILIES
    # =====================================


    def _extract_objects(
        self,
        graph,
        result
    ):


        objects = graph.get(
            "objects",
            {}
        ).get(
            "objects",
            []
        )



        for obj in objects:


            if isinstance(obj, dict):


                result["families"].append(

                    {

                        "category":
                            "Objects",

                        "family":
                            self._family_name(
                                obj
                            ),

                        "source":
                            obj.get(
                                "id"
                            )

                    }

                )





    # =====================================
    # FURNITURE FAMILIES
    # =====================================


    def _extract_furniture(
        self,
        graph,
        result
    ):


        furniture = graph.get(
            "furniture",
            {}
        ).get(
            "placements",
            []
        )


        for item in furniture:


            if isinstance(item, dict):

                result["families"].append(

                    {

                        "category":
                            "Furniture",

                        "family":
                            item.get(
                                "category",
                                "Furniture_Generic"
                            ),

                        "source":
                            item.get(
                                "id"
                            )

                    }

                )





    # =====================================
    # MEP FAMILIES
    # =====================================


    def _extract_mep(
        self,
        graph,
        result
    ):


        mep = graph.get(
            "mep",
            {}
        )



        electrical = mep.get(
            "electrical",
            {}
        )


        for light in electrical.get(
            "lights",
            []
        ):


            result["families"].append(

                {

                    "category":
                        "MEP",

                    "family":
                        "Lighting_Family",

                    "source":
                        light.get(
                            "id"
                        )

                }

            )





        hvac = mep.get(
            "hvac",
            {}
        )



        for unit in hvac.get(
            "units",
            []
        ):


            result["families"].append(

                {

                    "category":
                        "MEP",

                    "family":
                        "HVAC_Family",

                    "source":
                        unit.get(
                            "id"
                        )

                }

            )





    # =====================================
    # FAMILY NAME GENERATOR
    # =====================================


    def _family_name(
        self,
        obj
    ):


        obj_type = str(

            obj.get(
                "type",
                "Generic"
            )

        )


        return (

            obj_type.capitalize()
            +
            "_Family"

        )