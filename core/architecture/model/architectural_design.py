class ArchitecturalDesign:

    VERSION = "1.0"


    def __init__(self):

        self.site_strategy = {}

        self.levels = []

        self.spaces = []

        self.relationships = []

        self.facade_strategy = {}

        self.material_strategy = {}


        # ===============================
        # ARCHITECTURAL INTELLIGENCE
        # ===============================

        self.design_concept = {}

        self.layout = {}

        self.plan_model = {}

        self.form_analysis = {}

        self.massing_analysis = {}

        self.massing_selection = {}

        self.style_analysis = {}

        self.facade_language = {}

        self.facade_assembly = {}

        self.facade_composition = {}

        self.roof_strategy = {}

        self.dome_strategy = {}

        self.boundary_wall = {}

        self.boundary_entrance = {}

        self.landscape_strategy = {}

        self.exterior_details = {}


        # ===============================
        # SPATIAL CONTRACT
        # ===============================

        self.architectural_spatial_contract = {}


        # ===============================
        # BIM INTENT
        # ===============================

        self.exterior_bim = {}

        self.bim_enriched = {}

        self.ifc_mapping = {}

        self.geometry_resolution = {}



    def add_space(
        self,
        space
    ):

        self.spaces.append(space)



    def add_level(
        self,
        level
    ):

        self.levels.append(level)



    def to_dict(self):

        return {

            "site_strategy":
                self.site_strategy,

            "levels":
                self.levels,

            "spaces":
                self.spaces,

            "relationships":
                self.relationships,

            "facade_strategy":
                self.facade_strategy,

            "material_strategy":
                self.material_strategy

        }