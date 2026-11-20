from core.architecture.architectural_decision_graph import (
    ArchitecturalDecisionGraph
)



def test_architectural_decision_graph():


    graph = ArchitecturalDecisionGraph()



    graph.add_node(

        "site_south_access",

        "site_constraint",

        {

            "rule":

            "main_entry_from_south"

        }

    )



    graph.add_node(

        "main_ramp",

        "circulation_element",

        {

            "type":

            "ramp"

        }

    )



    graph.add_node(

        "central_stair",

        "vertical_element",

        {

            "type":

            "stair"

        }

    )



    graph.connect(

        "site_south_access",

        "main_ramp",

        [

            "accessibility",

            "public_entry"

        ]

    )



    graph.connect(

        "main_ramp",

        "central_stair",

        [

            "vertical_distribution"

        ]

    )



    print(graph.nodes)

    print(graph.connections)



    assert graph.validate()



    assert len(

        graph.dependencies(

            "main_ramp"

        )

    ) == 1