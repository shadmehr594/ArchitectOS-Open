# ==========================================================
# ArchitectOS Chat Runtime Test v1.1
# ==========================================================


from core.app_boot import AppBoot
from core.chat.chat_architect import ChatArchitect



print(
    "\n🚀 CHAT RUNTIME TEST START\n"
)



# ==================================================
# BOOT CORE
# ==================================================

app = AppBoot()


brain = app.get_brain()



# ==================================================
# CHAT GATEWAY
# ==================================================

chat = ChatArchitect(
    brain
)



# ==================================================
# TEST 1 - NORMAL CHAT
# ==================================================

print(
    "\n===== TEST CHAT ====="
)


result = chat.handle(
    "سلام"
)


print(result)




# ==================================================
# TEST 2 - DESIGN
# ==================================================

print(
    "\n===== TEST DESIGN ====="
)


result = chat.handle(
    "یک ویلای مدرن طراحی کن"
)


print(
    result["type"]
)


print(
    result["engine"]
)


print(
    result["result"]["status"]
)




# ==================================================
# TEST 3 - IMAGE GENERATE
# ==================================================

print(
    "\n===== TEST IMAGE GENERATE ====="
)


result = chat.handle(
    "draw a modern house"
)


print(result)




# ==================================================
# TEST 4 - IMAGE EDIT
# ==================================================

print(
    "\n===== TEST IMAGE EDIT ====="
)


image_path = (
    "D:/test/facade.png"
)


payload = {

    "text":
        "change facade to modern glass facade with natural stone",

    "image":
        image_path

}


result = chat.handle(
    payload
)


print(result)




print(
    "\n✅ CHAT RUNTIME TEST COMPLETE"
)