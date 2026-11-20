"""
ArchitectOS IFC Geometry Attachment V1

Attaches generated geometry
to IFC entities.

Pipeline:

IFC Entity
      +
Generated Geometry
      |
      v
IfcShapeRepresentation
"""


import ifcopenshell


class IFCGeometryAttachmentV1:


    VERSION = "1.0"



    def __init__(
        self,
        model
    ):

        print(
            f"📐 IFC GEOMETRY ATTACHMENT v{self.VERSION} ONLINE"
        )

        self.model = model



    # =====================================
    # MAIN ATTACH
    # =====================================

    def attach(
        self,
        entities,
        geometry_data
    ):


        attached = []


        for entity in entities:


            geometry = self.find_geometry(
                entity,
                geometry_data
            )


            if geometry:

                representation = (
                    self.create_representation(
                        entity,
                        geometry
                    )
                )


                entity.Representation = (
                    representation
                )


            attached.append(
                entity
            )



        return {

            "entities":
                attached,


            "element_count":
                len(
                    attached
                ),


            "source":
                "ifc_geometry_attachment_v1"

        }



    # =====================================
    # FIND MATCH
    # =====================================

    def find_geometry(
        self,
        entity,
        geometry_data
    ):


        name = entity.Name


        for item in geometry_data:


            if (
                item.get("name")
                ==
                name
            ):

                return item.get(
                    "geometry",
                    {}
                )


        return None



    # =====================================
    # REPRESENTATION
    # =====================================

    def create_representation(
        self,
        entity,
        geometry
    ):


        shape = self.model.create_entity(

            "IfcShapeRepresentation",

            RepresentationIdentifier="Body",

            RepresentationType="SweptSolid"

        )


        return shape