from core.app_boot import AppBoot


# ==========================================================
# TEST_IMPORT_GPU_SAFETY_V1
#
# This file used to boot the application and call `brain.think(...)` four times
# at MODULE level, so pytest imported it during collection and ran live
# inference turns. The body is now guarded: importing this module only imports
# AppBoot; running it as a program behaves exactly as before.
# ==========================================================

if __name__ == "__main__":

    print("\n🧪 UNKNOWN ROUTE TEST START\n")

    app = AppBoot()

    brain = app.get_brain()

    tests = [

        "hello",

        "help me",

        "what is ArchitectOS",

        "how are you"

    ]

    for text in tests:

        print("\n====================")

        print("INPUT:", text)

        result = brain.think(
            text
        )

        print("\nRESULT:")

        print(result)

        print("\nSTATUS:")

        print(
            result.get("status")
        )

        print(
            "TYPE:",
            result.get("type")
        )
