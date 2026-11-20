# General Visual Observer Bridge V1 — targeted B-1 / B-4 fix

## Verified baseline and scope

Started from exactly `209e44dc6e8484031fc8db035e1871a969234108`, parent
`be96f5bf0d582f07fe3b4976252728bd1ca00479`, with a clean tracked tree.
The authorized implementation-branch fetch populated `FETCH_HEAD`; its exact
commit and parent were verified before creating
`w4-2a-general-visual-observer-bridge-v1-fix1` directly from that commit.
No main fetch, inspection, merge, rebase, or stale `work` code was used.

Production changes are confined to normalizer configuration, its request options,
and its schema/prompt/version constants. The bridge, verifier, legacy adapter,
local detectors, and interpretation implementations are unchanged.

## B-1: cause, cost audit, and fix

Source inspection confirms the previous request had `num_predict=4096` and no
explicit `num_ctx`. The supplied live measurements identify separate context
and output exhaustion; this cloud task does not independently reproduce those
live measurements. Raising context alone cannot remove the output ceiling.

| Setting | Before | Fix |
| --- | --- | --- |
| `ARCHITECTOS_VISION_NORMALIZER_CTX` / `options.num_ctx` | Absent | Explicit, default 32768 |
| `ARCHITECTOS_VISION_NORMALIZER_TOKENS` / `options.num_predict` | 4096 | 8192 |
| Normalizer input character limit | 24000 | 24000, unchanged |
| `MAX_ITEMS` per array | 16 | 16, unchanged |
| Claim text maximum characters | 240 | 160 |
| Exact source quote maximum characters | 480 | 240 |
| Canonical kind maximum characters | 64 | 48 |
| Normalizer / schema version suffix | v1 | v1.1 |

There are 22 bounded arrays and one optional drawing-type claim: at most 353
claims. The old three free-text fields permitted 784 characters per claim;
the new bounds permit 448, a 42.9% reduction. A schema stress serialization
with every array full, ASCII strings at their limits, longest certainty, maximum
count, and compact JSON is 304685 characters before and 186077 after (38.9%
smaller). These are character measurements, not tokenizer measurements or a
promise that every schema-maximum payload fits the generation budget.

The cardinality cap is retained to avoid reducing coverage of dense categories.
The prompt asks for the shortest sufficient exact quote, one specific category
per fact rather than duplicate generic observations, and compact JSON. It
requires retaining negation, uncertainty and explicit counts; claims that cannot
fit safely remain in the full raw observation, rather than being paraphrased or
silently cut mid-meaning. Raw observation retention is unchanged.

The output budget is doubled rather than sized for the pathological schema
maximum. A 32K context provides prompt space in addition to the 8K output
allowance, including longer and multilingual observer input. This is a finite
operational default, not a tokenizer-independent guarantee: dense outputs,
unusual tokenization, explicit smaller overrides, and backend model limits can
still exhaust a budget. `done_reason=length` remains a failure even if its JSON
looks complete. Failed normalization is not cached as success. No retries,
scheduling changes, or automatic budget escalation were added.

Both budgets accept positive integer environment overrides. `asdict(config)`
already participates in provider identity, the raw cache key, and persisted
session cache validation; the new context field therefore invalidates both
caches. Tests check both context and output configuration. Version bumps also
invalidate the previous schema/prompt identity.

`parse_normalization` still requires every quote to be an exact substring of
the raw text and every claim text to be an exact substring of that quote.
Provider candidates revalidate the same contract. The unchanged verifier also
recovers full source lines for every occurrence of short quotes, preventing a
noun-only quote from concealing an unknown/ambiguous/negative surrounding claim.
Axes are not extrapolated; OCR categories, scale, dimensions and levels remain
separate. The normalizer still receives a string only, no image, path, or local
detector evidence, and sends `think=false` and `temperature=0`.

## B-4: complete legacy `observed` consumer audit

Repository searches covered the exact field in Python and non-Python sources,
and broader `observed` references to catch aliased raw/observation consumers.
Unrelated teaching-status fields named `observed` are not image understanding.

| Consumer | Effect of restoring unverified prose |
| --- | --- |
| `image_understanding_v1.build_understanding`, `_build_bridge_understanding` | Screens legacy prose and builds downstream fields; bridge adapter deliberately supplies only independently confirmed atomic objects. |
| `architectural_vision_grounding_v1._claims` / `ground_vision_evidence` | Treats `observed` as object/geometry evidence (`CLASS_OBJECT`, `SOURCE_GEOMETRY`); direct promotion risk. |
| `architectural_vision_interpreter_v1._provider_evidence_for_local_plan`, `_architectural_observations`, `_evidence_text`, `_space_type_basis`, interpretation flow | Uses observations for visible objects, space-function evidence, confidence and reporting. Local-plan filtering does not protect a render/photo without local evidence. |
| `architectural_observation_v1.build_architectural_observation`, `_phrase_confidence`, `visible_observations_passthrough` | Preserves raw data, extracts elements/relationships, provides fallback evidence phrases, and assigns stronger confidence to observed phrases. |
| `architectural_visual_interpretation_v2._building_type`, `_element_meaning` | Reads retained raw observations for possible building type and element-meaning confidence. |
| `image_session_v1.build_grounded_prompt` | Labels `observed` as visual evidence in a downstream prompt. |
| `reference_resolver_v1.resolve_region_reference` | Uses observed text to consider an element confirmed visible and raise reference confidence. |
| `chat_architect.ChatArchitect._vision_block` | Copies observations into the user-facing image-turn provenance payload. |

Indirect consumers include observation-mode rendering and architectural reports
through the grounding/interpretation results above. The live legacy-provider
adapter in `image_session_v1.analyze_record` already retains old provider payloads
as raw diagnostics instead of permitting them to bypass candidate verification.

Decision: keep the verified-only legacy field. Use
`visual_observer_bridge.raw_observer.raw_text` for attributable retained observer
output, and `provider_candidates` for successfully normalized, explicitly
unverified claims. No production compatibility workaround is needed or added.

The registry's check A uses **RELAX + ADD**: allow an empty `observed` list,
require nonempty retained raw observation, require candidates on successful
normalization, validate exact source attribution and grounding states, and
require every legacy observation to belong to independently confirmed atomic
objects. No old test was deleted.

A deterministic render/photo regression runs the real session path and the
actual updated check A with no local corroboration, both with successful and
failed normalization. Eight descriptive observations survive as raw text;
successful normalization also retains all eight unverified candidates. Legacy
`observed`, grounded provider evidence, and visible downstream observations
remain empty. Descriptions do not enter the grounded prompt. This is controlled
provider testing, not live image recognition.

## Validation

The required suites were run. Standalone runners are authoritative for legacy
tests that merely accumulate boolean checks under pytest.

| Required suite | Fix result |
| --- | --- |
| `test_general_visual_observer_bridge_v1.py` | 66 passed (baseline 52) |
| `test_vision_analysis_cache_v1.py` | 1 passed, 3 skipped: private acceptance image absent |
| `test_vision_evidence_integrity_w4_2a.py` | 37 passed |
| `test_architectural_vision_interpreter_v1.py` | 10 passed |
| `test_w4_2a_general_observation_completeness_v1.py` | 15/15 standalone |
| `test_architectural_vision_grounding_v1.py` | 17/21 standalone; same baseline G1, G3, G5, G21 failures |
| `test_vision_observation_mode_separation_v1.py` | 23/28 standalone; same baseline T2a, R4, R5, R6, T6 failures |
| `test_vision_report_language_01.py` | 16/16 standalone |
| `test_vision_image_registry_04.py` | Isolated pytest: 14 passed, 3 failed due to absent Windows render fixture (E, K, L); all 17 tests reached |

The cloud cache/evidence/interpreter total is 48 passed and 3 skipped, not a
claim of the supplied review environment's 51 passing cases. Live-only registry
A/B/C/D early-return with warnings when Ollama is unavailable; pytest labels these
returns passed, so the 14-pass figure must not be read as live validation.

New bridge cases cover default/overridden request budgets, rejection of invalid
budget settings, raw/persisted cache invalidation, exact schema string bounds,
a 45-claim rich observation (1422 input characters, 6290 compact JSON characters),
and complete-looking JSON rejected on `done_reason=length` with raw/local evidence
retained. Rich output completion uses a controlled transport response, not a
real model. Existing source-validation and uncertainty/axis/numeric separation
tests remain in place and pass.

For a supplemental **controlled routing** run, an external harness supplied a
temporary generic 32x32 PNG as `RENDER_IMAGE` only for that process. No acceptance
image or tracked fixture was altered. The complete registry standalone runner,
including its nested regression suites, finished: **28 checks passed, 4 warnings**
(live A/B/C/D unavailable). Its new B-4 test calls
the actual check A four times with controlled render/photo responses. This
establishes full offline traversal, not the original live 27/27 acceptance.

An untouched `git archive` of the exact implementation baseline reproduced the
three missing-fixture failures and all nine documented grounding/separation
failures. A single-process combined run of all nine suites reports
207 passed, 3 skipped, 4 failed, with 16 legacy return-value warnings. The fourth
failure is a pre-existing collection-order interaction: the report-language
test sets `ARCHITECTOS_COMFY_PORT=9`, while registry M's nested runtime test
expects 8188. The exact baseline combined run gives 192 passed, 3 skipped,
the same 4 failures and 16 warnings. Isolated registry M passes. Neither the
fixture failures nor test-global configuration was repaired in this task.

## Changed files and functions

- `config/vision_config.py`: `VisionConfig` field and `from_env`.
- `core/vision/vision_provider_ollama_v1.py`: `OllamaTextNormalizer.normalize` options.
- `core/vision/observation_normalizer_v1.py`: version, prompt and schema constants;
  no validation function changed.
- `tests/test_general_visual_observer_bridge_v1.py`: extend request assertion;
  add rich fixture and seven test functions, yielding 14 additional cases.
- `tests/test_vision_image_registry_04.py`: new contract assertion helper and
  render/photo regression; update check A and standalone `run_all`.
- `docs/GENERAL_VISUAL_OBSERVER_BRIDGE_V1.md`: current configuration and bounds.
- This report: cost analysis, consumer audit, decision and validation evidence.

## Deferred and unresolved

- Live model completion/latency and unseen acceptance images remain unvalidated:
  no running Ollama service or private review images in this environment.
- B-2's reported false local OCR `تراس` and kitchen counter/sink detections remain
  a separate future issue. No detector or threshold was changed.
- B-3's 300-second observer timeout sensitivity remains operational and unchanged.
- No BIM, IFC, Render, ComfyUI, acceptance-image contents, local reader, symbol
  detector, or element detector code changed. No acceptance-specific file/hash,
  phone/name, axis sequence, count, or image coordinates were added to production.
- No merge. Exact final commit and push status are recorded in the delivery report.
