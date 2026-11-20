from core.prompt_intelligence.architectural_llm_parser import architectural_llm_parser
from core.render.render_runtime import RenderRuntime


text = "یک ویلای مدرن با نمای شیشه و سنگ طبیعی طراحی کن"


intent = architectural_llm_parser.parse(text)


print("\nLLM INTENT:")
print(intent)


runtime = RenderRuntime()


design = {

    "prompt": text,

    "architectural_intent": intent,

    "mode": "text2img"

}


print("\nRUNTIME INPUT:")
print(design)

