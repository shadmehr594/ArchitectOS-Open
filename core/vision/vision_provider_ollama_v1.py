"""Ollama transport for the provider-independent two-stage visual bridge."""

import base64
import copy
from dataclasses import asdict, replace
from functools import lru_cache
import hashlib
from io import BytesIO
import math
import os
import time
from urllib.parse import urlparse

import requests
from PIL import Image

from config.vision_config import VisionConfig
from core.prompt_intelligence.reference_image_architectural_understanding_v1 import ArchitecturalVisionProvider
# FACADE-04D.3C-5B — the cross-process Ollama model lease. Every ArchitectOS
# Ollama call holds it so the vision->render GPU handoff (H2) can prove the
# model is unused before it is unloaded.
from core.runtime.gpu_handoff_v1 import ollama_model_call, OllamaModelBusy
from core.vision.general_visual_observer_v1 import (
    OBSERVER_PROMPT, OBSERVER_VERSION, raw_observation, run_visual_bridge,
)
from core.vision.observation_normalizer_v1 import (
    NORMALIZER_PROMPT, NORMALIZER_VERSION, SCHEMA_VERSION, STRUCTURED_SCHEMA,
    normalizer_input, parse_normalization,
)


OBSERVER_IMAGE_POLICY_VERSION = "bounded-observer-image-v1"


def _prepare_observer_image(path, config, diagnostics):
    """Prepare observer bytes only; never write to the asset or local readers.

    Keep the original encoding below both limits. Above them, uniformly reduce
    the whole raster with Lanczos and encode lossless PNG, entirely in memory.
    Incremental diagnostics survive decode/resize/encoding failures.
    """
    with open(path, "rb") as handle:
        original = handle.read()
    diagnostics["original_source_sha256"] = hashlib.sha256(original).hexdigest()
    with BytesIO(original) as source, Image.open(source) as image:
        width, height = image.size
        diagnostics.update(original_width=width, original_height=height)
        image.load()
        # The long edge cannot exceed the pixel budget even for a 1px strip.
        long_edge = min(config.observer_max_long_edge, config.observer_max_pixels)
        scale = min(1.0, long_edge / max(width, height),
                    math.sqrt(config.observer_max_pixels / (width * height)))
        size = (max(1, math.floor(width * scale)), max(1, math.floor(height * scale)))
        encoded = original
        if size != image.size:
            mode = "RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB"
            with image.convert(mode) as raster, raster.resize(size, Image.Resampling.LANCZOS) as bounded:
                with BytesIO() as output:
                    bounded.save(output, format="PNG")
                    encoded = output.getvalue()
        diagnostics.update(observer_input_width=size[0], observer_input_height=size[1],
                           observer_image_resized=size != image.size,
                           image_preparation_status="READY")
    return base64.b64encode(encoded).decode("ascii")


class OllamaVisualObserver:
    def __init__(self, config, session):
        self.config, self.session = config, session

    def observe(self, image_asset, prompt=None):
        """Observe one image, optionally with a caller-scoped question.

        FINE_DETAIL_ARCHITECTURAL_VISION_V6 — `prompt` is the ONLY extension.
        Omitting it reproduces the previous behaviour exactly (the drawing-
        oriented `OBSERVER_PROMPT`); supplying it scopes the same observation
        entry point to one local question without adding a second provider,
        a second preprocessing path or a second transport. Blank or non-string
        values fall back to the default so a question can never become empty.
        The question actually used is recorded in `diagnostics` for provenance.
        """
        cfg = self.config
        scoped = isinstance(prompt, str) and bool(prompt.strip())
        question = prompt if scoped else OBSERVER_PROMPT
        body, error, transport = None, None, None
        diagnostics = {
            "evidence_type": "RUNTIME_STATUS",
            "observer_context": cfg.observer_ctx,
            "image_policy_version": OBSERVER_IMAGE_POLICY_VERSION,
            "observer_max_long_edge": cfg.observer_max_long_edge,
            "observer_max_pixels": cfg.observer_max_pixels,
            "observer_prompt_source": "caller_scoped" if scoped else "default",
            "observer_prompt_sha256": hashlib.sha256(
                question.encode("utf-8")).hexdigest(),
            "original_width": None, "original_height": None,
            "observer_input_width": None, "observer_input_height": None,
            "observer_image_resized": None, "original_source_sha256": None,
            "image_preparation_status": "FAILED",
        }
        started = time.monotonic()
        try:
            path = OllamaVisionProvider.resolve_path(image_asset)
            if not path:
                raise ValueError("image_not_readable")
            encoded = _prepare_observer_image(path, cfg, diagnostics)
            # FACADE-04D.3C-5B — hold the model lease across the call.
            with ollama_model_call(cfg.model):
                response = self.session.post(
                    cfg.endpoint + "/api/generate",
                    json={"model": cfg.model, "prompt": question,
                          "images": [encoded], "stream": False, "think": cfg.thinking,
                          "options": {"temperature": 0, "num_predict": cfg.observer_tokens,
                                      "num_ctx": cfg.observer_ctx}},
                    timeout=cfg.observer_timeout,
                )
            transport = response.text
            body = response.json()
            if response.status_code != 200:
                error = "ollama_http_" + str(response.status_code)
            elif not isinstance(body, dict):
                error = "invalid_observer_envelope"
            elif body.get("error"):
                error = str(body["error"])
        except OllamaModelBusy:
            error = "ollama_model_busy"
        except Exception as exc:
            error = type(exc).__name__ + ":" + str(exc)
        raw = raw_observation(provider="ollama", model=cfg.model, backend=cfg.endpoint,
                              thinking_mode=cfg.thinking, body=body, error=error,
                              transport_text=transport)
        raw["elapsed_s"] = round(time.monotonic() - started, 3)
        raw["diagnostics"] = diagnostics
        return raw


class OllamaTextNormalizer:
    def __init__(self, config, session):
        self.config, self.session = config, session

    def normalize(self, raw_text):
        # Deliberately no asset/path/bytes argument or image resolving code.
        cfg = self.config
        text, input_meta = normalizer_input(raw_text, cfg.normalizer_input_chars)
        result = {"status": "FAILED", "normalizer_version": NORMALIZER_VERSION,
                  "schema_version": SCHEMA_VERSION, "model": cfg.normalizer_model,
                  "thinking_mode": False, "input": input_meta}
        try:
            # FACADE-04D.3C-5B — hold the model lease across the call.
            with ollama_model_call(cfg.normalizer_model):
                response = self.session.post(
                    cfg.endpoint + "/api/generate",
                    json={"model": cfg.normalizer_model, "system": NORMALIZER_PROMPT,
                          "prompt": text, "stream": False, "think": False,
                          "format": copy.deepcopy(STRUCTURED_SCHEMA),
                          "options": {"temperature": 0, "num_predict": cfg.normalizer_tokens,
                                      "num_ctx": cfg.normalizer_ctx}},
                    timeout=cfg.normalizer_timeout,
                )
            result["transport_text"] = response.text
            body = response.json()
            result["generation_metadata"] = copy.deepcopy(body)
            if response.status_code != 200:
                raise ValueError("normalizer_http_" + str(response.status_code))
            result["raw_text"] = body.get("response", "")
            if body.get("error") or body.get("done_reason") == "length" or body.get("done") is False:
                raise ValueError("normalizer_generation_incomplete")
            result["structured"] = parse_normalization(
                result["raw_text"], text, diagnostics=result)
            result["status"] = "NORMALIZED"
        except Exception as exc:
            result["error"] = type(exc).__name__ + ":" + str(exc)
        return result


class OllamaVisionProvider(ArchitecturalVisionProvider):
    name = "ollama"
    supports_grounding = False

    def __init__(self, model=None, endpoint=None, timeout=None, cache_size=64,
                 *, config=None, session=None):
        cfg = config or VisionConfig.from_env(model=model)
        self.config = replace(cfg, **{key: value for key, value in {
            "model": model, "endpoint": endpoint.rstrip("/") if endpoint else None,
            "timeout": timeout,
        }.items() if value is not None})
        if model is not None and config is None and "ARCHITECTOS_VISION_NORMALIZER_MODEL" not in os.environ:
            self.config = replace(self.config, normalizer_model=model)
        self.model, self.endpoint, self.timeout = self.config.model, self.config.endpoint, self.config.timeout
        self.cache_size, self._raw_cache = cache_size, {}
        self.session = session or requests.Session()
        # Preserve configured HTTP credentials/proxy for non-loopback backends.
        if urlparse(self.endpoint).hostname in ("localhost", "127.0.0.1", "::1"):
            self.session.trust_env = False
        self.observer = OllamaVisualObserver(self.config, self.session)
        self.normalizer = OllamaTextNormalizer(self.config, self.session)

    def cache_identity(self):
        return {"provider": self.name, **asdict(self.config),
                "observer_image_policy_version": OBSERVER_IMAGE_POLICY_VERSION,
                "observer_version": OBSERVER_VERSION,
                "normalizer_version": NORMALIZER_VERSION, "schema_version": SCHEMA_VERSION}

    def is_available(self):
        # Do not cache an outage for the lifetime of the process.
        try:
            response = self.session.get(self.endpoint + "/api/tags", timeout=10)
            if response.status_code != 200:
                return False
            names = {m.get("name") for m in response.json().get("models", []) if isinstance(m, dict)}
            # A missing text model is a normalizer failure, not a reason to
            # suppress useful raw observations from an available visual model.
            if self.model not in names:
                return False
            response = self.session.post(self.endpoint + "/api/show", json={"model": self.model}, timeout=10800)
            return response.status_code == 200 and "vision" in (response.json().get("capabilities") or [])
        except Exception:
            return False

    def describe(self):
        return {"provider": self.name, "model": self.model, "endpoint": self.endpoint,
                "available": bool(self.is_available()), "supports_grounding": False,
                "local": urlparse(self.endpoint).hostname in ("localhost", "127.0.0.1", "::1"),
                "cache_identity": self.cache_identity(), "architecture": "observer_then_text_normalizer"}

    @staticmethod
    def resolve_path(image_asset):
        if isinstance(image_asset, str):
            return image_asset if os.path.isfile(image_asset) else None
        if isinstance(image_asset, dict):
            for key in ("path", "file_path", "local_path"):
                path = image_asset.get(key)
                if isinstance(path, str) and os.path.isfile(path):
                    return path
        return None

    def _cache_key(self, path):
        import json
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        return digest, json.dumps(self.cache_identity(), sort_keys=True)

    def analyze(self, image_asset):
        path = self.resolve_path(image_asset)
        key = self._cache_key(path) if path else None
        if key in self._raw_cache:
            return copy.deepcopy(self._raw_cache[key])
        result = run_visual_bridge(self.observer, self.normalizer, image_asset)
        result["cache_identity"] = self.cache_identity()
        if (key and self.cache_size > 0
                and result["raw_observer"]["generation_status"] == "COMPLETE"
                and result["normalization"]["status"] == "NORMALIZED"):
            if len(self._raw_cache) >= self.cache_size:
                self._raw_cache.pop(next(iter(self._raw_cache)))
            self._raw_cache[key] = copy.deepcopy(result)
        return result


@lru_cache(maxsize=4)
def _configured_provider(config):
    return OllamaVisionProvider(config=config)


def get_vision_provider():
    """Configuration is read at selection time, not frozen at module import."""
    return _configured_provider(VisionConfig.from_env())
