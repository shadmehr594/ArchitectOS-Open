# ==========================================================
# ArchitectOS UI Gateway Test v1
#
# UI Gateway -> Core API
#
# Test:
# - Chat Proxy
# - Image Proxy availability
# ==========================================================


import requests


UI_BASE = "http://127.0.0.1:3000"



# ==========================================================
# CHAT TEST
# ==========================================================


def test_chat():


    print(
        "\n💬 TEST CHAT GATEWAY"
    )


    payload = {

        "text":
            "سلام"

    }


    try:


        response = requests.post(

            UI_BASE + "/api/chat",

            json=payload,

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
            response.text[:2000]
        )


    except Exception as e:


        print(
            "❌ CHAT TEST ERROR:",
            e
        )





# ==========================================================
# IMAGE ENDPOINT TEST
# ==========================================================


def test_image_endpoint():


    print(
        "\n🖼️ TEST IMAGE ENDPOINT"
    )


    try:


        response = requests.post(

            UI_BASE + "/api/image",

            timeout=10

        )


        print(
            "STATUS:",
            response.status_code
        )


        print(
            response.text
        )


    except Exception as e:


        print(
            "❌ IMAGE ENDPOINT ERROR:",
            e
        )





# ==========================================================
# RUN
# ==========================================================


if __name__ == "__main__":


    print(
        "🚀 ARCHITECTOS UI GATEWAY TEST v1"
    )


    test_chat()


    test_image_endpoint()


    print(
        "\n✅ TEST COMPLETE"
    )