from core.cad.cad_import_engine import CADImportEngine
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.architecture.brain.architectural_brain import ArchitecturalBrain


print("\n=== SITE TO PLANNING TEST ===\n")


# 1. LOAD CAD
cad = CADImportEngine().load(
    {
        "file_object":
        r"tests\data\site_polygon_test.dxf"
    }
)


site = cad["site_intelligence"]

print("✓ Site Intelligence")
print("Site:", site["site_id"])
print("Area:", site["area"])



# 2. CREATE ARCHITECTURAL INTENT

intent_engine = ArchitecturalIntent()

intent = intent_engine.extract(
    {
        "prompt":
        "طراحی ساختمان مسکونی مدرن"
    },
    {
        "site":
        site
    }
)


print("\n✓ Architectural Intent")
print(intent["style"])
print(intent["functions"])



# 3. BUILD ARCHITECTURAL BRAIN INPUT

brain_intent = {

    "building_type":
        intent.get(
            "building_type",
            "villa"
        ),

    "functions":
        intent.get(
            "functions",
            []
        ),

    "spaces":
        intent.get(
            "spaces",
            [
                "parking",
                "lobby",
                "living",
                "bedroom",
                "kitchen"
            ]
        ),

    "style":
        intent.get(
            "style",
            "modern"
        ),

    "requirements":
        intent.get(
            "requirements",
            []
        ),

    "site":
        site

}



# 4. ARCHITECTURAL PLANNING

brain = ArchitecturalBrain()


result = brain.design(
    brain_intent
)


design_model = result.to_dict()


architectural_intelligence = design_model[
    "architectural_intelligence"
]


layout = architectural_intelligence[
    "layout"
]


plan_model = architectural_intelligence[
    "plan_model"
]



# 5. VALIDATE ACTIVE PLANNING CONTRACT

assert isinstance(
    layout,
    dict
)


assert isinstance(
    plan_model,
    dict
)


assert len(
    plan_model.get(
        "spaces",
        []
    )
) > 0


assert len(
    plan_model.get(
        "floor_distribution",
        {}
    )
) > 0


assert len(
    layout.get(
        "space_registry",
        []
    )
) > 0



print(
    "\n✓ Architectural Planning Generated"
)


print(
    "Space Count:",
    len(
        plan_model.get(
            "spaces",
            []
        )
    )
)


print(
    "Floor Distribution:",
    plan_model.get(
        "floor_distribution"
    )
)


print(
    "Zones:",
    plan_model.get(
        "zones"
    )
)


print(
    "\n=== TEST PASSED ==="
)