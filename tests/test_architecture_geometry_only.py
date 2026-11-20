from core.intelligence.file_intelligence_router import FileIntelligenceRouter
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.architecture.brain.architectural_brain import ArchitecturalBrain
from core.bim.design_geometry_adapter import DesignGeometryAdapter
from core.spatial.spatial_position_solver import SpatialPositionSolver

import pprint


print("\n========== ARCHITECTURE GEOMETRY ONLY TEST ==========\n")


# ==========================================
# CAD INPUT
# ==========================================

cad = FileIntelligenceRouter().process(
    r"<repo-root>\tests\data\site_polygon_test.dxf"
)


print("\n====== CAD CONTEXT ======")

pprint.pp(
    cad["context"]
)


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
            cad["context"]["site_intelligence"]
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
        cad["context"]["site_intelligence"]

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


planning = architectural_intelligence[
    "layout"
]


plan_model = architectural_intelligence[
    "plan_model"
]


print("\n====== ARCHITECTURAL PLANNING ======")

pprint.pp(
    planning
)


print("\n====== PLAN MODEL ======")

pprint.pp(
    plan_model
)



# ==========================================
# ACTIVE ARCHITECTURAL LAYOUT
# ==========================================

layout = planning


print("\n====== ARCHITECTURAL LAYOUT ======")

pprint.pp(
    layout
)

# ==========================================
# PLANNING TO SPATIAL GEOMETRY CONTRACT
# ==========================================

floor_distribution = layout.get(
    "floor_distribution",
    {}
)


space_registry = layout.get(
    "space_registry",
    []
)


registry_by_name = {

    space["name"]:
        space

    for space in space_registry

    if space.get(
        "name"
    )

}


spatial_building = {}


for level, space_names in floor_distribution.items():

    floor_spaces = []


    for space_name in space_names:

        space = registry_by_name.get(
            space_name
        )


        if space is not None:

            floor_spaces.append(
                dict(
                    space
                )
            )


    spatial_building[level] = {

        "level":
            level,

        "spaces":
            floor_spaces

    }


print(
    "\n====== PLANNING TO SPATIAL CONTRACT ======"
)

pprint.pp(
    spatial_building
)

from core.spatial.spatial_geometry_generator import SpatialGeometryGenerator


# ==========================================
# SPATIAL GEOMETRY GENERATION
# ==========================================

geometry_generator = SpatialGeometryGenerator()


spatial_geometry = geometry_generator.generate(
    {
        "building":
            spatial_building
    }
)


print("\n====== GENERATED SPATIAL GEOMETRY ======")

pprint.pp(
    spatial_geometry
)

# ==========================================
# SPATIAL POSITION SOLVER
# ==========================================

solver = SpatialPositionSolver()


layout = solver.solve(
    spatial_building
)


print("\n====== SOLVED SPATIAL LAYOUT ======")

pprint.pp(
    layout
)



# ==========================================
# GEOMETRY ADAPTER TEST
# ==========================================

adapter = DesignGeometryAdapter()


geometry_input = {

    "spatial":
    {

        "floors":
        {

            floor["name"]:
                floor

            for floor in spatial_geometry["geometry_model"]["floors"]

        }

    }

}


print("\n====== GEOMETRY INPUT ======")

pprint.pp(
    geometry_input
)


print(
    "\n====== SPATIAL TO GEOMETRY CONTRACT ======"
)

for level, data in layout.items():

    print(
        "\nLEVEL:",
        level
    )

    for space in data["spaces"]:

        print(
            space["name"],
            "ZONE:",
            space.get("zone"),
            "X:",
            space.get("x"),
            "Y:",
            space.get("y"),
            "WIDTH:",
            space.get("width"),
            "HEIGHT:",
            space.get("height")
        )

print(
    "=========================================="
)


geometry_result = adapter.convert(
    geometry_input
)


print("\n====== GEOMETRY RESULT ======")

pprint.pp(
    geometry_result
)



print("\n========== END ==========\n")