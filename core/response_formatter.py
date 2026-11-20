class ResponseFormatter:

    def format(self, result):

        if not result:
            return "❌ No output"

        # --------------------------
        # MULTI STEP AGENT
        # --------------------------
        if isinstance(result, dict) and "steps" in result:

            steps = result.get("steps", [])
            final = result.get("final", {})

            text = []

            text.append("🧠 Agent Thinking Chain:\n")

            for i, s in enumerate(steps):

                text.append(f"{i+1}. Tool: {s.get('tool')}")
                text.append(f"   Input: {s.get('input')}")

                output = s.get("output")

                # 🔥 FIX: unwrap dict output
                if isinstance(output, dict):
                    output = output.get("output") or output.get("file") or output

                text.append(f"   Output: {output}\n")

            text.append("\n🔥 FINAL ANSWER:\n")

            final_output = final.get("output")

            # 🔥 FIX CRITICAL
            if isinstance(final_output, dict):
                final_output = final_output.get("output") or final_output.get("file")

            if not final_output:
                final_output = "⚠️ no final output"

            text.append(str(final_output))

            return "\n".join(text)

        # --------------------------
        # SIMPLE OUTPUT (FIXED)
        # --------------------------
        if isinstance(result, dict):

            output = result.get("output")

            if output:
                return str(output)

            if result.get("image"):
                return result

            if result.get("file"):
                return result

            if result.get("result"):
                return result.get("result")

            return "⚠️ empty output (no tool result)"