# ==========================================================
# ArchitectOS Building Analysis v70
# Standard Building Understanding Object
# ==========================================================


class BuildingAnalysis:


    def __init__(
        self,
        floors=0,
        facade_material=None,
        roof_type=None,
        balconies=False,
        columns=False,
        glazing_ratio=0.0,
        detected_style=None,
        preserve_elements=None
    ):

        self.floors = floors

        self.facade_material = facade_material

        self.roof_type = roof_type

        self.balconies = balconies

        self.columns = columns

        self.glazing_ratio = glazing_ratio

        self.detected_style = detected_style

        self.preserve_elements = (
            preserve_elements
            if preserve_elements
            else []
        )


    def to_dict(self):

        return {

            "floors":
                self.floors,

            "facade_material":
                self.facade_material,

            "roof_type":
                self.roof_type,

            "balconies":
                self.balconies,

            "columns":
                self.columns,

            "glazing_ratio":
                self.glazing_ratio,

            "detected_style":
                self.detected_style,

            "preserve_elements":
                self.preserve_elements

        }


    def __repr__(self):

        return str(
            self.to_dict()
        )