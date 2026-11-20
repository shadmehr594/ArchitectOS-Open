import json
import os


class MemoryBrain:

    def __init__(self, path="database/memory.json"):
        self.path = path
        self.memory = self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return {}

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def save(self, key, value):
        self.memory[key] = value
        self._persist()

    def get(self, key, default=None):
        return self.memory.get(key, default)

    def search(self, query):

        results = []

        for k, v in self.memory.items():
            if query.lower() in str(k).lower() or query.lower() in str(v).lower():
                results.append({"key": k, "value": v})

        return results

    # =========================
    # 🔥 FIX: missing method
    # =========================
    def build_context(self, input_text):

        results = self.search(input_text)

        if not results:
            return ""

        context_lines = []

        for item in results:
            context_lines.append(f"{item['key']} => {item['value']}")

        return "\n".join(context_lines)

    def _persist(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)