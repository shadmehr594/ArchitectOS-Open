"""
ArchitectOS Floor Program Reasoning Adapter v1.0

Converts reasoning program requirements
into floor program modifications.
"""


class FloorProgramReasoningAdapter:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"🏗️ Floor Program Reasoning Adapter v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # ADAPT PROGRAM
    # ==================================================

    def adapt(
        self,
        floor_input,
        reasoning_requirements
    ):


        result = dict(
            floor_input
        )


        additions = []

        space_types = []


        for item in reasoning_requirements.get(
            "program_requirements",
            []
        ):


            if item.get("target") != floor_input.get("level"):

                continue



            additions.extend(

                item.get(
                    "additions",
                    []
                )

            )


            space_types.extend(

                item.get(
                    "space_types",
                    []
                )

            )



        result["reasoning_additions"] = additions


        result["reasoning_space_types"] = space_types



        return result