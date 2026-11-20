# ==========================================================
# ArchitectOS Planner Context Bridge Debug Test
# ==========================================================

from core.brain import Brain


print("\n======================================")
print("🧠 PLANNER CONTEXT BRIDGE TEST")
print("======================================\n")


brain = Brain()


prompt = """
یک ویلای مدرن دو طبقه طراحی کن.
زمین 20x30 متر است.
پارکینگ و استخر داشته باشد.
"""


context = {

    "operation": "design_create",

    "memory_context": {

        "user_profile": {

            "preferences": {

                "architecture_style": "modern"

            }

        }

    }

}



result = brain.run(

    prompt,

    context=context

)

print("\n========== DESIGN RESULT KEYS ==========")

print(result.keys())


print("\n========== DESIGN RESULT GEOMETRY ==========")

print(
    result.get("design", {}).get("geometry")
)


print("\n========== DESIGN RESULT SPATIAL ==========")

print(
    result.get("spatial")
)



print("\n======================================")
print("FINAL RESULT")
print("======================================")

print(result)

print("\n======================================")
print("GEOMETRY")
print("======================================")

print(result.get("geometry"))

print("\n======================================")
print("SPATIAL")
print("======================================")

print(result.get("spatial"))

print("\n======================================")
print("ARCHITECTURAL INTENT")
print("======================================")

print(
    result.get(
        "architectural_intent",
        {}
    )
)