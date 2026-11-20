# ==========================================================
# ArchitectOS Execution Graph
# Unified Tool Registry Compatible
# ==========================================================


class ExecutionGraph:


    def run(
        self,
        plan,
        tools,
        context=None
    ):


        state = {

            "context":
                context or "",

            "result":
                None

        }



        for step in plan:


            action = step.get(
                "step"
            )


            input_data = step.get(
                "input"
            )



            # ==================================
            # TOOL GETTER
            # ==================================

            tool = None


            if hasattr(
                tools,
                "get"
            ):

                tool = tools.get(
                    self.resolve_tool(action)
                )


            elif isinstance(
                tools,
                dict
            ):

                tool = tools.get(
                    self.resolve_tool(action)
                )



            if tool is None:

                continue



            state["result"] = tool.execute(
                input_data
            )



        return state["result"]



    # ======================================
    # ACTION -> TOOL MAPPING
    # ======================================


    def resolve_tool(
        self,
        action
    ):


        mapping = {


            "search_memory":
                "memory",


            "save_memory":
                "memory",


            "generate_image":
                "image",


            "generate_response":
                "chat",


            "generate_bim":
                "bim",


            "speech_to_text":
                "speech_to_text",


            "text_to_speech":
                "text_to_speech"


        }


        return mapping.get(
            action,
            action
        )