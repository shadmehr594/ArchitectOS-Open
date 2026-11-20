# ArchitectOS

**Offline-first computational architecture and local AI orchestration.**

ArchitectOS turns a natural-language architectural brief — or a site survey, CAD plan, or 3D model — into a structured building model, multi-floor drawings, a BIM shell, and a rendered architectural image. Everything runs on the operator's machine: local LLM inference, local diffusion rendering, local CAD/BIM processing. There is no cloud dependency and no hosted model in the loop.

**Version:** 79.0 · **License:** AGPL-3.0 · **Author:** Mahdi Ranjbar

---

## What it does

| Capability | Output |
|---|---|
| Persian / English design brief → parametric building | Typed model: floors, rooms, walls, openings, stairs, furniture |
| Site survey ingestion (Krocki DXF/DWG) | Site boundary, setbacks, parcel geometry |
| Multi-floor plan production | DXF (AutoCAD), SVG, PNG |
| Elevations and sections | DXF sheets with Persian text as ASCII `\U+XXXX` |
| 3D / BIM export | IFC4, GLB, OBJ, interactive scene JSON, Revit companion bundle |
| Architectural rendering | ComfyUI (FLUX + ControlNet) with depth/line-art conditioning |
| Local visual analysis | Ollama vision model + Tesseract OCR |
| Iterative edits | Day/night relight and material edits locked to the previous render |

The system is deliberately **geometry-first**: the renderer consumes a structured model that already satisfies explicit invariants (floor count, wall containment, opening placement), rather than asking an image model to invent a building from a prompt.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser                                                         │
│  127.0.0.1:3000                                                  │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│  ui/            Flask gateway + 5 blueprints                     │
│                 chat · project workspace · files · voice         │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│  app.py         Core API (127.0.0.1:5000)                        │
│                                                                  │
│  core/chat        intent, conversation, routing                  │
│  core/vision      local image understanding (Ollama + OCR)       │
│  core/site        Krocki survey parser, form solvers             │
│  core/planning    multi-floor plan engine                        │
│  core/cad         DXF/DWG import, elevations, sections           │
│  core/bim         IFC-oriented building intelligence             │
│  core/render      render orchestration and evaluation            │
│  core/architecture domain rules, contracts, authority handoff    │
└───────┬───────────────────────────────┬──────────────────────────┘
        │                               │
┌───────▼─────────────┐     ┌───────────▼──────────────────────────┐
│ engine/             │     │ core/planning/multifloor_v1/engine/  │
│ 2.5D geometry       │     │ NL parser → synthesizer → DXF/IFC    │
│ compositor          │     │ CAD reader · 3D shell extruder       │
│ evaluator           │     │ exporter · ComfyUI bridge            │
└─────────────────────┘     └───────────┬──────────────────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
      ┌───────▼────────┐      ┌─────────▼─────────┐     ┌─────────▼────────┐
      │ Ollama         │      │ ComfyUI           │     │ Blender / 3ds Max│
      │ 127.0.0.1:11434│      │ 127.0.0.1:8188    │     │ optional, headless│
      └────────────────┘      └───────────────────┘     └──────────────────┘
```

### Data flow

```
brief / plan / 3D model
        │
        ▼
intent + create-vs-edit gate        (core/chat, nl_design_parser)
        │
        ▼
parametric synthesis                (architectural_synthesizer)
        │
        ├──► plan drawings             DXF · SVG · PNG      (exporter)
        ├──► 3D shell                  IFC4 · GLB · OBJ     (dxf_to_3d_shell_extruder)
        └──► render conditioning       depth · line-art    (geometry_2p5d)
                    │
                    ▼
              ComfyUI workflow       FLUX + ControlNet
                    │
                    ▼
              render PNG + scene JSON
```

---

## Requirements

| Component | Requirement |
|---|---|
| Python | **3.12** (the pinned `tesserocr` wheel targets cp312 / Windows) |
| OS | Developed and validated on Windows 10/11; Linux/macOS should work for the pure-Python paths |
| GPU | A **16 GB VRAM** class GPU is the documented design target for the diffusion stage |
| ComfyUI | Required for image rendering (`127.0.0.1:8188`) |
| Ollama | Required for chat and vision (`127.0.0.1:11434`) |
| Blender | Optional — headless 3D pre-render |
| 3ds Max | Optional — `.max` scene import via `3dsmaxbatch.exe` |

Nothing is downloaded at runtime by this repository. Model weights are **not** bundled; see `models/README.md`.

---

## Installation

```bash
git clone https://github.com/<your-account>/ArchitectOS.git
cd ArchitectOS

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

> The `tesserocr` dependency is pinned to a Windows / CPython 3.12 wheel. On other platforms, install `tesserocr` through your system package manager or remove that line if OCR is not needed.

### Local AI services (optional but required for their features)

```bash
# Chat + vision
ollama serve
ollama pull qwen3.8:27b        # or set ARCHITECTOS_CHAT_MODEL / ARCHITECTOS_VISION_MODEL

# Diffusion rendering
# start ComfyUI with FLUX + ControlNet models installed, listening on 127.0.0.1:8188
```

---

## Running

```bash
python launcher.py
```

Then open **http://127.0.0.1:3000**.

`launcher.py` starts the Core API (`:5000`) and the UI gateway (`:3000`) on loopback. `run.py` is a minimal single-process alternative and also binds loopback only (`127.0.0.1:5000`).

Health probes: `GET :5000/health`, `GET :3000/status`.

---

## Configuration

All settings are environment variables with safe defaults (see `config/runtime_config.py`, `config/chat_config.py`, `config/vision_config.py`).

| Variable | Default | Purpose |
|---|---|---|
| `ARCHITECTOS_CORE_API_PORT` | `5000` | Core API port |
| `ARCHITECTOS_UI_PORT` | `3000` | UI gateway port |
| `ARCHITECTOS_OLLAMA_URL` | `http://127.0.0.1:11434` | Local LLM / vision endpoint |
| `ARCHITECTOS_CHAT_MODEL` | `qwen3.8:27b` | Chat model |
| `ARCHITECTOS_VISION_MODEL` | `qwen3.8:27b` | Vision model |
| `ARCHITECTOS_MAX_UPLOAD_BYTES` | `67108864` (64 MiB) | HTTP request body cap |
| `ARCHITECTOS_3DFUTURE_DIR` | `<repo>/3D-FUTURE-model` | 3D-FUTURE dataset root |
| `ARCHITECTOS_3DFUTURE_ZIP` | `~/3D-FUTURE-model.zip` | Dataset archive, if unpacked copy is absent |

---

## Repository layout

```
app.py                     Core API
launcher.py                Process launcher (Core API + UI)
run.py                     Minimal single-process entry point
cli.py                     Plan-engine CLI

config/                    Runtime, chat, vision, ComfyUI configuration
core/                      Domain + platform code
  architecture/            Rules, contracts, authority handoff
  planning/                Multi-floor plan engine
  site/                    Survey / parcel geometry
  cad/                     DXF, DWG, elevations, sections
  bim/                     BIM intelligence
  vision/                  Local visual analysis
  render/                  Render orchestration
  chat/                    Conversation and intent
engine/                    2.5D render pipeline (6 modules)
ui/                        Flask gateway, blueprints, template
workflows/                 ComfyUI graphs (depth, 2.5D, relight, photoreal)
tests/                     Pytest suites
tools/                     Internal analysis and acceptance utilities
skills/                    Pluggable skill modules
docs/                      Release notes and design documents
```

---

## Testing

```bash
pytest tests -q
```

The v79.0 release package was validated by a **77-check acceptance suite (77/77 passing at release time)**, covering plan geometry, 3D/BIM export, DXF layer normalisation, render tier contracts, project isolation, and the high-rise rendering regressions.

The pytest tree is large and not uniformly green. Known issues are listed in `CONTRIBUTING.md`; some suites are long-running or require local AI services. Please scope your run (for example `pytest tests/architecture -q`) when iterating.

---

## Regulatory documents

This repository **does not bundle** municipal or national regulatory PDFs.

Supply your own local documents under `core/architecture/authorities/local/` (git-ignored). The application treats them as optional inputs: when a document is absent, regulatory values are reported as **unresolved** rather than inferred. See `AGENTS.md` for the full policy.

---

## Citation

If you use ArchitectOS in academic work, please cite the technical paper:

**DOI:** [10.5281/zenodo.24407073](https://doi.org/10.5281/zenodo.24407073)

```bibtex
@software{ranjbar_architectos_v79,
  author       = {Ranjbar, Mahdi},
  title        = {ArchitectOS: Offline-First Computational Architecture and Local AI Orchestration},
  year         = {2026},
  version      = {79.0},
  doi          = {10.5281/zenodo.24407073},
  url          = {https://doi.org/10.5281/zenodo.24407073}
}
```

---

## License

GNU Affero General Public License v3.0 — see [LICENSE](LICENSE).

Copyright (C) 2026 Mahdi Ranjbar.

---

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md), which lists the current engineering priorities.
