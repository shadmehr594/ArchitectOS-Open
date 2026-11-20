class ArchitecturalPlanModel:

    VERSION = "1.1"

    def __init__(self):

        self.spaces = []

        self.relationships = []

        self.planning_logic = []

        self.zones = {}

        self.floor_distribution = {}

        self.space_registry = []

        self.site_response = {}

        self.design_strategy = {}

        self.program_area_basis = {}

    # ==================================================
    # SPACE
    # ==================================================

    def add_space(
        self,
        space
    ):

        self.spaces.append(
            space
        )

    # ==================================================
    # RELATIONSHIP
    # ==================================================

    def add_relationship(
        self,
        relationship
    ):

        self.relationships.append(
            relationship
        )

    # ==================================================
    # PLANNING LOGIC
    # ==================================================

    def add_logic(
        self,
        logic
    ):

        if logic not in self.planning_logic:

            self.planning_logic.append(
                logic
            )

    # ==================================================
    # SERIALIZATION
    # ==================================================

    def to_dict(
        self
    ):

        return {

            "spaces":
                self.spaces,

            "relationships":
                self.relationships,

            "planning_logic":
                self.planning_logic,

            "zones":
                self.zones,

            "floor_distribution":
                self.floor_distribution,

            "space_registry":
                self.space_registry,

            "site_response":
                self.site_response,

            "design_strategy":
                self.design_strategy,

            "program_area_basis":
                self.program_area_basis

        }