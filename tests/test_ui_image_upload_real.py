# ==========================================================
# ArchitectOS UI Image Upload Flow Test v1
# NO IMAGE GENERATION
# Upload -> Gateway -> Core -> ImageHandler
# ==========================================================

import requests
import os


print("\n🚀 UI IMAGE UPLOAD FLOW TEST v1\n")


UI_IMAGE_ENDPOINT = (
    "http://127.0.0.1:3000/api/image"
)


TEST_IMAGE = (
    "tests/assets/test_upload.png"
)


# ==========================================================
# CREATE MOCK IMAGE
# ==========================================================

os.makedirs(
    "tests/assets",
    exist_ok=True
)


if not os.path.exists(TEST_IMAGE):

    with open(
        TEST_IMAGE,
        "wb"
    ) as f:

        f.write(
            b"architectos-test-image"
        )



# ==========================================================
# SEND IMAGE
# ==========================================================

with open(
    TEST_IMAGE,
    "rb"
) as image_file:


    files = {

        "image":
        (
            "test_upload.png",
            image_file,
            "image/png"
        )

    }


    response = requests.post(

        UI_IMAGE_ENDPOINT,

        files=files,

        timeout=10800

    )



print(
    "STATUS:",
    response.status_code
)


print(
    "RESPONSE:"
)


print(
    response.text
)



assert response.status_code == 200


print(
    "\n✅ IMAGE UPLOAD FLOW PASSED\n"
)