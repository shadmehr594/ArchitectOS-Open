class MultiCommandParser:

    def parse(self, text):

        # ساده ولی قابل توسعه
        commands = text.split(" and ")

        return [c.strip() for c in commands]