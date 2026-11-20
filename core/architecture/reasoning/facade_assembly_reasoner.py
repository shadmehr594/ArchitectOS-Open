class FacadeAssemblyReasoner:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🏛 FACADE ASSEMBLY REASONER v1.0 ONLINE"
        )


    def generate(
        self,
        style,
        facade_language,
        materials
    ):


        assembly = {


            "base": {},

            "wall_surface": {},

            "openings": {},

            "vertical_elements": {},

            "upper_elements": {}

        }


        if style == "roman_classic":


            assembly["base"] = {
                "element": "stone_plinth",
                "material": "travertine"
            }


            assembly["wall_surface"] = {
                "element": "stone_cladding",
                "material": "travertine"
            }


            assembly["openings"] = {
                "elements": [
                    "stone_window_frames",
                    "arched_windows"
                ]
            }


            assembly["vertical_elements"] = {
                "elements": [
                    "columns",
                    "pilasters"
                ]
            }


            assembly["upper_elements"] = {
                "elements": [
                    "cornice",
                    "balustrade"
                ]
            }


        elif style == "classic":


            assembly["base"] = {
                "element": "stone_plinth",
                "material": (
                    "travertine"
                    if "travertine" in materials
                    else (
                        "stone"
                        if "stone" in materials
                        else (
                            materials[0]
                            if materials
                            else None
                        )
                    )
                )
            }


            assembly["wall_surface"] = {
                "element": "refined_stone_cladding",
                "material": (
                    "travertine"
                    if "travertine" in materials
                    else (
                        "stone"
                        if "stone" in materials
                        else None
                    )
                )
            }


            assembly["openings"] = {
                "elements": [
                    "stone_window_frames",
                    "symmetrical_openings"
                ]
            }


            assembly["vertical_elements"] = {
                "elements": [
                    "pilasters",
                    "formal_vertical_frames"
                ]
            }


            assembly["upper_elements"] = {
                "elements": [
                    "classical_cornice",
                    "simple_balustrade"
                ]
            }



        elif style == "neoclassical":


            # ==================================================
            # FACADE_KNOWLEDGE_HANDOFF_V1 — NEOCLASSICAL ASSEMBLY
            #
            # The requested style had NO branch here, so every surface
            # resolved to `{}` and the facade knowledge layer could not say
            # which surface receives which finish. That is the mechanical
            # reason a neoclassical request collapsed into "one stone across
            # the image".
            #
            # This branch is deliberately DIFFERENT from `classic`:
            #
            #   * the wall field is restrained ashlar, not a stone-cladding
            #     envelope (the ontology's `classical_grid` / `refined_details`
            #     rather than `stone_cladding` + `arches`);
            #   * no arches are produced at all — arches belong to `classic`
            #     and `roman_classic` in `architectural_style_ontology.json`;
            #   * the vertical rhythm is PILASTERS on the existing structural
            #     lines, not free-standing columns;
            #   * soffit, glazing and site are named as SEPARATE surfaces, so
            #     the facade stone cannot be the only answer to every surface.
            #
            # `soffit` / `glazing` / `site` are ADDITIVE OPTIONAL keys, added
            # only for this style: every existing assembly (classic,
            # roman_classic, modern, iranian_*) keeps exactly its previous
            # five keys and its previous values.
            # ==================================================

            material_set = set(
                materials
                or []
            )

            wall_material = None

            if "travertine" in material_set:

                wall_material = "travertine"

            elif "stone" in material_set:

                wall_material = "stone"

            elif "marble" in material_set:

                wall_material = "marble"


            assembly["base"] = {

                "element":
                    "stone_plinth_with_entrance_treatment",

                "material":
                    wall_material,

                "note": (
                    "the plinth articulates the base only; it must not close "
                    "an existing open ground level"
                )
            }


            assembly["wall_surface"] = {

                "element":
                    "restrained_ashlar_wall_field",

                "material":
                    wall_material,

                "joints": "believable_recessed_ashlar_joints",

                "note": (
                    "restrained stone field; no heavy marble-like veining and "
                    "no brick coursing carried through the finish"
                )
            }


            assembly["openings"] = {

                "elements": [
                    "stone_window_surrounds",
                    "carved_stone_frames"
                ],

                "preserve_existing_openings": True,

                "note": (
                    "surrounds frame the EXISTING openings; no opening is "
                    "added, resized or moved"
                )
            }


            assembly["vertical_elements"] = {

                "elements": [
                    "pilasters",
                    "classical_capitals"
                ],

                "material":
                    wall_material,

                "alignment":
                    "existing_structural_rhythm",

                "note": (
                    "pilasters are applied relief on the wall plane and align "
                    "with the existing columns; they are not new structure"
                )
            }


            assembly["upper_elements"] = {

                "elements": [
                    "horizontal_stringcourses",
                    "projecting_cornice",
                    "stone_parapet_coping"
                ],

                "material":
                    wall_material,

                "note": (
                    "stringcourses follow the existing floor levels; the "
                    "parapet keeps its existing height and step"
                )
            }


            # ---- ADDITIVE OPTIONAL SURFACES -------------------
            #
            # The five-slot schema had no place for the surfaces that the
            # accepted evidence says were wrongly clad. These three keys exist
            # only for neoclassical, so no existing assembly changes shape.
            assembly["soffit"] = {

                "element":
                    "smooth_painted_plaster_soffit",

                "material":
                    "painted_plaster",

                "is_facade_stone":
                    False,

                "note": (
                    "exposed slab soffits and ceiling surfaces receive a "
                    "smooth painted or plastered finish; facade stone is NOT "
                    "applied to a soffit"
                )
            }


            assembly["glazing"] = {

                "element":
                    "glass_with_compatible_frames",

                "material":
                    "glass",

                "frame_material":
                    "metal",

                "is_facade_stone":
                    False,

                "note": (
                    "existing glazing and frames are glazing, never stone"
                )
            }


            assembly["site"] = {

                "element":
                    "separate_site_scope",

                "material":
                    None,

                "is_facade_stone":
                    False,

                "note": (
                    "paving, driveway, boundary walls and planting are a "
                    "SEPARATE architectural/landscape scope with their own "
                    "material decision; the facade cladding is not continued "
                    "onto the ground plane or the boundary walls"
                )
            }


        elif style == "iranian_brick":


            assembly["base"] = {
                "element": "brick_masonry_base",
                "material": (
                    "fire_brick"
                    if "fire_brick" in materials
                    else (
                        materials[0]
                        if materials
                        else None
                    )
                )
            }


            assembly["wall_surface"] = {
                "element": "brick_surface",
                "material": (
                    "fire_brick"
                    if "fire_brick" in materials
                    else None
                )
            }


            assembly["openings"] = {
                "elements": [
                    "brick_arches",
                    "deep_window_reveals",
                    "shaded_windows"
                ]
            }


            assembly["vertical_elements"] = {
                "elements": [
                    "brick_fins",
                    "brick_screen_panels"
                ]
            }


            assembly["upper_elements"] = {
                "elements": [
                    "brick_parapet",
                    "brick_shadow_band"
                ]
            }


        elif style == "iranian_traditional":


            assembly["base"] = {
                "element": "natural_stone_base",
                "material": (
                    "natural_stone"
                    if "natural_stone" in materials
                    else (
                        materials[0]
                        if materials
                        else None
                    )
                )
            }


            assembly["wall_surface"] = {
                "element": "earthen_wall_surface",
                "material": (
                    "kahgel"
                    if "kahgel" in materials
                    else (
                        "mud_brick"
                        if "mud_brick" in materials
                        else None
                    )
                )
            }


            assembly["openings"] = {
                "elements": [
                    "deep_recessed_openings",
                    "traditional_arches",
                    "shaded_openings"
                ],
                "material": (
                    "traditional_brick"
                    if "traditional_brick" in materials
                    else None
                )
            }


            assembly["vertical_elements"] = {
                "elements": [
                    "traditional_brick_frames",
                    "recessed_wall_planes"
                ],
                "material": (
                    "traditional_brick"
                    if "traditional_brick" in materials
                    else None
                )
            }


            assembly["upper_elements"] = {
                "elements": [
                    "traditional_parapet",
                    "brick_cornice_band"
                ],
                "material": (
                    "traditional_brick"
                    if "traditional_brick" in materials
                    else None
                )
            }


        elif style == "modern":


            material_set = set(
                materials
                or []
            )


            base_material = None

            if "stone" in material_set:

                base_material = "stone"

            elif "concrete" in material_set:

                base_material = "concrete"

            elif "exposed_concrete" in material_set:

                base_material = "exposed_concrete"


            wall_material = None

            if "architectural_render" in material_set:

                wall_material = "architectural_render"

            elif "stone" in material_set:

                wall_material = "stone"

            elif "concrete" in material_set:

                wall_material = "concrete"

            elif "wood_composite" in material_set:

                wall_material = "wood_composite"

            elif "wood" in material_set:

                wall_material = "wood"


            glazing_material = (
                "glass"
                if "glass" in material_set
                else None
            )


            frame_material = None

            if "aluminum" in material_set:

                frame_material = "aluminum"

            elif "dark_metal" in material_set:

                frame_material = "dark_metal"

            elif "metal" in material_set:

                frame_material = "metal"


            accent_material = None

            if "wood_composite" in material_set:

                accent_material = "wood_composite"

            elif "wood" in material_set:

                accent_material = "wood"

            elif "dark_metal" in material_set:

                accent_material = "dark_metal"


            assembly["base"] = {

                "element":
                    "minimal_plinth",

                "material":
                    base_material

            }


            assembly["wall_surface"] = {

                "element":
                    "clean_wall_surface",

                "material":
                    wall_material

            }


            assembly["openings"] = {

                "elements": [
                    "large_glazing",
                    "minimal_frames"
                ],

                "glazing_material":
                    glazing_material,

                "frame_material":
                    frame_material

            }


            assembly["vertical_elements"] = {

                "elements": [
                    "clean_vertical_planes",
                    "shading_elements"
                ],

                "material":
                    accent_material

            }


            assembly["upper_elements"] = {

                "elements": [
                    "minimal_parapet",
                    "shadow_gap"
                ],

                "material":
                    wall_material

            }

        return {

            "facade_system": assembly,

            "source":
            "architectural_knowledge"

        }