# ==================================================
# ArchitectOS IFC Import Adapter v1.0
# IFC File -> BIM Context
# ==================================================


class IFCImportAdapter:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"🧬 IFC Import Adapter v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # MAIN ENTRY
    # ==================================================

    def load(
        self,
        ifc_data=None
    ):


        ifc_data = ifc_data or {}


        return {

            "type":
            "ifc",


            "schema":
            ifc_data.get(
                "schema",
                "IFC4"
            ),


            "source":
            "IFC Import",


            "site":
            ifc_data.get(
                "site",
                {}
            ),


            "geometry":
            ifc_data.get(
                "geometry",
                {}
            ),


            "elements":
            ifc_data.get(
                "elements",
                [])


        }