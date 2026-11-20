"""
ArchitectOS Architectural Decision Graph v1.0

Stores architectural decisions,
dependencies and reasoning.
"""


class ArchitecturalDecisionGraph:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🧠 Architectural Decision Graph v{self.VERSION} ACTIVE"
        )


        self.nodes = []

        self.connections = []



    # ==================================================
    # ADD DECISION NODE
    # ==================================================

    def add_node(
        self,
        node_id,
        node_type,
        data=None
    ):


        node = {


            "id":

                node_id,


            "type":

                node_type,


            "data":

                data or {}

        }


        self.nodes.append(node)


        return node



    # ==================================================
    # CONNECT DECISIONS
    # ==================================================

    def connect(
        self,
        source,
        target,
        reason=None
    ):


        connection = {


            "from":

                source,


            "to":

                target,


            "reason":

                reason or []

        }


        self.connections.append(
            connection
        )


        return connection



    # ==================================================
    # FIND DEPENDENCIES
    # ==================================================

    def dependencies(
        self,
        node_id
    ):


        return [

            c

            for c in self.connections

            if c["to"] == node_id

        ]



    # ==================================================
    # VALIDATE
    # ==================================================

    def validate(self):


        return (

            len(self.nodes) > 0

            and

            all(

                "id" in node

                for node in self.nodes

            )

        )