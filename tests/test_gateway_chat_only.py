from core.brain import Brain
from core.chat.chat_architect import ChatArchitect


print("\n========== GATEWAY CHAT ONLY TEST ==========")


brain = Brain()


gateway = ChatArchitect(
    brain
)


tests = [

    "سلام",

    "خوبی؟",

    "چرا آسمان آبی است؟",

    "یک توضیح درباره معماری بده",

]


for text in tests:

    print("\nUSER:")
    print(text)

    try:

        result = gateway.handle(text)

        print("RESULT:")

        print(result)

    except Exception as e:

        print("ERROR:")
        print(type(e).__name__, e)


    print("-------------------------------------")


print("\n========== END ==========")