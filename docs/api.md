# API reference

```python
from smart_pdf_compare import compare_pdfs, highlight_differences
```

## `compare_pdfs(old_pdf, new_pdf, options=None)` → `ComparisonResult`

Configure with `ComparisonOptions(...)`.

### `ComparisonOptions` dataclass

| Field | Default | Description |
| --- | --- | --- |
| `alignment` | `"content"` | `"content"`, `"index"`, or `"sequential"` |
| `similarity_threshold` | `0.60` | Float in [0, 1] for page pairing |
| `lookahead` | `5` | Window for sequential resynchronization |
| `max_differences` | `1_000` | Cap on returned difference entries |
| `normalization` | `NormalizationOptions()` | Policy for token normalization |
| `sort_words` | `False` | If `True`, words are sorted by (y, x) within each page (PyMuPDF `sort=True`). If `False`, words are in native block/line order (preserves multi-column reading order). |
| `ignore_header_footer_dates` | `False` | When `True`, dates and times in page header and footer zones are ignored. |
| `ignore_header_footer_page_numbers` | `False` | When `True`, page numbers (`Page 2`, `2 of 10`, `- 2 -`) in header and footer zones are ignored. |
| `header_height` | `0.08` | Height of the top header zone. Values `<= 1.0` are fractions of visible page height (e.g. `0.08` = 8%); values `> 1.0` represent points (e.g. `54.0`). Must be non-negative (`>= 0`). |
| `footer_height` | `0.08` | Height of the bottom footer zone. Values `<= 1.0` are fractions of visible page height (e.g. `0.08` = 8%); values `> 1.0` represent points (e.g. `54.0`). Must be non-negative (`>= 0`). |
| `ignore_patterns` | `()` | Tuple of extra regular expressions applied *only* inside header and footer zones. Validated and compiled at option construction; invalid regex raises `InvalidOptionError`. |

### `ComparisonResult` attributes

| Attribute | Type | Description |
| --- | --- | --- |
| `is_identical` | `bool` | Whether the documents are textually identical |
| `summary` | `ComparisonSummary` | Aggregate counts (added/removed/moved/modified pages, words, and ignored words) |
| `differences` | `list[Difference]` | Structured difference entries (truncated by `max_differences`) |
| `reliable` | `bool` | **True** when both documents have extractable text; **False** if one or both are scanned/image-only. When `reliable` is `False`, `is_identical` is always `False`. |
| `warnings` | `list[str]` | Human-readable warnings (e.g. about missing text layer) |
| `truncated` | `bool` | True when `max_differences` limited the returned entries |
| `words_ignored` | `int` | Total number of tokens ignored in header/footer zones across both documents |
| `_markup` | `list[_PageMarkup]` | Internal coordinate data for rendering |

### `ComparisonSummary` attributes

- `old_pages` (`int`), `new_pages` (`int`)
- `added_pages` (`int`), `removed_pages` (`int`), `moved_pages` (`int`), `modified_pages` (`int`)
- `added_words` (`int`), `removed_words` (`int`), `differences` (`int`)
- `words_ignored` (`int`) — total tokens excluded by header/footer filter rules

### Raised exceptions

- `InvalidPDFError` — file missing, not a PDF, or empty
- `EncryptedPDFError` — PDF requires a password (subclass of `InvalidPDFError`)
- `MissingTextLayerError` — retained for backward compatibility; `compare_pdfs` now returns a result with `reliable=False` instead of raising. See `ComparisonResult.reliable`.
- `ConfigurationError` — unsupported option value
- `InvalidOptionError` — invalid option parameter (e.g. negative zone height or invalid regex in `ignore_patterns`; subclass of `ConfigurationError`)

## `highlight_differences(old_pdf, new_pdf, output_dir, result=None, options=None, style="highlight", include_report=False, overwrite=False)` → `HighlightOutputs`

Writes highlighted copies and optionally a side-by-side report.

- `overwrite` (`bool`) — If `False` (default), raises `OutputExistsError` if any output file already exists. If `True`, existing files are replaced.

### `HighlightOutputs` attributes

| Attribute | Type | Description |
| --- | --- | --- |
| `original` | `Path` | Path to highlighted original PDF |
| `revised` | `Path` | Path to highlighted revised PDF |
| `report` | `Path | None` | Path to difference report, or `None` if documents are identical |

## `create_side_by_side_report(old_pdf, new_pdf, result, output_path, removed_color, added_color, style="highlight", overwrite=False)` → `Path | None`

Creates the difference report PDF. Returns the path, or `None` if no differences.

- `overwrite` (`bool`) — If `False` (default), raises `OutputExistsError` if the output path already exists.

## Visual comparison

```python
from smart_pdf_compare import VisualComparisonOptions, compare_visual_pdfs

result = compare_visual_pdfs(
    "original.pdf",
    "revised.pdf",
    options=VisualComparisonOptions(dpi=144, pixel_threshold=8, output_mode="diff_image"),
    output_dir="visual-output",
)
```

`VisualComparisonOptions` fields: `dpi`, `pixel_threshold`, `min_changed_pixels`, `min_difference_ratio`, `output_mode` (`"none"`, `"side_by_side"`, `"diff_image"`).

```python
from smart_pdf_compare import compare_visual_documents

batch = compare_visual_documents(paths, reference=0, ...)
```

Every non-reference PDF is compared against the designated reference PDF; visual pages are paired by index.

## New exceptions (import from `smart_pdf_compare`)

- `PDFComparisonError` — base class
- `InvalidPDFError` — file missing, not a PDF, empty, or non-PDF file
- `EncryptedPDFError` — PDF is encrypted and requires a password
- `MissingTextLayerError` — no extractable text
- `ConfigurationError` — unsupported option
- `InvalidOptionError` — invalid option value (e.g. negative height or invalid regex)
- `OutputExistsError(FileExistsError, PDFComparisonError)` — output file already exists
- `InputOverwriteError` — refusing to overwrite an input file with output

## Example

```python
from smart_pdf_compare import compare_pdfs, ComparisonOptions

result = compare_pdfs(
    "orig.pdf",
    "revised.pdf",
    options=ComparisonOptions(
        ignore_header_footer_dates=True,
        ignore_header_footer_page_numbers=True,
    ),
)

if not result.reliable:
    print(f"Comparison unreliable: {result.warnings[0]}")
else:
    print(f"Identical: {result.is_identical}, Ignored words: {result.words_ignored}")
```
