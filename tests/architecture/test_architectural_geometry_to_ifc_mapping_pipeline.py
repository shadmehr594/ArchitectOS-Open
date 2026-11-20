"""
ArchitectOS Architectural Geometry To IFC Mapping Pipeline Test

Tests:

Architectural Geometry
        ->
Architectural To BIM Element Bridge
        ->
BIM Enrichment
        ->
IFC Mapping
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



def test_architectural_geometry_to_ifc_mapping_pipeline():


    print(
        "\n"
        "================================\n"
        "ARCHITECTURAL GEOMETRY TO IFC MAPPING TEST\n"
        "================================\n"
    )



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

                "shape":
                    "open_rectangular_space",

                "height":
                    3.2

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

        [

            {

                "name":
                    "stairs",

                "type":
                    "stair_geometry",

                "continuous":
                    True

            }

        ]

    }



    # ==============================
    # GEOMETRY → BIM
    # ==============================

    geometry_bridge = (
        ArchitecturalToBIMElementBridgeV1()
    )


    bim_data = geometry_bridge.convert(
        architectural_geometry
    )


    print(
        "\nBIM ELEMENTS:"
    )


    for element in bim_data["bim_elements"]:

        print(element)



    assert (
        bim_data["element_count"] > 0
    )



    # ==============================
    # BIM ENRICHMENT
    # ==============================

    enrichment = BIMEnrichmentBridge()


    enriched = enrichment.enrich(
        bim_data
    )


    print(
        "\nENRICHED BIM:"
    )


    for element in enriched["bim_elements"]:

        print(element)



    assert (
        enriched["element_count"]
        ==
        bim_data["element_count"]
    )



    # ==============================
    # IFC MAPPING
    # ==============================

    mapper = IFCMappingBridge()


    ifc_data = mapper.map(
        enriched
    )


    print(
        "\nIFC ELEMENTS:"
    )


    for element in ifc_data["ifc_elements"]:

        print(element)



    assert (
        ifc_data["element_count"]
        ==
        enriched["element_count"]
    )



    assert (
        ifc_data["source"]
        ==
        "ifc_mapping_v2"
    )



    print(
        "\n✅ ARCHITECTURAL GEOMETRY → IFC MAPPING PASSED"
    )