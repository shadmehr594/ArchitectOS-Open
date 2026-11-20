class RevitExportEngine:


    VERSION = "33.3"


    def __init__(self):

        print(
            f"🏢 Revit Export Engine v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # MAIN EXPORT
    # ==================================================

    def export(
        self,
        runtime_data,
        site=None
    ):


        import copy


        runtime_data = copy.deepcopy(
            runtime_data
        )


        for element in runtime_data.get(
            "bim_elements",
            []
        ):

            element.pop(
                "_ifc_entity",
                None
            )        


        normalized = self._normalize(
            runtime_data
        )


        print(
            "\n====== REVIT NORMALIZED DEBUG ======"
        )


        for level, data in normalized.items():

            print(
                level
            )

            for category, items in data.items():

                print(
                    category,
                    ":",
                    len(items)
                )

                if items:

                    print(
                        "FIRST ITEM TYPE:",
                        type(items[0])
                    )

                    print(
                        "FIRST ITEM:",
                        items[0]
                    )


        print(
            "\n====== REVIT EXPORT SERIALIZATION DEBUG ======"
        )


        ifc_result = self._to_ifc(
            normalized
        )


        print(
            "IFC RESULT TYPE:",
            type(ifc_result)
        )


        print(
            "IFC RESULT:"
        )

        print(
            ifc_result
        )


        mapping_result = self._family_mapping(
            normalized
        )


        print(
            "FAMILY MAPPING TYPE:",
            type(mapping_result)
        )


        material_result = self._type_material_mapping(
            normalized
        )
 

        print(
            "MATERIAL RESULT TYPE:",
            type(material_result)
        )


        import json


        print("\n====== REVIT JSON SERIALIZATION TEST ======")

        json.dumps(
            {
                "ifc": ifc_result,
                "dxf": self._to_dxf_layers(normalized),
                "type_materials": material_result,
                "revit_mapping": mapping_result
            },
            default=str
        )

        print("✅ REVIT SERIALIZATION TEST PASSED")


        return {


            "engine":
                f"revit_export_v{self.VERSION}",


            "status":
                "export_ready",


            "ifc":
                ifc_result,


            "dxf":
                self._to_dxf_layers(
                    normalized
                ),


           "type_materials":
                 material_result,

            "revit_mapping":
                mapping_result

        }



    # ==================================================
    # DATA NORMALIZER
    # ==================================================

    def _normalize(
        self,
        data
    ):


        floors = {

            "LEVEL_0":
            {

                "columns": [],
                "beams": [],
                "walls": [],
                "openings": []

            }

        }


        elements = data.get(
            "bim_elements",
            []
        )


        # -----------------------------
        # BIM ELEMENT CONTRACT
        # -----------------------------

        for element in elements:


            ifc_type = element.get(
                "ifc_type",
                element.get(
                    "type",
                    ""
                )
            )


            obj = {


                "id":
                    element.get(
                        "id"
                    ),


                "type":
                    element.get(
                        "type"
                    ),


                "ifc_type":
                    ifc_type,


                "system":
                    element.get(
                        "system"
                    ),


                "data":
                    element.get(
                        "data",
                        {}
                    )

            }



            if ifc_type == "IfcColumn":


                floors["LEVEL_0"]["columns"].append(
                    obj
                )


            elif ifc_type == "IfcBeam":


                floors["LEVEL_0"]["beams"].append(
                    obj
                )


            elif ifc_type == "IfcWall":


                floors["LEVEL_0"]["walls"].append(
                    obj
                )


            elif ifc_type in [

                "IfcOpeningElement",
                "IfcOpening",
                "IfcDoor",
                "IfcWindow"

            ]:


                floors["LEVEL_0"]["openings"].append(
                    obj
                )



        return floors




    # ==================================================
    # IFC
    # ==================================================

    def _to_ifc(
        self,
        data
    ):


        return {


            "IFCProject":

            {


                "schema":
                    "IFC4",


                "floors":

                {

                    floor:

                    {

                        "IfcColumn":
                        [
                            {
                                "id":
                                    c.get("id"),

                                "type":
                                    c.get("ifc_type"),

                                "data":
                                    c.get("data", {})
                            }

                            for c in elements.get(
                                "columns",
                                []
                            )
                        ],


                        "IfcBeam":
                            elements.get(
                                "beams",
                                []
                            ),


                        "IfcWall":
                            elements.get(
                                "walls",
                                []
                            ),


                        "IfcOpening":
                            elements.get(
                                "openings",
                                []
                            )

                    }


                    for floor, elements in data.items()

                }

            }

        }




    # ==================================================
    # DXF
    # ==================================================

    def _to_dxf_layers(
        self,
        data
    ):


        layers = {


            "COLUMNS": [],

            "BEAMS": [],

            "WALLS": [],

            "OPENINGS": []

        }



        for floor, elements in data.items():


            for category in [

                "columns",
                "beams",
                "walls",
                "openings"

            ]:


                for obj in elements.get(
                    category,
                    []
                ):


                    layers[
                        category.upper()
                    ].append(

                        {

                            "layer":
                                floor,


                            "entity":
                                obj

                        }

                    )


        return layers




    # ==================================================
    # REVIT FAMILY MAPPING
    # ==================================================

    def _family_mapping(
        self,
        data
    ):


        result = {}



        for floor, elements in data.items():


            result[floor] = {


                "columns":

                [

                    {

                        "id":
                            c.get(
                                "id"
                            ),

                        "family":
                            "Structural Columns - Concrete"

                    }

                    for c in elements.get(
                        "columns",
                        []
                    )

                ],



                "beams":

                [

                    {

                        "id":
                            b.get(
                                "id"
                            ),

                        "family":
                            "Structural Framing - Concrete"

                    }

                    for b in elements.get(
                        "beams",
                        []
                    )

                ],



                "walls":

                [

                    {

                        "id":
                            w.get(
                                "id"
                            ),

                        "family":
                            "Basic Wall - Concrete 200mm"

                    }

                    for w in elements.get(
                        "walls",
                        []
                    )

                ],



                "openings":

                [

                    {

                        "id":
                            o.get(
                                "id"
                            ),

                        "family":
                            "Door / Window System"

                    }

                    for o in elements.get(
                        "openings",
                        []
                    )

                ]

            }



        return result


    # ==================================================
    # TYPE MATERIAL MAPPING
    # ==================================================

    def _type_material_mapping(
        self,
        normalized
    ):

        print(
            "🧱 Revit Type Material Mapper v1.0 ACTIVE"
        )


        mapping = {}


        for floor, elements in normalized.items():


            mapping[floor] = {


                "columns":

                [
                    {
                        "id":
                            c.get("id"),

                        "material":
                            "Concrete"
                    }

                    for c in elements.get(
                        "columns",
                        []
                    )
                ],



                "beams":

                [
                    {
                        "id":
                            b.get("id"),

                        "material":
                            "Concrete"
                    }

                    for b in elements.get(
                        "beams",
                        []
                    )
                ],



                "walls":

                [
                    {
                        "id":
                            w.get("id"),

                        "material":
                            "Concrete"
                    }

                    for w in elements.get(
                        "walls",
                        []
                    )
                ],



                "openings":

                [
                    {
                        "id":
                            o.get("id"),

                        "material":
                            "Default"
                    }

                    for o in elements.get(
                        "openings",
                        []
                    )
                ]

            }



        return {

            "engine":
                "revit_type_material_mapper_v1.0",

            "elements":
                mapping

        }