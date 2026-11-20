class BIMContextBridge:


    VERSION = "1.1"



    def __init__(self):

        print(
            "🧠 BIM CONTEXT BRIDGE v1.1 ONLINE"
        )



    # ==================================================
    # NORMALIZE LIST
    # ==================================================

    def safe_list(
        self,
        value
    ):

        if isinstance(
            value,
            list
        ):

            return value


        return []



    # ==================================================
    # BUILD SPACE CONTEXT
    # ==================================================

    def build_spaces(
        self,
        spatial
    ):


        spaces = []


        registry = spatial.get(
            "space_registry",
            []
        )


        if registry:

            for item in registry:

                spaces.append(

                    {

                        "id":
                            item.get(
                                "id"
                            ),

                        "ifc_type":
                            item.get(
                                "type",
                                "IfcSpace"
                            ),

                        "status":
                            item.get(
                                "status",
                                "planned"
                            )

                    }

                )


            return spaces



        # fallback from nodes

        nodes = self.safe_list(
            spatial.get(
                "nodes"
            )
        )


        for node in nodes:


            spaces.append(

                {

                    "id":
                        node,

                    "ifc_type":
                        "IfcSpace",

                    "status":
                        "planned"

                }

            )


        return spaces



    # ==================================================
    # BUILD LEVEL CONTEXT
    # ==================================================

    def build_levels(
        self,
        bim_model
    ):


        levels = bim_model.get(
            "levels",
            []
        )


        if levels:

            return levels



        return [

            {

                "name":
                    "ground",

                "elevation":
                    0

            }

        ]



    # ==================================================
    # BUILD RELATIONSHIPS
    # ==================================================

    def build_relationships(
        self,
        spatial
    ):


        return {


            "connections":

                self.safe_list(

                    spatial.get(
                        "connections"
                    )

                ),


            "adjacency":

                self.safe_list(

                    spatial.get(
                        "adjacency"
                    )

                )

        }



    # ==================================================
    # BUILD CONTEXT
    # ==================================================

    def build_context(
        self,
        bim_model,
        ifc_model
    ):


        if not isinstance(
            bim_model,
            dict
        ):

            bim_model = {}



        if not isinstance(
            ifc_model,
            dict
        ):

            ifc_model = {}



        spatial = bim_model.get(
            "spatial",
            {}
        )



        return {


            "bim_context":

            {


                "building":

                {

                    "type":

                        bim_model.get(
                            "building",
                            {}
                        ).get(
                            "type"
                        ),


                    "category":

                        bim_model.get(
                            "building",
                            {}
                        ).get(
                            "category"
                        ),


                    "style":

                        bim_model.get(
                            "building",
                            {}
                        ).get(
                            "style"
                        )

                },



                "levels":

                    self.build_levels(
                        bim_model
                    ),



                "spaces":

                    self.build_spaces(
                        spatial
                    ),



                "relationships":

                    self.build_relationships(
                        spatial
                    )

            },



            "ifc_context":

            {


                "project":

                    ifc_model.get(
                        "ifc_project",
                        {}
                    ),


                "storeys":

                    self.safe_list(

                        ifc_model.get(
                            "storeys"
                        )

                    ),


                "spaces":

                    self.safe_list(

                        ifc_model.get(
                            "spaces"
                        )

                    )

            },



            "metadata":

            {


                "engine":

                    "BIMContextBridge",



                "version":

                    self.VERSION



            }


        }