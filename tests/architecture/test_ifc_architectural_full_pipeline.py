"""
ArchitectOS Architectural IFC Full Pipeline Test

Architecture Intelligence
        |
        v
BIM
        |
        v
IFC
        |
        v
Real Architectural IFC Model
"""

import ifcopenshell


from core.architecture.bim.architectural_to_bim_element_bridge_v1 import (
    ArchitecturalToBIMElementBridgeV1
)

from core.architecture.bim.bim_enrichment_bridge import (
    BIMEnrichmentBridge
)

from core.architecture.bim.ifc_mapping_bridge import (
    IFCMappingBridge
)

from core.architecture.bim.ifc_geometry_intent_resolver import (
    IFCGeometryIntentResolverV1
)

from core.architecture.bim.ifc_geometry_parameter_resolver_v1 import (
    IFCGeometryParameterResolverV1
)

from core.architecture.bim.ifc_geometry_generator_v1 import (
    IFCGeometryGeneratorV1
)

from core.architecture.bim.ifc_entity_builder_v1 import (
    IFCEntityBuilderV1
)

from core.architecture.bim.ifc_geometry_attachment_v1 import (
    IFCGeometryAttachmentV1
)

from core.architecture.bim.ifc_real_solid_builder_v1 import (
    IFCRealSolidBuilderV1
)

from core.architecture.bim.ifc_representation_finalizer_v1 import (
    IFCRepresentationFinalizerV1
)

from core.architecture.bim.ifc_spatial_structure_builder_v1 import (
    IFCSpatialStructureBuilderV1
)

from core.architecture.bim.ifc_element_placement_builder_v1 import (
    IFCElementPlacementBuilderV1
)


def test_ifc_architectural_full_pipeline():


    print(
        "\n"
        "================================\n"
        "IFC ARCHITECTURAL FULL PIPELINE TEST\n"
        "================================\n"
    )


    # ===============================
    # ARCHITECTURAL INPUT
    # ===============================

    architectural_geometry = {


        "spaces": [

            {
                "name": "Main_Hall",
                "floor": "F1",
                "type": "room_volume",
                "height": 3.2
            }

        ],


        "boundaries": [

            {
                "space": "Main_Hall",
                "floor": "F1",
                "type": "wall_boundary"
            }

        ],


        "slabs": [

            {
                "space": "Main_Hall",
                "floor": "F1",
                "type": "floor_slab"
            }

        ],


        "openings": [],


        "vertical_geometry": []

    }


    # ===============================
    # GEOMETRY → BIM
    # ===============================

    bim = (
        ArchitecturalToBIMElementBridgeV1()
        .convert(
            architectural_geometry
        )
    )


    assert bim["element_count"] > 0



    # ===============================
    # BIM ENRICHMENT
    # ===============================

    enriched = (
        BIMEnrichmentBridge()
        .enrich(
            bim
        )
    )


    # ===============================
    # IFC MAPPING
    # ===============================

    ifc = (
        IFCMappingBridge()
        .map(
            enriched
        )
    )


    # ===============================
    # GEOMETRY PIPELINE
    # ===============================

    resolved = (
        IFCGeometryIntentResolverV1()
        .resolve(
            ifc
        )
    )


    parameters = (
        IFCGeometryParameterResolverV1(
            context={
                "floor_height":3.2,
                "wall_thickness":0.25,
                "slab_thickness":0.20,
                "level_elevations":{
                    "F1":0.0
                },
                "wall_profile":"rectangular",
                "default_direction":[0,0,1]
            }
        )
        .resolve(
            resolved["geometry_elements"]
        )
    )


    geometry = (
        IFCGeometryGeneratorV1()
        .generate(
            parameters["geometry_parameters"]
        )
    )


    # ===============================
    # IFC BUILD
    # ===============================

    entities = (
        IFCEntityBuilderV1()
        .build(
            geometry["geometry_elements"]
        )
    )


    attached = (
        IFCGeometryAttachmentV1(
            entities["ifc_model"]
        )
        .attach(
            entities["entities"],
            geometry["geometry_elements"]
        )
    )


    solid_builder = IFCRealSolidBuilderV1(
        entities["ifc_model"]
    )

    solids = []

    for entity in attached["entities"]:

        entity_geometry = None

        for item in geometry["geometry_elements"]:

            if item["name"] == entity.Name:
                entity_geometry = item["geometry"]
                break


        if entity_geometry:

            solid = solid_builder.build(
                entity,
                entity_geometry
            )

            if solid:

                solids.append(
                    (
                        entity,
                        solid
                    )
                )


    finalizer = IFCRepresentationFinalizerV1(
        entities["ifc_model"]
    )

    final = []

    for entity, solid in solids:

        result = finalizer.finalize(
            entity,
            solid
        )

        final.append(
            result
        )


    # ===============================
    # SPATIAL
    # ===============================

    spatial = (
        IFCSpatialStructureBuilderV1(
            entities["ifc_model"]
        )
        .build()
    )


    # ===============================
    # PLACEMENT
    # ===============================


    placement = (
        IFCElementPlacementBuilderV1()
        .build(
            geometry["geometry_elements"]
        )
    )


    assert placement is not None


    print(
        "\n✅ FULL ARCHITECTURAL IFC PIPELINE PASSED"
    )