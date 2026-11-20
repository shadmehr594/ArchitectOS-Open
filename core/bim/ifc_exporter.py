class IFCExporter:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🏗 IFC EXPORTER v1.0 ONLINE"
        )



    # ==================================================
    # EXPORT PROJECT
    # ==================================================

    def export(
        self,
        bim_model
    ):


        project = (
            bim_model.get(
                "project",
                {}
            )
        )


        levels = (
            bim_model.get(
                "levels",
                []
            )
        )


        spaces = (
            bim_model.get(
                "spaces",
                []
            )
        )


        elements = (
            bim_model.get(
                "elements",
                []
            )
        )



        return {


            "ifc_project":

            {

                "name":
                    project.get(
                        "type",
                        "Architectural Project"
                    ),


                "category":
                    project.get(
                        "category"
                    )

            },



            "storeys":

                [

                    {

                        "name":
                            level.get(
                                "name"
                            ),


                        "level":
                            level.get(
                                "level"
                            )

                    }

                    for level in levels

                ],



            "spaces":

                [

                    {

                        "ifc_class":
                            "IfcSpace",


                        "name":
                            space.get(
                                "name"
                            ),


                        "type":
                            space.get(
                                "type"
                            ),


                        "zone":
                            space.get(
                                "zone"
                            ),


                        "storey":
                            space.get(
                                "level"
                            )

                    }

                    for space in spaces

                ],



            "elements":

                elements,



            "metadata":

            {

                "engine":
                    "IFCExporter",


                "version":
                    self.VERSION

            }

        }