import json
import os



class ArchitecturalMaterialResolverV1:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🧠 MATERIAL KNOWLEDGE RESOLVER V1 ONLINE"
        )


        base_path = os.path.dirname(
            __file__
        )


        self.materials = self.load_json(
            os.path.join(
                base_path,
                "material_ontology.json"
            )
        )


        self.styles = self.load_json(
            os.path.join(
                base_path,
                "architectural_style_ontology.json"
            )
        )


        self.facade_language = self.load_json(
            os.path.join(
                base_path,
                "facade_language_ontology.json"
            )
        )


        self.climate = self.load_json(
            os.path.join(
                base_path,
                "climate_facade_ontology.json"
            )
        )



    def load_json(
        self,
        path
    ):

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(
                file
            )



    def resolve(
        self,
        context
    ):


        style = context.get(
            "style",
            "modern"
        )


        climate = context.get(
            "climate",
            "default"
        )


        result = {


            "style":
                style,


            "climate":
                climate,


            "materials":
                self.find_materials(
                    style
                ),


            "facade_language":
                self.find_facade_language(
                    style
                )


        }


        return result



    def find_materials(
        self,
        style
    ):


        materials = []


        material_library = self.materials.get(
            "materials",
            {}
        )


        for name, data in material_library.items():


            if not isinstance(
                data,
                dict
            ):

                continue



            styles = data.get(
                "styles",
                []
            )


            if style in styles:


                material = {

                    "name":
                        name,

                    "category":
                        data.get(
                            "category",
                            "architectural_material"
                        ),

                    "styles":
                        styles,

                    "properties":
                        data.get(
                            "properties",
                            []
                        ),

                    "uses":
                        data.get(
                            "uses",
                            []
                        ),

                    "climates":
                        data.get(
                            "climates",
                            []
                        )

                }


                materials.append(
                    material
                )


        return materials



    def find_facade_language(
        self,
        style
    ):


        facade_languages = self.facade_language.get(
            "facade_languages",
            {}
        )


        if not isinstance(
            facade_languages,
            dict
        ):

            return None


        direct_match = facade_languages.get(
            style
        )


        if isinstance(
            direct_match,
            dict
        ):

            return {

                "name":
                    style,

                **direct_match

            }


        return None