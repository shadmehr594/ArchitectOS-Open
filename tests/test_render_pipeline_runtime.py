# ==========================================================
# ArchitectOS Render Pipeline Runtime Test
#
# Goal:
# Verify:
#
# User Text
# -> ChatArchitect
# -> Intent Router
# -> ImageHandler
# -> Semantic Intent
# -> PromptBuilder
# -> RenderRuntime
# -> WorkflowSelector
# -> WorkflowLoader
# -> WorkflowInjector
#
# NO IMAGE GENERATION
# Executor is mocked
# ==========================================================


from core.chat.chat_architect import ChatArchitect
from brain.brain_router import BrainRouter


from core.render.render_runtime import RenderRuntime



class DebugExecutor:


    def execute(
        self,
        workflow,
        engine
    ):


        print("\n==============================")
        print("🚫 EXECUTOR BLOCKED")
        print("==============================")


        print(
            "ENGINE:"
        )

        print(
            engine
        )


        print(
            "WORKFLOW TYPE:"
        )

        print(
            type(workflow)
        )


        print(
            "WORKFLOW KEYS:"
        )

        if isinstance(workflow, dict):

            print(
                list(workflow.keys())
            )


        return {

            "status":
                "debug_executor_blocked",

            "engine":
                engine

        }




def run():


    print(
        "\n🔥 ARCHITECTOS RENDER PIPELINE TEST START"
    )


    brain = BrainRouter()


    chat = ChatArchitect(
        brain
    )


    # ------------------------------------------
    # Replace executor only
    # Keep real RenderRuntime
    # ------------------------------------------


    runtime = RenderRuntime()


    runtime.executor = DebugExecutor()


    chat.render_runtime = runtime


    chat.image_handler.render_runtime = runtime



    test_prompt = (

        "یه ویلای مدرن با نمای شیشه و بتن "
        "و یک خودروی مدرن جلوی ویلا رندر کن"

    )


    print(
        "\nUSER TEST:"
    )

    print(
        test_prompt
    )


    result = chat.handle(
        test_prompt
    )


    print(
        "\n=============================="
    )

    print(
        "FINAL RESULT:"
    )

    print(
        result
    )


    print(
        "\n🔥 TEST FINISHED"
    )



if __name__ == "__main__":

    run()