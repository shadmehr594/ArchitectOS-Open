class IFCIntelligenceEngine:

    VERSION = "103.0"


    def __init__(self):

        print(
            "🧬 IFC Intelligence Engine v103.0 ACTIVE"
        )



    def generate(
        self,
        bim_model
    ):

        bim_elements = bim_model.get(
            "bim_elements",
            []
        )

        building_config = bim_model.get(
            "building_config",
            {}
        )


        print(
            "IFC BUILDING CONFIG:",
            building_config
        )


        if bim_elements is None:

            bim_elements = []



        model = {


            "schema":
                "IFC4",


            "engine":
                f"ifc_intelligence_v{self.VERSION}",


            "entities":
                {

                    "IfcProject":
                        {

                            "name":
                                "ArchitectOS Project",

                            "schema":
                                "IFC4"

                        },


                    "IfcSite": [],

                    "IfcBuilding": [],

                    "IfcColumn": [],

                    "IfcBeam": [],

                    "IfcSlab": [],

                    "IfcWall": [],

                    "IfcOpening": [],

                    "IfcDoor": [],

                    "IfcWindow": []

                }

        }



        print(
            "\n====== IFC LOOP DEBUG ======"
        )


        print(
            "INPUT LENGTH:",
            len(bim_elements)
        )


        if bim_elements:

            print(
                "FIRST ELEMENT:",
                bim_elements[0]
            )



        for element in bim_elements:


            try:


                if not isinstance(
                    element,
                    dict
                ):

                    print(
                        "SKIPPED NON DICT:",
                        element
                    )

                    continue



                ifc_type = element.get(
                    "ifc_type"
                )



                print(
                    "DEBUG IFC TYPE:",
                    ifc_type
                )


                print(
                    "====== IFC SOURCE DATA DEBUG ======"
                )

                print(
                    {
                        "id":
                            element.get("id"),

                        "ifc_type":
                            ifc_type,

                        "level":
                            element.get("level"),

                        "z":
                            element.get("z"),

                        "data":
                            element.get("data")
                    }
                )

                print(
                    "===================================="
                )



                # fallback mapping

                if not ifc_type:


                    element_type = element.get(
                        "type",
                        ""
                    )


                    mapping = {


                        "column":
                            "IfcColumn",


                        "beam":
                            "IfcBeam",


                        "slab":
                            "IfcSlab",


                        "wall":
                            "IfcWall",


                        "opening":
                            "IfcOpening",


                        "door":
                            "IfcDoor",


                        "window":
                            "IfcWindow"

                    }



                    ifc_type = mapping.get(
                        element_type
                    )



                if not ifc_type:


                    print(
                        "SKIPPED WITHOUT IFC TYPE:",
                        element.get("id")
                    )


                    continue



                entity = {


                    "GlobalId":
                        element.get(
                            "id"
                        ),


                    "Type":
                        element.get(
                            "type"
                        ),


                    "IFCType":
                        ifc_type,


                    "System":
                        element.get(
                            "system",
                            "unknown"
                        ),


                    "Level":
                        element.get(
                            "level"
                        ),


                    "Z":
                        element.get(
                            "z"
                        ),


                    "Properties":
                        element.get(
                            "data",
                            {}
                        )


                }



                if ifc_type not in model["entities"]:


                    model["entities"][ifc_type] = []



                model["entities"][ifc_type].append(
                    entity
                )



            except Exception as error:


                print(
                    "❌ IFC LOOP ERROR:",
                    error
                )



        model["statistics"] = {


            "IfcColumn":
                len(
                    model["entities"]["IfcColumn"]
                ),


            "IfcBeam":
                len(
                    model["entities"]["IfcBeam"]
                ),


            "IfcSlab":
                len(
                    model["entities"]["IfcSlab"]
                ),


            "IfcWall":
                len(
                    model["entities"]["IfcWall"]
                ),


            "IfcOpening":
                len(
                    model["entities"]["IfcOpening"]
                ),


            "IfcDoor":
                len(
                    model["entities"]["IfcDoor"]
                ),


            "IfcWindow":
                len(
                    model["entities"]["IfcWindow"]
                )

        }



        print(
            "\n====== IFC GENERATED STATISTICS ======"
        )


        print(
            model["statistics"]
        )



        model["status"] = "generated"



        return model