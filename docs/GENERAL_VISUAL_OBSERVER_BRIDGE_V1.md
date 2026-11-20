# General Visual Observer Bridge V1

Baseline: `be96f5bf0d582f07fe3b4976252728bd1ca00479` on
`w4-2a-general-observation-completeness-v1`. Implementation branch:
`w4-2a-general-visual-observer-bridge-v1`.

## Baseline audit and change rationale

The previous live path was `image_session_v1.analyze_record` → singleton
`OllamaVisionProvider.analyze` → image plus JSON request → optional second image
plus JSON repair → `build_understanding` → observation/interpretation consumers.
Non-JSON responses could be lost. Thinking was implicit. Cache reuse checked
`w4-2a-vision-evidence-integrity-v1` and local OCR environment, but not model or
stage identities. Existing local readers already supplied independent evidence.

Changes are confined to vision configuration, transport, session orchestration,
understanding, observation presentation, grounding audit fields, and tests:

| File / functions | Purpose |
| --- | --- |
| `config/vision_config.py`: `VisionConfig.from_env`, `_thinking`, `_positive` | Read model, endpoint, thinking and bounded generation settings at selection time. |
| `general_visual_observer_v1.py`: protocols, `raw_observation`, `run_visual_bridge`, `text_sha256` | Provider-independent observer → raw → text normalizer boundary; lossless raw envelope. |
| `observation_normalizer_v1.py`: schema builders, `validate_structured`, `iter_claims`, `parse_normalization`, `normalizer_input` | Closed, bounded schema, source quotations, explicit input reduction. |
| `vision_provider_ollama_v1.py`: `OllamaVisualObserver.observe`, `OllamaTextNormalizer.normalize`, provider constructor / `analyze` / `cache_identity` / `_cache_key` / `is_available` / `describe`, `get_vision_provider`, `_configured_provider` | Separate requests; retire image repair and `_parse_json`; replace import-time singleton with configuration-keyed selection. `resolve_path` remains the asset resolver. |
| `provider_candidate_verification_v1.py`: `provider_candidates`, `verify_candidates`, `local_ocr_evidence`, `_source_context`, `_numeric_category`, `_decision` | Candidate lifecycle and conservative independent verification, without detectors. |
| `image_session_v1.py`: `provider`, `_provider_cache_identity`, `_cache_reuse_reason`, `analyze_record` | Select configured provider, preserve local evidence and raw retries, prevent legacy bypass, invalidate stale/incomplete caches. |
| `image_understanding_v1.py`: `build_understanding`, `_build_bridge_understanding` | Keep audit evidence separate from safe legacy fields; retain local evidence on failure. |
| `vision_observation_mode_v1.py`: `build_observation`, `render_observation` | Carry verified/candidate evidence separately and label model claims by verdict. |
| `architectural_vision_grounding_v1.py`: `ground_vision_evidence` | Add candidate/verdict audit fields; existing grounding rules unchanged. |
| Vision tests | New bridge contracts and update the definition of a current cache. |

## Runtime architecture

Image → free-form observer → verbatim raw record → **text-only** normalizer →
provider candidates → independent local verification → grounded observation →
existing architectural interpretation and knowledge consumers.

Local reading remains independently scheduled by the session. Its output is
passed to verification after normalization; it is never supplied to the
normalizer or replaced by provider-supplied local evidence. Local-only operation
remains possible. No new detector, image-specific branch, or threshold change is
part of this bridge.

The observer protocol accepts an image asset. The normalizer protocol accepts
one string. The Ollama observer calls `/api/generate` with `images`, no `format`,
explicit thinking and temperature 0. The normalizer calls `/api/generate` with
raw text in `prompt`, a separate system instruction, `think: false`, temperature
0 and the strict JSON schema in `format`. It has no image/path argument, no file
reading and no repair image request.

## Configuration and swapping

Set environment variables before launch, or change runtime environment before
provider selection. No Python source edit is required.

| Variable | Default |
| --- | --- |
| `ARCHITECTOS_VISION_MODEL` | `gemma4:12b` |
| `ARCHITECTOS_VISION_NORMALIZER_MODEL` | Same as vision model |
| `ARCHITECTOS_VISION_THINK` | `low` for Qwen names; `false` otherwise |
| `ARCHITECTOS_VISION_OBSERVER_TOKENS` | `4096` (was `2048`; see the retention fix) |
| `ARCHITECTOS_VISION_OBSERVER_CTX` | `32768`, observer `options.num_ctx` only |
| `ARCHITECTOS_VISION_OBSERVER_MAX_LONG_EDGE` | `4096` pixels |
| `ARCHITECTOS_VISION_OBSERVER_MAX_PIXELS` | `12000000` pixels |
| `ARCHITECTOS_VISION_NORMALIZER_TOKENS` | `8192` |
| `ARCHITECTOS_VISION_NORMALIZER_CTX` | `32768` |
| `ARCHITECTOS_VISION_NORMALIZER_INPUT_CHARS` | `24000` |
| `ARCHITECTOS_VISION_OBSERVER_TIMEOUT` | `600` seconds, observer only (measured headroom) |
| `ARCHITECTOS_VISION_TIMEOUT` | `300` seconds; still drives the observer when set |
| `ARCHITECTOS_VISION_NORMALIZER_TIMEOUT` | `420` seconds, text normalizer only |
| `ARCHITECTOS_OLLAMA_URL` | `http://127.0.0.1:11434` |

For the validated Qwen setup, select `ARCHITECTOS_VISION_MODEL=qwen3.8:27b`;
observer thinking defaults to `low`. For Gemma, select
`ARCHITECTOS_VISION_MODEL=gemma4:12b`; observer thinking defaults to `false`.
The normalizer always uses `false`. Explicit thinking overrides accept
`true`, `false`, `low`, `medium`, `high`; a backend that rejects a setting records
a failure rather than silently changing the request. If the normalizer model
was explicitly overridden, change/unset that variable when switching both stages.
No models are downloaded, and no removed model is a dependency.

The provider-independent protocols can be implemented by a future transport;
this version supplies the Ollama implementation only. A missing text model does
not prevent an available observer from returning useful raw text.

### Observer image input

The Ollama observer prepares a separate in-memory input from the original asset.
Images within both configured bounds retain their original bytes. Larger images
are uniformly reduced to fit both bounds, with integer pixel rounding, Lanczos
resampling and lossless PNG encoding. The whole sheet is preserved: no crop or
upscale. The generous defaults retain detail instead of forcing every drawing
into a thumbnail. Context and image bounds are positive integer settings; the
observer context is independent of the text normalizer context.

The original file and registered asset are never modified. Local CV/OCR,
geometry, symbols and plan reading continue to receive the original path at
full resolution. No temporary files are created. Input/output buffers are
context-managed on success and failure. Bounds are a generic input policy, not
a guarantee about a backend's image tokenization or available device memory.

`visual_observer_bridge.raw_observer.diagnostics` records `original_width`,
`original_height`, `observer_input_width`, `observer_input_height`,
`observer_image_resized`, `observer_context`, `original_source_sha256`, the two
bounds, policy version and `image_preparation_status`. These are `RUNTIME_STATUS`
metadata, never architectural evidence. On preparation failure, unavailable
dimensions/resize state remain null; the actual error is retained in the raw
record, no observer request is sent, and no observation is invented. Generation
metadata and raw text retention retain their existing behavior.

Observer context, both image bounds and image policy version participate in
provider identity and both provider/persisted analysis cache invalidation.
The image-content cache key still hashes the original source bytes.
See [targeted Fix3](GENERAL_VISUAL_OBSERVER_BRIDGE_V1_FIX3.md) for verification.

## Contracts and retention

`RawVisualObservationV1` records provider, model, backend, observer version,
verbatim `raw_text`, UTF-8 SHA-256, generation status, done reason, thinking mode,
complete available generation metadata, transport response, elapsed time and
errors. Thinking-only output remains diagnostic metadata, not observation text.
Partial output remains partial even if normalization succeeds.

`GeneralVisualObserverBridgeV1` carries the raw observer record and complete
normalization result, including the normalizer's raw output and schema error.
`ImageUnderstandingV1.visual_observer_bridge` retains this envelope on success,
normalizer/schema failure, verification failure, and claim rejection. Previous
attempts are retained in `visual_observer_history` on reanalysis. The existing
image registry write-through mechanism persists the whole understanding for a
project; standalone sessions remain in memory under existing registry lifecycle
rules. This is not a separate archival service.

Raw text is never truncated by this bridge: `raw_truncated=false`, and
`original_length` counts Unicode characters. Only normalizer input may be
reduced at its configured character bound; the input metadata explicitly gives
`input_reduced`, original/input lengths and separate hashes. Raw and history
storage consequently grow with output and retry volume; no silent size cap is
introduced. A malformed HTTP envelope is preserved in `transport_text` even
when no valid response-text field can be recovered.

The structured schema distinguishes drawing type, observed elements, enclosed
spaces, walls, doors/windows/other openings, vertical circulation, furniture,
fixtures, structural elements, axes, orientation, provider OCR candidate,
exact/partial/unreadable OCR, scale, dimensions, level codes, spatial
relationships, interpretations and unknowns. Every array is capped at 16;
objects reject extra keys. Text, quote and kind strings are capped at 160, 240,
and 48 characters respectively. Each claim
has an explicit certainty and optional count. Final stored text/quote are verbatim
substrings of the source. Fix2 resolves exact matches first, then unique matches
under Unicode casefold and ASCII/U+2010/U+2011 hyphen equivalence, restoring raw
characters. No paraphrase, whitespace, numeric or mathematical-minus correction
is allowed. Unsupported/ambiguous quotes or text are rejected per claim after
schema validation; valid claims survive. Accepted/rejected counts, original
rejected claims/reasons, and canonical resolutions are retained in normalization
diagnostics. Omitted model observations remain available in raw
text. Schema limits do not claim exhaustive visual recall.

## Verification and semantic boundaries

Every normalized claim begins `PROVIDER_CANDIDATE`, ungrounded. The verifier
produces `CONFIRMED`, `CONTRADICTED`, `UNVERIFIED` or `AMBIGUOUS` with local
provenance and a reason. Only `CONFIRMED` provider claims enter the grounded
provider evidence list. Confidence is not a verification input.

The current verifier can corroborate atomic object-type presence using existing
validated local element/symbol contracts, exact text using independent uncorrected
local OCR, and signed level annotations using the existing local numeric OCR
contract. An explicitly claimed zero/absence contradicted by a locally visible
object becomes `CONTRADICTED`. Detector silence is never negative evidence.

Object verification is type presence, **not** instance count or confirmation of
modifiers such as size, material or room role. Whole phrases and total counts
without complete independent evidence remain unverified. Local reader candidate
geometry cannot confirm a provider object. Missing verification support for axes,
orientation or spatial relationships leaves those claims unverified, without
inventing detectors. Enclosures/walls continue through existing local grounding.

`ASSERTED` means the observer positively states visual presence or a reading;
it does not establish verification. `UNKNOWN` means the observer explicitly
cannot determine the fact, not merely that it has not been independently
verified. `AMBIGUOUS` means explicit hedging or multiple plausible readings.
Unknown claims retain an unverified verdict; ambiguous claims retain a distinct
certainty/verdict. Enclosing source lines are checked conservatively for
negation/uncertainty so noun-only extraction cannot readily strip qualifiers.
This guard is conservative and language-limited, not proof of semantic fidelity.

Observer OCR exactness describes **what the provider claims to have read**.
It does not mean independently verified OCR. `local_ocr` retains local readings;
`verified_ocr` contains corroborated provider readings. Lexicon-corrected local
labels remain valid local evidence under existing rules but cannot by themselves
verify an exact transcription. A phone number or a statement that text is visible
never becomes verified from model confidence alone.

Scale, dimensions and signed level codes retain separate categories. The verifier
rejects cross-category numeric forms and floor titles as level codes, and never
adds a unit. Axes are stored as the claimed entries, never expanded to sequences.
Orientation is a first-class category, never inferred from page layout.

Interpretations remain separate from observations and do not enter grounding.
The legacy downstream prose fields receive only corroborated atomic object
presence. Typed OCR/numeric evidence remains structured. Raw/candidate prose is
not passed into the legacy interpretation or knowledge inference fields. Existing
local evidence stays independently usable without a provider claim. An old
image-to-JSON adapter used by the live session is retained as diagnostic data and
local-only fallback, not allowed to bypass the new verifier.

## Cache audit and invalidation

The evidence pipeline is now `w4-2a-general-visual-observer-bridge-v1`.
Session cache identity includes provider, vision/normalizer models, endpoint,
thinking, generation/input budgets, observer version, normalizer version and
schema version. The existing local OCR environment comparison remains mandatory.
Only completed analyses with a complete bridge can be reused. Failed, unavailable,
partial, stale or verification-failed records are recomputed, with prior raw retained.
The provider's bounded in-memory cache also uses image content SHA-256 and full
configuration identity; callers receive copies. No raw/schema failure is cached
as success. Bump the evidence pipeline/version when verification semantics change.

## Validation and limits

Focused tests cover raw retention and hashing, partial/thinking-only responses,
text-only requests, strict schema bounds, source fidelity, model swapping,
verification states, OCR taxonomy, scale/dimension/level separation, axes,
orientation, local-only fallback, failed normalization/verification, persistence,
retry history, cache versions and acceptance-hardcode absence.

The cloud environment has no running Ollama service, no private acceptance images,
and no `tesserocr`. Transport/model-swap tests use controlled responses; they do
not establish real model quality or latency. No model download was attempted.
The exact `212` and B/C/D acceptance inputs were unavailable. Unseen-image
validation remains required with no code changes.

Baseline comparisons use an untouched `git archive` of the exact commit above,
never main or the stale work checkout. Some historical tests only accumulate
boolean results under pytest, so their standalone runners were checked too:

- Completeness: 15/15 standalone checks pass.
- Report language: 16/16 standalone checks pass.
- Observation separation: 23/28, with the same pre-existing failures at baseline
  and implementation: T2a, R4, R5, R6, T6.
- Grounding: 17/21, with the same pre-existing failures: G1, G3, G5, G21.
- Registry routing: E, K, L fail identically on baseline because the expected
  Windows image asset is absent; no unrelated code was changed to hide this.

BIM, IFC, Render, ComfyUI, structural/design-generation pipelines and local
detectors are unchanged. This implements the bridge, not general vision as a
solved capability.

### Recorded cloud test results

- New bridge suite: **52 parametrized cases, all passed**.
- Focused bridge + evidence integrity + cache run: **90 passed, 3 skipped**.
- Final combined 14-suite pytest run: **320 passed, 28 skipped, 3 failed**,
  with 16 legacy return-value warnings. The three failures are the identical
  baseline missing-fixture cases described above. Of the skips, 26 require
  private image assets and two require `tesserocr`.
- The standalone runner failures above are additionally disclosed because those
  legacy `_check` functions can appear as passing pytest tests despite false
  internal results. They are unchanged from the exact baseline.
- Python compilation/AST checks and `git diff --check` passed. Changed-path audit
  confirms no protected subsystem or local detector file changed.

The combined invocation used `python -m pytest -q -rs` on these files under
`tests/`: `test_general_visual_observer_bridge_v1.py`,
`test_w4_2a_general_observation_completeness_v1.py`,
`test_vision_evidence_integrity_w4_2a.py`,
`test_vision_observation_mode_separation_v1.py`,
`test_architectural_observation_v1.py`,
`test_architectural_vision_grounding_v1.py`, `test_vision_analysis_cache_v1.py`,
`test_architectural_vision_interpreter_v1.py`, `test_local_plan_reader_v1.py`,
`test_multi_plan_sheet_v1.py`, `test_architectural_plan_elements_v1.py`,
`test_furniture_function_generalization_v1.py`, `test_vision_image_registry_04.py`,
and `test_vision_report_language_01.py`.

Status: `IMPLEMENTATION_COMPLETE_NEEDS_UNSEEN_VALIDATION`.

The results above describe the original bridge implementation. See
[targeted B-1/B-4 fix](GENERAL_VISUAL_OBSERVER_BRIDGE_V1_FIX1.md) for the budget
rationale, legacy consumer audit, changed contract assertions, and fix results.
