from core.chat.conversation_state import ConversationState


state = ConversationState()


result = {

    "type": "design",

    "result": {

        "intent": "villa_design",

        "building_type": "villa"

    }

}


state.update_from_result(

    "یک ویلای مدرن طراحی کن",

    result

)


print(
    state.get()
)


print(
    state.is_followup(
        "استخر هم اضافه کن"
    )
)