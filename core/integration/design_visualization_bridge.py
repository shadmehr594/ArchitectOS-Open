# ==================================================
# ArchitectOS Design → Visualization Bridge v1.0
# Design Geometry -> DAE Visualization Export
# ==================================================


class DesignVisualizationBridge:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"🎬 Design Visualization Bridge v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # PREPARE VISUALIZATION DATA
    # ==================================================

    def prepare_visualization(
        self,
        design_result
    ):

        design_result = design_result or {}


        return {

            "source":
            "ArchitectOS DesignTool",


            "geometry":
            design_result.get(
                "geometry",
                {}
            ),


            "spatial":
            design_result.get(
                "spatial",
                {}
            ),


            "materials":
            design_result.get(
                "materials",
                {}
            ),


            "facade":
            design_result.get(
                "facade",
                {}
            ),


            "roof":
            design_result.get(
                "roof",
                {}

            )

        }



    # ==================================================
    # EXPORT DAE
    # ==================================================

    def export_dae(
        self,
        design_result
    ):


        from core.visualization.dae_export_adapter import (
            DAEExportAdapter
        )


        visualization_data = (
            self.prepare_visualization(
                design_result
            )
        )


        exporter = DAEExportAdapter()


        result = exporter.export(
            visualization_data
        )


        return {

            "bridge":
            f"DesignVisualizationBridge_v{self.VERSION}",


            "status":
            "completed",


            "input":
            visualization_data,


            "dae_result":
            result

        }