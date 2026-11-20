from core.intelligence.experience_memory import (
    ExperienceMemoryEngine
)

from core.intelligence.experience_persistence import (
    ExperiencePersistence
)


print(
    "\n🧠 EXPERIENCE PERSISTENCE LEARNING TEST START\n"
)


memory = ExperienceMemoryEngine()

persistence = ExperiencePersistence()



project_experience = {


    "simulation": {

        "energy":
        "optimized"

    },


    "scenario": {

        "future":
        "summer_load"

    },


    "optimization": {

        "result":
        "best_layout"

    },


    "knowledge": {

        "pattern":
        "modern_villa"

    }

}



print(
    "▶️ BUILD EXPERIENCE MEMORY"
)


result = memory.build(
    project_experience
)


print(
    result
)



print(
    "\n▶️ STORE EXPERIENCE"
)


store_result = persistence.store(
    result
)


print(
    store_result
)



print(
    "\n▶️ RECALL EXPERIENCE"
)


recall_result = persistence.recall()


print(
    recall_result
)



print(
    "\n✅ EXPERIENCE PERSISTENCE TEST COMPLETE\n"
)