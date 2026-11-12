"""Extraction of positioned PDF words using PyMuPDF."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

import pymupdf

from .exceptions import EncryptedPDFError, InvalidPDFError
from .normalization import NormalizationOptions, normalize_token

if TYPE_CHECKING:
    from .api import ComparisonOptions


@dataclass(frozen=True)
class Word:
    text: str
    normalized: str
    rect: tuple[float, float, float, float]
    block: int
    line: int


@dataclass(frozen=True)
class ExtractedPage:
    number: int
    words: tuple[Word, ...]
    words_ignored: int = 0

    @property
    def signature(self) -> str:
        return " ".join(word.normalized for word in self.words if word.normalized)


# English month names (full and 3-letter abbreviations)
_MONTHS = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)

_MONTH_DATE_PATTERN = (
    rf"\b(?:(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{2,4}})?"
    rf"|\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{_MONTHS})\.?(?:,?\s+\d{{2,4}})?"
    rf"|(?:{_MONTHS})\.?,?\s+\d{{4}})\b"
)

_DATE_TIME_RE = re.compile(
    # ISO date: 2025-06-27, 2025/06/27, 2025.06.27
    r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b"
    # Numeric date: 06/27/2025, 6-27-25, 27.06.2025, 6/27/25
    r"|\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b"
    # Time with AM/PM (attached or separate word, e.g. 06:08PM, 06:08 PM, 6:08 AM, 6:08 a.m.)
    r"|\b\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:[AaPp]\.?[Mm]\.?|[AaPp][Mm]))(?!\w)"
    # 24-hour time without AM/PM: 18:08:30, 18:08
    r"|\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\b"
    # Month-name forms: Jun 27, 2025 / 27 June 2025 / June 27 2025 / 27th June 2025 / June 2025
    rf"|{_MONTH_DATE_PATTERN}",
    re.IGNORECASE,
)

_PAGE_NUMBER_RE = re.compile(
    # Page 2, Page 2 of 10, page 2 / 10
    r"\bPage\s+\d+(?:\s*(?:of|/)\s*\d+)?\b"
    # 2 of 10, 2 / 10
    r"|\b\d+\s+(?:of|/)\s+\d+\b"
    # - 2 -, – 2 –, — 2 —
    r"|[-–—]\s*\d+\s*[-–—]",
    re.IGNORECASE,
)


def open_pdf(path: str | Path) -> pymupdf.Document:
    """Open a local PDF, converting PyMuPDF errors to a public exception."""
    candidate = Path(path)
    if not candidate.is_file():
        raise InvalidPDFError(f"PDF file does not exist: {candidate}")
    try:
        # filetype="pdf" rejects non-PDF files (PNG, EPUB, XPS, etc.)
        document = pymupdf.open(candidate, filetype="pdf")
    except pymupdf.FileDataError as exc:
        raise InvalidPDFError(f"Cannot read PDF '{candidate}': {exc}") from exc
    except pymupdf.EmptyFileError as exc:
        raise InvalidPDFError(f"PDF file is empty: {candidate}") from exc
    except (RuntimeError, OSError) as exc:
        raise InvalidPDFError(f"Cannot open PDF '{candidate}': {exc}") from exc

    if document.page_count == 0:
        document.close()
        raise InvalidPDFError(f"PDF has no pages: {candidate}")

    # Check for encrypted PDFs
    if document.needs_pass:
        document.close()
        raise EncryptedPDFError(f"PDF is encrypted and requires a password: {candidate}")

    return document


def _find_ignored_word_indices(
    page: pymupdf.Page,
    raw_words: Sequence[tuple],
    comparison_options: ComparisonOptions,
) -> set[int]:
    """Identify indices in raw_words that match active ignore rules inside header/footer zones."""
    ignore_dates = comparison_options.ignore_header_footer_dates
    ignore_pages = comparison_options.ignore_header_footer_page_numbers
    extra_patterns = comparison_options.ignore_patterns

    if not ignore_dates and not ignore_pages and not extra_patterns:
        return set()

    compiled_extra = [re.compile(p) for p in extra_patterns]

    page_rect = page.rect
    page_h = page_rect.height
    rot_matrix = page.rotation_matrix

    h_val = comparison_options.header_height
    f_val = comparison_options.footer_height

    h_pts = h_val if h_val > 1.0 else (page_h * h_val)
    f_pts = f_val if f_val > 1.0 else (page_h * f_val)

    header_limit = page_rect.y0 + h_pts
    footer_limit = page_rect.y1 - f_pts

    header_words: list[tuple[int, str, pymupdf.Rect]] = []
    footer_words: list[tuple[int, str, pymupdf.Rect]] = []

    for idx, item in enumerate(raw_words):
        text = str(item[4]).strip()
        if not text:
            continue
        vis_r = pymupdf.Rect(item[:4]) * rot_matrix
        vis_mid_y = (vis_r.y0 + vis_r.y1) / 2

        in_header = (h_pts > 0) and (
            vis_r.y1 <= header_limit or vis_mid_y <= header_limit
        ) and vis_r.y0 >= page_rect.y0 - 1.0

        in_footer = (f_pts > 0) and (
            vis_r.y0 >= footer_limit or vis_mid_y >= footer_limit
        ) and vis_r.y1 <= page_rect.y1 + 1.0

        if in_header:
            header_words.append((idx, text, vis_r))
        elif in_footer:
            footer_words.append((idx, text, vis_r))

    ignored_indices: set[int] = set()

    for zone_items in (header_words, footer_words):
        if not zone_items:
            continue

        # Group words in zone by visual line
        zone_items.sort(key=lambda item: ((item[2].y0 + item[2].y1) / 2, item[2].x0))
        lines: list[list[tuple[int, str, pymupdf.Rect]]] = []
        for it in zone_items:
            mid_y = (it[2].y0 + it[2].y1) / 2
            h = it[2].y1 - it[2].y0
            if not lines:
                lines.append([it])
            else:
                last_line = lines[-1]
                last_mid_y = (last_line[0][2].y0 + last_line[0][2].y1) / 2
                last_h = last_line[0][2].y1 - last_line[0][2].y0
                if abs(mid_y - last_mid_y) <= max(h, last_h) * 0.5:
                    last_line.append(it)
                else:
                    lines.append([it])

        for line in lines:
            line.sort(key=lambda it: it[2].x0)
            line_str = " ".join(it[1] for it in line)
            spans: list[tuple[int, int, int, str]] = []
            curr = 0
            for idx, text, _ in line:
                start = curr
                end = curr + len(text)
                spans.append((idx, start, end, text))
                curr = end + 1

            if ignore_dates:
                for m in _DATE_TIME_RE.finditer(line_str):
                    for idx, s, e, _ in spans:
                        if s < m.end() and e > m.start():
                            ignored_indices.add(idx)
                for idx, _, _, text in spans:
                    if _DATE_TIME_RE.search(text):
                        ignored_indices.add(idx)

            if ignore_pages:
                for m in _PAGE_NUMBER_RE.finditer(line_str):
                    for idx, s, e, _ in spans:
                        if s < m.end() and e > m.start():
                            ignored_indices.add(idx)
                for idx, _, _, text in spans:
                    if _PAGE_NUMBER_RE.search(text):
                        ignored_indices.add(idx)

            if compiled_extra:
                for pat in compiled_extra:
                    for m in pat.finditer(line_str):
                        for idx, s, e, _ in spans:
                            if s < m.end() and e > m.start():
                                ignored_indices.add(idx)
                    for idx, _, _, text in spans:
                        if pat.search(text):
                            ignored_indices.add(idx)

    return ignored_indices


def extract_document(
    document: pymupdf.Document,
    options: NormalizationOptions,
    sort_words: bool = False,
    *,
    comparison_options: ComparisonOptions | None = None,
) -> list[ExtractedPage]:
    """Extract reading-order words and their coordinates from every page.

    Args:
        document: Open PyMuPDF document.
        options: Normalization options.
        sort_words: If True, words are sorted by (y, x) within the page
            (PyMuPDF's default 'sort=True'). If False, words are in
            native block/line order (preserves multi-column reading order).
            Default False.
        comparison_options: Optional ComparisonOptions governing zone filtering
            (dates/times, page numbers, extra regex patterns in headers/footers).
    """
    pages: list[ExtractedPage] = []
    for number, page in enumerate(document):
        # sort=False preserves block/line reading order for multi-column pages
        raw_words: Sequence[tuple] = page.get_text("words", sort=sort_words)

        ignored_indices: set[int] = set()
        if comparison_options is not None:
            ignored_indices = _find_ignored_word_indices(page, raw_words, comparison_options)

        words = tuple(
            Word(
                str(item[4]),
                normalize_token(str(item[4]), options),
                tuple(float(v) for v in item[:4]),
                int(item[5]),
                int(item[6]),
            )
            for idx, item in enumerate(raw_words)
            if str(item[4]).strip() and idx not in ignored_indices
        )
        pages.append(ExtractedPage(number, words, words_ignored=len(ignored_indices)))
    return pages
