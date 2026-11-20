import requests

from config.chat_config import ChatConfig


class LLM:


    def __init__(
        self,
        base_url=None,
        model=None
    ):

        # CHAT_MODEL_ROUTING_V1 — no hardcoded (and since-deleted) model.
        # One authoritative default comes from config/chat_config.py.
        cfg = ChatConfig.from_env()

        self.base_url = base_url or cfg.generate_url()
        self.model = model or cfg.model


        print(
            "🧠 LLM GATEWAY v1.1 ONLINE (chat model: %s)" % self.model
        )



    def generate(
        self,
        prompt
    ):


        try:

            response = requests.post(

                self.base_url,

                json={

                    "model":
                        self.model,

                    "prompt":
                        prompt,

                    "stream":
                        False

                },

                timeout=10800

            )


            data = response.json()


            return data.get(

                "response",

                ""

            )


        except Exception as e:


            print(
                "❌ LLM ERROR:",
                repr(e)
            )


            return None