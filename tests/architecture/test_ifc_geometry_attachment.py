from core.architecture.bim.ifc_entity_builder_v1 import (
    ArchitecturalIFCEntityBuilderV1
)


from core.architecture.bim.ifc_geometry_attachment_v1 import (
    IFCGeometryAttachmentV1
)



def test_ifc_geometry_attachment():


    elements = [

        {
            "ifc_class":"IfcWall",
            "name":"Main_Wall",
            "level":"F1"
        }

    ]


    builder = ArchitecturalIFCEntityBuilderV1()


    result = builder.build(
        elements
    )


    entities = result["entities"]


    geometry = [

        {

            "name":"Main_Wall",

            "geometry":
            {

                "type":
                    "wall_extrusion",

                "height":
                    3.6

            }

        }

    ]



    attachment = IFCGeometryAttachmentV1(
        result["ifc_model"]
    )


    output = attachment.attach(
        entities,
        geometry
    )


    wall = output["entities"][0]


    assert (
        wall.Representation
        is not None
    )


    print(
        "\n✅ IFC GEOMETRY ATTACHMENT PASSED"
    )