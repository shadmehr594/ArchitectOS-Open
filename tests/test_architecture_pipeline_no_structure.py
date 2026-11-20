from core.intelligence.file_intelligence_router import FileIntelligenceRouter
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.architecture.brain.architectural_brain import ArchitecturalBrain

import pprint


print("\n========== ARCHITECTURE ONLY TEST ==========\n")


# ==========================================
# CAD INPUT
# ==========================================

cad = FileIntelligenceRouter().process(
    r"<repo-root>\tests\data\site_polygon_test.dxf"
)


site = cad[
    "context"
][
    "site_intelligence"
]


# ==========================================
# ARCHITECTURAL INTENT
# ==========================================

intent_engine = ArchitecturalIntent()


intent = intent_engine.extract(
    {
        "prompt":
            "design a modern villa 2 floor on this site"
    },
    {
        "site":
            site
    }
)


print("\n====== ARCHITECTURAL INTENT ======")

pprint.pp(
    intent
)


# ==========================================
# ARCHITECTURAL BRAIN INPUT
# ==========================================

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
        site

}


# ==========================================
# ARCHITECTURAL BRAIN
# ==========================================

brain = ArchitecturalBrain()


design_result = brain.design(
    brain_intent
)


design_model = design_result.to_dict()


architectural_intelligence = design_model[
    "architectural_intelligence"
]


layout = architectural_intelligence[
    "layout"
]


plan_model = architectural_intelligence[
    "plan_model"
]


# ==========================================
# RESULT
# ==========================================

print("\n====== RESULT TYPE ======")

print(
    type(design_result)
)


print("\n====== DESIGN MODEL ======")

pprint.pp(
    design_model
)


print("\n====== ARCHITECTURAL LAYOUT ======")

pprint.pp(
    layout
)


print("\n====== PLAN MODEL ======")

pprint.pp(
    plan_model
)


# ==========================================
# VALIDATE ACTIVE CONTRACT
# ==========================================

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


print("\n✓ ARCHITECTURE PIPELINE WITHOUT STRUCTURE PASSED")


print("\n========== END ==========")