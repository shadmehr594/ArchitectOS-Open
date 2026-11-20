from core.memory.memory_manager import memory_manager


print(
    "BEFORE"
)

print(
    memory_manager.get_profile()
)


memory_manager.save_conversation(
    "من اسمم مهدی هست و یه معمار هستم",
    "user"
)


print(
    "AFTER"
)

print(
    memory_manager.get_profile()
)


print(
    "USER MEMORY"
)

print(
    memory_manager.recall_user()
)