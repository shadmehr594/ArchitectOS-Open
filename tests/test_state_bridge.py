from core.brain import Brain
from core.chat.chat_architect import ChatArchitect


print("\n========== STATE BRIDGE TEST ==========\n")


brain = Brain()

chat = ChatArchitect(
    brain
)


text = "یک خانه کوچک آجری طراحی کن"


print("USER:")
print(text)


print("\n========== EXECUTE ==========\n")


result = chat.handle(text)


print("\n========== RESPONSE CHECK ==========\n")


print("RESULT KEYS:")
print(result.keys())


print("\nDESIGN:")
print(
    result.get("result")
)


print("\nARCH INTENT:")
print(
    result.get("architectural_intent")
)


print("\n========== INTERNAL STATE ==========\n")


state = getattr(
    chat,
    "conversation_state",
    None
)


print("CHAT STATE OBJECT:")
print(state)


if state is not None:

    print("\nSTATE TYPE:")
    print(type(state))


    # New ConversationState object API
    if hasattr(state, "get"):

        try:
            state_data = state.get()

        except Exception as e:
            state_data = None
            print("STATE GET ERROR:", e)


        if isinstance(state_data, dict):

            print("\nlast_design:")
            print(
                state_data.get("last_design")
            )

            print("\nlast_architectural_intent:")
            print(
                state_data.get("last_architectural_intent")
            )

            print("\nlast_prompt:")
            print(
                state_data.get("last_prompt")
            )


    else:

        print("\nlast_design:")
        print(
            getattr(
                state,
                "last_design",
                None
            )
        )

        print("\nlast_architectural_intent:")
        print(
            getattr(
                state,
                "last_architectural_intent",
                None
            )
        )

        print("\nlast_prompt:")
        print(
            getattr(
                state,
                "last_prompt",
                None
            )
        )


print("\n========== END ==========\n")