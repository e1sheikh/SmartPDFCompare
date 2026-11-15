# API Documentation

## ComparisonOptions

### Header/Footer Ignoring

Smart-PDF-Compare can optionally ignore dates, times, and page numbers that appear in page header and footer zones.

#### Options

- `ignore_header_footer_dates` (bool, default False): Ignore dates and times in header/footer zones
- `ignore_header_footer_page_numbers` (bool, default False): Ignore page numbers in header/footer zones
- `header_height` (float, default 0.08): Header zone height as fraction (<= 1.0) or points (> 1.0)
- `footer_height` (float, default 0.08): Footer zone height as fraction (<= 1.0) or points (> 1.0)
- `ignore_patterns` (tuple[str, ...], default ()): Extra regex patterns to ignore in header/footer zones

#### Zone Detection

Words are considered in header/footer zones based on their visible coordinates after rotation:

- Header zone: top `header_height` of visible page
- Footer zone: bottom `footer_height` of visible page
- Coordinates mapped using `page.rotation_matrix`

#### Date/Time Patterns

Supported formats:
- ISO: `2025-06-27`, `2025/06/27`, `2025.06.27`
- Numeric: `06/27/2025`, `6-27-25`, `27.06.2025`, `6/27/25`
- Time: `06:08PM`, `06:08 PM`, `6:08 AM`, `18:08:30`, `18:08`
- Month names: `Jun 27, 2025`, `27 June 2025`, `June 2025`

Month names: English only (Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec)

#### Page Number Patterns

- `Page 2`
- `Page 2 of 10`
- `2 of 10`
- `- 2 -`, `– 2 –`, `— 2 —`

#### Example

```python
from smart_pdf_compare import compare_pdfs, ComparisonOptions

options = ComparisonOptions(
    ignore_header_footer_dates=True,
    ignore_header_footer_page_numbers=True,
    header_height=0.1,
    footer_height=0.1
)

result = compare_pdfs("old.pdf", "new.pdf", options=options)
print(f"Words ignored: {result.summary.words_ignored}")
```

Words ignored are excluded from:
- Word diff counts
- Highlights/annotations
- Side-by-side reports
- Page alignment similarity calculations
