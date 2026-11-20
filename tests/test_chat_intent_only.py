from core.cognition.intent_engine import intent_engine


tests = [

    "سلام",

    "خوبی؟",

    "تو کی هستی؟",

    "چرا آسمان آبی است؟",

    "فرق هوش مصنوعی و انسان چیست؟",

    "یک توضیح درباره معماری بده",

    "ممنون",

]


print("\n========== CHAT INTENT TEST ==========\n")


for text in tests:

    print("USER:")
    print(text)

    result = intent_engine.analyze(text)

    print("RESULT:")
    print(result.__dict__)

    print("-------------------------------------")


print("\n========== END TEST ==========")