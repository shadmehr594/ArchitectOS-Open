# ==========================================================
# ArchitectOS Semantic Intent Qwen Debug Test v1
#
# Flow:
# Persian Request
#       |
#       ↓
# SemanticIntentEngine
#       |
#       ↓
# LLM Router (Qwen)
#       |
#       ↓
# Architectural JSON
#
# No Render
# No ComfyUI
# ==========================================================


from core.llm.model_router import model_router
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.intelligence.semantic_intent import SemanticIntentEngine



class QwenSemanticAdapter:


    def generate(
        self,
        prompt
    ):

        return model_router.generate(
            prompt,
            task="architecture"
        )



print("\n================================")
print("🧠 SEMANTIC INTENT QWEN TEST START")
print("================================\n")



llm = QwenSemanticAdapter()



semantic = SemanticIntentEngine(

    llm=llm,

    fallback=ArchitecturalIntent()

)



request = """

یک ویلای مدرن یک طبقه با نمای شیشه و بتن طراحی کن.
دارای حیاط جلو، نور طبیعی، پنجره های بزرگ و سبک مینیمال باشد.

"""


result = semantic.extract(
    request
)



print("\n========== FINAL RESULT ==========")

print(result)


print("\n========== CHECK ==========")


print(
    "STYLE:",
    result.get("style")
)


print(
    "MATERIALS:",
    result.get("materials")
)


print(
    "OBJECTS:",
    result.get("objects")
)


print(
    "FACADE:",
    result.get("facade_details")
)



print("\n================================")
print("✅ SEMANTIC INTENT QWEN TEST COMPLETE")
print("================================")