from core.intelligence.file_intelligence_router import FileIntelligenceRouter
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.architecture.brain.architectural_brain import ArchitecturalBrain
import pprint


print("\n========== ARCHITECTURE ONLY DXF FLOW ==========\n")


# ==========================================
# 1. DXF INPUT
# ==========================================

cad = FileIntelligenceRouter().process(
    r"<repo-root>\tests\data\site_polygon_test.dxf"
)


print("\n====== CAD RESULT ======")

print(
    cad.keys()
)


print(
    "SITE CONTEXT:"
)

pprint.pp(
    cad.get(
        "context"
    )
)



# ==========================================
# 2. ARCHITECTURAL INTENT
# ==========================================

intent_engine = ArchitecturalIntent()


intent = intent_engine.extract(
    {
        "prompt":
            "design a modern villa 2 floor on this site"
    },
    {
        "site":
            cad.get(
                "context",
                {}
            ).get(
                "site_intelligence",
                {}
            )
    }
)


print("\n====== ARCHITECTURAL INTENT ======")

pprint.pp(
    intent
)


# ==========================================
# 3. ARCHITECTURAL BRAIN
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
        cad.get(
            "context",
            {}
        ).get(
            "site_intelligence",
            {}
        )

}


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


plan_data = architectural_intelligence


print("\n====== ARCHITECTURAL RESULT ======")

print(
    design_model.keys()
)


print("\n====== RAW ARCHITECTURAL LAYOUT ======")

pprint.pp(
    layout
)


print("\n====== PLAN MODEL ======")

pprint.pp(
    plan_model
)


# ==========================================
# SPATIAL LAYOUT GENERATION
# ==========================================

print(
    "\n====== SPATIAL LAYOUT GENERATION ======"
)

from core.spatial.spatial_layout_engine import (
    SpatialLayoutEngine
)


spatial_engine = SpatialLayoutEngine()


# ==========================================
# ARCHITECTURAL LAYOUT -> SPATIAL DESIGN BRIDGE
# ==========================================


print("\n====== RAW ARCHITECTURAL LAYOUT ======")

pprint.pp(layout)

print("======================================")

print("\n====== ORIGINAL ARCH LAYOUT CHECK ======")

pprint.pp(layout)

print("========================================")

print(
    "\n====== ARCHITECTURAL RELATIONSHIP CONTRACT ======"
)

print(
    "LAYOUT KEYS:",
    layout.keys()
    if isinstance(layout, dict)
    else None
)

print(
    "RELATIONSHIPS:",
    layout.get(
        "relationships"
    )
    if isinstance(layout, dict)
    else None
)

print(
    "CONNECTIONS:"
)

pprint.pp(
    layout.get(
        "connections",
        []
    )
    if isinstance(
        layout,
        dict
    )
    else []
)

print(
    "SPACE REGISTRY SAMPLE:",
    layout.get(
        "space_registry",
        []
    )[:5]
    if isinstance(layout, dict)
    else None
)

print(
    "==============================================="
)

# ==========================================
# ARCHITECTURAL LAYOUT -> FLOOR CONTRACT
# ==========================================

floor_distribution = layout.get(
    "floor_distribution",
    {}
)


space_registry = layout.get(
    "space_registry",
    []
)


layout_connections = layout.get(
    "connections",
    []
)


if not isinstance(
    layout_connections,
    list
):

    layout_connections = []


registry_by_name = {

    space["name"]:
        space

    for space in space_registry

    if space.get(
        "name"
    )

}


floor_layout = {}


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


    floor_layout[level] = {

        "level":
            level,

        "spaces":
            floor_spaces

    }


print(
    "\n====== FLOOR LAYOUT CONTRACT ======"
)

pprint.pp(
    floor_layout
)


spatial_design = {}


for level, floor in floor_layout.items():

    if not isinstance(
        floor,
        dict
    ):
        continue


    spaces = floor.get(
        "spaces",
        []
    )


    nodes = {}


    for space in spaces:

        name = space.get(
            "name"
        )

        resolved_dimensions = space.get(
            "resolved_dimensions",
            {}
        )


        if not isinstance(
            resolved_dimensions,
            dict
        ):

            resolved_dimensions = {}


        dimensional_requirements = space.get(
            "dimensional_requirements",
            {}
        )


        if not isinstance(
            dimensional_requirements,
            dict
        ):

            dimensional_requirements = {}


        resolved_width = (
            resolved_dimensions.get(
                "width"
            )
            or
            dimensional_requirements.get(
                "resolved_width"
            )
        )


        resolved_depth = (
            resolved_dimensions.get(
                "depth"
            )
            or
            dimensional_requirements.get(
                "resolved_depth"
            )
        )


        if name:

            nodes[name] = {

                "type": "IfcSpace",

                "canonical_name":
                    space.get(
                        "canonical_name"
                    ),

                "zone":
                    space.get(
                        "zone"
                    ),

                "planning_zone":
                    space.get(
                        "planning_zone"
                    ),

                "space_type":
                    space.get(
                        "space_type"
                    ),

                "access":
                    list(
                        space.get(
                            "access",
                            []
                        )
                    ),

                "adjacent_to":
                    list(
                        space.get(
                            "adjacent_to",
                            []
                        )
                    ),

                "protected_zone":
                    space.get(
                        "protected_zone",
                        False
                    ),

                "circulation_profile":
                    space.get(
                        "circulation_profile"
                    ),

                "dimensional_requirements":
                    dict(
                        space.get(
                            "dimensional_requirements",
                            {}
                        )
                    ),

                "semantic":
                    space.get(
                        "semantic",
                        {}
                    ),


                "w":
                    space.get(
                        "w",
                        space.get(
                            "width",
                            resolved_width
                            if resolved_width is not None
                            else 4
                        )
                    ),


                "h":
                    space.get(
                        "h",
                        space.get(
                            "height",
                            resolved_depth
                            if resolved_depth is not None
                            else 4
                        )
                    ),


                "width":
                    space.get(
                        "width",
                        space.get(
                            "w",
                            resolved_width
                            if resolved_width is not None
                            else 4
                        )
                    ),


                "height":
                    space.get(
                        "height",
                        space.get(
                            "h",
                            resolved_depth
                            if resolved_depth is not None
                            else 4
                        )
                    )

            }

            if space.get(
                "x"
            ) is not None:

                nodes[name]["x"] = (
                    space.get(
                        "x"
                    )
                )


            if space.get(
                "y"
            ) is not None:

                nodes[name]["y"] = (
                    space.get(
                        "y"
                    )
                )


    floor_space_names = set(
        nodes.keys()
    )


    floor_connections = []


    for connection in layout_connections:

        if not isinstance(
            connection,
            dict
        ):

            continue


        source = connection.get(
            "from"
        )

        target = connection.get(
            "to"
        )


        if (
            source in floor_space_names
            and
            target in floor_space_names
        ):

            floor_connections.append(
                dict(
                    connection
                )
            )


    spatial_design[level] = {

        "nodes":
            nodes,

        "connections":
            floor_connections

    }

print(
    "====== SPATIAL DESIGN BRIDGE ======"
)

pprint.pp(
    spatial_design
)

print(
    "===================================="
)

# ==========================================
# SPATIAL ENGINE GENERATION
# ==========================================

spatial_result = spatial_engine.generate(
    spatial_design,
    plan_data
)

print("\n====== SPATIAL ENGINE OUTPUT DEBUG ======")

print(type(spatial_result))

if isinstance(spatial_result, dict):
    print(spatial_result.keys())

print("========================================")


print("\n====== FINAL SPATIAL CHECK ======")

for floor, data in spatial_result["floors"].items():

    print("\nFLOOR:", floor)

    for room in data["spaces"]:

        print(
            room.get("name"),
            room.get("x"),
            room.get("y")
        )

print("=================================")

print("\n====== FINAL SPATIAL CHECK ======")

spatial = spatial_result

print(
    "SPATIAL KEYS:",
    spatial.keys()
)

for floor, data in spatial.get("floors", {}).items():

    print("\nFLOOR:", floor)

    for room in data.get("spaces", []):

        print(
            room.get("name"),
            room.get("x"),
            room.get("y"),
            room.get("w"),
            room.get("h")
        )

print("=================================")


print("\n====== SPATIAL ENGINE OUTPUT DEBUG ======")

print(type(spatial_result))

if isinstance(spatial_result, dict):

    print(spatial_result.keys())

    print("\nFLOORS:")
    pprint.pp(
        spatial_result.get("floors")
    )

    print("\nGROUND FLOOR:")
    pprint.pp(
        spatial_result
        .get("floors", {})
        .get("ground_floor")
    )

print("========================================")


print(
    "SPATIAL RESULT:"
)

pprint.pp(
    spatial_result
)

print(
    "========================================"
)

# ==========================================
# EXPORT COMPATIBLE SPATIAL
# ==========================================

export_spatial = {}

for level, data in spatial_design.items():

    export_spatial[level] = {

        "nodes":
            data.get(
                "nodes",
                {}
            ),

        "connections":
            []

    }


print(
    "====== EXPORT SPATIAL ======"
)

pprint.pp(
    export_spatial
)

print(
    "============================"
)



# ==========================================
# GEOMETRY INPUT
# ==========================================

geometry_input = {

    "spatial":
        spatial_result

}


print(
    "\n====== GEOMETRY INPUT ======"
)

pprint.pp(
    geometry_input
)

print(
    "============================="
)



# ==========================================
# EXPORT SESSION
# ==========================================

export_session = (
    "ARCHITECTURE_ONLY_DXF"
)



# ==========================================
# DESIGN GEOMETRY ADAPTER
# ==========================================

print(
    "\n====== ARCH RESULT GEOMETRY DEBUG ======"
)


from core.bim.design_geometry_adapter import (

    DesignGeometryAdapter

)


adapter = DesignGeometryAdapter()



geometry_result = adapter.convert(

    geometry_input

)



geometry = geometry_result.get(

    "geometry"

)

# ==========================================
# PRODUCTION EXPORT BRIDGE
# ==========================================

from core.export.production_export_engine import (
    ProductionExportEngine
)


bim_state = {

    "spatial":
    spatial_result,

    "geometry":
    geometry,

    "levels":
    geometry.get(
        "levels",
        []
    ),

    "walls":
    geometry.get(
        "walls",
        []
    ),

    "rooms":
    geometry.get(
        "rooms",
        []
    ),

    "doors":
    geometry.get(
        "doors",
        []
    ),

    "windows":
    geometry.get(
        "windows",
        []
    )

}


print(
    "\n====== PRODUCTION EXPORT INPUT ======"
)

pprint.pp(
    bim_state.keys()
)

print(
    "====================================="
)

print("\n====== DXF INPUT DEBUG ======")

print("WALL SAMPLE:")
for w in geometry["walls"][:5]:
    print(w)

print("\nDOOR SAMPLE:")
for d in geometry["doors"][:5]:
    print(d)

print("\nWINDOW SAMPLE:")
for win in geometry["windows"][:5]:
    print(win)

print("==============================")


export_engine = ProductionExportEngine()


export_result = export_engine.export(
    bim_state
)


print(
    "\n====== EXPORT RESULT ======"
)

pprint.pp(
    export_result
)

print(
    "============================"
)

# ==========================================
# DXF EXPORT
# ==========================================

print(
    "\n====== DXF EXPORT ======"
)

from core.export.cad_exporter import CADExporter


dxf_exporter = CADExporter()

print("\n====== DXF INPUT CHECK ======")

print(type(geometry))

print(geometry.keys())

print("walls:", len(geometry.get("walls", [])))

print("rooms:", len(geometry.get("rooms", [])))

print("levels:", geometry.get("levels"))

print("============================")

spatial = {
    "nodes": {}
}


dxf_path = dxf_exporter.export(

    spatial,

    geometry,

    output=r"<repo-root>\exports\architecture_only_villa.dxf"

)


print(
    "DXF CREATED:",
    dxf_path
)

print(
    "========================"
)



print(

    "GEOMETRY KEYS:",

    geometry.keys()

    if geometry

    else None

)



print(

    "WALLS:",

    len(

        geometry.get(

            "walls",

            []

        )

    )

    if geometry

    else 0

)



print(

    "ROOMS:",

    len(

        geometry.get(

            "rooms",

            []

        )

    )

    if geometry

    else 0

)



print(

    "DOORS:",

    len(

        geometry.get(

            "doors",

            []

        )

    )

    if geometry

    else 0

)



print(

    "WINDOWS:",

    len(

        geometry.get(

            "windows",

            []

        )

    )

    if geometry

    else 0

)



print(
    "========================================"
)



print(
    design_model.keys()
)



print(
    "\nLAYOUT:"
)

pprint.pp(
    layout
)



print(
    "\nSPATIAL:"
)

pprint.pp(
    spatial_result
)



print(
    "\n========== END ==========\n"
)