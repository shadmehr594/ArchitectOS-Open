from core.app_boot import AppBoot


# ==========================================================
# TEST_IMPORT_GPU_SAFETY_V1
#
# This file used to boot the application and call `brain.think(...)` three times
# at MODULE level, so pytest imported it during collection and ran live
# inference turns. The body is now guarded: importing this module only imports
# AppBoot; running it as a program behaves exactly as before.
# ==========================================================

if __name__ == "__main__":

    print("\n🏛️ DESIGN ROUTE TEST START\n")

    app = AppBoot()

    brain = app.get_brain()

    tests = [

        "create a modern architectural villa",

        "design a two floor house",

        "update my previous design"

    ]

    for text in tests:

        print("\n====================")

        print("INPUT:", text)

        result = brain.think(
            text
        )

        print("\nTYPE:")
        print(
            result.get("type")
        )

        print("\nSTATUS:")
        print(
            result.get("status")
        )

        print("\nINTENT:")
        print(
            result.get("intent")
        )
