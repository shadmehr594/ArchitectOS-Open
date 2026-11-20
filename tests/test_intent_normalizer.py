# ==========================================================
# Intent Normalizer Test
# ==========================================================


from core.prompt_intelligence.architectural_llm_parser import (
    architectural_llm_parser
)


from core.prompt_intelligence.intent_normalizer import (
    intent_normalizer
)



def run():


    text = (
        "یک خانه سنتی ایرانی کنار رودخانه خروشان "
        "با نمای آجری و یک ماشین لوکس جلوی خانه"
    )


    llm_result = architectural_llm_parser.parse(
        text
    )


    normalized = intent_normalizer.normalize(
        llm_result
    )


    print(
        "\nFINAL NORMALIZED:"
    )


    print(normalized)




if __name__ == "__main__":

    run()