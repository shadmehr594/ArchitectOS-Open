import json
import os


class ArchitecturalFacadeResolverV1:


    VERSION = "1.0"



    def __init__(self):

        base = os.path.dirname(
            __file__
        )


        self.facade_language = self.load_json(
            os.path.join(
                base,
                "facade_language_ontology.json"
            )
        )


        self.climate_facade = self.load_json(
            os.path.join(
                base,
                "climate_facade_ontology.json"
            )
        )


        print(
            "🏛 FACADE INTELLIGENCE RESOLVER V1 ONLINE"
        )



    def load_json(
        self,
        path
    ):

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)



    def resolve(
        self,
        context
    ):


        result = {

            "facade_language":
                None,

            "composition":
                [],

            "elements":
                [],

            "strategies":
                [],

            "facade_modifications":
                [],

            "orientation_rules":
                [],

            "materials":
                [],

            "rules":
                []

        }



        style = context.get(
            "style"
        )


        climate = context.get(
            "climate"
        )



        # -----------------------------
        # FACADE LANGUAGE
        #
        # Ontology contract:
        #
        # facade_languages = {
        #     "modern": {...},
        #     "roman_classic": {...},
        #     ...
        # }
        #
        # Therefore the ontology key itself is the
        # canonical facade style identifier.
        # -----------------------------

        facade_languages = self.facade_language.get(
            "facade_languages",
            {}
        )


        if not isinstance(
            facade_languages,
            dict
        ):

            facade_languages = {}


        for name, data in facade_languages.items():

            if not isinstance(
                data,
                dict
            ):

                continue


            aliases = data.get(
                "styles",
                []
            )


            if not isinstance(
                aliases,
                list
            ):

                aliases = []


            if (
                style == name
                or
                style in aliases
            ):

                result[
                    "facade_language"
                ] = name


                result[
                    "materials"
                ] = list(
                    data.get(
                        "materials",
                        []
                    )
                    or []
                )


                result[
                    "composition"
                ] = list(
                    data.get(
                        "composition",
                        []
                    )
                    or []
                )


                result[
                    "elements"
                ] = list(
                    data.get(
                        "elements",
                        []
                    )
                    or []
                )


                break


        # -----------------------------
        # CLIMATE STRATEGY
        # -----------------------------

        climates = self.climate_facade.get(
            "climates",
            {}
        )


        if not isinstance(
            climates,
            dict
        ):

            climates = {}


        climate_data = climates.get(
            climate
        )


        if isinstance(
            climate_data,
            dict
        ):

            result[
                "strategies"
            ].extend(
                climate_data.get(
                    "strategies",
                    []
                )
                or []
            )


            result[
                "rules"
            ].extend(
                climate_data.get(
                    "rules",
                    []
                )
                or []
            )


            result[
                "facade_modifications"
            ] = list(
                climate_data.get(
                    "facade_modifications",
                    []
                )
                or []
            )


        # -----------------------------
        # ORIENTATION RULES
        # -----------------------------

        orientation = context.get(
            "orientation"
        )


        orientation_rules = self.climate_facade.get(
            "orientation_rules",
            {}
        )


        result[
            "orientation_rules"
        ] = []


        if (
            orientation
            and
            isinstance(
                orientation_rules,
                dict
            )
        ):

            result[
                "orientation_rules"
            ] = list(
                orientation_rules.get(
                    orientation,
                    []
                )
                or []
            )


        return result