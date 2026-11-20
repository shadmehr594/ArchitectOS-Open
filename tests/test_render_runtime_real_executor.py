# ==========================================================
# ArchitectOS RenderRuntime Real Executor Test v1
#
# LLM Intent
#      |
#      v
# Intent Normalizer
#      |
#      v
# RenderRuntime
#      |
#      v
# WorkflowExecutor v4.1
#      |
#      v
# ComfyHTTPRuntime v3.1
#
# No Mock Executor
# Real execution path check
# ==========================================================


from core.prompt_intelligence.architectural_llm_parser import (
    architectural_llm_parser
)


from core.prompt_intelligence.intent_normalizer import (
    intent_normalizer
)


from core.render.render_runtime import (
    RenderRuntime
)



def run():


    user_text = (

        "یک خانه سنتی ایرانی کنار رودخانه خروشان "
        "با نمای آجری و یک ماشین لوکس جلوی خانه"

    )



    print(
        "\n👤 INPUT:"
    )

    print(
        user_text
    )



    # ==================================================
    # INTENT
    # ==================================================


    llm_intent = architectural_llm_parser.parse(
        user_text
    )


    normalized = intent_normalizer.normalize(
        llm_intent
    )



    design = {


        "prompt":

            user_text,


        "architectural_intent":

            normalized,


        "floors":

            1


    }



    print(
        "\n🎨 DESIGN:"
    )

    print(
        design
    )



    # ==================================================
    # REAL RUNTIME
    # ==================================================


    runtime = RenderRuntime()



    # ==================================================
    # REAL EXECUTOR
    # ==================================================

    result = runtime.render(

        project_id="real_executor_test",

        design=design,

        engine="flux"

    )



    print(
        "\n🔥 REAL RUNTIME RESULT:"
    )


    print(
        result
    )



    print(
        "\n🧠 FINAL INTENT:"
    )


    print(

        result.get(
            "architectural_intent"
        )

    )




if __name__ == "__main__":

    run()