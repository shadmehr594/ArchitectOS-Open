# ==========================================================
# ArchitectOS Personal Context Engine v1 TEST
# ==========================================================

from core.memory.personal_context_engine import PersonalContextEngine
from core.memory.memory_intelligence_engine import MemoryIntelligenceEngine
from core.memory.user_profile_memory import user_profile_memory


print("\n🧠 PERSONAL CONTEXT TEST START\n")


# ----------------------------------------------------------
# Seed User Profile
# ----------------------------------------------------------

user_profile_memory.update({
    "family": {
        "last_note": "من دو فرزند دارم"
    },

    "food_preferences": {
        "last_note": "به آشپزی علاقه دارم"
    },

    "preferences": {
        "architecture_style": "modern"
    },

    "projects": {
        "current": "پروژه اصلی من ArchitectOS است"
    },

    "interests": [
        "architecture",
        "cooking"
    ]
})


# ----------------------------------------------------------
# Smart Memory
# ----------------------------------------------------------

memory = MemoryIntelligenceEngine()


queries = [

    "برای بچه ها یک اتاق طراحی کن",

    "یک غذای ایرانی درست کنم",

    "وضعیت پروژه ArchitectOS چیست",

    "یک خانه مدرن طراحی کن"

]


for query in queries:

    print("\n👤 QUERY:")
    print(query)


    result = memory.analyze(query)


    print("\n🧠 MEMORY RESULT:")
    print(result)



# ----------------------------------------------------------
# Personal Context
# ----------------------------------------------------------

context_engine = PersonalContextEngine()


context = context_engine.build(
    "یک خانه مدرن برای خانواده طراحی کن"
)


print("\n\n🧠 PERSONAL CONTEXT:")
print(context)


print(
    "\n✅ PERSONAL CONTEXT v1 TEST COMPLETE\n"
)