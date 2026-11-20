# ==========================================================
# ArchitectOS Full UI Response Flow Contract Test v1
# UI -> Core -> RuntimeResponse -> ResponseAdapter
# ==========================================================


print(
    "🚀 FULL UI RESPONSE FLOW TEST v1"
)


from core.chat.runtime_response import RuntimeResponse
from core.chat.response_adapter import ResponseAdapter



adapter = ResponseAdapter()



# ==========================================================
# TEST 1: CHAT FLOW
# ==========================================================

print(
    "\nTEST 1: CHAT FLOW"
)


chat_runtime = RuntimeResponse(

    response_type="chat",

    engine="llm_gateway",

    result="Hello ArchitectOS"

)



chat_payload = adapter.adapt(

    chat_runtime.json()

)


print(chat_payload)



assert (
    chat_payload["type"]
    ==
    "chat"
)


assert (
    chat_payload["result"]
    ==
    "Hello ArchitectOS"
)


print(
    "✅ CHAT FLOW OK"
)





# ==========================================================
# TEST 2: DESIGN FLOW
# ==========================================================

print(
    "\nTEST 2: DESIGN FLOW"
)



design_runtime = RuntimeResponse(

    response_type="design",

    engine="god_core",

    result={

        "architectural_intent": {

            "building_type":
                "villa",

            "style":
                "modern"

        }

    }

)



design_payload = adapter.adapt(

    design_runtime.json()

)



print(design_payload)



assert (
    design_payload["type"]
    ==
    "design"
)


assert (
    "design"
    in
    design_payload
)


print(
    "✅ DESIGN FLOW OK"
)





# ==========================================================
# TEST 3: RENDER MOCK FLOW
# ==========================================================

print(
    "\nTEST 3: RENDER MOCK FLOW"
)



render_runtime = RuntimeResponse(

    response_type="render",

    engine="render_runtime",

    result={

        "image": {

            "filename":
                "test.png",

            "url":
                "/output/test.png"

        }

    }

)



render_payload = adapter.adapt(

    render_runtime.json()

)



print(render_payload)



assert (
    render_payload["type"]
    ==
    "render"
)


print(
    "✅ RENDER FLOW OK"
)





# ==========================================================
# COMPLETE
# ==========================================================


print(
    "\n🎉 FULL UI RESPONSE FLOW PASSED"
)