"""
ArchitectOS Architectural Geometry Pipeline v1.0

Connects architectural placement,
geometry intent generation,
geometry generation,
and facade/material intelligence.
"""


from core.architecture.geometry.architectural_geometry_intent_generator_v1 import (
    ArchitecturalGeometryIntentGeneratorV1
)


from core.architecture.geometry.architectural_geometry_engine_v2 import (
    ArchitecturalGeometryEngineV2
)


from core.architecture.geometry.facade_material_bridge_v1 import (
    FacadeMaterialBridgeV1
)

from core.architecture.bim.architectural_to_bim_element_bridge_v1 import (
    ArchitecturalToBIMElementBridgeV1
)


from core.architecture.bim.bim_enrichment_bridge import (
    BIMEnrichmentBridge
)



class ArchitecturalGeometryPipelineV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"📐 Architectural Geometry Pipeline v{self.VERSION} ACTIVE"
        )


        self.intent_generator = (
            ArchitecturalGeometryIntentGeneratorV1()
        )


        self.geometry_engine = (
            ArchitecturalGeometryEngineV2()
        )


        self.facade_bridge = (
            FacadeMaterialBridgeV1()
        )


        self.geometry_to_bim = (
            ArchitecturalToBIMElementBridgeV1()
        )


        self.bim_enrichment = (
            BIMEnrichmentBridge()
        )



    # ==================================
    # GENERATE ARCHITECTURAL GEOMETRY
    # ==================================

    def generate(
        self,
        placement_output,
        facade_context=None,
        roof_strategy=None,
        vertical_section=None
    ):


        # -------------------------------
        # Geometry Intent
        # -------------------------------

        geometry_intent = (
            self.intent_generator.generate(
                placement_output,
                roof_strategy=roof_strategy,
                vertical_section=vertical_section
            )
        )



        # -------------------------------
        # Geometry Generation
        # -------------------------------

        geometry = (
            self.geometry_engine.generate(
                geometry_intent
            )
        )

        architectural_bim = (
            self.geometry_to_bim.convert(
                geometry
            )
        )


        enriched_bim = (
            self.bim_enrichment.enrich(
                architectural_bim
            )
        )



        # -------------------------------
        # Facade + Materials
        # -------------------------------

        facade = (
            self.facade_bridge.resolve(
                facade_context or {}
            )
        )



        return {


            "version":
                self.VERSION,


            "geometry_intent":
                geometry_intent,


            "geometry":
                geometry,


            "architectural_bim":
                architectural_bim,


            "enriched_bim":
                enriched_bim,


            "facade":
                facade,


            "bim_ready":
                True

        }
