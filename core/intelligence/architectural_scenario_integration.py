"""
ArchitectOS Architectural Scenario Integration v1.0

Connects scenario reasoning with architectural program generation.
"""


from core.intelligence.scenario_program_adapter import (
    ScenarioProgramAdapter
)



class ArchitecturalScenarioIntegration:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🏛️ Architectural Scenario Integration v{self.VERSION} ACTIVE"
        )


        self.adapter = ScenarioProgramAdapter()



    # ==================================================
    # APPLY SCENARIO
    # ==================================================

    def apply(
        self,
        program,
        scenario
    ):


        if not scenario:

            return program



        return self.adapter.apply(

            program,

            scenario

        )