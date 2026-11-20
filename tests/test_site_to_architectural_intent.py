from core.cad.cad_import_engine import CADImportEngine
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent


print("\n=== SITE TO ARCHITECTURAL INTENT TEST ===\n")


# ==========================================
# 1) LOAD CAD SITE
# ==========================================

result = CADImportEngine().load(
    {
        "file_object":
            r"tests\data\site_polygon_test.dxf"
    }
)


site = result.get(
    "site_intelligence"
)


constraints = result.get(
    "constraints"
)


if not site:

    raise Exception(
        "Site Intelligence not generated"
    )


print("✓ Site Intelligence loaded")

print(
    "Site:",
    site.get("site_id")
)

print(
    "Area:",
    site.get("area")
)



# ==========================================
# 2) BUILD CONTEXT FOR ARCHITECTURAL INTENT
# ==========================================

site_context = {


    "site": {

        "site_id":
            site.get("site_id"),


        "area":
            site.get("area"),


        "boundary":
            site.get(
                "boundary",
                []
            ),


        "bbox":
            site.get(
                "bbox",
                {}
            ),


        "orientation":
            site.get(
                "orientation"
            )

    },


    "site_constraints":

        constraints.get(
            "constraints",
            constraints
        )

}


print(
    "✓ Site Context created"
)



# ==========================================
# 3) ARCHITECTURAL INTENT
# ==========================================

engine = ArchitecturalIntent()



intent = engine.extract(

    {

        "prompt":

            "طراحی ساختمان مسکونی مدرن"

    },

    context=site_context

)



print(
    "\nArchitectural Intent:"
)


print(intent)



# ==========================================
# VALIDATION
# ==========================================


if not intent:

    raise Exception(
        "Architectural Intent failed"
    )



print(
    "\n✓ Architectural Intent generated"
)


print(
    "\n=== TEST PASSED ===\n"
)