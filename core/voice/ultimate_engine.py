class UltimateVoiceEngine:

    def __init__(self, listener, brain, router, tts, memory, vector, graph, fixer):

        self.listener = listener
        self.brain = brain
        self.router = router
        self.tts = tts
        self.memory = memory
        self.vector = vector
        self.graph = graph
        self.fixer = fixer

    def run(self):

        while True:

            text = self.listener.listen()

            if not text:
                continue

            print("🎤 INPUT:", text)

            # 🧠 1. Vector memory retrieval
            memory_context = self.vector.search(text)

            # 🧠 2. Planning
            plan = self.brain.run(text)

            # 🔗 3. Build graph
            nodes = self.graph.build(plan)

            results = []

            # ⚙️ 4. Execute graph
            for node in nodes:

                tool = self.router.route(node)

                raw = tool.execute(node["input"])

                fixed = self.fixer.fix(raw, node["tool"])

                if fixed["status"] == "retry":
                    raw = tool.execute(node["input"])

                results.append(raw)

            # 💾 5. Memory write
            self.memory.add(text, results)

            self.vector.add(text, results)

            # 🔊 6. Speak
            self.tts.execute(str(results))

            print("✅ DONE:", results)