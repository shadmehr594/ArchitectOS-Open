from core.cognition.runtime_dispatcher import runtime_dispatcher
from core.cognition.execution_plan import ExecutionPlan


print("\n🚀 RUNTIME DISPATCHER EDIT TEST START\n")


plan = ExecutionPlan(

    intent="renovate existing villa facade",

    workflow="flux_img2img",

    engine="flux",

    inputs={}

)


result = runtime_dispatcher.dispatch(

    plan,

    "change facade material to glass and wood",

    mode="image"

)


print("\n===== EDIT DISPATCH RESULT =====")

print(result)