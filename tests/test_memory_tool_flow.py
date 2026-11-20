# ==========================================================
# ArchitectOS Memory Tool Flow Test
# Simple Recall Test
# ==========================================================

from core.memory.memory_manager import memory_manager
from core.tools.memory_tool import MemoryTool


print("\n==============================")
print("MEMORY TOOL FLOW TEST")
print("==============================\n")


tool = MemoryTool(
    memory_manager
)


# Save test
save_result = tool.execute(
    "من یک معمار هستم"
)

print("SAVE:")
print(save_result)



# Recall test
recall_result = tool.execute(
    "یادته من کی هستم"
)

print("\nRECALL:")
print(recall_result)



# Profile
print("\nPROFILE:")
print(
    memory_manager.get_profile()
)


print("\nTEST COMPLETE")