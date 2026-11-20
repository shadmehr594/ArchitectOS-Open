# ==========================================================
# ArchitectOS Brain Memory Route Simple Test
# GOD CORE v21.7 Memory Bridge Validation
# ==========================================================


from core.app_boot import AppBoot



print("==============================")
print("BRAIN MEMORY ROUTE TEST")
print("==============================")


# ==========================================
# REAL BOOT PATH
# ==========================================

app = AppBoot()

brain = app.get_brain()



# ==========================================
# MEMORY QUERY
# ==========================================

result = brain.process(
    "یادته من کی هستم"
)



print("\nRESULT:")
print(result)



print("\nTEST COMPLETE")