# ==========================================================
# ArchitectOS LLM Router Debug Test v1
# Test:
# Chat -> Gemma
# Reasoning -> Qwen
# Backup -> Llama
# ==========================================================


from core.llm.model_router import model_router



print("\n================================")
print("🧠 LLM ROUTER DEBUG TEST START")
print("================================\n")



# ==========================================================
# TEST CHAT
# ==========================================================

print("\n===== CHAT MODEL TEST =====")


chat_result = model_router.generate(
    "سلام، خودت را معرفی کن",
    task="chat"
)


print("\nCHAT RESULT:")
print(chat_result)



# ==========================================================
# TEST REASONING
# ==========================================================

print("\n===== REASONING MODEL TEST =====")


reason_result = model_router.generate(
    """
یک درخواست معماری را تحلیل کن:

یک ویلای مدرن با نمای شیشه و بتن طراحی کن.
اطلاعات را به صورت JSON معماری استخراج کن.
""",
    task="architecture"
)


print("\nREASONING RESULT:")
print(reason_result)



# ==========================================================
# COMPLETE
# ==========================================================

print("\n================================")
print("✅ LLM ROUTER DEBUG COMPLETE")
print("================================")