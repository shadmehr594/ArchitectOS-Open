# ==========================================================
# ArchitectOS Memory Runtime Test v1
# MemoryManager + ContextRecall
# ==========================================================


from core.memory.memory_manager import memory_manager
from core.memory.context_recall import ContextRecall



print("\n🧠 MEMORY RUNTIME TEST START\n")



recall = ContextRecall(
    memory_manager
)



print("Saving memory...")


memory_manager.save_context({

    "message":
        "ArchitectOS final integration test"

})


memory_manager.save_conversation(

    "ArchitectOS final integration test",

    "user"

)



print("Reading memory...")



result = recall.recall(

    "ArchitectOS"

)



print("\nRESULT:")
print(result)



if result:

    print("\n✅ MEMORY TEST PASSED")


else:

    print("\n⚠️ MEMORY EMPTY")



print("\n🧠 MEMORY RUNTIME TEST COMPLETE")