# ==========================================================
# ArchitectOS Design Profile v69.2
# Unified Architectural Design Object
# ==========================================================


class DesignProfile:

    def __init__(

        self,

        style,

        materials,

        design_language,

        lighting,

        negative,

        runtime,

        preserve,

        editable

    ):

        self.style = style

        self.materials = materials

        self.design_language = design_language

        self.lighting = lighting

        self.negative = negative

        self.runtime = runtime

        self.preserve = preserve

        self.editable = editable

    # ======================================================

    def to_dict(self):

        return {

            "style": self.style,

            "materials": self.materials,

            "design_language": self.design_language,

            "lighting": self.lighting,

            "negative": self.negative,

            "runtime": self.runtime,

            "preserve": self.preserve,

            "editable": self.editable

        }

    # ======================================================

    def __repr__(self):

        return str(

            self.to_dict()

        )