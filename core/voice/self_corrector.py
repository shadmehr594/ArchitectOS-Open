class SelfCorrector:

    def fix(self, result, tool_name):

        if result is None or result == "error":

            return {
                "status": "retry",
                "action": tool_name
            }

        return {
            "status": "ok",
            "result": result
        }