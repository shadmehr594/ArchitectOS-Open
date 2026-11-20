from core.architecture.reasoning.space_identity_mapper import (
    SpaceIdentityMapper
)


class FloorProgramKnowledgeAdapter:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"🧩 FLOOR PROGRAM KNOWLEDGE ADAPTER v{self.VERSION} ONLINE"
        )

        self.identity_mapper = SpaceIdentityMapper()


    # ==================================================
    # ZONE RESOLUTION
    # ==================================================

    def resolve_zone(
        self,
        space_type
    ):

        zone_map = {

            # ------------------------------------------
            # PUBLIC / COMMERCIAL
            # ------------------------------------------

            "shop":
                "public",

            "mezzanine":
                "public",

            "street_frontage":
                "public",


            # ------------------------------------------
            # SERVICE
            # ------------------------------------------

            "parking_area":
                "service",

            "storage":
                "service",

            "wc":
                "service",

            "caretaker":
                "service",

            "ducts":
                "service",


            # ------------------------------------------
            # CIRCULATION
            # ------------------------------------------

            "corridor":
                "circulation",

            "stair":
                "circulation",

            "stairs":
                "circulation",

            "elevator":
                "circulation",

            "core":
                "circulation",

            "internal_stair":
                "circulation",


            # ------------------------------------------
            # ENVIRONMENTAL / VOID
            # ------------------------------------------

            "lightwell":
                "environmental",


            # ------------------------------------------
            # RESIDENTIAL PROGRAM CONTAINER
            # ------------------------------------------

            "unit_cluster":
                "private",


            # ------------------------------------------
            # EXTERNAL
            # ------------------------------------------
            "entrance":
                "public",

            "ticketing":
                "public",

            "foyer":
                "public",

            "auditorium":
                "public",

            "audience_area":
                "external",

            "stage":
                "performance",

            "backstage":
                "service",

            "performer_entrance":
                "service",

            "performer_circulation":
                "service",

            "projection_room":
                "service",

            "control_room":
                "service",

            "service_access":
                "service",

            "audience_circulation":
                "circulation",

            "egress_circulation":
                "circulation",

            "terrace":
                "external"

        }

        return zone_map.get(
            space_type,
            "unclassified"
        )


    # ==================================================
    # ROLE RESOLUTION
    # ==================================================

    def resolve_role(
        self,
        space_type
    ):

        if space_type in {
            "corridor",
            "stair",
            "stairs",
            "elevator",
            "core",
            "internal_stair"
        }:

            return "circulation"


        if space_type in {
            "ducts"
        }:

            return "service_infrastructure"


        if space_type == "lightwell":

            return "environmental_void"


        if space_type == "unit_cluster":

            return "program_container"


        if space_type == "parking_area":

            return "parking"

        if space_type in {
            "entrance",
            "ticketing",
            "foyer"
        }:

            return "public_access"


        if space_type in {
            "auditorium",
            "audience_area"
        }:

            return "assembly_space"


        if space_type == "stage":

            return "performance_space"


        if space_type in {
            "backstage",
            "performer_entrance",
            "performer_circulation"
        }:

            return "performer_support"


        if space_type in {
            "projection_room",
            "control_room"
        }:

            return "technical_support"


        if space_type == "service_access":

            return "service_access"


        if space_type == "audience_circulation":

            return "assembly_circulation"


        if space_type == "egress_circulation":

            return "egress"


        return "space"


    # ==================================================
    # PROTECTED ZONE RESOLUTION
    # ==================================================

    def resolve_protected_zone(
        self,
        space_type
    ):

        return space_type in {

            "corridor",

            "stair",
            "stairs",

            "elevator",
            "core",

            "internal_stair",

            "lightwell",

            "ducts",

            "audience_circulation",

            "egress_circulation",

            "performer_circulation",

            "service_access"

        }

    def resolve_circulation_profile(
        self,
        space
    ):

        dimensional_requirements = space.get(
            "dimensional_requirements",
            {}
        )

        space_type = space.get(
            "type"
        )


        if space_type in {
            "corridor",
            "stairs",
            "stair",
            "elevator",
            "core"
        }:

            width = dimensional_requirements.get(
                "preferred_width"
            )

            if width:

                return {
                    "resolved_width": width,
                    "source": "dimensional_requirements",
                    "status": "resolved"
                }


        return None


    # ==================================================
    # ADAPT SPACE
    # ==================================================

    def adapt_space(
        self,
        space,
        floor_program
    ):

        space_type = space.get(
            "type"
        )


        level = floor_program.get(
            "level"
        )


        floor_type = floor_program.get(
            "type"
        )


        canonical_name = (
            self.identity_mapper.canonicalize(
                space_type
            )
        )


        result = {

            "name":
                space_type,

            "canonical_name":
                canonical_name,

            "space_type":
                space_type,

            "floor":
                level,

            "floor_type":
                floor_type,

            "zone":
                self.resolve_zone(
                    space_type
                ),

            "planning_zone":
                self.resolve_zone(
                    space_type
                ),

            "role":
                self.resolve_role(
                    space_type
                ),

            "protected_zone":
                self.resolve_protected_zone(
                    space_type
                ),

            "circulation_profile":
                self.resolve_circulation_profile(
                    space
                ),

            "source":
                space.get(
                    "source",
                    "floor_program"
                )

        }


        if "count" in space:

            result["count"] = space[
                "count"
            ]


        if "dimensional_requirements" in space:

            result[
                "dimensional_requirements"
            ] = dict(
                space[
                    "dimensional_requirements"
                ]
            )


        return result


    # ==================================================
    # MAIN
    # ==================================================

    def adapt(
        self,
        floor_programs
    ):

        generated_spaces = []

        floor_metadata = {}

        for floor_program in floor_programs:

            if not isinstance(
                floor_program,
                dict
            ):

                continue

            level = floor_program.get(
                "level"
            )


            if level is not None:

                floor_metadata[
                    level
                ] = {

                    "level":
                        level,

                    "type":
                        floor_program.get(
                            "type"
                        ),

                    "height":
                        floor_program.get(
                            "height"
                        ),

                    "height_source":
                        floor_program.get(
                            "height_source"
                        ),

                    "height_status":
                        floor_program.get(
                            "height_status"
                        ),

                    "role":
                        floor_program.get(
                            "role"
                        ),

                    "constraints":
                        dict(
                            floor_program.get(
                                "constraints",
                                {}
                            )
                        )
                        if isinstance(
                            floor_program.get(
                                "constraints"
                            ),
                            dict
                        )
                        else {}

                }


            for space in floor_program.get(
                "spaces",
                []
            ):

                if not isinstance(
                    space,
                    dict
                ):

                    continue


                if not space.get(
                    "type"
                ):

                    continue


                generated_spaces.append(
                    self.adapt_space(
                        space,
                        floor_program
                    )
                )


        return {

            "engine":
                "FLOOR_PROGRAM_KNOWLEDGE_ADAPTER",

            "version":
                self.VERSION,

            "generated_spaces":
                generated_spaces,

            "floor_metadata":
                floor_metadata,

            "space_count":
                len(
                    generated_spaces
                )

        }