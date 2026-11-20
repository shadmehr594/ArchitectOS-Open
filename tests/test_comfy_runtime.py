from skills.comfyui.comfy_runtime import ComfyRuntime


# ==========================================================
# TEST_IMPORT_GPU_SAFETY_V1
#
# This file used to call `runtime.generate(...)` at MODULE level, so pytest
# imported it during collection and submitted a REAL ComfyUI job (prefix
# `architectos_v11`, no client_id). The live call is now guarded: importing
# this module does nothing; running it as a program behaves exactly as before.
# ==========================================================

if __name__ == "__main__":

    runtime = ComfyRuntime()

    result = runtime.generate(
        "modern architectural villa, realistic photography",
        mode="image"
    )

    print("\n===== RESULT =====")
    print(result)
