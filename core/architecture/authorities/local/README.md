# Local regulatory documents

Place operator-supplied municipal / zoning documents here.

- Supported: PDF (primary), plus an optional `<name>.meta.json` sidecar.
- This directory is **git-ignored** except for this README and `.gitkeep`.
- Nothing in this repository bundles a copyrighted municipal or national regulation.

The application and tests treat these documents as **optional inputs**. When a document is absent, regulatory values must be reported as unresolved rather than inferred.

Example layout:

```
core/architecture/authorities/local/
├── README.md
├── .gitkeep
├── <your-city>_zoning_<year>.pdf
└── <your-city>_zoning_<year>.meta.json
```

Example sidecar:

```json
{
  "jurisdiction": "<city / district>",
  "issuing_authority": "<authority name>",
  "document_title": "<official title>",
  "edition": "<edition or date>",
  "approval_status": "unresolved",
  "source": "operator-supplied",
  "sha256": "<sha256 of the PDF>"
}
```
