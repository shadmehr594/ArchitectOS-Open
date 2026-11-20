import json
import os


class SpatialNormalizer:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 SPATIAL NORMALIZER v1.0 ONLINE"
        )


        self.aliases = {

            # -------------------------
            # Persian spaces
            # -------------------------

            "لابی": "lobby",

            "ورودی": "lobby",

            "فضای ورودی": "lobby",


            "پارکینگ": "parking",

            "پارکینگ خودرو": "parking",


            "parking_area": "parking",

            "driveway parking area": "parking",

            "parking space": "parking",



            "فودکورت": "food_court",

            "رستوران مرکزی": "food_court",



            "سینما": "cinema",

            "سالن نمایش": "cinema",



            "واحد تجاری": "retail",

            "مغازه": "retail",

            "فروشگاه": "retail",



            "راهرو": "public_circulation",

            "مسیر حرکت": "public_circulation",



            "پذیرایی": "living_room",

            "نشیمن": "living_room",



            "آشپزخانه": "kitchen",



            "اتاق خواب": "bedroom",



            "استخر": "pool",


            "تراس": "terrace",


            "باغ": "garden",


            "حیاط": "yard"

        }



    # ==================================================
    # NORMALIZE VALUE
    # ==================================================

    def normalize_space(
        self,
        value
    ):


        if not value:

            return value



        return self.aliases.get(
            value,
            value
        )



    # ==================================================
    # NORMALIZE LIST
    # ==================================================

    def normalize_list(
        self,
        values
    ):


        result = []


        for value in values:


            normalized = self.normalize_space(
                value
            )


            if normalized not in result:

                result.append(
                    normalized
                )


        return result



    # ==================================================
    # NORMALIZE ZONES
    # ==================================================

    def normalize_zones(
        self,
        zones
    ):


        normalized = {}



        for zone, spaces in zones.items():


            normalized[zone] = self.normalize_list(
                spaces
            )



        return normalized



    # ==================================================
    # NORMALIZE CONNECTIONS
    # ==================================================

    def normalize_connections(
        self,
        connections
    ):


        result = []



        for connection in connections:


            item = {


                "source":
                    self.normalize_space(
                        connection.get(
                            "source"
                        )
                    ),


                "target":
                    self.normalize_space(
                        connection.get(
                            "target"
                        )
                    ),


                "behavior":
                    connection.get(
                        "behavior"
                    )

            }



            result.append(
                item
            )



        return result



    # ==================================================
    # MAIN NORMALIZER
    # ==================================================

    def normalize(
        self,
        spatial_model
    ):


        normalized_nodes = self.normalize_list(
            spatial_model.get(
                "nodes",
                []
            )
        )


        model = {


            "nodes":
                normalized_nodes,


            "connections":
                self.normalize_connections(
                    spatial_model.get(
                        "connections",
                        []
                    )
                ),


            "zones":
                self.normalize_zones(
                    spatial_model.get(
                        "zones",
                        {}
                    )
                )

        }



        return model