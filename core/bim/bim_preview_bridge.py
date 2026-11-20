# ==========================================================
# ArchitectOS BIM Preview Bridge v1.1
#
# BIM Semantic Model -> Review Preview
#
# FIX:
# - Support BIMModelAdapter v1.0 contract
# - Read project instead of building
# - Read spaces from BIM semantic spaces list
# - Prepare approval gate
# - No rendering execution
# ==========================================================


class BIMPreviewBridge:


    VERSION = "1.1"



    def __init__(self):

        print(
            "🏗 BIM PREVIEW BRIDGE v1.1 ONLINE"
        )



    # ======================================================
    # BUILD PREVIEW
    # ======================================================


    def build_preview(
        self,
        bim_model
    ):


        bim_model = bim_model or {}



        # ==================================================
        # BUILDING / PROJECT
        # ==================================================

        building = (

            bim_model.get(
                "project",
                {}
            )

        )


        if not isinstance(
            building,
            dict
        ):

            building = {}



        # ==================================================
        # LEVELS
        # ==================================================

        levels = (

            bim_model.get(
                "levels",
                []
            )

        )


        if not isinstance(
            levels,
            list
        ):

            levels = []



        # ==================================================
        # SPACES
        # ==================================================

        source_spaces = (

            bim_model.get(
                "spaces",
                []
            )

        )


        if not isinstance(
            source_spaces,
            list
        ):

            source_spaces = []



        spaces = []



        for space in source_spaces:


            if not isinstance(
                space,
                dict
            ):

                continue



            spaces.append(

                {

                    "name":
                        space.get(
                            "name"
                        ),


                    "zone":
                        space.get(
                            "zone"
                        ),


                    "position":
                        space.get(
                            "position"
                        ),


                    "level":
                        space.get(
                            "level"
                        )

                }

            )



        # ==================================================
        # LEVEL SUMMARY
        # ==================================================

        level_summary = []



        for level in levels:


            if not isinstance(
                level,
                dict
            ):

                continue



            level_name = (

                level.get(
                    "level"
                )

                or

                level.get(
                    "name"
                )

            )



            count = len(

                [

                    s

                    for s in spaces

                    if s.get(
                        "level"
                    ) == level_name

                ]

            )



            level_summary.append(

                {

                    "level":
                        level_name,


                    "space_count":
                        count

                }

            )



        print(
            "🏗 PREVIEW LEVELS:",
            level_summary
        )


        print(
            "🏗 PREVIEW SPACES:",
            spaces
        )



        return {


            "preview_status":

                "ready_for_review",



            "building":

                {

                    "type":

                        building.get(
                            "type"
                        ),


                    "category":

                        building.get(
                            "category"
                        )

                },



            "levels":

                level_summary,



            "spaces":

                spaces,



            "approval_required":

                True


        }