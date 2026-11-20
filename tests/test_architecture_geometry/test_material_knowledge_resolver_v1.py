from core.architecture.knowledge.material_resolver import (
    ArchitecturalMaterialResolverV1
)



def test_material_knowledge_resolver_v1():


    resolver = ArchitecturalMaterialResolverV1()


    output = resolver.resolve(

        {

            "style":
                "modern",

            "climate":
                "dry"

        }

    )


    assert output["style"] == "modern"


    assert (
        "materials"
        in output
    )


    assert (
        "facade_language"
        in output
    )