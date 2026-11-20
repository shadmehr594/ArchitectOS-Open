# ==========================================================
# ArchitectOS Response Adapter Contract Test v1
# ==========================================================


print(
    "📦 RESPONSE ADAPTER CONTRACT TEST v1"
)


from core.chat.response_adapter import ResponseAdapter



adapter = ResponseAdapter()



print(
    "\nTEST 1: CHAT ADAPT"
)


chat = {

    "status":"success",

    "type":"chat",

    "engine":"llm_gateway",

    "result":
        "Hello ArchitectOS"

}



chat_result = adapter.adapt(
    chat
)


print(chat_result)


assert chat_result["status"] == "success"
assert chat_result["type"] == "chat"
assert chat_result["result"] == "Hello ArchitectOS"


print(
    "✅ CHAT ADAPTER OK"
)




print(
    "\nTEST 2: DESIGN ADAPT"
)


design = {

    "status":"success",

    "type":"design",

    "engine":"god_core",

    "result":{

        "architectural_intent":{

            "building_type":"villa",

            "style":"modern"

        }

    }

}



design_result = adapter.adapt(
    design
)


print(design_result)


assert "design" in design_result


print(
    "✅ DESIGN ADAPTER OK"
)





print(
    "\nTEST 3: RENDER ADAPT"
)



render = {


    "status":"success",

    "type":"render",

    "engine":"render_runtime",


    "image":{

        "filename":"render.png",

        "url":"/output/render.png",

        "path":"C:/ComfyUI-Zluda/output/render.png"

    }

}



render_result = adapter.adapt(
    render
)


print(render_result)



assert "image" in render_result

assert render_result["image"]["url"] == "/output/render.png"



print(
    "✅ RENDER ADAPTER OK"
)



print(
    "\n🎉 RESPONSE ADAPTER CONTRACT PASSED"
)