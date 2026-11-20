class ResponseFilter:

    def clean(self, text: str):

        if not text:
            return "I don't know"

        text = text.strip()

        # remove mixed language noise
        if len(text.split()) > 12:
            text = " ".join(text.split()[:12])

        return text