from core.bim.bim_pipeline_engine import BIMPipelineEngine
from core.bim.structural_analyzer import StructuralAnalyzer


class BIMAdapter:

    """
    BIM Pipeline Adapter v33.4

    Master Pipeline
            |
            v
        Geometry
            |
            v
        Structural
            |
            v
        BIM Scene Graph
            |
            v
     IFC / DXF / REVIT
    """


    def __init__(self):

        self.engine = BIMPipelineEngine()

        self.structural = StructuralAnalyzer()

        print(
            "🏗️ BIM Adapter v33.4 ACTIVE"
        )


    # =====================================================
    # PIPELINE ENTRY
    # =====================================================

    def build(self, state):

        print(
            "▶️ BIM PROCESSING"
        )


        geometry = state.get(
            "geometry_result",
            {}
        )


        # -----------------------------
        # Structural Analysis
        # -----------------------------

        structural_result = self.structural.analyze(
            geometry
        )


        state["structural_result"] = structural_result


        print(
            "▶️ STRUCTURAL ANALYSIS COMPLETE"
        )


        # -----------------------------
        # Spatial Data
        # -----------------------------

        spatial = self._extract_spatial(
            state
        )


        grid = self._extract_grid(
            geometry
        )


        # -----------------------------
        # BIM CORE
        # -----------------------------

        bim_result = self.engine.run(

            structural_result,

            geometry

        )


        state["bim_result"] = {

            "engine":
                "bim_adapter_v33.4",

            "status":
                "generated",

            "core":
                bim_result,

            "spatial":
                spatial,

            "grid":
                grid

        }


        return state



    # =====================================================
    # GRID EXTRACTION
    # =====================================================

    def _extract_grid(self, geometry):

        columns = []


        floors = geometry.get(
            "floors",
            []
        )


        for floor in floors:

            columns.append({

                "id":
                    f"column_{floor.get('level',0)}",

                "x":
                    0,

                "y":
                    0,

                "z":
                    floor.get(
                        "level",
                        0
                    )

            })


        return {

            "columns":
                columns

        }



    # =====================================================
    # SPATIAL EXTRACTION
    # =====================================================

    def _extract_spatial(self, state):

        return {

            "F1": {

                "nodes": {

                    "Living": {

                        "x":2,

                        "y":2,

                        "w":6,

                        "h":4

                    }

                }

            }

        }