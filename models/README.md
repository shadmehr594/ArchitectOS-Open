# Models and datasets (not bundled)

This directory is intentionally empty. ArchitectOS does not redistribute model
weights or third-party datasets.

| Asset | Purpose | Where to obtain |
|---|---|---|
| **3D-FUTURE** | Furniture model retrieval for interior layouts | Official 3D-FUTURE distribution; unpack to `<repo>/3D-FUTURE-model/` or set `ARCHITECTOS_3DFUTURE_DIR` |
| **Tesseract OCR data** | Local OCR for plan/photo reading | `tesseract-ocr` language data; install via your package manager or the `tesserocr` wheel |
| **FLUX / ControlNet weights** | Diffusion rendering | Installed inside ComfyUI, not in this repository |
| **Ollama models** | Local LLM / vision inference | `ollama pull <model>`; see `config/chat_config.py` and `config/vision_config.py` |

None of these are required to import the package or run the test suite; they are
required only for the features that consume them.
