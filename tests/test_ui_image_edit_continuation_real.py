# ==========================================================
# ArchitectOS UI Image Edit Continuation Flow Test v1
# NO IMAGE GENERATION
#
# Upload Image
#        |
#        ↓
# Chat Instruction
#        |
#        ↓
# Image Edit State
# ==========================================================

import requests
import os


print(
    "\n🚀 UI IMAGE EDIT CONTINUATION TEST v1\n"
)


UI_IMAGE = (
    "http://127.0.0.1:3000/api/image"
)


UI_CHAT = (
    "http://127.0.0.1:3000/api/chat"
)


TEST_IMAGE = (
    "tests/assets/test_edit.png"
)



# ==========================================================
# CREATE TEST IMAGE
# ==========================================================

os.makedirs(
    "tests/assets",
    exist_ok=True
)


with open(
    TEST_IMAGE,
    "wb"
) as f:

    f.write(
        b"architectos-edit-test"
    )



# ==========================================================
# STEP 1
# UPLOAD IMAGE
# ==========================================================

print(
    "STEP 1: IMAGE UPLOAD"
)


with open(
    TEST_IMAGE,
    "rb"
) as image:


    response = requests.post(

        UI_IMAGE,

        files={

            "image":
            (
                "test_edit.png",
                image,
                "image/png"
            )

        },

        timeout=10800

    )



print(
    response.text
)


assert response.status_code == 200



upload_data = response.json()



assert (

    upload_data["status"]
    ==
    "success"

)



print(
    "✅ IMAGE UPLOAD OK"
)



# ==========================================================
# STEP 2
# EDIT INSTRUCTION
# ==========================================================

print(
    "\nSTEP 2: EDIT COMMAND"
)



response = requests.post(

    UI_CHAT,

    json={

        "text":
        "این تصویر را مدرن‌تر کن"

    },

    timeout=10800

)



print(
    response.text
)



assert response.status_code == 200



chat_data = response.json()



assert (

    chat_data["status"]
    ==
    "success"

    or

    chat_data.get("response")

)



print(
    "\n✅ IMAGE EDIT CONTINUATION FLOW PASSED\n"
)