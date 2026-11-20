from core.prompt_intelligence.architectural_llm_parser import (
    architectural_llm_parser
)

from core.prompt_intelligence.intent_normalizer import (
    intent_normalizer
)

from core.render.prompt_builder import PromptBuilder



def run():


    text = (
        "یک خانه سنتی ایرانی کنار رودخانه خروشان "
        "با نمای آجری و یک ماشین لوکس جلوی خانه"
    )


    llm_intent = architectural_llm_parser.parse(
        text
    )


    normalized = intent_normalizer.normalize(
        llm_intent
    )


    design = {

        "prompt": text,

        "architectural_intent": normalized,

        "floors":1

    }


    builder = PromptBuilder()


    result = builder.build(
        design
    )


    print("\nFINAL PROMPT RESULT:")
    print(result)



if __name__ == "__main__":

    run()