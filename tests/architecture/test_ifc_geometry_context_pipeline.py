"""
ArchitectOS IFC Geometry Context Pipeline Test

Architecture Intelligence
        |
        v
Geometry
        |
        v
BIM
        |
        v
IFC Mapping
        |
        v
IFC Geometry Intent
        |
        v
IFC Geometry Parameters
        |
        v
IFC Geometry
"""


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



def test_ifc_geometry_context_pipeline():


    print(
        "\n"
        "================================\n"
        "IFC GEOMETRY CONTEXT PIPELINE TEST\n"
        "================================\n"
    )



    # ==================================
    # ARCHITECTURAL GEOMETRY
    # ==================================

    architectural_geometry = {


        "spaces":

        [

            {

                "name":
                    "Main_Hall",

                "floor":
                    "F1",

                "type":
                    "room_volume",

                "height":
                    None

            }

        ],



        "boundaries":

        [

            {

                "space":
                    "Main_Hall",

                "floor":
                    "F1",

                "type":
                    "wall_boundary"

            }

        ],



        "slabs":

        [

            {

                "space":
                    "Main_Hall",

                "floor":
                    "F1",

                "type":
                    "floor_slab"

            }

        ],



        "openings":
            [],



        "vertical_geometry":
            []

    }



    # ==================================
    # GEOMETRY → BIM
    # ==================================

    geometry_bridge = (
        ArchitecturalToBIMElementBridgeV1()
    )


    bim = geometry_bridge.convert(
        architectural_geometry
    )


    assert (
        bim["element_count"]
        >
        0
    )



    # ==================================
    # BIM ENRICHMENT
    # ==================================

    enrichment = BIMEnrichmentBridge()


    enriched = enrichment.enrich(
        bim
    )


    assert (
        enriched["element_count"]
        ==
        bim["element_count"]
    )



    # ==================================
    # IFC MAPPING
    # ==================================

    mapper = IFCMappingBridge()


    ifc = mapper.map(
        enriched
    )


    assert (
        ifc["element_count"]
        >
        0
    )



    # ==================================
    # GEOMETRY INTENT
    # ==================================

    intent_resolver = (
        IFCGeometryIntentResolverV1()
    )


    resolved = intent_resolver.resolve(
        ifc
    )

    print(
        "\n=== RESOLVED KEYS ==="
    )

    print(
        resolved.keys()
    )

    print(
        "\nRESOLVER OUTPUT:"
    )

    print(
        resolved
    )


    assert (
        resolved["element_count"]
        ==
        ifc["element_count"]
    )



    # ==================================
    # CONTEXT PARAMETERS
    # ==================================

    context = {


        "floor_height":
            3.6,


        "wall_thickness":
            0.30,


        "slab_thickness":
            0.25,


        "level_elevations":
        {

            "F1":
                0.0

        },


        "wall_profile":
            "rectangular",


        "default_direction":
            [0,0,1]

    }



    parameter_resolver = IFCGeometryParameterResolverV1(
        context=context
    )


    parameters = parameter_resolver.resolve(
        resolved["geometry_elements"]
    )


    assert (
        parameters["element_count"]
        ==
        resolved["element_count"]
    )



    # ==================================
    # IFC GEOMETRY GENERATION
    # ==================================

    generator = IFCGeometryGeneratorV1()


    geometry = generator.generate(
        parameters["geometry_parameters"]
    )


    assert (
        geometry["element_count"]
        ==
        parameters["element_count"]
    )



    print(
        "\n✅ FULL IFC GEOMETRY CONTEXT PIPELINE PASSED"
    )