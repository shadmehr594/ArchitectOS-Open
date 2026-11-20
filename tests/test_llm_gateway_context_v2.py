# ==========================================================
# ArchitectOS LLM Gateway v2 Context Test
# ==========================================================


from core.llm.llm_gateway import (
    llm_gateway
)



print(
    "\n🧠 LLM GATEWAY v2 CONTEXT TEST START\n"
)



queries = [

    "برای بچه ها یک اتاق مدرن طراحی کن",

    "یک غذای ایرانی درست کنم",

    "وضعیت پروژه ArchitectOS چیست"

]



for q in queries:


    print("\n========================")

    print(
        "👤 USER:"
    )

    print(q)



    response = llm_gateway.generate(
        q
    )


    print("\n🤖 RESPONSE:")

    print(response)



print(
    "\n✅ LLM GATEWAY v2 CONTEXT TEST COMPLETE"
)