# ==========================================================
# ArchitectOS Unified Tool Registry
# FINAL INTEGRATION LAYER
# ==========================================================


class ToolRegistry:


    def __init__(self):

        self.tools = {}



    # ==========================================
    # REGISTER TOOL
    # ==========================================

    def register(
        self,
        name,
        tool
    ):

        self.tools[name] = tool



    # ==========================================
    # GET TOOL
    # ==========================================

    def get(
        self,
        name
    ):

        return self.tools.get(
            name
        )



    # ==========================================
    # LIST TOOLS
    # ==========================================

    def list_tools(
        self
    ):

        return list(
            self.tools.keys()
        )



    # ==========================================
    # CHECK TOOL
    # ==========================================

    def has(
        self,
        name
    ):

        return name in self.tools



    # ==========================================
    # DEBUG STATUS
    # ==========================================

    def status(
        self
    ):

        return {

            "count":
                len(self.tools),

            "tools":
                self.list_tools()

        }