# ==========================================================
# ArchitectOS Workflow Executor Contract Test
#
# Purpose:
# Validate Injector -> Executor contract
#
# NO COMFYUI EXECUTION
# NO IMAGE GENERATION
# ==========================================================


from core.render.workflow_injector import WorkflowInjector



print(
    "🚀 WORKFLOW EXECUTOR CONTRACT TEST START"
)



injector = WorkflowInjector()



# ----------------------------------------------------------
# MOCK COMFY WORKFLOW
# ----------------------------------------------------------

workflow = {


    "1":
    {

        "class_type":
            "CLIPTextEncode",

        "inputs":
        {

            "text":
                "old prompt"

        }

    },


    "2":
    {

        "class_type":
            "KSampler",

        "inputs":
        {

            "seed":
                123,

            "positive":
                ["1", 0],

            "negative":
                ["3", 0]

        }

    },


    "3":
    {

        "class_type":
            "CLIPTextEncode",

        "inputs":
        {

            "text":
                "old negative"

        }

    }

}



context = {


    "seed":
        999999,


    "mode":
        "text2img"

}



prompt = (
    "modern villa architectural visualization, "
    "glass facade, exposed concrete"
)



# ----------------------------------------------------------
# INJECT
# ----------------------------------------------------------

result = injector.inject(

    workflow,

    prompt,

    context

)



print(
    "🔥 INJECT RESULT:"
)

print(
    result
)



# ----------------------------------------------------------
# CONTRACT CHECK
# ----------------------------------------------------------

assert isinstance(
    result,
    dict
)


assert "workflow" in result


assert isinstance(
    result["workflow"],
    dict
)



workflow_payload = result["workflow"]



print(
    "📦 WORKFLOW PAYLOAD TYPE:",
    type(workflow_payload)
)


print(
    "📦 NODE COUNT:",
    len(workflow_payload)
)



assert len(workflow_payload) >= 3



# seed check

assert (
    workflow_payload["2"]["inputs"]["seed"]
    ==
    999999
)



print(
    "✅ SEED INJECTION VALIDATED"
)



print(
    "✅ INJECTOR -> EXECUTOR CONTRACT OK"
)



print(
    "🔥 TEST FINISHED"
)