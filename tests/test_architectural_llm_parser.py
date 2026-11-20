# ==========================================================
# ArchitectOS Architectural LLM Parser Test
# Isolated Test
# ==========================================================


from core.prompt_intelligence.architectural_llm_parser import (
    architectural_llm_parser
)



def run():


    text = (
        "یک خانه سنتی ایرانی کنار رودخانه خروشان "
        "با نمای آجری و یک ماشین لوکس جلوی خانه"
    )


    print(
        "\nUSER INPUT:"
    )

    print(text)



    result = architectural_llm_parser.parse(
        text
    )



    print(
        "\nFINAL SEMANTIC RESULT:"
    )


    print(result)




if __name__ == "__main__":

    run()