from core.architecture.knowledge.facade_resolver import (
    ArchitecturalFacadeResolverV1
)

from core.architecture.knowledge.material_resolver import (
    ArchitecturalMaterialResolverV1
)



class FacadeMaterialBridgeV1:


    VERSION = "1.0"



    def __init__(self):

        self.facade_resolver = (
            ArchitecturalFacadeResolverV1()
        )

        self.material_resolver = (
            ArchitecturalMaterialResolverV1()
        )


        print(
            "🔗 FACADE MATERIAL BRIDGE V1 ONLINE"
        )



    def resolve(
        self,
        context
    ):


        facade = self.facade_resolver.resolve(
            context
        )


        materials = self.material_resolver.resolve(
            context
        )


        result = {


            "facade_language":

                facade.get(
                    "facade_language"
                ),


            "strategies":

                facade.get(
                    "strategies",
                    []
                ),


            "rules":

                facade.get(
                    "rules",
                    []
                ),


            "materials":

                materials.get(
                    "materials",
                    []
                )


        }


        return result