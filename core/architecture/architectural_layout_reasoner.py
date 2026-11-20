"""
ArchitectOS Architectural Layout Reasoner v1.0

Reasoning engine for architectural arrangement.
"""


class ArchitecturalLayoutReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🧠 Architectural Layout Reasoner v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # SPACE PRIORITY
    # ==================================================

    def evaluate_space(
        self,
        space
    ):


        space_type = space.get(
            "type"
        )


        rules = []

        zone = space.get(
            "zone"
        )

        role = space.get(
            "role"
        )


        if space_type in [

            "shop",
            "commercial",
            "entrance"

        ]:

            rules.append(

                "place_near_public_access"

            )



        if space_type in [

            "courtyard",
            "garden"

        ]:

            rules.append(

                "maximize_daylight_connection"

            )



        if space_type in [

            "storage",
            "service"

        ]:

            rules.append(

                "place_away_from_public_flow"

            )



        if space_type in [

            "gym",
            "activity"

        ]:

            rules.append(

                "require_open_circulation"

            )

        # ==================================================
        # ASSEMBLY / CINEMA / AUDITORIUM / AMPHITHEATER
        # ==================================================

        if space_type == "foyer":

            rules.extend(
                [
                    "place_near_public_access",
                    "place_between_entrance_and_audience_circulation"
                ]
            )


        if space_type == "ticketing":

            rules.extend(
                [
                    "place_near_public_access",
                    "place_before_foyer"
                ]
            )


        if space_type == "audience_circulation":

            rules.extend(
                [
                    "connect_foyer_to_assembly_space",
                    "maintain_clear_audience_flow",
                    "protect_assembly_circulation"
                ]
            )


        if space_type in [
            "auditorium",
            "audience_area"
        ]:

            rules.extend(
                [
                    "place_adjacent_to_stage",
                    "connect_to_audience_circulation",
                    "connect_to_egress_circulation",
                    "separate_from_backstage_service_flow"
                ]
            )


        if space_type == "stage":

            rules.extend(
                [
                    "place_adjacent_to_assembly_space",
                    "place_adjacent_to_backstage",
                    "connect_to_performer_circulation",
                    "separate_from_public_entrance_flow"
                ]
            )


        if space_type == "backstage":

            rules.extend(
                [
                    "place_adjacent_to_stage",
                    "connect_to_performer_circulation",
                    "place_away_from_public_flow"
                ]
            )


        if space_type == "performer_entrance":

            rules.extend(
                [
                    "place_away_from_public_entrance",
                    "connect_to_performer_circulation"
                ]
            )


        if space_type == "performer_circulation":

            rules.extend(
                [
                    "connect_performer_entrance_to_backstage",
                    "connect_backstage_to_stage",
                    "protect_performer_service_flow",
                    "separate_from_audience_flow"
                ]
            )


        if space_type == "egress_circulation":

            rules.extend(
                [
                    "connect_directly_to_assembly_space",
                    "maintain_clear_egress_path",
                    "protect_egress_route",
                    "avoid_service_flow_conflict"
                ]
            )


        if space_type == "projection_room":

            rules.extend(
                [
                    "maintain_technical_connection_to_auditorium",
                    "place_away_from_public_flow"
                ]
            )


        if space_type == "control_room":

            rules.extend(
                [
                    "maintain_technical_connection_to_assembly_space",
                    "place_away_from_public_flow"
                ]
            )


        if space_type == "service_access":

            rules.extend(
                [
                    "connect_to_backstage",
                    "place_away_from_public_flow",
                    "protect_service_access"
                ]
            )


        return {

            "space":
                space.get(
                    "id",
                    space.get("name")
                ),

            "type":

                space_type,

            "zone":

                zone,

            "role":

                role,

            "rules":

                rules

        }



    # ==================================================
    # GENERATE LAYOUT DECISIONS
    # ==================================================

    def reason(
        self,
        spaces
    ):


        decisions = []


        for space in spaces:


            decisions.append(

                self.evaluate_space(
                    space
                )

            )


        return decisions