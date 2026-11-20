"""
ArchitectOS Architectural IFC Exporter V2

Full Pipeline:

Architectural Geometry
        |
        v
BIM
        |
        v
IFC Mapping
        |
        v
IFC Geometry
        |
        v
IFC Entities
        |
        v
Real IFC Export
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

from core.architecture.bim.ifc_element_placement_builder_v1 import (
    IFCElementPlacementBuilderV1
)

from core.architecture.bim.ifc_spatial_structure_builder_v1 import (
    IFCSpatialStructureBuilderV1
)


class ArchitecturalIFCExporterV2:


    VERSION = "2.0"


    def __init__(self):

        print(
            f"🏛 ARCHITECTURAL IFC EXPORTER v{self.VERSION} ONLINE"
        )


    def export(
        self,
        architectural_geometry,
        path
    ):

        # ===============================
        # SEMANTIC CONTEXT
        # ===============================

        from core.architecture.bim.architectural_semantic_context_v1 import (
            ArchitecturalSemanticContextV1
        )


        semantic_context = ArchitecturalSemanticContextV1(
            architectural_geometry
        ).build()


        print(
            "\n=== SEMANTIC CONTEXT DEBUG ==="
        )


        print(
            "Spaces:",
            len(
                semantic_context["spaces"]
            )
        )


        print(
            "Elements:",
            len(
                semantic_context["elements"]
            )
        )


        # ===============================
        # ARCHITECTURE -> BIM
        # ===============================

        bim = (
            ArchitecturalToBIMElementBridgeV1()
            .convert(
                architectural_geometry
            )
        )


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

        mapped = (
            IFCMappingBridge()
            .map(
                enriched
            )
        )


        # ===============================
        # GEOMETRY INTENT
        # ===============================

        resolved = (
            IFCGeometryIntentResolverV1()
            .resolve(
                mapped
            )
        )


        # ===============================
        # PARAMETERS
        # ===============================

        parameters = (
            IFCGeometryParameterResolverV1(
                context={
                    "floor_height":3.2,
                    "wall_thickness":0.25,
                    "slab_thickness":0.20,
                    "level_elevations":{
                    "F1":0.0,
                    "F2":3.2,
                    "F3":6.4
                    }
                }
            )
            .resolve(
                resolved["geometry_elements"]
            )
        )


        # ===============================
        # GEOMETRY
        # ===============================

        geometry = (
            IFCGeometryGeneratorV1()
            .generate(
                parameters
            )
        )


        # ===============================
        # IFC ENTITIES
        # ===============================

        entities = (
            IFCEntityBuilderV1()
            .build(
                geometry["geometry_elements"]
            )
        )


        model = entities["ifc_model"]


        # ===============================
        # SPATIAL STRUCTURE
        # ===============================

        spatial_builder = IFCSpatialStructureBuilderV1(
            model
        )

        spatial = spatial_builder.build()


        # ===============================
        # ATTACH GEOMETRY
        # ===============================

        attached = (
            IFCGeometryAttachmentV1(
                model
            )
            .attach(
                entities["entities"],
                geometry["geometry_elements"]
            )
        )


        # ===============================
        # SOLIDS
        # ===============================

        solid_builder = IFCRealSolidBuilderV1(
            model
        )


        solids = []


        for entity in attached["entities"]:

            for item in geometry["geometry_elements"]:

                if item["name"] == entity.Name:

                    solid = solid_builder.build(
                        entity,
                        item["geometry"]
                    )

                    if solid:
                        solids.append(
                            (
                                entity,
                                solid
                            )
                        )


        # ===============================
        # REPRESENTATION
        # ===============================

        finalizer = IFCRepresentationFinalizerV1(
            model
        )


        for entity, solid in solids:

            finalizer.finalize(
                entity,
                solid
            )

        # ===============================
        # MATERIAL LAYERS
        # ===============================

        from core.architecture.bim.ifc_material_layer_builder_v1 import (
            IFCMaterialLayerBuilderV1
        )


        material_builder = IFCMaterialLayerBuilderV1(
            model
        )


        material_builder.build()

        # ===============================
        # PROPERTY SETS
        # ===============================

        from core.architecture.bim.ifc_property_set_builder_v1 import (
            IFCPropertySetBuilderV1
        )


        property_builder = IFCPropertySetBuilderV1(
            model
        )


        property_builder.build()


        # ===============================
        # CONTAINMENT
        # ===============================

        from core.architecture.bim.ifc_containment_builder_v1 import (
            IFCContainmentBuilderV1
        )


        containment_builder = IFCContainmentBuilderV1(
            model,
            semantic_context,
            entity_levels=entities.get(
                "entity_levels",
                {}
            )
        )

        print("\n=== IFC CONTAINMENT DEBUG ===")

        for space in model.by_type("IfcSpace"):

            print(
                "SPACE:",
                space.Name
            )


        for storey in model.by_type("IfcBuildingStorey"):

            print(
                "STOREY:",
                storey.Name
            )


        containment_builder.build(
            semantic_context=semantic_context,
            entity_levels=entities.get(
                "entity_levels",
                {}
            )
        )


        # ===============================
        # TYPE SYSTEM
        # ===============================

        from core.architecture.bim.ifc_type_system_builder_v1 import (
            IFCTypeSystemBuilderV1
        )


        type_builder = IFCTypeSystemBuilderV1(
            model
        )


        type_builder.build()

        # ===============================
        # SPACE BOUNDARIES
        # ===============================

        from core.architecture.bim.ifc_space_boundary_builder_v1 import (
            IFCSpaceBoundaryBuilderV1
        )


        boundary_builder = IFCSpaceBoundaryBuilderV1(
            model
        )


        boundary_builder.build()

        # ===============================
        # OPENING RELATIONSHIPS
        # ===============================

        from core.architecture.bim.ifc_opening_relationship_builder_v1 import (
            IFCOpeningRelationshipBuilderV1
        )


        opening_builder = IFCOpeningRelationshipBuilderV1(
            model
        )


        opening_builder.build()


        # ===============================
        # IFC ELEMENT PLACEMENT
        # ===============================


        # --------------------------------
        # BUILD ENTITY -> LEVEL MAP
        # --------------------------------

        entity_levels = {}


        for item in geometry["geometry_elements"]:


            entity_levels[item["name"]] = item.get(
                "level",
                "F1"
            )



        # --------------------------------
        # BUILD LEVEL ELEVATIONS
        # --------------------------------

        levels = set(
            entity_levels.values()
        )


        level_elevations = {}


        floor_height = 3.2


        for level in levels:


            try:

                floor_number = int(
                    level.replace(
                        "F",
                        ""
                    )
                )


                level_elevations[level] = (
                    floor_number - 1
                ) * floor_height


            except Exception:


                level_elevations[level] = 0.0



        # --------------------------------
        # PLACEMENT BUILDER
        # --------------------------------

        placement_builder = IFCElementPlacementBuilderV1(
            {
                "level_elevations":
                    level_elevations
            }
        )



        # --------------------------------
        # ATTACH PLACEMENT
        # --------------------------------

        for entity in attached["entities"]:


            level = entity_levels.get(
                entity.Name,
                "F1"
            )


            placement = (
                placement_builder.resolve_placement(
                    level
                )
            )


            placement_builder.attach(
                entity,
                placement
            )


        # ===============================
        # WRITE IFC
        # ===============================

        model.write(
            path
        )


        return {

            "path": path,

            "entity_count":
                len(
                    entities["entities"]
                ),

            "model":
                model

        }