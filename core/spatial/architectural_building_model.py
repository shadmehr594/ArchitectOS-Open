# ==========================================================
# ArchitectOS Architectural Building Model v1.2
#
# Planning
#     |
#     ↓
# Building Semantic Model
#     |
#     ↓
# BIM Intent Object
#     |
#     ↓
# Render Context
#
# ==========================================================


class ArchitecturalBuildingModel:


    VERSION = "1.2"



    def __init__(self):

        print(
            "🏗 ARCHITECTURAL BUILDING MODEL v1.2 ONLINE"
        )



    # ==================================================
    # SPACE ENTITY BUILDER
    # BIM READY
    # ==================================================

    def build_spaces(
        self,
        spatial
    ):


        spaces = []


        nodes = spatial.get(
            "nodes",
            []
        )


        for node in nodes:


            spaces.append(

                {

                    "id":
                        node,


                    "entity":
                        "IfcSpace",


                    "status":
                        "planned"

                }

            )


        return spaces



    # ==================================================
    # BIM ENTITY CONTAINER
    # ==================================================

    def build_bim_entities(
        self
    ):


        return {


            "spaces": [],


            "walls": [],


            "slabs": [],


            "columns": [],


            "beams": [],


            "openings": [],


            "stairs": [],


            "ramps": []

        }



    # ==================================================
    # BUILD LEVEL MODEL
    # ==================================================

    def build_levels(
        self,
        project
    ):


        levels = project.get(
            "levels",
            {}
        )


        if not levels:

            levels = {

                "basement":0,

                "ground":1,

                "above_ground":1,

                "total":1

            }


        return levels



    # ==================================================
    # SITE MODEL
    # ==================================================

    def build_site(
        self,
        project
    ):


        site = {

            "boundary": [],

            "area": None,

            "coordinate_system": None

        }


        project_site = project.get(
            "site",
            []
        )


        if isinstance(
            project_site,
            list
        ) and len(project_site):


            source = project_site[0]


            if isinstance(
                source,
                dict
            ):


                site["boundary"] = source.get(
                    "boundary",
                    []
                )


                site["area"] = source.get(
                    "area"
                )


                site["coordinate_system"] = source.get(
                    "coordinate_system"
                )


        return site



    # ==================================================
    # RENDER CONTEXT
    # ==================================================

    def build_render_context(
        self,
        project
    ):


        return {


            "style":
                project.get(
                    "style"
                ),


            "materials":
                project.get(
                    "materials",
                    []
                ),


            "environment":
                project.get(
                    "environment",
                    []
                ),


            "camera":
                project.get(
                    "camera",
                    "architectural visualization"
                ),


            "mood":
                project.get(
                    "mood",
                    "professional archviz"
                )

        }



    # ==================================================
    # BUILD MODEL
    # ==================================================

    def build(

        self,

        project,

        spatial,

        layout,

        geometry,

        constraints,

        validation,

        render_context=None

    ):



        if render_context is None:

            render_context = self.build_render_context(
                project
            )



        spaces = self.build_spaces(
            spatial
        )


        bim_entities = self.build_bim_entities()



        bim_entities["spaces"] = spaces



        levels = self.build_levels(
            project
        )



        site = self.build_site(
            project
        )



        return {


            # ======================================
            # BUILDING INFORMATION
            # ======================================

            "building": {


                "type":
                    project.get(
                        "building_type"
                    ),


                "category":
                    project.get(
                        "category"
                    ),


                "style":
                    project.get(
                        "style"
                    ),


                "materials":
                    project.get(
                        "materials",
                        []
                    ),


                "levels":
                    levels

            },



            # ======================================
            # BIM SPATIAL MODEL
            # ======================================

            "spatial": {


                "nodes":
                    spatial.get(
                        "nodes",
                        []
                    ),


                "connections":
                    spatial.get(
                        "connections",
                        []
                    ),


                "adjacency":
                    spatial.get(
                        "adjacency",
                        []
                    ),


                "zones":
                    spatial.get(
                        "zones",
                        {}
                    ),


                "privacy":
                    spatial.get(
                        "privacy",
                        {}
                    ),


                "circulation":
                    spatial.get(
                        "circulation",
                        []
                    ),


                "space_registry":
                    spaces

            },



            # ======================================
            # SITE INTELLIGENCE
            # ======================================

            "site":

                site,



            # ======================================
            # FLOOR LAYOUT
            # ======================================

            "layout":

                layout,



            # ======================================
            # GEOMETRY PLACEHOLDER
            # ======================================

            "geometry":

                geometry,



            # ======================================
            # CONSTRAINTS
            # ======================================

            "constraints":

                constraints,



            # ======================================
            # VALIDATION
            # ======================================

            "validation":

                validation,



            # ======================================
            # BIM OBJECTS
            # ======================================

            "bim_entities":

                bim_entities,



            # ======================================
            # RENDER
            # ======================================

            "render_context":

                render_context,



            # ======================================
            # META
            # ======================================

            "metadata": {


                "engine":

                    "Architectural Building Model",


                "version":

                    self.VERSION

            }

        }