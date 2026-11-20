# ==========================================================
# ArchitectOS Runtime Dispatcher Test
# Dispatcher v80 + Comfy Runtime v8.3
# ==========================================================


from core.cognition.runtime_dispatcher import runtime_dispatcher
from core.cognition.execution_plan import ExecutionPlan


print("\n🚀 RUNTIME DISPATCHER TEST START\n")


plan = ExecutionPlan(

    intent="create architectural villa",

    workflow="flux",

    engine="flux",

    inputs={}

)


result = runtime_dispatcher.dispatch(

    plan,

    "modern architectural villa, realistic photography",

    mode="image"

)


print("\n===== DISPATCH RESULT =====")

print(result)