# Changelog

## 0.2.0 - 2026-10-28

Add rendered-page visual comparison with PNG artifact generation, reference-based multi-PDF comparison, visual CLI controls, adjacent-word annotation grouping, typographic-quote normalization, and an optional lazy-Tk desktop viewer entry point.

## 0.2.1 - 2026-11-04

### Added

- Weighted Longest Increasing Subsequence (LIS) page-move detection with Fenwick tree, weight = similarity**4, diagonal tie-break
- `--overwrite` flag for `highlight_differences` and CLI to prevent accidental file overwrite
- `reliable` flag and warnings in `ComparisonResult` when documents lack extractable text
- `sort_words` option in `ComparisonOptions` (default `False`, preserves native block/line reading order)
- CLI exit code 3 for unreliable comparison (no text layer)
- New exceptions: `EncryptedPDFError`, `OutputExistsError`, `InputOverwriteError`
- Visual fast-path row-level comparison in `_difference_image` for performance improvement
- New normalization rules: preserve decimal points and signs inside numbers, remove soft hyphen/zero-width characters
- Visual comparison row-level byte-slice optimization for unchanged rows

### Changed

- Alignment candidate generation uses Jaccard similarity of word sets instead of SequenceMatcher during pairing
- Large documents use inverted index over rare words + small window, capped at 25 candidates per page
- `_content()` no longer performs positional zip-pairing fallback; unmatched pages are left unpaired
- `open_pdf()` now rejects non-PDF files with `filetype="pdf"` and raises `EncryptedPDFError` for encrypted documents
- `extract_document()` default `sort_words=False` (native block/line order); `sort_words=True` available for column-interleaved order
- `ComparisonResult.to_dict()` now includes `reliable` field
- CLI: errors output to `stderr`; JSON `--json -` writes only JSON to stdout
- `highlight_differences()` and `create_side_by_side_report()` use safe temp-file writes with `os.replace()` and cleanup on exception
- Rotated page report rendering now draws source pages through a scratch document with rotation reset to 0
- Annotation rectangles on report pages mapped through source page's rotation matrix
- `NormalizationOptions.ignore_punctuation` now preserves decimal points, signs, and apostrophes inside words
- Default Python version in CI matrix updated from 3.9 to 3.10, 3.11, 3.12 (matching `pyproject.toml`)

### Fixed

- False "moved"/"replaced" pages: positional zip-pairing fallback removed; LIS chain correctly identifies actual moves
- Rotated pages in report: content no longer clipped; annotations overlap changed words by >90%
- Annotations on rotated source copies: clips against unrotated bounds instead of rotated rect
- CLI: exit code 3 for unreliable comparison; errors to stderr; `--overwrite` flag added
- Normalization: `1.2` != `12` even with `ignore_punctuation=True`; contraction `isn't` preserved; dash/minus variants mapped to `-`
- Visual comparison: fast path for identical rasters; row-level byte-slice comparison
- Safe output handling: temp file + `os.replace()`; refuse to overwrite input files; dedicated "output exists" exception

### Fixed (pre-existing)

- Fixed edge cases in `_PUNCTUATION_EDGE` regex for ignore_punctuation
- Fixed zero-width and soft hyphen removal in token normalization
- Fixed curly quote/apostrophe mapping to ASCII
- Fixed dash/minus variant mapping (U+2010-U+2015, U+2212, U+FE58, U+FE63, U+FF0D)

## 0.1.1 - 2026-10-28

Fix side-by-side report annotations so the selected `highlight` or `box` style is applied consistently to highlighted copies and the merged difference report. Add regression coverage for annotation types, unpaired pages, rotated pages, and different page sizes.

## 0.1.0 - 2026-10-28

Initial public release: text extraction through the current PyMuPDF API (`import pymupdf`), Unicode-aware word diffs, three page alignment strategies, highlighted copies, a side-by-side report, CLI, packaging, and tests.
