# ==========================================================
# ArchitectOS Memory Intelligence Engine v31 Test
# ==========================================================


from core.memory.memory_intelligence_v31 import memory_intelligence



print(
    "\n🧠 MEMORY INTELLIGENCE v31 TEST START\n"
)



# ==========================================================
# TEST 1
# ARCHITECTURE + FAMILY
# ==========================================================


query1 = "برای بچه ها یک اتاق مدرن طراحی کن"


print(
    "\n👤 QUERY:",
    query1
)


result1 = memory_intelligence.build(
    query1
)


print(
    "\n🧠 MEMORY RESULT:"
)


print(
    result1
)




# ==========================================================
# TEST 2
# COOKING
# ==========================================================


query2 = "یک غذای ایرانی درست کنم"


print(
    "\n👤 QUERY:",
    query2
)


result2 = memory_intelligence.build(
    query2
)


print(
    "\n🧠 MEMORY RESULT:"
)


print(
    result2
)




# ==========================================================
# TEST 3
# PROJECT
# ==========================================================


query3 = "وضعیت پروژه ArchitectOS چیست"


print(
    "\n👤 QUERY:",
    query3
)


result3 = memory_intelligence.build(
    query3
)


print(
    "\n🧠 MEMORY RESULT:"
)


print(
    result3
)




print(
    "\n✅ MEMORY INTELLIGENCE v31 TEST COMPLETE\n"
)