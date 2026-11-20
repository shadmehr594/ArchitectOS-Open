from core.intelligence.vertical_circulation_network_engine import (
    VerticalCirculationNetworkEngine
)

from core.intelligence.vertical_program_integration_engine import (
    VerticalProgramIntegrationEngine
)

from core.spatial.vertical_spatial_layout_engine import (
    VerticalSpatialLayoutEngine
)

from core.geometry.vertical_geometry_integration_engine import (
    VerticalGeometryIntegrationEngine
)

from core.bim.semantic_vertical_mapping_engine import (
    SemanticBIMVerticalMappingEngine
)



def test_full_bim_vertical_integration():


    print(
        "\n🔗 FULL BIM VERTICAL INTEGRATION v1.0 ACTIVE"
    )



    # ---------------------------------
    # 1. NETWORK
    # ---------------------------------

    network_engine = VerticalCirculationNetworkEngine()


    network = network_engine.analyze(

        {

            "building_type":
                "shopping_center",

            "floors":
                6,

            "basement":
                2,

            "public_flow":
                "high",

            "parking":
                True,

            "wheelchair_access":
                True

        }

    )



    # ---------------------------------
    # 2. PROGRAM
    # ---------------------------------

    program_engine = VerticalProgramIntegrationEngine()



    program = {


        "level":
            "G",


        "type":
            "commercial",


        "spaces":
            [

                {
                    "type":
                        "shop"
                }

            ]

    }



    program = program_engine.apply(

        program,

        network

    )



    # ---------------------------------
    # 3. SPATIAL
    # ---------------------------------

    spatial_engine = VerticalSpatialLayoutEngine()


    layout = spatial_engine.generate(

        program

    )



    # ---------------------------------
    # 4. GEOMETRY
    # ---------------------------------

    geometry_engine = VerticalGeometryIntegrationEngine()


    geometry = geometry_engine.generate(

        layout

    )



    # ---------------------------------
    # 5. SEMANTIC BIM
    # ---------------------------------

    bim_engine = SemanticBIMVerticalMappingEngine()


    bim = bim_engine.generate(

        geometry

    )



    print(
        "\n===== FINAL VERTICAL BIM RESULT ====="
    )


    print(bim)



    types = [

        x["semantic_type"]

        for x in bim["semantic_elements"]

    ]



    assert "escalator" in types

    assert "moving_ramp" in types

    assert "elevator" in types

    assert "stair" in types



    print(
        "\n✅ FULL BIM VERTICAL INTEGRATION TEST PASSED"
    )



if __name__ == "__main__":

    test_full_bim_vertical_integration()