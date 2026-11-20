# ==========================================================
# Prompt Engine Context Fusion v3.1 Test
# ==========================================================


from core.prompt_engine_context import (
    prompt_context_engine
)



print(
    "\n🧠 PROMPT ENGINE CONTEXT FUSION TEST START\n"
)



queries = [

    "برای بچه ها یک اتاق مدرن طراحی کن",

    "یک غذای ایرانی درست کنم",

    "وضعیت پروژه ArchitectOS چیست"

]


for q in queries:

    print("\n===================")

    print(
        "USER:"
    )

    print(q)


    result = prompt_context_engine.build(
        q
    )


    print("\nGENERATED PROMPT:")

    print(result)



print(
    "\n✅ PROMPT ENGINE CONTEXT FUSION v3.1 TEST COMPLETE"
)