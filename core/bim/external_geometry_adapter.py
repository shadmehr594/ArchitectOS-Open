"""
ArchitectOS External Geometry Adapter

Purpose:
Convert external geometry sources
(CAD / IFC / Design adapters)
into BIM Geometry Contract.

No modification to:
- BIM Pipeline
- Structure Engine
- IFC Engine

Only adapter layer.
"""


from core.bim.bim_geometry_contract_normalizer import (
    BIMGeometryContractNormalizer
)



class ExternalGeometryAdapter:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🔌 External Geometry Adapter v1.0 ACTIVE"
        )

        self.normalizer = (
            BIMGeometryContractNormalizer()
        )



    # ==================================================
    # CONVERT EXTERNAL GEOMETRY
    # ==================================================

    def convert(
        self,
        geometry_input
    ):


        geometry_input = (
            geometry_input
            or
            {}
        )


        normalized = self.normalizer.normalize(
            geometry_input
        )


        return {


            "adapter":
            f"ExternalGeometryAdapter_v{self.VERSION}",


            "status":
            "normalized",


            "source":
            geometry_input.get(
                "source",
                "unknown"
            ),


            "rooms":
            normalized.get(
                "rooms",
                []
            ),


            "floors":
            normalized.get(
                "floors",
                []
            )

        }