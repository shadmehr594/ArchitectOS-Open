"""
ArchitectOS Floor Program Engine v1.0

Creates spatial program for each floor type.
"""

from core.architecture.knowledge.building_program_knowledge import (
    BuildingProgramKnowledge
)


class FloorProgramEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🏗️ Floor Program Engine v{self.VERSION} ACTIVE"
        )

        self.program_knowledge = (
            BuildingProgramKnowledge()
        )



    # ==================================================
    # PARKING
    # ==================================================

    def parking_floor(
        self,
        floor
    ):


        return {


            "level":
                floor.get(
                    "level"
                ),


            "type":
                "parking",


            "spaces":[

                {
                    "type":
                        "parking_area"
                },

                {
                    "type":
                        "caretaker"
                }

            ]

        }



    # ==================================================
    # COMMERCIAL
    # ==================================================

    def commercial_floor(
        self,
        floor
    ):


        return {


            "level":
                floor.get(
                    "level"
                ),


            "type":
                "commercial",


            "spaces":[

                {
                    "type":
                        "shop"
                },

                {
                    "type":
                        "storage"
                },

                {
                    "type":
                        "wc"
                },

                {
                    "type":
                        "mezzanine"
                },

                {
                    "type":
                        "core"
                }

            ]

        }



    # ==================================================
    # RESIDENTIAL
    # ==================================================

    def residential_floor(
        self,
        floor
    ):


        units = floor.get(
            "units",
            1
        )


        return {


            "level":
                floor.get(
                    "level"
                ),


            "type":
                "residential",


            "spaces":[


                {

                    "type":
                        "unit_cluster",

                    "count":
                        units

                },


                {

                    "type":
                        "corridor"

                },


                {

                    "type":
                        "stair"

                },


                {

                    "type":
                        "elevator"

                },


                {

                    "type":
                        "lightwell"

                },


                {

                    "type":
                        "ducts"

                }

            ]

        }



    # ==================================================
    # DUPLEX
    # ==================================================

    def duplex_floor(
        self,
        floor
    ):


        result = self.residential_floor(
            floor
        )


        result["type"] = "duplex"


        result["spaces"].append(

            {
                "type":
                    "internal_stair"

            }

        )


        return result


    # ==================================================
    # FLOOR ROLE
    # ==================================================

    def resolve_floor_role(
        self,
        floor
    ):

        explicit_role = floor.get(
            "floor_role",
            floor.get(
                "program_floor"
            )
        )


        if explicit_role:

            return str(
                explicit_role
            ).lower()


        level = str(
            floor.get(
                "level",
                ""
            )
        ).upper()


        if level in {
            "G",
            "GF",
            "GROUND",
            "GROUND_FLOOR"
        }:

            return "ground_floor"


        if (
            level.startswith("B")
            or
            "BASEMENT" in level
        ):

            return "basement"


        if level:

            return "upper_floor"


        return None


    # ==================================================
    # KNOWLEDGE-BACKED FLOOR PROGRAM
    # ==================================================

    def knowledge_floor(
        self,
        floor
    ):

        floor_type = floor.get(
            "type"
        )


        if not floor_type:

            return None


        program_data = (
            self.program_knowledge.get_program(
                floor_type
            )
        )


        if not program_data:

            return None


        floor_role = self.resolve_floor_role(
            floor
        )


        spaces = []


        required_spaces = program_data.get(
            "required_spaces",
            []
        )


        for space in required_spaces:

            if not isinstance(
                space,
                dict
            ):

                continue


            space_name = space.get(
                "name"
            )


            if not space_name:

                continue


            program_floor = space.get(
                "floor"
            )


            if (
                program_floor
                and
                floor_role
                and
                str(program_floor).lower()
                !=
                str(floor_role).lower()
            ):

                continue


            result_space = {

                "type":
                    space_name,

                "source":
                    "building_program_knowledge"

            }


            if space.get(
                "zone"
            ) is not None:

                result_space["zone"] = (
                    space.get(
                        "zone"
                    )
                )


            dimensional_requirements = (
                space.get(
                    "dimensional_requirements"
                )
            )


            if isinstance(
                dimensional_requirements,
                dict
            ):

                result_space[
                    "dimensional_requirements"
                ] = dict(
                    dimensional_requirements
                )


            spaces.append(
                result_space
            )


        # ==================================================
        # EXPLICIT OPTIONAL SPACES
        # ==================================================

        requested_spaces = floor.get(
            "requirements",
            floor.get(
                "spaces",
                []
            )
        )


        if isinstance(
            requested_spaces,
            str
        ):

            requested_spaces = [
                requested_spaces
            ]


        if not isinstance(
            requested_spaces,
            list
        ):

            requested_spaces = []


        requested_names = {

            str(item).lower()

            for item in requested_spaces

            if not isinstance(
                item,
                dict
            )

        }


        existing_types = {

            str(
                item.get(
                    "type"
                )
            ).lower()

            for item in spaces

            if item.get(
                "type"
            )
        }


        for space in program_data.get(
            "optional_spaces",
            []
        ):

            if not isinstance(
                space,
                dict
            ):

                continue


            space_name = space.get(
                "name"
            )


            if not space_name:

                continue


            if (
                str(space_name).lower()
                not in requested_names
            ):

                continue


            program_floor = space.get(
                "floor"
            )


            if (
                program_floor
                and
                floor_role
                and
                str(program_floor).lower()
                !=
                str(floor_role).lower()
            ):

                continue


            if (
                str(space_name).lower()
                in existing_types
            ):

                continue


            result_space = {

                "type":
                    space_name,

                "source":
                    "building_program_knowledge"

            }


            if space.get(
                "zone"
            ) is not None:

                result_space["zone"] = (
                    space.get(
                        "zone"
                    )
                )


            dimensional_requirements = (
                space.get(
                    "dimensional_requirements"
                )
            )


            if isinstance(
                dimensional_requirements,
                dict
            ):

                result_space[
                    "dimensional_requirements"
                ] = dict(
                    dimensional_requirements
                )


            spaces.append(
                result_space
            )

        # ==================================================
        # FLOOR-SPECIFIC RELATIONSHIPS
        # ==================================================

        space_types = {

            str(
                item.get(
                    "type"
                )
            ).lower()

            for item in spaces

            if item.get(
                "type"
            )

        }


        floor_relationships = []


        for relationship in program_data.get(
            "relationships",
            []
        ):

            if not isinstance(
                relationship,
                dict
            ):

                continue


            relationship_from = relationship.get(
                "from"
            )


            relationship_to = relationship.get(
                "to"
            )


            if (
                relationship_from
                and
                relationship_to
                and
                str(
                    relationship_from
                ).lower()
                in space_types
                and
                str(
                    relationship_to
                ).lower()
                in space_types
            ):

                floor_relationships.append(
                    dict(
                        relationship
                    )
                )


        return {

            "level":
                floor.get(
                    "level"
                ),

            "type":
                floor_type,

            "floor_role":
                floor_role,

            "spaces":
                spaces,

            "relationships":
                floor_relationships,

            "source":
                "building_program_knowledge"

        }

    
    # ==================================================
    # REASONING APPLY
    # ==================================================

    def apply_reasoning(
        self,
        program,
        reasoning
    ):

        if not reasoning:

            return program


        additions = reasoning.get(
            "reasoning_additions",
            []
        )


        existing = [

            space.get("type")

            for space in program.get(
                "spaces",
                []
            )

        ]


        for item in additions:


            if item == "mezzanine" and "mezzanine" not in existing:

                program["spaces"].append(

                    {
                        "type":
                            "mezzanine",

                        "source":
                            "architectural_reasoning"

                    }

                )


            if item == "private_terrace" and "terrace" not in existing:

                program["spaces"].append(

                    {
                        "type":
                            "terrace",

                        "source":
                            "architectural_reasoning"

                    }

                )


            if item == "internal_stair" and "internal_stair" not in existing:

                program["spaces"].append(

                    {
                        "type":
                            "internal_stair",

                        "source":
                            "architectural_reasoning"

                    }

                )


        return program



    # ==================================================
    # MAIN
    # ==================================================

    def generate(
        self,
        floor,
        reasoning=None
    ):


        floor_type = floor.get(
            "type"
        )



        if floor_type == "parking":

            program = self.parking_floor(
                floor
            )

            return self.apply_reasoning(
                program,
                reasoning
            )



        if floor_type == "commercial":

            program = self.commercial_floor(
                floor
            )

            return self.apply_reasoning(
                program,
                reasoning
            )



        if floor_type == "residential":

            program = self.residential_floor(
                floor
            )

            return self.apply_reasoning(
                program,
                reasoning
            )



        if floor_type == "duplex":

            program = self.duplex_floor(
                floor
            )

            return self.apply_reasoning(
                program,
                reasoning
            )

        # ==================================================
        # KNOWLEDGE-BACKED TYPOLOGY
        # ==================================================

        program = self.knowledge_floor(
            floor
        )


        if program is not None:

            return self.apply_reasoning(
                program,
                reasoning
            )

        space_types = {

            str(
                item.get(
                    "type"
                )
            ).lower()

            for item in spaces

            if item.get(
                "type"
            )

        }


        floor_relationships = []


        for relationship in program_data.get(
            "relationships",
            []
        ):

            if not isinstance(
                relationship,
                dict
            ):

                continue


            relationship_from = relationship.get(
                "from"
            )


            relationship_to = relationship.get(
                "to"
            )


            if (
                relationship_from
                and
                relationship_to
                and
                str(
                    relationship_from
                ).lower()
                in space_types
                and
                str(
                    relationship_to
                ).lower()
                in space_types
            ):

                floor_relationships.append(
                    dict(
                        relationship
                    )
                )


        return {

            "level":
                floor.get(
                    "level"
                ),

            "type":
                floor_type,

            "spaces":[]

        }