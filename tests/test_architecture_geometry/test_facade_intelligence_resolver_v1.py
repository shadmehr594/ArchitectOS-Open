from core.architecture.knowledge.facade_resolver import (
    ArchitecturalFacadeResolverV1
)



def test_facade_intelligence_resolver_v1():


    resolver = ArchitecturalFacadeResolverV1()


    output = resolver.resolve(

        {

            "style":
                "modern",

            "climate":
                "hot_dry"

        }

    )


    print(output)


    assert output is not None

    assert "strategies" in output