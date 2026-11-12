<div align="center">
  <a href="https://github.com/SmartPDFCompare/SmartPDFCompare">
    <img src="https://raw.githubusercontent.com/SmartPDFCompare/SmartPDFCompare/main/docs/assets/cover.svg" alt="SmartPDFCompare" width="760">
  </a>
  <br>
  <a href="https://github.com/SmartPDFCompare/SmartPDFCompare">
    <img src="https://readme-typing-svg.demolab.com?font=Inter&weight=700&size=25&duration=3200&pause=900&color=2563EB&center=true&vCenter=true&width=650&lines=Find+the+words+that+changed+in+your+PDFs;Compare.+Highlight.+Review." alt="Animated SmartPDFCompare introduction">
  </a>
  <br><br>
  <a href="https://github.com/SmartPDFCompare/SmartPDFCompare/actions/workflows/tests.yml"><img src="https://github.com/SmartPDFCompare/SmartPDFCompare/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="https://pypi.org/project/smart-pdf-compare/"><img src="https://img.shields.io/pypi/v/smart-pdf-compare.svg?color=2563eb" alt="PyPI"></a>
  <a href="https://pypi.org/project/smart-pdf-compare/"><img src="https://img.shields.io/pypi/pyversions/smart-pdf-compare.svg" alt="Supported Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2563eb.svg" alt="MIT license"></a>
  <a href="https://pymupdf.readthedocs.io/en/latest/"><img src="https://img.shields.io/badge/powered%20by-PyMuPDF%202-16a34a.svg" alt="Powered by PyMuPDF 2"></a>
</div>

<p align="center">
  <a href="#quick-start"><strong>Quick start</strong></a> ·
  <a href="#features"><strong>Features</strong></a> ·
  <a href="#ignoring-header--footer-dates-and-page-numbers"><strong>Header/Footer Ignore</strong></a> ·
  <a href="#command-line"><strong>CLI</strong></a> ·
  <a href="docs/api.md"><strong>API</strong></a> ·
  <a href="docs/architecture.md"><strong>Architecture</strong></a> ·
  <a href="#limitations"><strong>Limitations</strong></a>
</p>

**SmartPDFCompare** is a lightweight Python library for comparing the extractable text in two PDF versions. It gives applications structured word and page changes, then uses the **same coordinates** to write readable highlighted PDFs and an optional side-by-side review report.

> [!IMPORTANT]
> SmartPDFCompare uses the current [PyMuPDF 2](https://pymupdf.readthedocs.io/en/latest/) API exclusively: `import pymupdf`.

## Features

- **[Structured comparison](docs/api.md)** — added, removed, replaced, added-page, removed-page, and moved-page records with JSON serialization.
- **[Header and footer filtering](#ignoring-header--footer-dates-and-page-numbers)** — opt-in filtering of print timestamps, generation dates, and page numbers inside page margin zones.
- **[Unicode-aware text extraction](https://pymupdf.readthedocs.io/en/latest/textpage.html)** — PyMuPDF word coordinates, NFKC normalization, case folding, ligatures, NBSPs, and dash/minus variants.
- **[Practical page alignment](docs/architecture.md)** — content matching for inserted/moved pages, bounded sequential look-ahead, and index-by-index comparison.
- **[Visual review](#highlighted-output)** — native PDF highlights or boxes in safe output copies; optional side-by-side report pages.
- **[Small CLI](#command-line)** — terminal summary, JSON result, highlighted output, report, alignment policy, and style controls.

## Install

```bash
python -m pip install --upgrade smart-pdf-compare
```

The package tracks the current major [PyMuPDF](https://pypi.org/project/PyMuPDF/) release. Create a virtual environment first for a predictable setup:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade smart-pdf-compare
```

## Quick start

```python
from smart_pdf_compare import compare_pdfs, highlight_differences

result = compare_pdfs("original.pdf", "revised.pdf")

print(result.is_identical)
print(result.summary)
for change in result.differences:
    print(f"{change.change_type}: {change.old_text!r} -> {change.new_text!r}")

outputs = highlight_differences(
    "original.pdf",
    "revised.pdf",
    output_dir="diff-output",
    result=result,
    include_report=True,
)
print(outputs)
```

### Work with JSON

```python
import json

with open("comparison.json", "w", encoding="utf-8") as file:
    json.dump(result.to_dict(), file, indent=2)
```

`result.truncated` is `True` when `max_differences` limits returned detail entries. Aggregate counts in `result.summary` always cover the full comparison.

## Highlighted output

<table>
  <tr>
    <td width="50%"><strong>Original</strong><br>Removed or replaced text receives red markup.</td>
    <td width="50%"><strong>Revised</strong><br>Added or replaced text receives green markup.</td>
  </tr>
  <tr>
    <td><code>original_highlighted.pdf</code></td>
    <td><code>revised_highlighted.pdf</code></td>
  </tr>
</table>

Use real PDF annotations by default, or boxes where highlights are not desired:

```python
from smart_pdf_compare import highlight_differences

highlight_differences(
    "original.pdf", "revised.pdf", "diff-output",
    style="box",          # "highlight" is the default
    include_report=True,   # creates difference_report.pdf
)
```

Source PDFs are never overwritten. The side-by-side report contains only pages with differences, displays page labels, and leaves a clearly labeled blank side for an inserted or removed page.

## Alignment choices

```python
from smart_pdf_compare import ComparisonOptions, compare_pdfs

result = compare_pdfs(
    "original.pdf", "revised.pdf",
    options=ComparisonOptions(
        alignment="content",       # default
        similarity_threshold=0.60,
        lookahead=5,
        max_differences=1_000,
    ),
)
```

| Strategy | Best for | Trade-off |
| --- | --- | --- |
| `content` | Documents with inserted, deleted, or moved pages | Greedy matching; not globally optimal for highly repetitive pages. |
| `sequential` | Mostly ordered revisions | Resynchronizes only inside `lookahead`. |
| `index` | Stable page-for-page documents | An insertion can make later pages appear modified. |

Normalization is deliberately conservative: it uses NFKC, case folding, ligature compatibility, non-breaking-space cleanup, and dash/minus unification. Punctuation remains significant by default, so decimal values, negative numbers, negation, and contractions do not silently disappear.

## Ignoring Header & Footer Dates and Page Numbers

Many documents regenerate timestamps, print dates, or page numbers in their headers or footers on every export, producing false differences between revisions whose actual content has not changed.

For example, comparing footers like:
- Original: `06/27/2025 06:08PM | Page 2`
- Revised: `10/15/2025 06:22PM | Page 2`

Without filtering, `06/27/2025` vs `10/15/2025` and `06:08PM` vs `06:22PM` are reported as text differences. With `ignore_header_footer_dates=True`, these timestamps are ignored, leaving only `| Page 2`. If the rest of the page is equal, the documents compare as identical.

```python
from smart_pdf_compare import ComparisonOptions, compare_pdfs

options = ComparisonOptions(
    ignore_header_footer_dates=True,          # Ignore dates & times in header/footer zones
    ignore_header_footer_page_numbers=True,    # Ignore "Page 2", "2 of 10", "- 2 -"
    header_height=0.08,                        # Top 8% of page (or points if > 1.0)
    footer_height=0.08,                        # Bottom 8% of page (or points if > 1.0)
    ignore_patterns=(r"CONFIDENTIAL",),        # Extra regex patterns applied inside zones
)

result = compare_pdfs("original.pdf", "revised.pdf", options=options)
print(result.is_identical)
print(f"Ignored words: {result.words_ignored}")
```

### Key properties

- **Zone-restricted**: Only words located within the top `header_height` or bottom `footer_height` of the visible page (respecting page rotation) are eligible for filtering. Dates and numbers in the **body text are never ignored**.
- **Transparent**: The number of ignored tokens is tracked in `result.words_ignored` (and `result.summary.words_ignored`), ensuring ignoring is never silent.
- **Consistent downstream**: Ignored words behave like empty tokens: excluded from word diffs, diff counts, page alignment similarity sets, and highlight annotations.
- **Rotation-aware**: Works on rotated pages (90°, 180°, 270°) by evaluating word positions in viewer coordinates via `page.rotation_matrix`.

### Limits & Scope

1. **Zone height heuristic**: Defaults to `0.08` (8% of visible page height). Values `> 1.0` are treated as absolute points (e.g. `header_height=54.0`). If a header or footer extends deeper than the zone limit, adjust `header_height` or `footer_height`.
2. **Date & time formats covered**:
   - Numeric dates: `MM/DD/YYYY`, `M-D-YY`, `DD.MM.YYYY`, `YYYY-MM-DD` (e.g. `06/27/2025`, `6-27-25`, `27.06.2025`, `2025-06-27`).
   - Times: 12-hour or 24-hour formats (e.g. `06:08PM`, `06:08 PM`, `18:08:30`, `6:08 a.m.`).
   - Month-name dates: English month names only, full or abbreviated (e.g. `Jun 27, 2025`, `27 June 2025`, `June 27, 2025`, `June 2025`). Other languages can be matched via `ignore_patterns`.
3. **Page numbers covered**: Forms matching `"Page X"`, `"Page X of Y"`, `"X of Y"`, `"X / Y"`, and hyphenated forms like `"- X -"` or `"– X –"`.

## Command line

```bash
smart-pdf-compare original.pdf revised.pdf \
  --alignment content \
  --ignore-header-footer-dates \
  --ignore-header-footer-page-numbers \
  --header-height 0.08 \
  --footer-height 0.08 \
  --ignore-pattern "DRAFT" \
  --output-dir diff-output \
  --style highlight \
  --report \
  --json diff-output/comparison.json
```

| Exit code | Meaning |
| --- | --- |
| `0` | Textually identical under the chosen policy. |
| `1` | Differences were found. |
| `2` | Input, extraction, or configuration error. |
| `3` | Comparison unreliable: one or both documents lack extractable text layer. |

## Visual comparison

Text diffs and visual diffs answer different questions. The text API compares extracted words; the visual API renders pages through PyMuPDF and detects changes to layout, graphics, lines, and images as pixels. It requires no OpenCV, NumPy, or Pillow dependency.

```python
from smart_pdf_compare import VisualComparisonOptions, compare_visual_pdfs

result = compare_visual_pdfs(
    "original.pdf",
    "revised.pdf",
    options=VisualComparisonOptions(dpi=144, pixel_threshold=8, output_mode="diff_image"),
    output_dir="visual-output",
)
print(result.pages[0].difference_ratio)
```

Choose `output_mode="side_by_side"` for paired rendered images or `"none"` for metrics only. Visual pages are intentionally paired by index; page-count differences become explicit unmatched-page records. For several PDFs, `compare_visual_documents(paths, reference=0, ...)` compares each non-reference input against the designated reference.

```bash
smart-pdf-compare original.pdf revised.pdf --visual-only \
  --visual-mode diff_image --visual-output-dir visual-output --json visual-output/result.json
```

## Optional desktop viewer

On a desktop Python installation with Tk support, launch a two-pane viewer that reuses the same comparison results, change navigation, and save-highlighting workflow:

```bash
smart-pdf-compare-viewer original.pdf revised.pdf
```

The viewer is separate from core imports and creates no window until invoked. It intentionally focuses on PDF comparison; clipboard and Microsoft Word conversion were excluded because they are platform-dependent utilities outside the core library.

## Limitations

SmartPDFCompare compares the PDF **text layer**, not rendered pixels. It does not perform OCR, visual-diff analysis, or image comparison.

If either document has no extractable text, the comparison returns a `ComparisonResult` with `reliable=False` and a warning naming the document(s). The CLI exits with code 3 to signal an unreliable comparison (exit code 3) so no information is lost and the user is explicitly warned that OCR and visual comparison are not supported.

Complex tables and multi-column PDFs can expose an unreliable reading order from the source PDF. The `sort_words` option (default `False` in `ComparisonOptions`) preserves native block/line reading order; set to `True` if column-interleaved order is preferred, at the cost of confusing context lines in hunks.

PyMuPDF is available under [AGPL or commercial terms](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright). Confirm that its license is appropriate for your use case.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m build
python -m twine check dist/*
```

Read the [contribution guide](CONTRIBUTING.md), [public API](docs/api.md), [architecture notes](docs/architecture.md), and [changelog](CHANGELOG.md). Before publishing, verify availability of `smart-pdf-compare` on [PyPI](https://pypi.org/), upload to TestPyPI, install the artifact in a clean environment, and use [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) for the production release.

## License

SmartPDFCompare's own source code is licensed under the [MIT License](LICENSE). Its PyMuPDF dependency has separate licensing, described above.

---

<div align="center"><sub>Built for clear, reviewable PDF changes.</sub></div>
