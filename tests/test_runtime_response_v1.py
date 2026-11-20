# ==========================================================
# ArchitectOS Runtime Response Contract Test v1
# ==========================================================


print(
    "🚀 RUNTIME RESPONSE CONTRACT TEST v1"
)


from core.chat.runtime_response import RuntimeResponse



print(
    "\nTEST 1: CHAT RESPONSE"
)


chat = RuntimeResponse(
    response_type="chat",
    engine="llm_gateway",
    result="سلام ArchitectOS"
)


chat_json = chat.json()


print(chat_json)


assert chat_json["type"] == "chat"
assert chat_json["engine"] == "llm_gateway"
assert chat_json["result"] == "سلام ArchitectOS"
assert chat_json["status"] == "success"



print(
    "✅ CHAT CONTRACT OK"
)



print(
    "\nTEST 2: DESIGN RESPONSE"
)


design = RuntimeResponse(
    response_type="design",
    engine="god_core",
    result={
        "architectural_intent":{
            "building_type":"villa",
            "style":"modern"
        }
    }
)


design_json = design.json()


print(design_json)


assert design_json["type"] == "design"
assert design_json["engine"] == "god_core"
assert "architectural_intent" in design_json["result"]


print(
    "✅ DESIGN CONTRACT OK"
)



print(
    "\nTEST 3: RENDER RESPONSE"
)


render = RuntimeResponse(
    response_type="render",
    engine="render_runtime",
    result={
        "image":{
            "filename":"test.png",
            "url":"/output/test.png"
        }
    }
)


render_json = render.json()


print(render_json)


assert render_json["type"] == "render"
assert render_json["engine"] == "render_runtime"
assert render_json["result"]["image"]["url"] == "/output/test.png"



print(
    "✅ RENDER CONTRACT OK"
)



print(
    "\n🎉 RUNTIME RESPONSE CONTRACT PASSED"
)