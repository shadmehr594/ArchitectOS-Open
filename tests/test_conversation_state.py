from core.chat.conversation_state import ConversationState


state = ConversationState()


print(
    state.get()
)


state.update({

    "last_intent": "villa_design",

    "active_project": "modern_villa",

    "last_request": "یک ویلای مدرن طراحی کن"

})


print(
    state.get()
)


print(
    state.is_followup(
        "استخر هم اضافه کن"
    )
)