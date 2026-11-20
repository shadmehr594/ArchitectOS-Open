from skills.comfyui.comfy_runtime import ComfyRuntime


# ==========================================================
# TEST_IMPORT_GPU_SAFETY_V1
#
# This file used to call `runtime.generate(...)` at MODULE level, so pytest
# imported it during collection and submitted a REAL ComfyUI job (prefix
# `architectos_img2img_edit`, no client_id). The live call is now guarded:
# importing this module does nothing; running it as a program behaves exactly
# as before.
# ==========================================================

if __name__ == "__main__":

    runtime = ComfyRuntime()

    result = runtime.generate(
        "change facade material to glass and wood",
        mode="edit"
    )

    print("\n===== EDIT RESULT =====")
    print(result)
