from core.llm.llm_gateway_v30 import llm_gateway


print(
    llm_gateway.generate(
        "سلام، خودت را معرفی کن",
        "chat"
    )
)


print(
    llm_gateway.generate(
        "توضیح بده معماری نرم افزار چیست",
        "reasoning"
    )
)