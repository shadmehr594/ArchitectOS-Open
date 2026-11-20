# ==========================================================
# ArchitectOS LLM Render Bridge Test v1
#
# Parser
#   ->
# Intent Normalizer
#   ->
# Render Input
#   ->
# PromptBuilder
#
# No production changes
# ==========================================================


from core.prompt_intelligence.architectural_llm_parser import (
    architectural_llm_parser
)


from core.prompt_intelligence.intent_normalizer import (
    intent_normalizer
)


from core.render.prompt_builder import (
    PromptBuilder
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
    # LLM PARSER
    # ==================================================

    llm_intent = architectural_llm_parser.parse(
        user_text
    )



    print(
        "\n🧠 LLM INTENT:"
    )

    print(
        llm_intent
    )



    # ==================================================
    # NORMALIZE
    # ==================================================

    normalized = intent_normalizer.normalize(
        llm_intent
    )



    print(
        "\n🔄 NORMALIZED:"
    )

    print(
        normalized
    )



    # ==================================================
    # RENDER INPUT CONTRACT
    # ==================================================

    render_input = {


        "prompt":

            user_text,


        "architectural_intent":

            normalized,


        "floors":

            1,


        "mode":

            "generate",


        "engine":

            "flux"


    }



    print(
        "\n🎨 RENDER INPUT:"
    )

    print(
        render_input
    )



    # ==================================================
    # PROMPT BUILD
    # ==================================================

    builder = PromptBuilder()


    prompt = builder.build(
        render_input
    )



    print(
        "\n🔥 FINAL RENDER PROMPT:"
    )

    print(
        prompt
    )





if __name__ == "__main__":

    run()