from core.cad.cad_import_engine import CADImportEngine

from core.prompt_intelligence.architectural_intent import (
    ArchitecturalIntent
)

from core.architecture.brain.architectural_brain import (
    ArchitecturalBrain
)

from core.spatial.architectural_building_model import (
    ArchitecturalBuildingModel
)


print(
    "\n=== ONTOLOGY TO PLANNING TEST ===\n"
)



# ==================================================
# LOAD SITE INTELLIGENCE
# ==================================================

site_result = CADImportEngine().load(
    {
        "file_object":
            r"tests\data\site_polygon_test.dxf"
    }
)


assert (
    "site_intelligence"
    in
    site_result
)


site = site_result[
    "site_intelligence"
]


print(
    "✓ Site Intelligence"
)

print(
    "Site:",
    site["site_id"]
)



assert (
    site["status"]
    ==
    "ready"
)



# ==================================================
# ARCHITECTURAL INTENT
# ==================================================

intent_engine = ArchitecturalIntent()



intent = intent_engine.extract(

    {

        "prompt":
            "طراحی ویلای مدرن با استخر و تراس"

    },


    {

        "site":
            site

    }

)



print(
    "\n✓ Architectural Intent"
)


print(
    intent["building_type"]
)


print(
    intent["style"]
)


print(
    intent["spaces"]
)



# ==================================================
# ONTOLOGY VALIDATION
# ==================================================

assert (
    intent["category"]
    ==
    "residential"
)


assert (
    intent["building_type"]
    ==
    "villa"
)


assert (
    intent["style"]
    ==
    "modern"
)


assert (
    isinstance(
        intent["spaces"],
        list
    )
)


assert (
    "living_room"
    in
    intent["spaces"]
)


assert (
    "pool"
    in
    intent["spaces"]
)



assert (
    "zones"
    in
    intent
)


assert (
    "relationships"
    in
    intent
)



# ==================================================
# ARCHITECTURAL BRAIN
# ==================================================

brain_intent = {

    "building_type":
        intent.get(
            "building_type",
            "villa"
        ),

    "category":
        intent.get(
            "category",
            "residential"
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

    "zones":
        intent.get(
            "zones",
            {}
        ),

    "relationships":
        intent.get(
            "relationships",
            []
        ),


    "site":
        site

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


print(
    "\n✓ Architectural Planning Generated"
)


print(
    "\n====== ACTIVE LAYOUT ======"
)

print(
    layout
)


print(
    "\n====== ACTIVE PLAN MODEL ======"
)

print(
    plan_model
)



# ==================================================
# ACTIVE PLANNING CONTRACT VALIDATION
# ==================================================

assert isinstance(
    layout,
    dict
)


assert isinstance(
    plan_model,
    dict
)


assert (
    "spaces"
    in
    plan_model
)


assert (
    "floor_distribution"
    in
    plan_model
)


assert (
    "space_registry"
    in
    layout
)


assert (
    "connections"
    in
    layout
)


assert (
    "zones"
    in
    layout
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
    "\n✓ Active Planning Contract Validation Passed"
)


# ==================================================
# ONTOLOGY -> PLAN SPACE VALIDATION
# ==================================================

registry = layout.get(
    "space_registry",
    []
)


registry_names = {

    space.get(
        "name"
    )

    for space in registry

    if isinstance(
        space,
        dict
    )

}


canonical_names = {

    space.get(
        "canonical_name"
    )

    for space in registry

    if isinstance(
        space,
        dict
    )

}


resolved_names = (
    registry_names
    |
    canonical_names
)


assert (
    "living_room"
    in
    resolved_names
    or
    "living"
    in
    resolved_names
)


assert (
    "pool"
    in
    resolved_names
)


assert (
    "terrace"
    in
    resolved_names
)


print(
    "\n✓ Ontology Space Propagation Validation Passed"
)


# ==================================================
# RELATIONSHIP VALIDATION
# ==================================================

connections = layout.get(
    "connections",
    []
)


assert isinstance(
    connections,
    list
)


assert any(

    connection.get(
        "from"
    )
    in
    {
        "living",
        "living_room"
    }

    and

    connection.get(
        "to"
    )
    ==
    "terrace"

    for connection in connections

)


assert any(

    connection.get(
        "from"
    )
    ==
    "terrace"

    and

    connection.get(
        "to"
    )
    ==
    "pool"

    for connection in connections

)


print(
    "\n✓ Architectural Relationship Validation Passed"
)


# ==================================================
# ZONE VALIDATION
# ==================================================

zones = layout.get(
    "zones",
    {}
)


assert isinstance(
    zones,
    dict
)


assert len(
    zones
) > 0


print(
    "\n✓ Architectural Zone Validation Passed"
)


# ==================================================
# RESIDENTIAL CORRIDOR INTELLIGENCE
# ==================================================

corridors = [

    space

    for space in registry

    if (
        isinstance(
            space,
            dict
        )
        and
        space.get(
            "name"
        )
        ==
        "corridor"
    )

]


if corridors:

    for corridor in corridors:

        dimensional_requirements = corridor.get(
            "dimensional_requirements",
            {}
        )


        circulation_profile = corridor.get(
            "circulation_profile",
            {}
        ) or dimensional_requirements.get(
            "circulation_profile",
            {}
        )


        resolved_width = (

            corridor.get(
                "resolved_width"
            )

            or

            dimensional_requirements.get(
                "resolved_width"
            )

            or

            circulation_profile.get(
                "resolved_width"
            )

        )


        assert (
            resolved_width
            ==
            1.5
        )


        assert (
            corridor.get(
                "protected_zone"
            )
            is True

            or

            circulation_profile.get(
                "protected_zone"
            )
            is True
        )


    print(
        "\n✓ Residential Corridor Intelligence Validation Passed"
    )


# ==================================================
# BUILDING MODEL GENERATION
# ==================================================

model_engine = ArchitecturalBuildingModel()


model = model_engine.build(

    project=
        intent,

    spatial=
        {

            "nodes":
                [],

            "connections":
                layout.get(
                    "connections",
                    []
                ),

            "zones":
                layout.get(
                    "zones",
                    {}
                )

        },

    layout=
        layout,

    geometry=
        site_result.get(
            "geometry",
            {}
        ),

    constraints=
        site_result.get(
            "constraints",
            {}
        ),

    validation=
        {
            "status":
                "pending"
        },

    render_context=
        {

            "camera":
                intent.get(
                    "camera"
                ),

            "mood":
                intent.get(
                    "mood"
                )

        }

)


print(
    "\n✓ Building Model Generated"
)


# ==================================================
# BUILDING MODEL VALIDATION
# ==================================================

assert (
    model["building"]["type"]
    ==
    "villa"
)


assert (
    model["building"]["category"]
    ==
    "residential"
)


assert (
    model["building"]["style"]
    ==
    "modern"
)


assert (
    "spatial"
    in
    model
)


assert (
    "layout"
    in
    model
)


assert (
    "metadata"
    in
    model
)


assert isinstance(
    model["layout"],
    dict
)


assert len(
    model["layout"].get(
        "space_registry",
        []
    )
) > 0


print(
    "\n✓ Building Model Validation Passed"
)


# ==================================================
# FINAL RESULT
# ==================================================

print(
    "\n================================="
)

print(
    "ONTOLOGY → ARCHITECTURAL BRAIN → BUILDING MODEL"
)

print(
    "ACTIVE ARCHITECTURAL CONTRACT VALIDATED SUCCESSFULLY"
)

print(
    "=================================\n"
)


print(
    "=== TEST PASSED ===\n"
)