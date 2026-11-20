# ==========================================================
# ArchitectOS Prompt Context Injector Test v1
# ==========================================================


from core.ai.prompt_context_injector import (
    prompt_context_injector
)



print(
    "\n🧠 PROMPT CONTEXT INJECTOR TEST START\n"
)



queries = [

    "برای بچه ها یک اتاق مدرن طراحی کن",

    "یک غذای ایرانی درست کنم",

    "وضعیت پروژه ArchitectOS چیست"

]


for q in queries:


    print("\nUSER:")
    print(q)


    result = prompt_context_injector.build_context(
        q
    )


    print("\nCONTEXT:")
    print(result)



print(
    "\n✅ PROMPT CONTEXT INJECTOR v1 TEST COMPLETE"
)