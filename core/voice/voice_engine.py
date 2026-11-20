from core.voice.stream_listener import StreamListener
from core.voice.parser import MultiCommandParser
from core.voice.memory import VoiceMemory


class VoiceEngine:

    def __init__(self, stt, brain, tts, router):

        self.stt = stt
        self.brain = brain
        self.tts = tts
        self.router = router

        self.listener = StreamListener()
        self.parser = MultiCommandParser()
        self.memory = VoiceMemory()

    def run(self):

        while True:

            text = self.listener.listen()

            if not text:
                continue

            print("🧠 INPUT:", text)

            commands = self.parser.parse(text)

            results = []

            for cmd in commands:

                result = self.router.route(cmd)

                self.memory.add(cmd, result)

                self.tts.execute(str(result))

                results.append(result)

            print("✅ DONE:", results)