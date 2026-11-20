import numpy as np

class VectorMemory:

    def __init__(self):
        self.vectors = []
        self.data = []

    def embed(self, text):
        # ساده placeholder (بعداً OpenAI / sentence-transformer)
        return np.array([hash(text) % 1000])

    def add(self, text, meta=None):

        vec = self.embed(text)

        self.vectors.append(vec)
        self.data.append({
            "text": text,
            "meta": meta
        })

    def search(self, query):

        q = self.embed(query)

        if not self.vectors:
            return []

        # ساده similarity
        scores = [
            np.linalg.norm(q - v)
            for v in self.vectors
        ]

        idx = int(np.argmin(scores))

        return self.data[idx]