import speech_recognition as sr

class SpeechToTextTool:

    def __init__(self, mic_index=11):
        self.mic_index = mic_index
        self.recognizer = sr.Recognizer()

    def execute(self, _):

        try:
            mic_list = sr.Microphone.list_microphone_names()

            if not mic_list:
                return None

            with sr.Microphone(device_index=self.mic_index) as source:
                self.recognizer.adjust_for_ambient_noise(source)
                audio = self.recognizer.listen(source, timeout=5)

            text = self.recognizer.recognize_google(audio)
            return text

        except Exception as e:
            print("STT ERROR:", e)
            return None