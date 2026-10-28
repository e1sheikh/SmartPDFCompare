"""Safe highlighted-copy and side-by-side PDF generation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pymupdf

from .api import ComparisonOptions, compare_pdfs
from .exceptions import ConfigurationError
from .results import ComparisonResult, _PageMarkup

HighlightStyle = Literal["highlight", "box"]


@dataclass(frozen=True)
class HighlightOutputs:
    original: Path
    revised: Path
    report: Path | None = None


def _validate_style(style: HighlightStyle) -> None:
    if style not in ("highlight", "box"):
        raise ConfigurationError("style must be 'highlight' or 'box'")


def _annotate(page: pymupdf.Page, rects: list[tuple[float, float, float, float]], color: tuple[float, float, float], style: HighlightStyle) -> None:
    for coords in rects:
        rect = pymupdf.Rect(coords) & page.rect
        if rect.is_empty or rect.is_infinite:
            continue
        annot = page.add_highlight_annot(rect) if style == "highlight" else page.add_rect_annot(rect)
        annot.set_colors(stroke=color)
        if style == "box":
            annot.set_border(width=1.2)
        annot.update(opacity=0.45)


def highlight_differences(old_pdf: str | Path, new_pdf: str | Path, output_dir: str | Path, *, result: ComparisonResult | None = None, options: ComparisonOptions | None = None, style: HighlightStyle = "highlight", include_report: bool = False, removed_color: tuple[float, float, float] = (1, 0.2, 0.2), added_color: tuple[float, float, float] = (0.1, 0.65, 0.2)) -> HighlightOutputs:
    """Write highlighted copies without modifying either source PDF."""
    _validate_style(style)
    comparison = result or compare_pdfs(old_pdf, new_pdf, options=options)
    target = Path(output_dir); target.mkdir(parents=True, exist_ok=True)
    old_output, new_output = target / "original_highlighted.pdf", target / "revised_highlighted.pdf"
    with pymupdf.open(old_pdf) as old_document, pymupdf.open(new_pdf) as new_document:
        for mark in comparison._markup:
            if mark.old_page is not None:
                _annotate(old_document[mark.old_page], mark.old_rects, removed_color, style)
            if mark.new_page is not None:
                _annotate(new_document[mark.new_page], mark.new_rects, added_color, style)
        old_document.save(old_output, garbage=4, deflate=True)
        new_document.save(new_output, garbage=4, deflate=True)
    # Reopen output now: callers never receive a corrupt path silently.
    with pymupdf.open(old_output), pymupdf.open(new_output):
        pass
    report = create_side_by_side_report(old_pdf, new_pdf, comparison, target / "difference_report.pdf", removed_color, added_color) if include_report and not comparison.is_identical else None
    return HighlightOutputs(old_output, new_output, report)


def create_side_by_side_report(old_pdf: str | Path, new_pdf: str | Path, result: ComparisonResult, output_path: str | Path, removed_color: tuple[float, float, float] = (1, 0.2, 0.2), added_color: tuple[float, float, float] = (0.1, 0.65, 0.2)) -> Path | None:
    """Create a report containing only changed page pairs; return None if equal."""
    changed = [mark for mark in result._markup if mark.changed]
    if not changed:
        return None
    destination = Path(output_path); destination.parent.mkdir(parents=True, exist_ok=True)
    report = pymupdf.open()
    try:
        with pymupdf.open(old_pdf) as old_document, pymupdf.open(new_pdf) as new_document:
            for mark in changed:
                old_page = old_document[mark.old_page] if mark.old_page is not None else None
                new_page = new_document[mark.new_page] if mark.new_page is not None else None
                old_width = old_page.rect.width if old_page else 300
                new_width = new_page.rect.width if new_page else 300
                height = max(old_page.rect.height if old_page else 200, new_page.rect.height if new_page else 200) + 28
                page = report.new_page(width=old_width + new_width, height=height)
                left = pymupdf.Rect(0, 28, old_width, height)
                right = pymupdf.Rect(old_width, 28, old_width + new_width, height)
                page.insert_text((6, 18), f"Original page {mark.old_page + 1}" if old_page else "Original: no matching page", fontsize=10)
                page.insert_text((old_width + 6, 18), f"Revised page {mark.new_page + 1}" if new_page else "Revised: no matching page", fontsize=10)
                if old_page:
                    page.show_pdf_page(left, old_document, mark.old_page)
                    for rect in mark.old_rects:
                        source = pymupdf.Rect(rect)
                        page.draw_rect(
                            pymupdf.Rect(source.x0, source.y0 + 28, source.x1, source.y1 + 28),
                            color=removed_color,
                            width=1.2,
                            overlay=True,
                        )
                if new_page:
                    page.show_pdf_page(right, new_document, mark.new_page)
                    for rect in mark.new_rects:
                        source = pymupdf.Rect(rect)
                        page.draw_rect(
                            pymupdf.Rect(source.x0 + old_width, source.y0 + 28, source.x1 + old_width, source.y1 + 28),
                            color=added_color,
                            width=1.2,
                            overlay=True,
                        )
        report.save(destination, garbage=4, deflate=True)
    finally:
        report.close()
    with pymupdf.open(destination):
        pass
    return destination
