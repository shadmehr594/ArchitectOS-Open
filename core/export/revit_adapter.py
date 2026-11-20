class RevitAdapter:


    VERSION = "1.6"



    def __init__(self):

        print(
            f"🔗 Revit Adapter v{self.VERSION} ACTIVE"
        )



    def convert(
        self,
        revit_export
    ):


        if "build_plan" in revit_export:

            revit_export = (
                revit_export["build_plan"]
            )


        return {

            "engine":
                f"revit_adapter_v{self.VERSION}",


            "levels":
                self._extract_levels(
                    revit_export
                ),


            "families":
                self._extract_families(
                    revit_export
                ),


            "type_materials":
                self._extract_type_materials(
                    revit_export
                ),


            "elements":
                self._extract_elements(
                    revit_export
                )

        }



    # ==================================
    # LEVELS
    # ==================================

    def _extract_levels(
        self,
        data
    ):


        if data.get(
            "levels"
        ):

            return data.get(
                "levels"
            )


        plan = data.get(
            "plan",
            {}
        )


        return plan.get(
            "levels",
            {}
        )



    # ==================================
    # FAMILIES
    # ==================================

    def _extract_families(
        self,
        data
    ):


        if data.get(
            "families"
        ):

            return data.get(
                "families"
            )


        plan = data.get(
            "plan",
            {}
        )


        return plan.get(
            "families",
            {}
        )



    # ==================================
    # TYPE MATERIAL MAP
    # ==================================

    def _extract_type_materials(
        self,
        data
    ):


        candidates = [

            data.get(
                "type_materials",
                {}
            ),


            data.get(
                "plan",
                {}
            ).get(
                "type_materials",
                {}
            )

        ]



        for source in candidates:


            if not isinstance(
                source,
                dict
            ):

                continue



            # New structure:
            # {
            #   "column_001": {
            #       "category": "...",
            #       "family": "...",
            #       "type": "...",
            #       "material": "..."
            #   }
            # }

            if source:


                if "elements" not in source:

                    return source



                # Old structure:
                # {
                #   "elements": {
                #       ...
                #   }
                # }

                elements = source.get(
                    "elements",
                    {}
                )


                if elements:

                    return elements



        return {}



    # ==================================
    # ELEMENT EXTRACTION
    # ==================================

    def _extract_elements(
        self,
        data
    ):


        source = (

            data.get(
                "elements",
                []
            )

        )



        if not source:


            source = (

                data.get(
                    "plan",
                    {}
                ).get(
                    "elements",
                    []
                )

            )



        materials = (

            self._extract_type_materials(
                data
            )

        )



        elements = []



        for item in source:


            element_id = (

                item.get(
                    "id"
                )

            )



            geometry = (

                item.get(
                    "data"
                )

                or

                item.get(
                    "geometry"
                )

                or {}

            )



            element_type = (

                item.get(
                    "revit_type"
                )

                or

                item.get(
                    "type"
                )

                or

                item.get(
                    "ifc_type"
                )

                or

                geometry.get(
                    "type"
                )

            )



            mapping = (

                materials.get(
                    element_id,
                    {}
                )

            )



            elements.append({

                "id":
                    element_id,


                "type":
                    element_type,


                "ifc_type":
                    item.get(
                        "ifc_type"
                    ),


                "category":
                    mapping.get(
                        "category"
                    ),


                "family":
                    mapping.get(
                        "family"
                    ),


                "revit_type":
                    mapping.get(
                        "type"
                    ),


                "material":
                    mapping.get(
                        "material"
                    ),


                "geometry":
                    geometry

            })



        return elements