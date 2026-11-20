# ==========================================================
# ArchitectOS Memory Recall Simple Test
# ==========================================================

from core.memory.memory_manager import memory_manager


print("\n==============================")
print("MEMORY SIMPLE TEST")
print("==============================\n")


result = memory_manager.recall_everything(
    "یادته من کی هستم"
)


print("PROFILE:")
print(
    result.get(
        "profile"
    )
)


print("\nUSER MEMORY:")
print(
    result.get(
        "user_memory"
    )
)


print("\nCONVERSATION COUNT:")

print(
    len(
        result.get(
            "conversation",
            []
        )
    )
)


print("\nTEST COMPLETE")