# ==========================================================
# ArchitectOS LLM -> Prompt Contract Test
#
# LLM Intent
#       |
#       v
# PromptRouter
#       |
#       v
# PromptBuilder
#
# No Render Execution
# ==========================================================


from core.prompt_intelligence.architectural_llm_parser import (
    architectural_llm_parser
)

from core.prompt_intelligence.prompt_router import (
    PromptRouter
)



text = (
    "یک ویلای مدرن با نمای شیشه و سنگ طبیعی طراحی کن"
)



print("\n==============================")
print("USER REQUEST")
print("==============================")

print(text)



# ----------------------------------------------------------
# LLM ARCHITECTURAL PARSE
# ----------------------------------------------------------

intent = architectural_llm_parser.parse(
    text
)



print("\n==============================")
print("NORMALIZED INTENT")
print("==============================")

print(intent)



# ----------------------------------------------------------
# PROMPT ROUTER
# ----------------------------------------------------------

router = PromptRouter()



payload = {

    "prompt":
        text,

    "architectural_intent":
        intent

}



print("\n==============================")
print("PROMPT INPUT")
print("==============================")

print(payload)



result = router.build(
    payload,
    mode="text2img"
)



print("\n==============================")
print("FINAL PROMPT RESULT")
print("==============================")

print(result)