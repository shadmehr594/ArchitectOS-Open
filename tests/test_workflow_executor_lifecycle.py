# ==========================================================
# ArchitectOS Workflow Executor v4.2 Lifecycle Test
#
# Purpose:
# Validate submit -> prompt_id -> wait -> result lifecycle
#
# NO COMFYUI EXECUTION
# ==========================================================


from core.render.workflow_executor import WorkflowExecutor



print(
    "🚀 WORKFLOW EXECUTOR LIFECYCLE TEST START"
)



# ==========================================================
# MOCK COMFY RUNTIME
# ==========================================================


class MockComfyRuntime:


    def __init__(self):

        print(
            "🧪 MOCK COMFY RUNTIME ONLINE"
        )


    def submit(
        self,
        workflow
    ):

        print(
            "🧪 MOCK SUBMIT RECEIVED"
        )

        print(
            "WORKFLOW TYPE:",
            type(workflow)
        )

        return {

            "prompt_id":
                "TEST_PROMPT_001"

        }



    def wait_for_result(
        self,
        prompt_id
    ):


        print(
            "🧪 MOCK WAIT:",
            prompt_id
        )


        return {

            "status":
                "completed",

            "output":
                {

                    "images":
                        []

                }

        }



# ==========================================================
# PATCH EXECUTOR
# ==========================================================


executor = WorkflowExecutor()


executor.comfy = MockComfyRuntime()



workflow = {


    "1":
    {

        "class_type":
            "KSampler",

        "inputs":
        {}

    }

}



# ==========================================================
# EXECUTE
# ==========================================================


result = executor.execute(

    workflow,

    "comfyui"

)



print(
    "🔥 EXECUTOR RESULT:"
)

print(
    result
)



# ==========================================================
# VALIDATION
# ==========================================================


assert isinstance(
    result,
    dict
)


assert (
    result["engine"]
    ==
    "comfyui"
)


assert (
    result["status"]
    ==
    "completed"
)


assert (
    result["prompt_id"]
    ==
    "TEST_PROMPT_001"
)


assert (
    result["execution"]["status"]
    ==
    "completed"
)



print(
    "✅ SUBMIT VALIDATED"
)


print(
    "✅ PROMPT ID VALIDATED"
)


print(
    "✅ WAIT RESULT VALIDATED"
)


print(
    "✅ REAL STATUS PRESERVATION VALIDATED"
)


print(
    "🔥 TEST FINISHED"
)