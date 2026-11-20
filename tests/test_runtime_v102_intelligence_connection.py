from core.runtime.architectos_runtime import ArchitectOSRuntime


print(
    "\n🏛️ RUNTIME v102 INTELLIGENCE CONNECTION TEST\n"
)


runtime = ArchitectOSRuntime()


result = runtime.run(
    {
        "project": "test_project",
        "request": "create modern villa design"
    }
)


print("\n===== RESULT =====")

print(result)


print(
    "\n✅ RUNTIME v102 TEST COMPLETE"
)