class ToolGenerator:

    def __init__(self, registry):
        self.registry = registry
        self.generated = {}

    # ==========================
    # 🔍 DETECT GAP IN SYSTEM
    # ==========================
    def detect_gap(self, signal, state):

        if not state or "state" not in state:
            return None

        dominant = state.get("dominant", "chat")
        counts = state.get("state", {})

        # اگر یک رفتار خیلی زیاد تکرار شده
        if counts.get(dominant, 0) >= 5:

            return {
                "name": f"auto_{dominant}_tool",
                "type": dominant,
                "reason": "high frequency pattern detected"
            }

        return None

    # ==========================
    # 🧠 GENERATE TOOL
    # ==========================
    def generate_tool(self, spec):

        if not spec:
            return None

        tool_name = spec["name"]

        # جلوگیری از دوباره‌سازی
        if tool_name in self.generated:
            return None

        # --------------------------
        # AUTO TOOL CLASS
        # --------------------------
        class AutoTool:

            def execute(self, input_text, context=""):
                return f"[AUTO TOOL ACTIVE: {spec['type']}] {input_text}"

        tool_instance = AutoTool()

        self.generated[tool_name] = tool_instance

        return tool_instance

    # ==========================
    # 🚀 DEPLOY TOOL
    # ==========================
    def deploy(self, name, tool):

        if tool:
            self.registry.register(name, tool)