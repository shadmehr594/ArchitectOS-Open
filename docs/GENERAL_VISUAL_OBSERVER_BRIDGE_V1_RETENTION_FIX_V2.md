# VISION END-TO-END RETENTION FIX V2

Starting branch `w4-2a-vision-end-to-end-retention-fix-v1`, starting commit
`dcbb761037eb505e97c9a1841f3e7beb237d974f` (parent `837c5708…`).
Branch `w4-2a-vision-end-to-end-retention-fix-v2`. Not merged.

This change addresses exactly the three findings of the V1 post-audit:

* **BLOCKER 1** — Fix V1 disabled the first-class `plan_reading` contract for
  genuine SINGLE floor plans.
* **BLOCKER 2** — the conflict path read raw `label["semantic_function"]`
  without the OCR trust gate, so a low-trust guess created a trusted
  LOCAL PRESENT (and with it a conflict).
* **TRUST ISSUE 3** — `independent_passes >= 2` was consumed as *independent
  verification*, although every pass shares one engine, one traineddata and one
  source image.

## A. Genuine single-plan recovery — an evidence gate, not a shortcut

`core/vision/image_understanding_v1.py` — `_image_type_evidence` replaces
`_independent_image_type`, and `_build_bridge_understanding` records the result
as `understanding["image_type_evidence"]`.

The canonical type is `floor_plan_or_sketch` **only** when there is POSITIVE,
non-default local plan-structure evidence
(`core/vision/local_evidence_trust_v1.local_plan_structure_evidence`):

| family | signal | why it is positive, not a default |
| --- | --- | --- |
| `PLAN_ELEMENT_TOPOLOGY` | `grounded_plan_elements` of type door / window / opening / stair / duct / shaft / column / axis whose own detector requirement is satisfied (`_local_requirement_met`) | a localized plan symbol with a raster footprint. `level` is EXCLUDED — an elevation marker also appears on facades |
| `PLAN_FURNITURE_SYMBOL_TOPOLOGY` | `grounded_plan_items` (bed / sofa / kitchen counter / sink / sanitary / storage / dining) | requires a localized raster patch plus corroboration; a plan-specific symbol library hit |
| `MULTI_PANEL_STRUCTURE` | `sheet_type` in `multi_plan` / `plan_pair` | a POSITIVE panel detection; the reader's default is `single_plan` |

Deliberately **not** used: `local.status` (true for any evidence), the default
`single_plan` value, raw OCR words, lexicon-substituted labels, and
`enclosure_geometry.regions` — a facade render produced **nine** of them, so
regions are not a plan signal.

Measured discrimination on the real corpus (retained local readings):

| image | furniture symbols | requirement-met plan elements | multi-panel | gate |
| --- | --- | --- | --- | --- |
| 212 (furnished plan) | 6 | 9 (window 5, door 4) | no | **positive** |
| 4bd (unfurnished plan) | 0 | 7 (window 4, door 3) | no | **positive** |
| NEW-L1 (cadastral) | 0 | 0 | no | negative |
| NEW-L2 (facade render) | 0 | 0 (9 raw `level`, all unmet) | no | negative |
| PARCEL2 (rejection/access schematic) | 0 | 0 | no | negative |

### Why this does not make the provider authoritative

The provider's drawing type is a separate `MODEL_OBSERVED` observation
(`provider_drawing_type`), and `provider_is_authoritative` is `False` in the
provenance record. Provider agreement only changes the BASIS label
(`CORROBORATED` vs `LOCAL_STRUCTURAL`); it is never required, so ArchitectOS
still reaches a plan reading when provider semantics are unavailable. A
provider plan observation with no local structure stays `PROVIDER_OBSERVED` and
the canonical type remains `unknown`.

### Image-type provenance contract

```json
"image_type_evidence": {
  "canonical_image_type": "floor_plan_or_sketch | unknown",
  "basis": "LOCAL_STRUCTURAL | CORROBORATED | PROVIDER_OBSERVED | UNKNOWN",
  "local_positive": true, "local_families": ["..."], "local_signals": {...},
  "provider_drawing_type": {...}, "provider_canonical": "...",
  "provider_agrees": true, "provider_is_authoritative": false, "rule": "..."
}
```

## B. Trust-gated conflict path

`core/vision/architectural_vision_grounding_v1.py`:

* `_trusted_local_labels(local, independent_texts)` — only labels whose
  `ocr_trust_state` is `INDEPENDENTLY_VERIFIED_OCR`.
* `_trusted_local_elements(local)` — only `status == "visible"` elements that
  satisfy `_local_requirement_met`.
* `_local_present_kinds(local, independent_texts)` now consumes only those.
* `_scope_conflicts` derives `independent_texts` via
  `independently_verified_ocr_texts(raw)` and uses the trusted helpers for both
  the SCOPE and the KIND level.

A low-trust OCR token can therefore no longer create a LOCAL PRESENT kind, and
with it no scope or kind conflict. It remains an auditable OCR candidate. The
existing machine-readable CONTRADICTED semantics are untouched.

## C. OCR trust-state semantics

`core/vision/local_evidence_trust_v1.py` — three fail-closed tiers:

| tier | meaning | may name a space? |
| --- | --- | --- |
| `LOW_TRUST_OCR` | a lexicon SUBSTITUTION (`correction` set), insufficient stability, or malformed evidence | never |
| `STABLE_LOCAL_OCR` | no substitution and `>= 2` passes agree — several preprocessing configurations of ONE engine over ONE image | no: reportable AS OCR only |
| `INDEPENDENTLY_VERIFIED_OCR` | corroborated by a genuinely independent path | yes |

**The legacy `independent_passes` field is retained for compatibility but is
re-read as LOCAL OCR STABILITY** (`stability_passes()`), and new records carry
both `independent_passes` (legacy) and `stability_passes` with the stability
meaning. It is no longer used anywhere as proof of independent verification.

**The independent corroboration source** is the EXISTING verification contract
in `provider_candidate_verification_v1`: a provider OCR claim
(`provider_ocr_candidate` / `ocr_exact` / `ocr_partial` / `scale` /
`dimensions` / `level_codes`) whose text exactly matches a local label and which
the verifier CONFIRMED as `verbatim_independent_local_ocr`. Provider confidence
alone never qualifies, and same-engine pass counts never qualify. No fuzzy match
was invented.

Applied at every consumer: `architectural_observation_v1` (trusted →
`text_labels_if_visible`; `stable_local_ocr_labels`; `low_trust_ocr_labels`;
`independently_verified_ocr_texts`), `architectural_vision_interpreter_v1._read_labels`
(three tiers; `semantic_function`/`zone` only for the independently verified),
and `vision_observation_mode_v1._grounded_categories` + `render_observation`
(new `stable_local_ocr` category rendered as *"stable (N passes, same engine) —
NOT independently verified"*).

## Tests

* New: `tests/test_vision_retention_fix_v2.py` — 19 tests covering all 15
  required cases plus the preserved machine-readable contradiction.
* Updated to the V2 semantics (they encoded the superseded rule, not a
  regression): `test_vision_end_to_end_retention_v1.py`,
  `test_local_plan_reader_v1.py`,
  `test_w4_2a_general_observation_completeness_v1.py`.

## Remaining known weaknesses

* `LOCAL_READER_QUALITY_V1` remains open: on the facade render the local reader
  still produces nine uncertain enclosed regions, which stay visible in the
  observation turn's `geometry` category under local provenance.
* The `plan_reading` gate needs at least one requirement-met plan element or
  furniture symbol; a genuine plan whose symbols all fail their own detector
  requirement would stay `unknown` (fail-closed by design).
* The provider-observation summary remains capped, so a very dense sheet can
  still lose low-priority text lines from the concise answer.
