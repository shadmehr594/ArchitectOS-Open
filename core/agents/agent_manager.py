# ==========================================================
# ArchitectOS Agent Manager v1
# Autonomous Agent Registry
# ==========================================================


from core.memory.context_builder import context_builder



class AgentManager:


    VERSION = "v1"



    def __init__(self):

        self.agents = {}

        self.context = context_builder


        print(
            "🤖 AGENT MANAGER v1 ONLINE"
        )



    # ======================================================
    # REGISTER AGENT
    # ======================================================

    def register(
        self,
        name,
        agent
    ):


        self.agents[name] = agent



    # ======================================================
    # SELECT AGENT
    # ======================================================

    def select(
        self,
        intent
    ):


        if intent in self.agents:

            return self.agents[intent]


        return self.agents.get(
            "general"
        )



    # ======================================================
    # RUN AGENT
    # ======================================================

    def run(
        self,
        intent,
        query
    ):


        agent = self.select(
            intent
        )


        if not agent:


            return {

                "status":
                    "no_agent",

                "query":
                    query

            }



        context = self.context.build(
            query,
            intent
        )


        return agent.run(
            query,
            context
        )





# ==========================================================
# SINGLETON
# ==========================================================


agent_manager = AgentManager()