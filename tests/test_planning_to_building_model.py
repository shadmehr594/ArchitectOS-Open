from core.cad.cad_import_engine import CADImportEngine
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.architecture.brain.architectural_brain import ArchitecturalBrain
from core.spatial.architectural_building_model import ArchitecturalBuildingModel


print("\n=== PLANNING TO BUILDING MODEL TEST ===\n")


# -----------------------------
# SITE
# -----------------------------

cad = CADImportEngine()

site = cad.load(
    {
        "file_object":
            r"tests\data\site_polygon_test.dxf"
    }
)


print("✓ Site loaded")
print(
    "Site:",
    site["site_intelligence"]["site_id"]
)


# -----------------------------
# INTENT
# -----------------------------

intent_engine = ArchitecturalIntent()

intent = intent_engine.extract(
    {
        "prompt":
            "طراحی ساختمان مسکونی مدرن"
    },
    {
        "site":
            site["site_intelligence"]
    }
)


print("✓ Architectural Intent")
print(
    intent["style"]
)


# -----------------------------
# ARCHITECTURAL PLANNING
# -----------------------------

brain_intent = {

    "building_type":
        intent.get(
            "building_type",
            "building"
        ),

    "functions":
        intent.get(
            "functions",
            []
        ),

    "spaces":
        intent.get(
            "spaces",
            []
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
        site["site_intelligence"]

}


brain = ArchitecturalBrain()


design_result = brain.design(
    brain_intent
)


design_model = design_result.to_dict()


architectural_intelligence = design_model[
    "architectural_intelligence"
]


planning = architectural_intelligence[
    "layout"
]


plan_model = architectural_intelligence[
    "plan_model"
]


assert isinstance(
    planning,
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


print("✓ Architectural Planning generated")

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
        "floor_distribution",
        {}
    )
)


# -----------------------------
# BUILDING MODEL
# -----------------------------

model_engine = ArchitecturalBuildingModel()


building_model = model_engine.build(

    project=intent,

    spatial={
        "nodes": [],
        "connections": [],
        "zones":
            intent["zones"]
    },

    layout=planning,

    geometry=
        site["geometry"],

    constraints=
        site["constraints"],

    validation=
        {
            "status":
                "pending"
        },

    render_context=
        {
            "camera":
                intent["camera"],

            "mood":
                intent["mood"]
        }

)


print("✓ Building Model generated")


print("\nBUILDING:")
print(
    building_model["building"]
)


print("\nLAYOUT:")
print(
    building_model["layout"]
)


print("\nMETADATA:")
print(
    building_model["metadata"]
)


print("\n=== TEST PASSED ===\n")