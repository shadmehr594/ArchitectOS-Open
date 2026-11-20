class RenderContextBuilder:


    VERSION = "1.2"



    def __init__(
        self
    ):

        print(
            "🧠 RENDER CONTEXT BUILDER v1.2 ONLINE"
        )



    # ==================================================
    # BUILD PROMPT CONTEXT
    # ==================================================

    def build(
        self,
        render_context
    ):


        payload = (
            render_context.get(
                "render_payload",
                {}
            )
        )



        building_type = (
            payload.get(
                "building_type",
                "architectural project"
            )
        )



        category = (
            payload.get(
                "category",
                ""
            )
        )



        layout = (
            payload.get(
                "layout",
                {}
            )
        )



        levels = (
            payload.get(
                "levels",
                []
            )
        )



        spaces = []



        # ==================================================
        # EXTRACT SPACES SAFELY
        # ==================================================

        for floor_name, floor in layout.items():


            for space in floor.get(
                "spaces",
                []
            ):


                if isinstance(
                    space,
                    dict
                ):

                    name = (
                        space.get(
                            "name"
                        )
                    )


                    if name:
                        spaces.append(
                            name
                        )


                else:

                    spaces.append(
                        space
                    )



        architecture_summary = (
            f"{building_type} "
            f"{category} building. "
            "Spaces include: "
            +
            ", ".join(
                spaces
            )
            +
            ". "
            "Professional architectural visualization."
        )



        return {


            "architectural_context":

            {

                "building_type":
                    building_type,


                "category":
                    category,


                "spaces":
                    spaces,


                "levels":
                    levels

            },



            "prompt_context":

                architecture_summary,



            "camera":

                payload.get(
                    "camera"
                ),



            "mood":

                payload.get(
                    "mood"
                ),



            "metadata":

            {

                "engine":
                    "RenderContextBuilder",


                "version":
                    self.VERSION

            }

        }