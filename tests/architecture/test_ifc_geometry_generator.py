"""
ArchitectOS IFC Geometry Generator Test v1.0
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
    IFCGeometryIntentResolver
)


from core.architecture.bim.ifc_geometry_generator_v1 import (
    IFCGeometryGeneratorV1
)



def test_ifc_geometry_generator():


    print(
        "\n"
        "================================\n"
        "IFC GEOMETRY GENERATOR TEST\n"
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
                    "wall_boundary",

                "height":
                    3.2,

                "thickness":
                    0.25

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
                    "floor_slab",

                "thickness":
                    0.20

            }

        ],



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



    # Geometry → BIM

    bridge = ArchitecturalToBIMElementBridgeV1()


    bim = bridge.convert(
        architectural_geometry
    )



    # BIM Enrichment

    enrichment = BIMEnrichmentBridge()


    enriched = enrichment.enrich(
        bim
    )



    # IFC Mapping

    mapper = IFCMappingBridge()


    ifc = mapper.map(
        enriched
    )



    print(
        "\nIFC ELEMENTS:"
    )


    for element in ifc["ifc_elements"]:

        print(element)



    # Intent Resolution

    resolver = IFCGeometryIntentResolver()


    resolved = resolver.resolve(
        ifc
    )



    print(
        "\nRESOLVED:"
    )


    for element in resolved["geometry_elements"]:

        print(element)



    # Geometry Generation

    generator = IFCGeometryGeneratorV1()


    generated = generator.generate(
        {
            "resolved_geometry":
                resolved["geometry_elements"]
        }
    )



    print(
        "\nGENERATED GEOMETRY:"
    )


    for element in generated["geometry_elements"]:

        print(element)



    assert (
        generated["element_count"]
        ==
        len(
            resolved["geometry_elements"]
        )
    )


    wall = next(
        e for e in generated["geometry_elements"]
        if e["ifc_class"] == "IfcWall"
    )


    slab = next(
        e for e in generated["geometry_elements"]
        if e["ifc_class"] == "IfcSlab"
    )


    assert (
        wall["geometry"]["type"]
        ==
        "wall_extrusion"
    )


    assert (
        slab["geometry"]["type"]
        ==
        "horizontal_slab"
    )


    print(
        "\n✅ IFC GEOMETRY GENERATION PASSED"
    )