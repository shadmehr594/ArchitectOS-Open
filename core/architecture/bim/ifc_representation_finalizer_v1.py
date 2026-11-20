"""
ArchitectOS IFC Representation Finalizer V1

Connects IFC solids to product representations.

Pipeline:

IfcEntity
    +
IfcSolid
    |
    v
IfcProductDefinitionShape
"""


class IFCRepresentationFinalizerV1:


    VERSION = "1.0"



    def __init__(
        self,
        model
    ):

        print(
            f"🏗 IFC REPRESENTATION FINALIZER v{self.VERSION} ONLINE"
        )

        self.model = model



    # =====================================
    # FINALIZE
    # =====================================

    def finalize(
        self,
        entity,
        solid
    ):


        if not solid:

            return entity



        shape_representation = (
            self.model.create_entity(

                "IfcShapeRepresentation",

                RepresentationIdentifier="Body",

                RepresentationType="SweptSolid",

                Items=[

                    solid

                ]

            )
        )



        product_shape = (
            self.model.create_entity(

                "IfcProductDefinitionShape",

                Representations=[

                    shape_representation

                ]

            )
        )



        entity.Representation = (
            product_shape
        )


        return entity