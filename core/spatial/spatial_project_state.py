class ArchitecturalProjectState:


    VERSION = "1.0"



    def __init__(
        self,
        context
    ):


        print(
            "🏗 ARCHITECTURAL PROJECT STATE v1.0 ONLINE"
        )


        self.context = context



        self.project = (
            context.get(
                "project",
                {}
            )
        )



        self.spatial = (
            context.get(
                "spatial",
                {}
            )
        )



        self.layout = (
            context.get(
                "layout",
                {}
            )
        )



        self.validation = (
            context.get(
                "validation",
                {}
            )
        )



        self.render_context = (
            context.get(
                "render_context",
                {}
            )
        )



        # Canonical spatial cleanup
        self.clean_spatial_nodes()



        self.metadata = {

            "engine":
                "ArchitecturalProjectState",

            "version":
                self.VERSION

        }



    # ==================================================
    # CANONICAL SPATIAL CLEANER
    # ==================================================

    def clean_spatial_nodes(
        self
    ):


        spatial_model = (
            self.spatial.get(
                "model",
                {}
            )
        )



        aliases = {


            "parking_area":
                "parking",


            "driveway parking area":
                "parking",


            "parking space":
                "parking"

        }



        nodes = []



        for node in spatial_model.get(
            "nodes",
            []
        ):


            canonical = aliases.get(
                node,
                node
            )



            if canonical not in nodes:

                nodes.append(
                    canonical
                )



        spatial_model["nodes"] = nodes



        return nodes



    # ==================================================
    # PROJECT INFO
    # ==================================================

    def get_project_type(
        self
    ):


        return self.project.get(
            "building_type"
        )



    # ==================================================
    # PLAN
    # ==================================================

    def get_plan(
        self
    ):


        return self.layout.get(
            "plan"
        )



    # ==================================================
    # CONSTRAINTS
    # ==================================================

    def get_constraints(
        self
    ):


        return self.spatial.get(
            "constraints"
        )



    # ==================================================
    # VALIDATION STATUS
    # ==================================================

    def is_valid(
        self
    ):


        return (

            self.validation.get(
                "validation"
            )
            ==
            "passed"

        )



    # ==================================================
    # RENDER CONTEXT
    # ==================================================

    def get_render_context(
        self
    ):


        return self.render_context



    # ==================================================
    # EXPORT
    # ==================================================

    def export(
        self
    ):


        return {


            "project":
                self.project,


            "spatial":
                self.spatial,


            "layout":
                self.layout,


            "validation":
                self.validation,


            "render_context":
                self.render_context,


            "metadata":
                self.metadata

        }