from core.architecture.bim.ifc_entity_builder_v1 import (
    ArchitecturalIFCEntityBuilderV1
)



def test_architectural_ifc_entity_builder():


    elements = [

        {
            "ifc_class":"IfcSpace",
            "name":"Main_Hall",
            "level":"F1"
        },


        {
            "ifc_class":"IfcWall",
            "name":"Main_Hall_Wall",
            "level":"F1"
        },


        {
            "ifc_class":"IfcSlab",
            "name":"Main_Hall_Slab",
            "level":"F1"
        }

    ]


    builder = ArchitecturalIFCEntityBuilderV1()


    result = builder.build(
        elements
    )


    assert (
        result["entity_count"]
        ==
        3
    )


    model = result["ifc_model"]


    assert (
        len(
            model.by_type("IfcWall")
        )
        ==
        1
    )


    assert (
        len(
            model.by_type("IfcSpace")
        )
        ==
        1
    )


    assert (
        len(
            model.by_type("IfcSlab")
        )
        ==
        1
    )


    print(
        "\n✅ ARCHITECTURAL IFC ENTITY BUILDER PASSED"
    )