import speech_recognition as sr

class AsyncListener:

    def __init__(self, mic_index=11):

        self.recognizer = sr.Recognizer()
        self.mic_index = mic_index

    async def listen(self):

        with sr.Microphone(device_index=self.mic_index) as source:

            self.recognizer.adjust_for_ambient_noise(source)

            audio = self.recognizer.listen(source)

            try:
                return self.recognizer.recognize_google(audio)

            except:
                return None