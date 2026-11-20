class BIMIFCIntelligenceEngine:


    """
    BIM IFC Intelligence Engine v54.1


    Responsibilities:

        IFC Project Structure
        IFC Site Mapping
        IFC Building Mapping
        IFC Storey Mapping
        Space Conversion
        Element Conversion
        BIM Metadata Export

    """



    VERSION = "54.1"



    def __init__(self):

        print(
            "🏗️ BIM IFC Intelligence Engine v54.1 ACTIVE"
        )



    # =====================================
    # BUILD
    # =====================================

    def build(
        self,
        graph
    ):


        print(
            "▶️ BUILD BIM IFC INTELLIGENCE v54.1"
        )



        graph = self._normalize_context(
            graph
        )



        result = {


            "engine":
                f"bim_ifc_intelligence_v{self.VERSION}",


            "schema":
                "IFC4",


            "project":
                {},


            "site":
                {},


            "building":
                {},


            "storeys":
                [],


            "spaces":
                [],


            "elements":
                [],


            "statistics":
                {}

        }



        result["project"] = {

            "id":
                "PROJECT_001",

            "name":
                "ArchitectOS BIM Project"

        }



        result["site"] = {

            "id":
                "SITE_001",

            "type":
                "building_site"

        }



        result["building"] = {

            "id":
                "BUILDING_001",

            "type":
                "IfcBuilding"

        }



        self._build_storeys(
            graph,
            result
        )


        self._build_spaces(
            graph,
            result
        )


        self._build_elements(
            graph,
            result
        )



        result["statistics"] = {


            "storeys":
                len(
                    result["storeys"]
                ),


            "spaces":
                len(
                    result["spaces"]
                ),


            "elements":
                len(
                    result["elements"]
                )

        }



        print(
            f"🏢 IFC STOREYS GENERATED: {result['statistics']['storeys']}"
        )


        print(
            f"🚪 IFC SPACES GENERATED: {result['statistics']['spaces']}"
        )


        print(
            f"🧱 IFC ELEMENTS GENERATED: {result['statistics']['elements']}"
        )



        return result



    # =====================================
    # CONTEXT NORMALIZER
    # =====================================

    def _normalize_context(
        self,
        graph
    ):


        if "bim_context" in graph:

            context = graph["bim_context"]


            return {


                "levels":
                    context.get(
                        "levels",
                        []
                    ),


                "spaces":
                    context.get(
                        "spaces",
                        []
                    ),


                "elements":
                    context.get(
                        "elements",
                        []
                    )

            }



        return graph



    # =====================================
    # STOREYS
    # =====================================

    def _build_storeys(
        self,
        graph,
        result
    ):


        levels = graph.get(
            "levels",
            []
        )


        for level in levels:


            if isinstance(
                level,
                dict
            ):

                name = level.get(
                    "name",
                    "Ground"
                )

            else:

                name = str(
                    level
                )



            result["storeys"].append(

                {

                    "id":
                        name.upper()
                        +
                        "_STOREY",


                    "name":
                        name,


                    "type":
                        "IfcBuildingStorey"

                }

            )



    # =====================================
    # SPACES
    # =====================================

    def _build_spaces(
        self,
        graph,
        result
    ):


        spaces = graph.get(
            "spaces",
            []
        )



        for space in spaces:


            if not isinstance(
                space,
                dict
            ):
                continue



            result["spaces"].append(

                {

                    "id":
                        space.get(
                            "id"
                        ),


                    "type":
                        "IfcSpace",


                    "status":
                        space.get(
                            "status",
                            "planned"
                        )

                }

            )



    # =====================================
    # ELEMENTS
    # =====================================

    def _build_elements(
        self,
        graph,
        result
    ):


        elements = graph.get(
            "elements",
            []
        )


        for item in elements:


            if not isinstance(
                item,
                dict
            ):
                continue



            result["elements"].append(

                {

                    "id":
                        item.get(
                            "id",
                            "ELEMENT"
                        ),


                    "ifc_type":
                        self._map_ifc_type(
                            item
                        ),


                    "name":
                        item.get(
                            "name",
                            "Unnamed"
                        ),


                    "properties":
                        item.get(
                            "properties",
                            {}
                        )

                }

            )



    # =====================================
    # IFC TYPE MAP
    # =====================================

    def _map_ifc_type(
        self,
        element
    ):


        mapping = {


            "wall":
                "IfcWall",

            "door":
                "IfcDoor",

            "window":
                "IfcWindow",

            "column":
                "IfcColumn",

            "beam":
                "IfcBeam",

            "slab":
                "IfcSlab"

        }



        return mapping.get(

            element.get(
                "bim_type",
                ""
            ),

            "IfcBuildingElementProxy"

        )