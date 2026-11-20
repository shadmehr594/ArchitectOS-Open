class WakeWordDetector:

    def __init__(self, wake_word="hey architect"):
        self.wake_word = wake_word.lower()

    def detect(self, text):

        if not text:
            return False

        return self.wake_word in text.lower()