# ==========================================================
# ArchitectOS BIM Intent Adapter v1.0
#
# Architectural Building Model
#          |
#          ↓
# BIM Semantic Contract
#
# IFC Ready Layer
#
# ==========================================================


class BIMIntentAdapter:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🏗 BIM INTENT ADAPTER v1.0 ONLINE"
        )



    # ==================================================
    # IFC ENTITY MAPPING
    # ==================================================

    def map_entity_type(
        self,
        entity
    ):


        mapping = {


            "project":
                "IfcProject",


            "site":
                "IfcSite",


            "building":
                "IfcBuilding",


            "level":
                "IfcBuildingStorey",


            "space":
                "IfcSpace",


            "wall":
                "IfcWall",


            "slab":
                "IfcSlab",


            "column":
                "IfcColumn",


            "beam":
                "IfcBeam",


            "opening":
                "IfcOpeningElement"

        }


        return mapping.get(
            entity,
            "IfcBuildingElementProxy"
        )



    # ==================================================
    # SPACE CONVERSION
    # ==================================================

    def convert_spaces(
        self,
        building_model
    ):


        result = []


        spaces = building_model.get(
            "spatial",
            {}
        ).get(
            "space_registry",
            []
        )


        for space in spaces:


            result.append(

                {

                    "id":
                        space.get(
                            "id"
                        ),


                    "ifc_type":
                        self.map_entity_type(
                            "space"
                        ),


                    "status":
                        space.get(
                            "status",
                            "planned"
                        )

                }

            )


        return result



    # ==================================================
    # SPATIAL RELATIONSHIP
    # ==================================================

    def convert_relationships(
        self,
        building_model
    ):


        spatial = building_model.get(
            "spatial",
            {}
        )


        return {


            "connections":
                spatial.get(
                    "connections",
                    []
                ),


            "adjacency":
                spatial.get(
                    "adjacency",
                    []
                )

        }



    # ==================================================
    # LEVEL CONVERSION
    # ==================================================

    def convert_levels(
        self,
        building_model
    ):


        levels = building_model.get(
            "building",
            {}
        ).get(
            "levels",
            {}
        )


        return {


            "IfcBuildingStorey":

                {


                    "count":
                        levels.get(
                            "total",
                            1
                        ),


                    "ground":
                        levels.get(
                            "ground",
                            1
                        ),


                    "basement":
                        levels.get(
                            "basement",
                            0
                        )

                }

        }

    # ==================================================
    # COMPATIBILITY ENTRY POINT
    # BIM CONVERSION CONTRACT
    # ==================================================

    def convert(
        self,
        building_model
    ):

        return self.adapt(
            building_model
        )



    # ==================================================
    # MAIN ADAPTER
    # ==================================================

    def adapt(
        self,
        building_model
    ):



        return {


            "bim_project":

            {


                "entity":

                    self.map_entity_type(
                        "project"
                    )

            },



            "site":

            {


                "entity":

                    self.map_entity_type(
                        "site"
                    ),


                "data":

                    building_model.get(
                        "site",
                        {}
                    )

            },



            "building":

            {


                "entity":

                    self.map_entity_type(
                        "building"
                    ),


                "data":

                    building_model.get(
                        "building",
                        {}
                    )

            },



            "levels":

                self.convert_levels(
                    building_model
                ),



            "spaces":

                self.convert_spaces(
                    building_model
                ),



            "relationships":

                self.convert_relationships(
                    building_model
                ),



            "metadata":

            {

                "adapter":
                    "BIM Intent Adapter",


                "version":
                    self.VERSION

            }

        }