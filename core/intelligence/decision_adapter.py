# ==========================================================
# ArchitectOS Decision Adapter v1.2
# Reasoning Output -> Executable Design Actions
# ==========================================================


class DecisionAdapter:


    VERSION = "1.2"



    def __init__(self):

        print(
            f"🧠 Decision Adapter v{self.VERSION} ACTIVE"
        )



    # ======================================================
    # CONVERT RECOMMENDATIONS / DECISIONS
    # ======================================================

    def convert(
        self,
        recommendations
    ):


        actions = []


        if not isinstance(
            recommendations,
            list
        ):

            return actions



        for item in recommendations:



            if not isinstance(
                item,
                dict
            ):

                continue



            # ==================================================
            # SUPPORT BOTH FORMATS
            # ==================================================

            action = item.get(
                "action",
                ""
            )


            recommendation = item.get(
                "recommendation",
                ""
            )


            target = item.get(
                "target",
                ""
            )


            reason = item.get(
                "reason",
                ""
            )


            if not action:

                action = recommendation



            # ==================================================
            # ALREADY ACTION FORMAT
            # ==================================================

            if (
                item.get("module")
                and
                item.get("action")
            ):

                actions.append(item)

                continue



            # ==================================================
            # FACADE
            # ==================================================

            if action == "add_horizontal_shading":


                actions.append({

                    "module":
                    "facade",

                    "action":
                    "add_shading",

                    "parameters":
                    {

                        "type":
                        "horizontal"

                    },

                    "reason":
                    reason

                })



            elif action == "add_solar_protection":


                actions.append({

                    "module":
                    "facade",

                    "action":
                    "solar_protection",

                    "parameters":
                    {

                        "level":
                        "high"

                    },

                    "reason":
                    reason

                })



            # ==================================================
            # MATERIALS
            # ==================================================

            elif action == "prefer_thermal_materials":


                actions.append({

                    "module":
                    "materials",

                    "action":
                    "select_thermal_materials",

                    "parameters":
                    {

                        "strategy":
                        "heat_reduction"

                    },

                    "reason":
                    reason

                })



            # ==================================================
            # ROOF
            # ==================================================

            elif action == "preserve_green_roof":


                actions.append({

                    "module":
                    "roof",

                    "action":
                    "preserve_green_roof",

                    "parameters":
                    {

                        "thermal_strategy":
                        True

                    },

                    "reason":
                    reason

                })



            # ==================================================
            # UNKNOWN PASSTHROUGH
            # ==================================================

            elif action:


                actions.append({

                    "module":
                    target or "unknown",

                    "action":
                    action,

                    "parameters":
                    {},

                    "reason":
                    reason

                })



        return actions



# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


decision_adapter = DecisionAdapter()