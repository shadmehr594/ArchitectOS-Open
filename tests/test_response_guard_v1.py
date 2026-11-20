from core.chat.response_guard import response_guard



print(
    "\n🛡️ RESPONSE GUARD TEST START\n"
)



tests = [

    (
        "سلام",
        "سلام! Hello! Bonjour!"
    ),


    (
        "hello",
        "Hello! How are you?"
    ),


    (
        "یک خانه مدرن طراحی کن",
        "A modern house design"
    )

]



for user, answer in tests:


    print("\nUSER:")
    print(user)


    print("\nRAW:")
    print(answer)


    result = response_guard.apply(

        user,

        answer

    )


    print("\nRESULT:")
    print(result)



print(
    "\n✅ RESPONSE GUARD v1 TEST COMPLETE"
)