# Regulatory authority policy

ArchitectOS resolves regulatory values only from documents the operator supplies. **No municipal, national, or copyrighted regulatory document is bundled with this repository.**

## Required sources

For every architecture or planning task, consult both authority families before resolving a regulatory value:

1. **National building regulations** — the applicable official edition, cited to a verifiable clause and page.
2. **Local municipal plan / zoning document** — supplied by the operator under `core/architecture/authorities/local/`.

## Supplying local documents

Place the PDF, and optionally a sidecar `<name>.meta.json`, in:

```
core/architecture/authorities/local/
```

Recommended sidecar fields:

| Field | Meaning |
|---|---|
| `jurisdiction` | City / district the document governs |
| `issuing_authority` | Body that issued it |
| `document_title` | Official title, in its original language |
| `edition` | Edition or date |
| `approval_status` | `approved` / `draft` / `unresolved` |
| `source` | How the operator obtained it |
| `sha256` | File hash, for provenance |

`core/architecture/authorities/local/` is git-ignored except for its `README.md` and `.gitkeep`. **Do not commit copyrighted regulatory documents.**

## Evidence rules

Record jurisdiction, issuing authority, document title, edition/date, clause/article, printed page, PDF page, applicability, and provenance in machine-readable evidence.

- Never infer parcel zoning, commercial subtype, floor scope, occupiable area, population, or conversion factors from a document title alone.
- A local rule applies only after the parcel's zoning/map condition and the rule's stated conditions are verified.
- Do not silently reconcile conflicts between national and local sources. Report them as unresolved.
- Secondary sources may locate documents but may not be authority.
- When a required document is absent, the correct behaviour is to report the value as **unresolved** — not to guess.
