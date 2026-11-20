class ArchitecturalIntent:

    VERSION = "1.0"


    def __init__(
        self,
        building_type,
        area,
        floors,
        style=None,
        requirements=None,
        budget=None
    ):

        self.building_type = building_type

        self.area = area

        self.floors = floors

        self.style = style

        self.requirements = (
            requirements or []
        )

        self.budget = budget


    def to_dict(self):

        return {

            "building_type":
                self.building_type,

            "area":
                self.area,

            "floors":
                self.floors,

            "style":
                self.style,

            "requirements":
                self.requirements,

            "budget":
                self.budget

        }