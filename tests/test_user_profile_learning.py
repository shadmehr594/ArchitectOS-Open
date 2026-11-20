# ==========================================================
# ArchitectOS User Profile Learning Test v1
# ==========================================================

from core.memory.user_profile_memory import user_profile_memory
from core.memory.profile_extractor import ProfileExtractor


print("\n🧠 USER PROFILE LEARNING TEST START\n")


extractor = ProfileExtractor(
    user_profile_memory
)


messages = [

    "من دو فرزند دارم",

    "غذاهای ایرانی دوست دارم",

    "به آشپزی علاقه دارم",

    "سبک معماری مدرن را دوست دارم",

    "پروژه اصلی من ArchitectOS است"

]


for msg in messages:

    print("\n👤 USER:", msg)

    result = extractor.extract(
        msg
    )

    print(
        "🧠 EXTRACTED:",
        result
    )



print("\n===== PROFILE =====")

print(
    user_profile_memory.get_profile()
)


print("\n===== SUMMARY =====")

print(
    user_profile_memory.summary()
)


print(
    "\n✅ USER PROFILE LEARNING TEST COMPLETE"
)