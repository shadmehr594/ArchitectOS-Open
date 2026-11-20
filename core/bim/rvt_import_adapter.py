# ==================================================
# ArchitectOS RVT Import Adapter v1.0
# RVT File -> BIM Context
# ==================================================


class RVTImportAdapter:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"🏢 RVT Import Adapter v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # MAIN ENTRY
    # ==================================================

    def load(
        self,
        rvt_data
    ):

        rvt_data = rvt_data or {}


        return {

            "type":
            "rvt",


            "source":
            "RVT Import",


            "format":
            "Autodesk Revit",


            "project":
            rvt_data.get(
                "project",
                {}
            ),


            "levels":
            rvt_data.get(
                "levels",
                []
            ),


            "elements":
            rvt_data.get(
                "elements",
                []
            ),


            "geometry":
            rvt_data.get(
                "geometry",
                {}
            )

        }