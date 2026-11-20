class ExperienceMemoryEngine:

    def __init__(self):

        print(
            "🧠 ArchitectOS Experience Memory v61.0 ACTIVE"
        )


    def build(self, graph):

        print(
            "▶️ BUILD EXPERIENCE MEMORY v61"
        )


        experiences = []


        # ===============================
        # LEARN FROM SIMULATION
        # ===============================

        simulation = graph.get(
            "simulation",
            {}
        )


        if simulation:

            experiences.append(
                {
                    "source": "simulation",
                    "pattern": "occupancy_energy_relation",
                    "lesson": "monitor_energy_usage"
                }
            )


        # ===============================
        # LEARN FROM SCENARIO
        # ===============================

        scenario = graph.get(
            "scenario",
            {}
        )


        if scenario:

            experiences.append(
                {
                    "source": "scenario",
                    "pattern": "scenario_prediction",
                    "lesson": "prepare_future_states"
                }
            )


        # ===============================
        # LEARN FROM OPTIMIZATION
        # ===============================

        optimization = graph.get(
            "optimization",
            {}
        )


        if optimization:

            experiences.append(
                {
                    "source": "optimization",
                    "pattern": "optimization_result",
                    "lesson": "apply_best_configuration"
                }
            )


        # ===============================
        # LEARN FROM KNOWLEDGE
        # ===============================

        knowledge = graph.get(
            "knowledge",
            {}
        )


        if knowledge:

            experiences.append(
                {
                    "source": "knowledge",
                    "pattern": "knowledge_extraction",
                    "lesson": "reuse_project_insights"
                }
            )


        return {

            "engine":
                "architectos_experience_v61.0",

            "experiences":
                experiences,

            "memory_nodes":
                len(experiences),

            "learned_patterns":
                len(experiences)

        }