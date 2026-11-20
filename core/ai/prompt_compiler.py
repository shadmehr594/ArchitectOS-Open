# ==========================================================
# ArchitectOS Prompt Compiler v84
# Clean Architectural Prompt Generator
# Intelligence / Compiler Separation Edition
# ==========================================================


class PromptCompiler:


    def __init__(self):

        print(
            "📝 Prompt Compiler v84 ACTIVE"
        )



    def compile(
        self,
        user_prompt,
        design_profile,
        building_analysis,
        edit_params=None
    ):


        runtime = {}


        if edit_params:

            runtime = edit_params.copy()



        mode = runtime.get(

            "mode",

            "image"

        )



        # ==================================================
        # NEW BUILD
        # ==================================================

        if mode == "image":


            request = user_prompt


            if isinstance(user_prompt, dict):

                request = user_prompt.get(
                    "user_request",
                    ""
                )



            prompt = f"""

Create a new architectural building.



USER REQUEST:

{request}



ARCHITECTURAL DESIGN:

Generate a premium architectural design.


Requirements:

- luxury villa
- realistic architectural proportions
- modern facade
- glass
- stone
- concrete
- metal details
- professional architectural photography



ARCHITECTURAL STYLE:

{design_profile.style}



DESIGN LANGUAGE:

{', '.join(design_profile.design_language)}



MATERIAL DIRECTION:

{', '.join(design_profile.materials)}



ENVIRONMENT:

- realistic site context
- landscape integration
- natural daylight



QUALITY:

Ultra realistic.

Photorealistic.

High detail.

Professional architectural visualization.



IMPORTANT:

Create a complete new building.

Do not edit an existing image.

Do not preserve previous structures.

"""



        # ==================================================
        # RENOVATION
        # ==================================================

        else:


            request = user_prompt


            if isinstance(user_prompt, dict):

                request = user_prompt.get(
                    "user_request",
                    ""
                )



            prompt = f"""

Edit existing architectural building.



USER REQUEST:

{request}



BUILDING ANALYSIS:



Floors:

{building_analysis.floors}



Facade Material:

{building_analysis.facade_material}



Roof:

{building_analysis.roof_type}



Style:

{building_analysis.detected_style}



PRESERVATION RULES:

Preserve:

- building geometry
- building silhouette
- floor count
- structural rhythm
- columns
- balconies
- windows
- roof shape
- camera perspective



MODIFY ONLY:

- facade materials
- textures
- lighting
- colors
- architectural details
- realism quality



DESIGN DIRECTION:

Style:

{design_profile.style}



Materials:

{', '.join(design_profile.materials)}



QUALITY:

Ultra realistic architectural photography.

Natural daylight.

Photorealistic.



IMPORTANT:

Do not redesign structure.

Do not create a new building.

"""



        return {


            "prompt":

                prompt.strip(),


            "runtime":

                runtime

        }





# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


prompt_compiler = PromptCompiler()