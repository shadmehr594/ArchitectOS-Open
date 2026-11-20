# VISION END-TO-END RETENTION FIX V1

Starting commit `837c570866726b062b867ad39e307f43d4ec3a8a`, branch
`w4-2a-vision-end-to-end-retention-fix-v1`. Not merged.

The measurement that motivated this change is
`ARCHITECTOS_VISION_END_TO_END_RETENTION_V1_REPORT.md`: the observer was
semantically strong, the bridge was provably honest, and **31/34 (NEW-L1) and
29/31 (NEW-L2) required facts died at the response adapter / renderer**, while
the local reader's false OCR was published as grounded architectural fact.

This change fixes ONLY those proven defects. It adds no model, no Vision V2, no
exploration, no evidence graph; it does not touch BIM, IFC, Render or ComfyUI;
it does not retrain a detector; and it contains no image-specific token.

## 1. The canonical image type is evidence-based, never a local side effect

`core/vision/image_understanding_v1.py::_build_bridge_understanding` used to set

```python
image_type = "floor_plan_or_sketch" if local.status == "grounded" else "unknown"
```

A local reader reporting `grounded` means only that it found *some* OCR,
opening, symbol or region, and its `single_plan` sheet type is the DEFAULT for
any raster. That rule typed a **cadastral land-survey sheet** and a **facade
render** as floor plans.

Now `_independent_image_type` returns `floor_plan_or_sketch` **only** for a
POSITIVE multi-panel structure detection (`sheet_structure.sheet_type` in
`multi_plan` / `plan_pair`); otherwise `unknown`.

A model's drawing-type observation never sets `image_type`. It is recorded
separately as `understanding["provider_drawing_type"]` =
`{text, canonical, state, verified, source: "MODEL_OBSERVED"}` and is reported
to the user with its verification state.

`core/vision/drawing_type_v1.py` (new) maps the observer's free text to the
canonical vocabulary, negation-aware and clause-scoped: a negated clause
contributes NO markers, so "not a building floor plan" and "rendering (not a
line drawing, plan, or section)" can never be inverted into a positive type.

## 2. A lexicon guess is not a reading

`core/vision/local_evidence_trust_v1.py` (new) is the consumer-side trust rule.
Promotion of a local OCR label to a GROUNDED architectural space label requires
BOTH:

* **no lexicon substitution** — `correction` is `None`. A reader's deterministic
  right-to-left re-orientation legitimately leaves `raw_ocr` different from
  `text` and stays valid; a lexicon SUBSTITUTION does not, and
* **independent verification** — `independent_passes >= 2`.

Anything else is preserved as a **low-trust OCR candidate** (`status:
low_trust_ocr`) with its raw OCR, box, correction, match score and promotion
reason. It is never deleted, never given a semantic function, never given a
zone, and never allowed to name a space.

Applied at both consumers:

* `core/vision/architectural_observation_v1.py` — only trusted labels enter
  `text_labels_if_visible`; the rest go to a new `low_trust_ocr_labels` list.
* `core/vision/architectural_vision_interpreter_v1.py::_read_labels` — trusted
  labels stay `grounded_ocr`; the rest become `low_trust_ocr` with
  `semantic_function = None` and `zone = None`.
* `core/vision/vision_observation_mode_v1.py::_grounded_categories` — splits the
  two, and `render_observation` prints the guesses under
  «خوانش OCR تأییدنشده (حدس، نه متن اثباتشده)» with their raw OCR.

A related, fail-closed rule: a local raster ELEMENT whose own detector declares
an UNSATISFIED requirement (`corroboration` contains a `*_required` marker that
is not met — e.g. `localized_numeric_annotation_required` for a level marker
with no grounded annotation) is a CLUE, never a visible object
(`architectural_vision_grounding_v1._local_requirement_met`).

## 3. The default answer reports the model's observation

`core/vision/vision_report_v1.py` gained `_provider_observation_summary`, and
`render_vision_report` now appends it (Persian) to the plan answer and uses it
as the whole answer when the image is not a plan.

It reports, categorised and capped:

* the model's drawing type, with the canonical mapping and an explicit
  "not yet confirmed by independent evidence" qualifier,
* confirmed observations (separate section),
* architectural observations (not independently verified),
* text / numeric content (not independently verified), ordered so the scale,
  exact readings and level codes come before looser OCR candidates,
* ambiguous readings,
* what the model states as unknown,
* an honesty note that no definite conclusion is drawn from them.

Reporting is not grounding: an UNVERIFIED claim is REPORTED and never presented
as proven. The section is additive and appears only when the interpretation
actually carries provider observation, so a legacy interpretation and the whole
English rendering are unchanged (G19/G20/V1 stay green).

## 4. Provider ABSENCE and local PRESENCE conflict visibly

`provider_candidate_verification_v1.claim_polarity` gives every candidate a
structured `polarity` of `PRESENT` / `ABSENT` / `UNKNOWN`, derived from the
claim's own `count`, its own text and its enclosing `source_context` — no
per-room phrase list.

`architectural_vision_grounding_v1._scope_conflicts` publishes the disagreement
in `grounding["conflicts"]` at two levels:

* **SCOPE** — a provider claim that negates the DOCUMENT SCOPE ("… not an
  architectural interior") against any local interior space;
* **KIND** — a provider ABSENT claim about a kind the local evidence asserts as
  PRESENT.

Neither level decides which source is correct. **No verification verdict
changed**: the machine-readable CONTRADICTED form (`count == 0` AND the literal
`no <kind>` AND eligible local evidence) is preserved exactly, and a prose
absence stays `UNVERIFIED` in the verifier while the conflict is surfaced by
grounding instead.

## 5. Observer runtime defaults are the measured ones

Measured live on the largest sheet (17.4 MP, 4096-pixel bounded input,
32768 ctx): observer completion **395.203 s**, and the 2048-token cap truncated
it (`done_reason=length`, `eval_count=2048`).

| Setting | Before | After |
| --- | --- | --- |
| `ARCHITECTOS_VISION_OBSERVER_TOKENS` | 2048 | **4096** — the same image now finishes naturally (`stop`, `eval_count=2656`) |
| observer wait | `ARCHITECTOS_VISION_TIMEOUT` = 300 | **`ARCHITECTOS_VISION_OBSERVER_TIMEOUT` = 600** (~1.5x headroom over the measured 395.203 s) |

`ARCHITECTOS_VISION_TIMEOUT` is retained and still drives the observer when it
is set, so an existing deployment override keeps its exact meaning.
`cfg.timeout` keeps its 300 default. 900 s is deliberately NOT the production
default — it was only the diagnostic value. Normalizer semantics are untouched.

## 6. Regression

* Bridge / retention / grounding / separation / interpreter / report /
  local-plan / multi-plan / furnished / plan-elements / completeness /
  evidence-integrity / cache / architectural-observation / function-evidence:
  **448 passed, 51 skipped, 1 failed**, and that single failure
  (`test_old_hardcoded_false_cache_is_stale`) **fails identically at the
  starting commit** — verified by stashing every tracked edit and re-running it.
* Standalone acceptance runners: grounding **17/21**, observation separation
  **23/28**, report language **16/16**, general observation completeness
  **15/15** — all identical to the recorded baseline.
* New: `tests/test_vision_end_to_end_retention_v1.py`, **34 passed**, covering
  the image-type rule, the drawing-type classifier, the OCR trust rule, the
  provider-observation report, polarity and conflicts, and the runtime defaults.
* Two test expectations were updated because they encoded the DEFECT being
  fixed, not a regression: `test_local_plan_reader_v1` asserted that a
  lexicon-substituted label is printed as a grounded plan space, and the
  completeness `RICH` fixture used a lexicon-substituted label as its `text`
  category member.

## 7. Known weaknesses (unchanged, deferred)

* `LOCAL_READER_QUALITY_V1` — the local reader still produces false raster
  evidence on non-plan images (on the facade render: nine uncertain enclosed
  regions). Those remain visible in the observation turn under local
  provenance; they no longer reach the default answer.
* The normalizer drops explicit prose absences (e.g. "no internal stairs are
  visible"), so a per-kind conflict can only exist when an absence survives as
  a claim. The scope-level conflict does not depend on that.
