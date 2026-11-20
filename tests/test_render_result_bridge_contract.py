# ==========================================================
# ArchitectOS Render Result Bridge Contract Test
#
# Validate:
# - Direct execution image consume
# - RenderMemoryBridge store
# - Architectural intent preservation
# - Prompt preservation
# - No real render execution
# ==========================================================


import os
import json


from core.render.render_result_bridge import RenderResultBridge



print(
    "🚀 RENDER RESULT BRIDGE CONTRACT TEST START"
)



TEST_MEMORY = "core/memory/test_render_memory_contract.json"



# ==========================================================
# CLEAN TEST MEMORY
# ==========================================================


if os.path.exists(TEST_MEMORY):

    os.remove(
        TEST_MEMORY
    )



bridge = RenderResultBridge()


bridge.memory.storage_path = TEST_MEMORY


os.makedirs(
    os.path.dirname(TEST_MEMORY),
    exist_ok=True
)


if not os.path.exists(TEST_MEMORY):

    with open(
        TEST_MEMORY,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            [],
            f
        )



# ==========================================================
# MOCK COMPLETED EXECUTION
# ==========================================================


render_result = {


    "project_id":

        "TEST_PROJECT",



    "engine":

        "flux",



    "workflow":

        "flux.json",



    "prompt":

        "modern villa architectural visualization",



    "architectural_intent":

        {

            "building_type":

                "villa",


            "style":

                "modern",


            "materials":

                [

                    "glass facade",

                    "exposed concrete"

                ]

        },



    "execution":

        {


            "status":

                "completed",



            "prompt_id":

                "TEST_PROMPT_001",



            "images":

                [

                    {

                        "filename":

                            "test_render.png",

                        "type":

                            "output"

                    }

                ]

        }

}



# ==========================================================
# RESOLVE
# ==========================================================


result = bridge.resolve(
    render_result
)



print(
    "🔥 BRIDGE RESULT:"
)

print(
    result
)



# ==========================================================
# VALIDATION
# ==========================================================


assert result["status"] == "success"


assert result["image"]["filename"] == "test_render.png"


assert result["architectural_intent"]["building_type"] == "villa"


assert result["prompt"] == "modern villa architectural visualization"


assert "memory" in result



print(
    "✅ IMAGE ASSET VALIDATED"
)


print(
    "✅ ARCHITECTURAL INTENT VALIDATED"
)


print(
    "✅ PROMPT PRESERVATION VALIDATED"
)


print(
    "✅ MEMORY STORE VALIDATED"
)



# ==========================================================
# VERIFY MEMORY FILE
# ==========================================================


with open(
    TEST_MEMORY,
    "r",
    encoding="utf-8"
) as f:

    memory = json.load(
        f
    )



assert len(memory) == 1


assert memory[0]["project_id"] == "TEST_PROJECT"



print(
    "✅ PERSISTENT MEMORY VALIDATED"
)


print(
    "🔥 RENDER RESULT BRIDGE CONTRACT TEST FINISHED"
)