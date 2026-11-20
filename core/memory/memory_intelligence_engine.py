# ==========================================================
# ArchitectOS Memory Intelligence Engine Adapter v31
# Compatibility Bridge
# ==========================================================


from .memory_intelligence_v31 import (
    MemoryIntelligence,
    memory_intelligence
)



class MemoryIntelligenceEngine(
    MemoryIntelligence
):


    VERSION = "v31"



    def __init__(self):

        super().__init__()



    def analyze(
        self,
        query
    ):

        return self.build(
            query
        )



# ==========================================================
# SINGLETON
# ==========================================================


memory_intelligence_engine = MemoryIntelligenceEngine()