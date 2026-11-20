# General Visual Observer Bridge V1 — targeted Fix3

## Verified base and scope

The remote starting branch `w4-2a-general-visual-observer-bridge-v1-fix2`
was fetched and verified at `67a8df07d697fa48752734e031a9be64881453d1`, with
sole parent `911afea2fe5d714fd5914bbe39412c381ee8f29d`.
An isolated worktree branches directly from that exact commit as
`w4-2a-general-visual-observer-bridge-v1-fix3`.

This change addresses only F-1: observer context and large-image transport.
No merge is part of this task. No live model or unseen-image validation is
claimed. The execution environment does not have the live Ollama backend or
private acceptance images.

## Root cause and context

The observer supplied `num_predict` but omitted `options.num_ctx`, so the
reported runtime used its 4096-token default and rejected large image requests
before observer generation. The text normalizer already configured its own
context, which cannot fix an observer request rejected before producing text.

`ARCHITECTOS_VISION_OBSERVER_CTX` now defaults to 32768 and is explicitly sent
as the observer's `options.num_ctx`. This is separately configurable from
`ARCHITECTOS_VISION_NORMALIZER_CTX`; neither overrides the other. Model choice,
observer prompt, thinking mode, generation budget and normalizer requests are
unchanged. No automatic retry or silent configuration downgrade was added.

## Bounded observer input

Provider-side `_prepare_observer_image` reads the original file without writing
it. Images within both bounds retain their original bytes and encoding:

| Setting | Default |
| --- | --- |
| `ARCHITECTOS_VISION_OBSERVER_MAX_LONG_EDGE` | 4096 pixels |
| `ARCHITECTOS_VISION_OBSERVER_MAX_PIXELS` | 12000000 pixels |

Above either bound, the observer receives a separate memory-only PNG. A uniform
scale fits both limits, with subpixel rounding down, no upscale, no crop, and
Lanczos resampling. The one-pixel minimum also respects the pixel budget for
extremely thin images. RGB/RGBA conversion preserves transparency where present
and avoids palette/monochrome nearest-neighbor resizing. PNG avoids adding JPEG
compression artifacts to the reduction.

These conservative defaults preserve detailed multi-megapixel sheets below the
bounds. Explicit context is the first fix for those images; they are not resized
unnecessarily. Bounds are generic configuration, not acceptance-image-specific
rules or a model-specific token predictor. Operators can tune them for their
backend capacity. Runtime token counts, memory use and visual quality still
require live validation.

The session's original path is independently passed to `read_local_plan`.
Neither the uploaded file nor any registered asset identity/path is modified.
Local OCR, geometry, symbol and plan pipelines keep their full-resolution input.
No temporary files exist; in-memory buffers close on success, encoding failure
and transport failure. Original source SHA-256 remains the provider cache key.

## Diagnostics, retention and cache

The raw observer's `diagnostics` contains:

- `original_width`, `original_height`;
- `observer_input_width`, `observer_input_height`;
- `observer_image_resized`, `observer_context`;
- `original_source_sha256`;
- `observer_max_long_edge`, `observer_max_pixels`, `image_policy_version`;
- `image_preparation_status`, with `evidence_type=RUNTIME_STATUS`.

Preparation failures retain known source facts and the actual exception, leaving
unknown dimensions and resize state null. They generate no request, observation
or normalizer call. A transport failure after preparation keeps READY input
diagnostics and FAILED generation status. Failed bridges remain uncached.

Existing full raw text, text hash, thinking, transport response, generation/token
metadata, elapsed time and history retention are unchanged. Diagnostics persist
through the existing bridge/registry envelope and cannot become evidence.

`VisionConfig` fields automatically enter `cache_identity()` via `asdict`.
The explicit `observer_image_policy_version` also invalidates old identities.
Tests cover observer-context and both bound changes at the provider content
cache and persisted session cache boundaries. Provider selection rereads the
configuration and returns a different configured provider after changes.

## Files and functions

- `config/vision_config.py`: added three `VisionConfig` fields and environment
  loading in `VisionConfig.from_env`.
- `core/vision/vision_provider_ollama_v1.py`: new `_prepare_observer_image`;
  modified `OllamaVisualObserver.observe` and `OllamaVisionProvider.cache_identity`.
- `tests/test_general_visual_observer_bridge_v1.py`: synthetic valid-image
  fixture, transport helper, expanded context/version cache tests and 32 new
  parametrized cases.
- `docs/GENERAL_VISUAL_OBSERVER_BRIDGE_V1.md`: configuration and input policy.
- `docs/GENERAL_VISUAL_OBSERVER_BRIDGE_V1_FIX3.md`: this audit.

New coverage includes small images and detailed sheets unchanged, portrait,
landscape and pixel-limited inputs, whole-sheet colored corners, aspect ratio,
no upscale, source bytes/mtime/hash, registered asset identity, full-resolution
local-reader path versus bounded observer bytes, explicit context, independent
normalizer context, positive finite configuration, both cache layers, corrupt
images, thin images, buffer cleanup and failures before/after preparation.
Only generic synthetic images are added; no acceptance filenames, hashes or
content were added to production code or tests. The existing transport fixture
now contains a valid synthetic PNG because preparation must decode real images.

## Validation

The exact Fix2 baseline and Fix3 use the same isolated Python 3.12 environment.
The requested four primary pytest files and five additional Vision suites are
run. Standalone runners are also used because some legacy tests return booleans
or collect their own result records that pytest alone does not enforce.

| Suite | Exact Fix2 baseline | Fix3 |
| --- | --- | --- |
| Bridge pytest | 104 passed | 136 passed |
| Analysis cache pytest | 1 passed, 3 skipped | Same |
| Evidence integrity pytest | 37 passed | Same |
| Architectural interpreter pytest | 10 passed | Same |
| General observation completeness standalone | 15/15 | Same |
| Grounding standalone | 17/21 | Same |
| Observation separation standalone | 23/28 | Same |
| Report language standalone | 16/16 | Same |
| Registry isolated pytest | 14 passed, 3 failed | Same |

The primary files total **184 passed, 3 skipped**, compared with baseline
**152 passed, 3 skipped**. The combined nine-file pytest invocation reports
**277 passed, 3 skipped, 4 failed**, compared with baseline
**245 passed, 3 skipped, 4 failed**. Grounding failures remain G1/G3/G5/G21;
separation failures remain T2a/R4/R5/R6/T6. Registry E/K/L require the unavailable
Windows render fixture; its standalone runner stops at E. Registry M has a
pre-existing combined-suite environment contamination failure (Ollama URL
`http://127.0.0.1:9`) and passes when the registry suite runs in isolation.
Cache skips require the unavailable private image. Live registry A/B/C/D return
early when the backend is unavailable: pytest passes are not live acceptance.

## Frozen boundaries and deferred work

Normalizer code, schema, prompt and semantics are unchanged. Candidate
verification, grounding and legacy observed semantics are unchanged. No local
OCR heuristic or detector threshold changed. BIM, IFC, Render and ComfyUI
pipelines are untouched.

F-2 is explicitly deferred as **LOCAL_READER_QUALITY_V1**: reversed والدین being
lexicon-corrected to دالان, false تراس OCR, facade cornices/arches interpreted as
level/door, false HALL and false kitchen symbols. None is repaired by this task.
