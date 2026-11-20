# ==========================================================
# ArchitectOS LLM Gateway v2
# Context Aware Local Model Bridge
# Ollama Compatible
# Memory + Prompt Fusion Integration
#
# CHAT_MODEL_ROUTING_V1 — the chat model is no longer hardcoded.
# It comes from config/chat_config.py (ARCHITECTOS_CHAT_MODEL),
# which is the single authoritative default. The configuration is
# read at CALL time, not frozen at module import, so a runtime
# change takes effect without re-importing this module.
#
# A model that is not installed is NEVER silently replaced by a
# deleted one: the call fails, `last_error` records why, and the
# caller keeps its existing truthful degraded reply.
#
# CHAT_MODEL_ROUTING_V1 — `think` is sent explicitly (false by
# default). A thinking model otherwise returns an EMPTY `response`
# while it spends its budget in the private `thinking` channel, and
# the chat path would show nothing. Internal reasoning is never
# published as the chat answer.
# ==========================================================


import requests


from config.chat_config import ChatConfig


from core.prompt_engine_context import (
    prompt_context_engine
)



class LLMGateway:


    VERSION = "2.0"



    def __init__(
        self,
        url=None,
        model=None,
        timeout=None,
        num_predict=None
    ):


        # Explicit constructor arguments still win (they are the
        # documented override surface). Everything else comes from the
        # authoritative runtime configuration at call time.
        self._url_override = url

        self._model_override = model

        self._timeout_override = timeout

        # CODER-03 — an OPTIONAL, per-instance output-token ceiling. It is
        # applied ONLY when explicitly supplied, so the shared chat gateway
        # (constructed with no arguments) is byte-for-byte unchanged.
        self._num_predict_override = num_predict

        self.last_error = None

        self.last_model = None


        cfg = ChatConfig.from_env()

        self.url = url or cfg.generate_url()

        self.model = model or cfg.model


        # CHAT_LANGUAGE_02 / RUNTIME_FOUNDATION_01
        # Ollama is a LOCAL service. An ambient HTTP_PROXY would route the
        # call away from 127.0.0.1 and silently break the chat path.
        self.session = requests.Session()

        self.session.trust_env = False


        print(
            "🧠 LLM GATEWAY v2 ONLINE (chat model: %s)" % self.model
        )



    # ======================================================
    # RUNTIME RESOLUTION
    # ======================================================

    def _resolved(self):

        """Current (url, model, timeout, think, temperature) — read at call time."""

        cfg = ChatConfig.from_env()


        return (

            self._url_override or cfg.generate_url(),

            self._model_override or cfg.model,

            self._timeout_override or cfg.timeout,

            cfg.think,

            cfg.temperature,

        )



    def is_model_available(self):

        """Truthful availability probe for the CONFIGURED chat model."""

        _, model, timeout, _, _ = self._resolved()

        try:

            response = self.session.get(

                ChatConfig.from_env().tags_url(),

                timeout=min(timeout, 15)

            )

            if response.status_code != 200:

                return False

            names = {

                item.get("name")

                for item in response.json().get("models", [])

                if isinstance(item, dict)

            }

            return model in names

        except Exception:

            return False



    # ======================================================
    # GENERATE
    # ======================================================

    def generate(
        self,
        user,
        use_context=False
    ):


        url, model, timeout, think, temperature = self._resolved()

        self.last_error = None

        self.last_model = model


        try:


            # ----------------------------------
            # PROMPT BUILD
            # ----------------------------------

            if use_context:

                prompt = prompt_context_engine.build(
                    user
                )


            else:


                prompt = user



            # CODER-03 — the output-token ceiling is applied ONLY when the
            # instance was given one (the coder path). The default chat
            # gateway sends exactly the same options as before.
            _options = {"temperature": temperature}

            if self._num_predict_override:

                _options["num_predict"] = int(self._num_predict_override)


            payload = {


                "model":
                    model,


                "prompt":
                    prompt,


                "stream":
                    False,


                # Thinking models otherwise answer into the private
                # `thinking` channel and leave `response` empty.
                "think":
                    bool(think),


                # CHAT-02D_LIVE_FAILURE_FIX — an explicit sampling
                # temperature. The installed model's own default (0.7)
                # makes its READING of the user's request unstable and
                # it can answer a different, similar-looking topic; at 0
                # that switch was not observed. Override with
                # ARCHITECTOS_CHAT_TEMPERATURE.
                "options":
                    _options,


                "keep_alive":
                    "5m"

            }



            print(
                "🔥 LLM REQUEST:",
                model
            )



            # FACADE-04D.3C-5B — hold the cross-process lease for this Ollama
            # model for the duration of the call. The vision->render GPU
            # handoff (H2) takes the SAME lease exclusively, so this is what
            # makes "no other chat/vision/teaching request is using
            # qwen3.8:27b" provable ACROSS PROCESSES. Uncontended this is a
            # no-op; it only serialises calls to the same model, which Ollama
            # already does internally.
            from core.runtime.gpu_handoff_v1 import (
                ollama_model_call,
                OllamaModelBusy,
            )

            try:

                with ollama_model_call(model):

                    response = self.session.post(

                        url,

                        json=payload,

                        timeout=timeout

                    )

            except OllamaModelBusy:

                # Truthful failure: never call Ollama outside the handoff's
                # accounting while another request owns the model.
                print(
                    "⛔ OLLAMA MODEL LEASE NOT ACQUIRED:",
                    model
                )

                self.last_error = "model_busy:" + str(model)

                return None



            if response.status_code != 200:


                # A missing model is the case that used to be hidden:
                # the configured chat model is not installed locally.
                # Report it truthfully instead of pretending a reply.
                if response.status_code == 404:

                    self.last_error = (
                        "model_not_installed:" + str(model)
                    )

                    print(

                        "❌ CHAT MODEL NOT INSTALLED:",

                        model

                    )

                else:

                    self.last_error = (
                        "ollama_http_" + str(response.status_code)
                    )

                    print(

                        "❌ OLLAMA HTTP ERROR:",

                        response.status_code

                    )


                return None




            print(

                "🔥 OLLAMA RAW:",

                response.text[:300]

            )



            data = response.json()



            result = data.get(

                "response",

                ""

            )


            if not result:


                print(
                    "⚠️ EMPTY LLM RESPONSE"
                )

                self.last_error = "empty_response"

                return None



            print(
                "🧠 LLM RESPONSE READY v2"
            )

            return result.strip()



        except requests.exceptions.ConnectionError:


            print(
                "❌ OLLAMA CONNECTION FAILED"
            )

            self.last_error = "connection_error"

            return None



        except Exception as e:


            print(

                "❌ LLM GATEWAY v2 ERROR:",

                repr(e)

            )

            self.last_error = type(e).__name__ + ":" + str(e)

            return None




# ==========================================================
# SINGLETON
# ==========================================================


llm_gateway = LLMGateway()


# ==========================================================
# CODER-03 — DEDICATED CODING GATEWAY FACTORY
#
# Returns a NEW gateway bound to the dedicated coding model. The shared chat
# gateway (and its state) is never touched: this is a per-call object that
# only changes WHICH model answers a code-writing turn.
# ==========================================================

def coder_gateway():

    cfg = ChatConfig.from_env()

    return LLMGateway(

        model=cfg.coder_model,

        timeout=cfg.coder_timeout,

        num_predict=cfg.coder_num_predict,

    )
