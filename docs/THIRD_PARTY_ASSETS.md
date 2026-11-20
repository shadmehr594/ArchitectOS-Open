# Third-party assets excluded from the Git repository

This repository intentionally excludes downloaded, generated, or user-supplied
assets whose redistribution provenance is not established by an adjacent
licence record.

## OCR language data

Excluded paths:

- `models/ocr/tessdata_best/*.traineddata`
- `models/ocr/tessdata_fast/*.traineddata`

The filenames are compatible with Tesseract `tessdata_best` and
`tessdata_fast`, but this local checkout contains no adjacent source record or
licence file proving the provenance of these exact copies. Obtain language data
from an approved Tesseract distribution, verify its licence and integrity, and
place it in the paths above for local OCR use. Do not commit the downloaded
files without recording their source, version, hashes, and redistribution
terms.

## 3D-FUTURE derived registry

Excluded path:

- `models/3d_future/asset_registry.json`

This is a generated registry derived from a locally available 3D-FUTURE
dataset. The dataset and registry redistribution terms are not established in
this checkout. Rebuild the registry locally with
`scripts/build_3d_future_registry.py` from a lawfully obtained dataset and keep
the generated registry outside Git unless redistribution permission is
documented.

## Regulatory PDFs

Excluded paths:

- `core/architecture/authorities/minab/*.pdf`
- `core/architecture/authorities/national/*.pdf`

These are user-supplied reference documents. Their source code integrations
and non-binary metadata may remain in Git, but the PDFs themselves are excluded
until redistribution permission is verified. Restore approved local copies at
the expected paths when performing regulatory work.

## Compiled Revit/.NET outputs

Excluded paths:

- `tools/reference_analysis/RevitReferenceExtractor/bin/`
- `tools/reference_analysis/RevitReferenceExtractor/obj/`

These folders contain build products and bundled dependency binaries. Build
them locally from the retained project source and dependency manifest.
