"""
ArchitectOS IFC Real Export Pipeline Test v1.0
"""


from core.bim.semantic_bim_mapping_engine import (
    SemanticBIMMappingEngine
)

from core.bim.bim_geometry_adapter import (
    BIMGeometryAdapter
)

from core.bim.ifc_geometry_bridge import (
    IFCGeometryBridge
)

from core.bim.ifc_geometry_provider_adapter import (
    IFCGeometryProviderAdapter
)



def test_ifc_real_export_pipeline():


    semantic_engine = SemanticBIMMappingEngine()

    geometry_engine = BIMGeometryAdapter()

    bridge_engine = IFCGeometryBridge()

    provider_engine = IFCGeometryProviderAdapter()



    # ==========================================
    # SEMANTIC BIM INPUT
    # ==========================================


    semantic_result = {


        "elements":[


            {

                "ifc_type":
                    "IfcSpace",

                "name":
                    "living",

                "zone":
                    "public",

                "geometry":[

                    [0,0],

                    [4,0],

                    [4,5],

                    [0,5]

                ]

            },


            {

                "ifc_type":
                    "IfcWall",

                "wall_type":
                    "exterior",

                "boundary":[

                    [0,0],

                    [4,0]

                ],

                "thickness":
                    0.2

            },


            {

                "ifc_type":
                    "IfcDoor",

                "room":
                    "living",

                "source":
                    "entrance"

            },


            {

                "ifc_type":
                    "IfcWindow",

                "room":
                    "living",

                "source":
                    "facade"

            }

        ]

    }



    # ==========================================
    # PIPELINE
    # ==========================================


    geometry_result = geometry_engine.generate(

        semantic_result,

        "F1"

    )



    bridge_result = bridge_engine.generate(

        geometry_result

    )



    ifc_input = provider_engine.generate(

        bridge_result

    )



    print(

        "\n========== IFC PIPELINE RESULT =========="

    )


    print(

        ifc_input

    )



    entities = ifc_input.get(

        "ifc_entities",

        []

    )



    assert len(

        entities

    ) == 4



    types = [

        entity.get(

            "entity"

        )

        for entity in entities

    ]



    assert "IfcSpace" in types

    assert "IfcWall" in types

    assert "IfcDoor" in types

    assert "IfcWindow" in types



    print(

        "\n✅ IFC REAL EXPORT PIPELINE TEST PASSED"

    )



if __name__ == "__main__":

    test_ifc_real_export_pipeline()