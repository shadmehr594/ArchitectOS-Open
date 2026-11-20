# ==========================================================
# ArchitectOS Building Program Generator v1.0
#
# Architectural Intent
#        |
#        ↓
# Building Program
#        |
#        ↓
# BIM / CAD / Render
#
# Generates:
# - Floor functions
# - Core requirements
# - Service spaces
# - Parking integration
# - User program preservation
#
# ==========================================================


class BuildingProgramGenerator:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🏢 Building Program Generator v1.0 ACTIVE"
        )



    def generate(
        self,
        intent
    ):


        program = {


            "levels": [],


            "spaces": [],


            "functions": [],


            "core": {

                "elevators": [],

                "stairs": [],

                "ramps": []

            },


            "services": [],


            "parking": None,


            "warnings": []

        }



        building_type = intent.get(
            "building_type",
            "building"
        )


        levels = intent.get(
            "levels",
            {}
        )


        spaces = intent.get(
            "spaces",
            []
        )


        functions = intent.get(
            "functions",
            []
        )



        # ==================================================
        # PRESERVE USER REQUIREMENTS
        # ==================================================

        program["spaces"].extend(
            spaces
        )


        program["functions"].extend(
            functions
        )



        # ==================================================
        # PARKING
        # ==================================================

        parking = intent.get(
            "parking"
        )


        if parking:


            program["parking"] = parking


            # ==============================================
            # EXPLICIT BASEMENT AUTHORITY
            # ==============================================
            #
            # Parking requirement does NOT automatically
            # imply a basement.
            #
            # "surface_or_basement" is an unresolved
            # parking-placement possibility, not permission
            # to create a basement.
            #
            # ArchitecturalIntent levels have higher
            # authority over inferred parking placement.
            # ==============================================

            basement_count = 0

            if isinstance(
                levels,
                dict
            ):

                basement_count = levels.get(
                    "basement",
                    0
                )


            explicit_basement = (
                isinstance(
                    basement_count,
                    int
                )
                and
                basement_count > 0
            )


            parking_type = parking.get(
                "type"
            )


            explicit_basement_parking = (
                parking_type
                in [
                    "basement",
                    "basement_parking"
                ]
            )


            if (
                parking.get(
                    "required"
                )
                and
                (
                    explicit_basement
                    or
                    explicit_basement_parking
                )
            ):


                program["levels"].append({

                    "level":
                        "basement",

                    "functions":
                        [
                            "parking"
                        ]

                })


            elif parking.get(
                "required"
            ):


                parking[
                    "placement_status"
                ] = "pending"


                parking[
                    "placement_reason"
                ] = (
                    "parking required but basement "
                    "not explicitly requested"
                )



        # ==================================================
        # RESIDENTIAL
        # ==================================================

        if building_type in [

            "house",

            "villa",

            "residential"

        ]:


            program["levels"].append({

                "level":
                "ground",


                "functions":[

                    "living",

                    "kitchen",

                    "guest"

                ]

            })


            program["services"].extend([

                "storage",

                "laundry_room"

            ])



            program["core"]["stairs"].append({

                "type":
                "main_stair",

                "required":
                True

            })



        # ==================================================
        # COMMERCIAL
        # ==================================================

        elif building_type in [

            "commercial",

            "shopping_mall"

        ]:


            program["levels"].append({

                "level":
                "ground",


                "functions":[

                    "retail",

                    "lobby"

                ]

            })


            program["services"].extend([

                "storage",

                "mechanical_room",

                "electrical_room"

            ])



            # Vertical Core

            program["core"]["stairs"].append({

                "type":
                "emergency_stair",

                "required":
                True

            })


            program["core"]["elevators"].append({

                "type":
                "passenger_elevator",

                "count":
                1

            })



        # ==================================================
        # OFFICE
        # ==================================================

        elif building_type == "office":


            program["levels"].append({

                "level":
                "typical_floor",


                "functions":[

                    "office",

                    "meeting"

                ]

            })


            program["core"]["elevators"].append({

                "type":
                "passenger_elevator",

                "count":
                1

            })



        # ==================================================
        # MULTI LEVEL EXPANSION
        # ==================================================

        above = levels.get(
            "above_ground",
            0
        )

        if not isinstance(
            above,
            int
        ):

            above = 0


        if above > 1:

            for i in range(
                1,
                above
            ):

                if building_type in [
                    "house",
                    "villa",
                    "residential"
                ]:

                    floor_functions = [
                        "master_bedroom",
                        "bedroom",
                        "bathroom",
                        "family_lounge"
                    ]

                elif building_type in [
                    "commercial",
                    "shopping_mall"
                ]:

                    floor_functions = [
                        "retail",
                        "public_circulation"
                    ]

                elif building_type == "office":

                    floor_functions = [
                        "office",
                        "meeting"
                    ]

                else:

                    floor_functions = [
                        "typical_space"
                    ]


                program["levels"].append({

                    "level":
                        f"floor_{i}",

                    "functions":
                        floor_functions

                })



        # ==================================================
        # LARGE BUILDING INTELLIGENCE
        # ==================================================

        if above >= 5:


            program["core"]["elevators"] = [

                {

                    "type":
                    "passenger_elevator",

                    "count":
                    2

                }

            ]


            program["core"]["stairs"].append({

                "type":
                "secondary_emergency_stair",

                "required":
                True

            })



        return {


            "engine":

            "building_program_generator_v1.0",


            "program":

            program

        }