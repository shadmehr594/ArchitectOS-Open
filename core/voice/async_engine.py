import asyncio

class AsyncVoiceEngine:

    def __init__(self, listener, brain, router, tts, memory):

        self.listener = listener
        self.brain = brain
        self.router = router
        self.tts = tts
        self.memory = memory

    async def process(self, text):

        if not text:
            return

        print("🧠 INPUT:", text)

        # 🧠 1. PLAN (LLM)
        plan = self.brain.run(text)

        # 🧩 2. EXECUTE PLAN (multi-step)
        result = await self.execute_plan(plan)

        # 💾 3. MEMORY SAVE
        self.memory.add(text, result)

        # 🔊 4. SPEAK
        await self.speak(result)

        return result

    async def execute_plan(self, plan):

        results = []

        steps = plan.get("steps", [plan])

        for step in steps:

            tool = self.router.route(step)

            if hasattr(tool, "execute"):
                out = tool.execute(step)
            else:
                out = tool

            results.append(out)

        return results

    async def speak(self, text):

        self.tts.execute(str(text))