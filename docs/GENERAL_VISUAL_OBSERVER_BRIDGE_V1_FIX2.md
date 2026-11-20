# General Visual Observer Bridge V1 — targeted Fix2

Fix2 starts exactly at `911afea2fe5d714fd5914bbe39412c381ee8f29d`, whose sole
parent is `209e44dc6e8484031fc8db035e1871a969234108`. Only the Fix1 branch was
fetched, without tags. The isolated Fix2 branch is
`w4-2a-general-visual-observer-bridge-v1-fix2`; no main/work import, merge or
rebase was performed.

## B-5: independent timeout

The supplied measurement classifies B-5 as
`NORMALIZER_LATENCY_EXCEEDS_CLIENT_TIMEOUT`: a normalizer request exceeded
300 seconds and completed at 305.8 seconds with a longer client timeout.
`ARCHITECTOS_VISION_NORMALIZER_TIMEOUT` now configures the text request alone,
with a finite positive-integer default of 420 seconds. The existing observer
setting `ARCHITECTOS_VISION_TIMEOUT` remains 300 seconds by default, independent
of the new setting and of constructor observer-timeout overrides. No retries or
automatic repeated inference were added. Context/output defaults remain
32768/8192, with normalizer thinking disabled. Both timeout fields participate
in provider identity and raw/persisted cache invalidation. Normalizer/schema
versions advance to v1.2 for changed normalization behavior and guidance.

## B-6: exact raw attribution with isolated losses

Previously, one quote differing in capitalization or hyphen representation
raised an exception for the entire schema-valid response. Fix2 validates the
complete closed schema first, then resolves each claim independently:

1. Accept an exact substring first.
2. Otherwise casefold Unicode characters and map only ASCII hyphen, U+2010
   HYPHEN and U+2011 NON-BREAKING HYPHEN to ASCII hyphen.
3. Search all canonical occurrences, including overlaps, while preserving
   original character boundaries. A match cannot split a casefold expansion.
4. Accept only a unique canonical span and restore the exact raw substring.
   Zero matches are unsupported; multiple canonical spans are ambiguous.
5. Resolve claim text within that exact quote by the same rules, then revalidate
   the resolved claim bounds. Expansion beyond schema bounds rejects only that
   claim, preventing a later trust-boundary schema failure.

No semantic matching, embeddings, second model, whitespace cleanup, arbitrary
word/number correction, or mathematical-minus conversion is used. Exact quotes
remain exact-first even when repeated; the existing verifier examines enclosing
lines of every exact occurrence. Final accepted `text` is an exact substring of
`source_quote`, itself an exact substring of retained observer text.

The normalization record exposes `accepted_claim_count`, `rejected_claim_count`,
`source_resolution_failures` (original claim, index, category, field and reason),
and `source_resolutions` (original and restored strings and resolution methods).
Rejected claims do not enter `structured` or provider candidates. Structural
invalidity still fails the document. Candidate-boundary revalidation reports
its own losses under `candidate_source_validation`, preserving upstream losses.
Original normalizer output/metadata and raw observer text remain intact.

## B-7: certainty is distinct from verification

Prompt and schema guidance now define ASSERTED as positive visual presence or a
reading; AMBIGUOUS as explicit hedging or multiple plausible readings; UNKNOWN
as explicit inability to determine/read the fact. UNKNOWN must not mean merely
not independently verified. Prompt examples cover the six requested phrases
and a readable scale. No runtime heuristic upgrades UNKNOWN or hedged claims.
All accepted claims still begin `PROVIDER_CANDIDATE`, `grounded=false`.
Only independent local corroboration can confirm an eligible claim.

The six phrase tests are deterministic prompt/schema and controlled-transport
contract tests. They do not prove that a live model will emit the intended enum.
Live model certainty distribution, latency and image acceptance require future
runtime validation; none is claimed here.

## Validation against the exact baseline

| Suite | Exact Fix1 baseline | Fix2 |
| --- | --- | --- |
| Bridge pytest | 66 passed | 104 passed |
| Analysis cache pytest | 1 passed, 3 skipped | Same |
| Evidence integrity pytest | 37 passed | Same |
| Architectural interpreter pytest | 10 passed | Same |
| General observation completeness standalone | 15/15 | Same |
| Grounding standalone | 17/21 | Same |
| Observation separation standalone | 23/28 | Same |
| Report language standalone | 16/16 | Same |
| Registry isolated pytest | 14 passed, 3 failed | Same |

The four primary pytest files total **152 passed, 3 skipped** (baseline
114 passed, 3 skipped). Cache skips require an unavailable private image.
Known grounding failures remain G1/G3/G5/G21; separation failures remain
T2a/R4/R5/R6/T6. No unrelated baseline failure was repaired.

Registry standalone reaches its existing missing Windows render-fixture failure
at E. Isolated registry pytest reaches all 17 cases; E/K/L fail on that same
missing fixture in both checkouts. Live A/B/C/D return early with provider-
unavailable warnings; pytest labels those returns passed, which is not live
acceptance. No acceptance image or registry fixture was replaced.

Added coverage includes timeout defaults/overrides/independence, finite positive
configuration, raw and persisted cache changes, no retry after ReadTimeout,
exact/case/hyphen/Unicode source resolution, expansion boundaries, ambiguity,
no-match/numeric/whitespace/minus rejection, exact restoration of both quote and
text, per-claim diagnostics, all category shapes, 64 surviving generic claims
beside one rejected claim, oversized restored claims, certainty guidance and
candidate lifecycle. Existing strict-schema, raw-retention, text-only transport,
independent verification and verified-only legacy-field tests still pass.

## Preserved boundaries

The image → observer → raw retention → text-only normalizer → provider candidate
→ local verification → grounded observation → interpretation sequence remains.
Legacy `understanding["observed"]` is verified-only. Raw text and provider
candidates remain the provider-attributable surfaces. No BIM, IFC, Render,
ComfyUI, local reader/symbol/element implementation or detector threshold changed.
No acceptance-image-specific names, hashes, phone numbers, counts or coordinates
were added. Local B-2 OCR and kitchen counter/sink detector issues remain deferred.
No merge was performed. Final commit and push status are supplied in the delivery
report rather than claimed in advance here.
