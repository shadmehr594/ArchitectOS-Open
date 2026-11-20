"""
ArchitectOS IFC Geometry Intent Resolution Test

Tests:
Architectural Geometry
        ↓
BIM
        ↓
IFC Mapping
        ↓
IFC Geometry Intent Resolver
"""


from core.architecture.geometry.architectural_geometry_pipeline_v1 import (
    ArchitecturalGeometryPipelineV1
)


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
    IFCGeometryIntentResolver
)



def test_ifc_geometry_intent_resolution():


    print(
        "\n"
        "================================\n"
        "IFC GEOMETRY INTENT RESOLUTION TEST\n"
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



    # ==============================
    # BIM ENRICHMENT
    # ==============================

    enrichment = BIMEnrichmentBridge()


    enriched = enrichment.enrich(
        bim_data
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
        >
        0
    )



    # ==============================
    # GEOMETRY INTENT RESOLUTION
    # ==============================

    resolver = IFCGeometryIntentResolver()


    resolved = resolver.resolve(
        ifc_data
    )



    print(
        "\nRESOLVED GEOMETRY:"
    )


    for element in resolved["geometry_elements"]:

        print(element)



    assert (
        resolved["element_count"]
        ==
        ifc_data["element_count"]
    )



    # ==============================
    # CHECK WALL
    # ==============================

    wall = next(
        e for e in resolved["geometry_elements"]
        if e["ifc_class"] == "IfcWall"
    )


    assert (
        wall["geometry"]["geometry_type"]
        ==
        "extruded_wall"
    )



    # ==============================
    # CHECK SLAB
    # ==============================

    slab = next(
        e for e in resolved["geometry_elements"]
        if e["ifc_class"] == "IfcSlab"
    )


    assert (
        slab["geometry"]["geometry_type"]
        ==
        "floor"
    )



    # ==============================
    # CHECK STAIR
    # ==============================

    stair = next(
        e for e in resolved["geometry_elements"]
        if e["ifc_class"] == "IfcStair"
    )


    assert (
        stair["geometry"]["geometry_type"]
        ==
        "stair"
    )



    print(
        "\n✅ IFC GEOMETRY INTENT RESOLUTION PASSED"
    )