# ==========================================================
# ArchitectOS LLM Gateway v30
# Ollama Multi Model Router
#
# CHAT_MODEL_ROUTING_V1 — the model table is no longer hardcoded
# to deleted models. It is derived from config/chat_config.py at
# call time:
#
#   chat      -> ARCHITECTOS_CHAT_MODEL      (default qwen3.8:27b)
#   reasoning -> ARCHITECTOS_INTENT_MODEL    (default = the chat model)
#   backup    -> the chat model              (no separate deleted role)
#
# There is no "gemma for chat" and no "qwen2.5:7b for reasoning"
# route any more: both of those models are no longer installed.
# ==========================================================

import requests


from config.chat_config import ChatConfig


class LLMGatewayV30:


    VERSION = "30.0"


    # Kept as a class-level convenience for callers that read it.
    # It is rebuilt from the runtime configuration by `models()`.
    OLLAMA_URL = (
        "http://127.0.0.1:11434/api/generate"
    )


    def __init__(self):

        self.session = requests.Session()

        # Local Ollama: never let an ambient HTTP_PROXY take the call away.
        self.session.trust_env = False

        self.last_error = None

        print(
            "🧠 LLM GATEWAY v30 ONLINE (chat model: %s)"
            % ChatConfig.from_env().model
        )



    # ======================================================
    # MODEL TABLE (runtime, never frozen at import)
    # ======================================================

    def models(self):

        cfg = ChatConfig.from_env()

        return {

            "chat": cfg.model,

            "reasoning": cfg.intent_model,

            "backup": cfg.model,

        }


    # Compatibility accessor: existing callers read `gateway.MODELS[...]`.
    # It is now resolved from the runtime configuration, never hardcoded.
    @property
    def MODELS(self):

        return self.models()



    # ======================================================
    # LOW LEVEL CALL
    # ======================================================

    def call_model(
        self,
        model,
        prompt
    ):


        cfg = ChatConfig.from_env()

        self.last_error = None

        payload = {

            "model":
                model,

            "prompt":
                prompt,

            "stream":
                False

        }


        try:

            response = self.session.post(

                cfg.generate_url(),

                json=payload,

                timeout=cfg.timeout

            )

        except Exception as exc:

            self.last_error = type(exc).__name__ + ":" + str(exc)

            return ""


        if response.status_code != 200:

            self.last_error = (

                "model_not_installed:" + str(model)

                if response.status_code == 404

                else "ollama_http_" + str(response.status_code)

            )

            return ""


        try:

            data = response.json()

        except Exception as exc:

            self.last_error = type(exc).__name__ + ":" + str(exc)

            return ""


        return data.get(

            "response",

            ""

        )



    # ======================================================
    # CHAT MODEL
    # ======================================================

    def chat(
        self,
        prompt
    ):

        model = self.models()["chat"]

        return {

            "model":
                model,

            "task":
                "chat",

            "response":
                self.call_model(

                    model,

                    prompt

                )

        }



    # ======================================================
    # REASONING MODEL
    # ======================================================

    def reason(
        self,
        prompt
    ):

        model = self.models()["reasoning"]

        return {

            "model":
                model,

            "task":
                "reasoning",

            "response":
                self.call_model(

                    model,

                    prompt

                )

        }



    # ======================================================
    # AUTO ROUTER
    # ======================================================

    def generate(
        self,
        prompt,
        mode="chat"
    ):


        if mode == "reasoning":

            return self.reason(

                prompt

            )


        return self.chat(

            prompt

        )



# ==========================================================
# SINGLETON
# ==========================================================


llm_gateway = LLMGatewayV30()
