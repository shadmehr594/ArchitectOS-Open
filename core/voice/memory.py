class VoiceMemory:

    def __init__(self):

        self.short = []
        self.long = []

    def add(self, user, bot):

        self.short.append((user, bot))

        if len(self.short) > 10:
            self.long.append(self.short.pop(0))

    def context(self):

        return {
            "short": self.short[-5:],
            "long": self.long[-20:]
        }