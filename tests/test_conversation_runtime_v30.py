from core.chat.conversation_state import ConversationState


state = ConversationState()


print("\n🧠 CONVERSATION RUNTIME v30 TEST START\n")


state.update({

    "last_request":
        "یک ویلای مدرن طراحی کن",

    "last_response_type":
        "design",

    "last_topic":
        "design",

    "active_project":
        "villa"

})


print(state.get())


state.update({

    "last_request":
        "یک تصویر بساز",

    "last_response_type":
        "image",

    "last_topic":
        "render"

})


print(state.get())


print("\n✅ CONVERSATION RUNTIME v30 TEST COMPLETE")