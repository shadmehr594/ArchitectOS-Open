class ArchitecturalDecisionEngine:

    VERSION = "1.0"


    def __init__(self):

        print(
            "🧭 ARCHITECTURAL DECISION ENGINE v1.0 ONLINE"
        )


    def analyze(
        self,
        plan_model,
        site_analysis,
        design_concept
    ):


        if hasattr(plan_model, "to_dict"):

            plan_data = plan_model.to_dict()

        else:

            plan_data = plan_model

        decisions = {

            "mass_strategy": [],

            "spatial_strategy": [],

            "circulation_strategy": [],

            "environmental_strategy": [],

            "privacy_strategy": [],

            "facade_strategy": [],

            "vertical_strategy": []

        }


        zones = plan_data.get(
            "zones",
            {}
        )

        floor_distribution = plan_data.get(
            "floor_distribution",
            {}
        )


        relationships = plan_data.get(
            "relationships",
            []
        )


        # -----------------------------
        # VERTICAL ORGANIZATION LOGIC
        # -----------------------------

        if floor_distribution:

            decisions["vertical_strategy"].append(
                "vertical_organization_should_follow_program_distribution"
            )


        # -----------------------------
        # MASSING LOGIC
        # -----------------------------

        if zones.get("external"):

            decisions["mass_strategy"].append(
                "building should preserve meaningful outdoor relationships"
            )


        # -----------------------------
        # SPACE ORGANIZATION
        # -----------------------------

        if zones.get("public"):

            decisions["spatial_strategy"].append(
                "public spaces should form the social core of the building"
            )


        if zones.get("private"):

            decisions["privacy_strategy"].append(
                "private spaces should be separated from public activity"
            )


        # -----------------------------
        # RELATIONSHIPS
        # -----------------------------

        if relationships:

            decisions["spatial_strategy"].append(
                "spaces should be organized based on architectural relationships"
            )


        # -----------------------------
        # SITE RESPONSE
        # -----------------------------

        if site_analysis:

            decisions["environmental_strategy"].append(
                "design should respond to orientation, climate and site conditions"
            )


        # -----------------------------
        # FACADE
        # -----------------------------

        decisions["facade_strategy"].append(
            "facade expression should reflect architectural concept and climate response"
        )


        return decisions