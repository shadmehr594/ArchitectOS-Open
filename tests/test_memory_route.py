# ==========================================================
# ArchitectOS Memory Route Test
# ==========================================================


from core.app_boot import AppBoot


# ==========================================================
# TEST_IMPORT_GPU_SAFETY_V1
#
# This file used to boot the application and call `brain.think(...)` at MODULE
# level, so pytest imported it during collection and ran a live inference turn.
# The body is now guarded: importing this module only imports AppBoot; running
# it as a program behaves exactly as before.
# ==========================================================

if __name__ == "__main__":

    print("\n🧠 MEMORY ROUTE TEST START\n")

    # ==========================================================
    # BOOT
    # ==========================================================

    app = AppBoot()

    brain = app.get_brain()

    # ==========================================================
    # MEMORY QUERY
    # ==========================================================

    result = brain.think(

        "یادته من کی هستم"

    )

    print("\n===== MEMORY RESULT =====")

    print(result)

    print("\n===== STATUS =====")

    print(

        result.get(
            "status"
        )

    )

    print("\n===== TYPE =====")

    print(

        result.get(
            "type"
        )

    )
