# ==========================================================
# ArchitectOS Facade Prompt Builder v2
# Vision -> Photorealistic Architectural Edit Prompt
# Geometry Preservation Edition
# ==========================================================


class FacadePromptBuilder:


    def __init__(self):

        print(
            "🏛️ Facade Prompt Builder v2 ACTIVE"
        )



    def build(
        self,
        vision_result,
        facade_result
    ):


        style = vision_result.get(
            "style",
            "existing architectural style"
        )


        materials = facade_result.get(
            "materials",
            []
        )


        if materials:

            material_text = ", ".join(
                materials
            )

        else:

            material_text = (
                "premium stone, glass, concrete and realistic facade materials"
            )



        prompt = f"""
Edit the existing architectural photograph.

IMPORTANT:
Preserve the exact original building geometry.
Do not change the building shape.
Do not redesign the structure.

Keep:
- original facade proportions
- original curved front elements
- existing balconies
- existing sun shades
- roof geometry
- windows position
- structural layout
- camera perspective

Only improve:
- facade materials
- realistic textures
- lighting
- shadows
- architectural photography quality

Architectural style:
{style}

Materials:
{material_text}

Result:
Ultra realistic architectural photography.
Real building visualization.
Natural daylight.
High detail.
Photorealistic.
Not a sketch.
Not a 3D render.
Do not create a new building.
"""


        return {

            "engine":
                "FacadePromptBuilder_v2",


            "prompt":
                " ".join(
                    prompt.split()
                )

        }



facade_prompt_builder = FacadePromptBuilder()