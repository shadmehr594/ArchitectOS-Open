from core.intent_router import IntentRouter


router = IntentRouter()


tests = [

    "سلام",

    "چرا آسمان آبی است؟",

    "یک توضیح درباره معماری بده",

    "یک ویلای مدرن طراحی کن"

]


print("\n========== ROUTER CHAT TEST ==========\n")


for text in tests:

    print("USER:")
    print(text)

    result = router.route(text)

    print("ROUTE:")
    print(result)

    print("-------------------------------------")


print("\n========== END ==========")