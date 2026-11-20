# ==================================================
# ArchitectOS Intelligence Runtime Bridge Test v1
# ==================================================

from core.intelligence.architectos_runtime_adapter import (
    ArchitectOSRuntimeAdapter
)


print(
    "\n🧠 ARCHITECTOS INTELLIGENCE BRIDGE TEST START\n"
)


runtime = ArchitectOSRuntimeAdapter()


request = {

    "type": "design_request",

    "message":
    "Design a modern residential house",

    "context": {

        "style":
        "modern"

    }

}



result = runtime.process(
    request
)


print(
    "\n===== RESULT ====="
)


print(result)



assert isinstance(
    result,
    dict
)


assert (
    result.get("engine")
    ==
    "architectos_intelligence_orchestrator_v70.0"
)



assert (
    result.get("status")
    ==
    "completed"
)



print(
    "\n✅ INTELLIGENCE BRIDGE TEST COMPLETE\n"
)