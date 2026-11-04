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


def _safe_save(document: pymupdf.Document, output_path: Path) -> None:
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(dir=output_path.parent, delete=False, suffix=".tmp") as tmp:
        tmp_path = Path(tmp.name)
    try:
        document.save(tmp_path, garbage=4, deflate=True)
        os.replace(tmp_path, output_path)
    except BaseException:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def _validate_style(style: HighlightStyle) -> None:
    if style not in ("highlight", "box"):
        raise ConfigurationError("style must be 'highlight' or 'box'")


def _group_rects(rects: list[tuple[float, float, float, float]]) -> list[tuple[float, float, float, float]]:
    """Merge nearby changed words on one visual line into a readable region."""
    grouped: list[pymupdf.Rect] = []
    for coords in sorted(rects, key=lambda item: (item[1], item[0])):
        current = pymupdf.Rect(coords)
        if grouped:
            previous = grouped[-1]
            same_line = abs((previous.y0 + previous.y1) / 2 - (current.y0 + current.y1) / 2) <= max(previous.height, current.height) * 0.45
            nearby = current.x0 - previous.x1 <= max(6, max(previous.height, current.height) * 0.75)
            if same_line and nearby:
                grouped[-1] = previous | current
                continue
        grouped.append(current)
    return [(rect.x0, rect.y0, rect.x1, rect.y1) for rect in grouped]


def _annotate(page: pymupdf.Page, rects: list[tuple[float, float, float, float]], color: tuple[float, float, float], style: HighlightStyle) -> None:
    """Add annotations to a page. Rects are in the page's unrotated coordinate space."""
    for coords in _group_rects(rects):
        rect = pymupdf.Rect(coords)
        # Validate against unrotated bounds (page.rect is rotated, use derotation_matrix)
        unrotated_bounds = page.rect * page.derotation_matrix
        clipped = rect & unrotated_bounds
        if clipped.is_empty or clipped.is_infinite:
            continue
        annot = page.add_highlight_annot(clipped) if style == "highlight" else page.add_rect_annot(clipped)
        annot.set_colors(stroke=color)
        if style == "box":
            annot.set_border(width=1.2)
        annot.update(opacity=0.45)


def _display_rect(source: pymupdf.Page, target: pymupdf.Rect) -> pymupdf.Rect:
    """Return the exact area occupied by ``show_pdf_page``'s default fitting."""
    source_rect = source.rect
    scale = min(target.width / source_rect.width, target.height / source_rect.height)
    width, height = source_rect.width * scale, source_rect.height * scale
    return pymupdf.Rect(
        target.x0 + (target.width - width) / 2,
        target.y0 + (target.height - height) / 2,
        target.x0 + (target.width + width) / 2,
        target.y0 + (target.height + height) / 2,
    )


def _report_rects(source: pymupdf.Page, rects: list[tuple[float, float, float, float]], target: pymupdf.Rect) -> list[tuple[float, float, float, float]]:
    """Map source word coordinates into a source page's report placement.

    Word rectangles from ``get_text('words')`` are in the unrotated coordinate space.
    The source page is placed on the report page via a scratch document with rotation=0,
    then rotated to match the visible orientation. We must map the unrotated word
    rectangles through the source page's rotation matrix, then scale/translate to the
    report placement.
    """
    source_rect = source.rect
    display = _display_rect(source, target)
    scale = display.width / source_rect.width

    # The visible rotation of the source page
    rot = source.rotation
    rot_matrix = source.rotation_matrix

    mapped: list[tuple[float, float, float, float]] = []
    for coords in rects:
        source_word = pymupdf.Rect(coords) & source_rect
        if source_word.is_empty or source_word.is_infinite:
            continue
        # Map from unrotated to visible coordinates: apply rotation matrix
        rotated_word = source_word * rot_matrix
        # Now scale and translate to the report placement
        mapped.append((
            display.x0 + (rotated_word.x0 - source_rect.x0) * scale,
            display.y0 + (rotated_word.y0 - source_rect.y0) * scale,
            display.x0 + (rotated_word.x1 - source_rect.x0) * scale,
            display.y0 + (rotated_word.y1 - source_rect.y0) * scale,
        ))
    return mapped


def highlight_differences(
    old_pdf: str | Path,
    new_pdf: str | Path,
    output_dir: str | Path,
    *,
    result: ComparisonResult | None = None,
    options: ComparisonOptions | None = None,
    style: HighlightStyle = "highlight",
    include_report: bool = False,
    removed_color: tuple[float, float, float] = (1, 0.2, 0.2),
    added_color: tuple[float, float, float] = (0.1, 0.65, 0.2),
    overwrite: bool = False,
) -> HighlightOutputs:
    """Write highlighted copies without modifying either source PDF."""
    _validate_style(style)
    comparison = result or compare_pdfs(old_pdf, new_pdf, options=options)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    old_output, new_output = target / "original_highlighted.pdf", target / "revised_highlighted.pdf"
    report_output = target / "difference_report.pdf"

    # Check overwrite
    for path in (old_output, new_output, report_output if include_report else None):
        if path and path.exists() and not overwrite:
            raise FileExistsError(f"Output file already exists: {path}. Use overwrite=True to replace.")
        if path and path.resolve() in (Path(old_pdf).resolve(), Path(new_pdf).resolve()):
            raise FileExistsError(f"Refusing to overwrite input file: {path}")

    with pymupdf.open(old_pdf) as old_document, pymupdf.open(new_pdf) as new_document:
        for mark in comparison._markup:
            if mark.old_page is not None:
                _annotate(old_document[mark.old_page], mark.old_rects, removed_color, style)
            if mark.new_page is not None:
                _annotate(new_document[mark.new_page], mark.new_rects, added_color, style)
        _safe_save(old_document, old_output)
        _safe_save(new_document, new_output)

    # Reopen output now: callers never receive a corrupt path silently.
    with pymupdf.open(old_output), pymupdf.open(new_output):
        pass

    report = create_side_by_side_report(
        old_pdf,
        new_pdf,
        comparison,
        report_output,
        removed_color,
        added_color,
        style=style,
        overwrite=overwrite,
    ) if include_report and not comparison.is_identical else None
    return HighlightOutputs(old_output, new_output, report)


def create_side_by_side_report(
    old_pdf: str | Path,
    new_pdf: str | Path,
    result: ComparisonResult,
    output_path: str | Path,
    removed_color: tuple[float, float, float] = (1, 0.2, 0.2),
    added_color: tuple[float, float, float] = (0.1, 0.65, 0.2),
    *,
    style: HighlightStyle = "highlight",
    overwrite: bool = False,
) -> Path | None:
    """Create a report containing only changed page pairs; return None if equal."""
    _validate_style(style)
    changed = [mark for mark in result._markup if mark.changed]
    if not changed:
        return None
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not overwrite:
        raise FileExistsError(f"Output file already exists: {destination}. Use overwrite=True to replace.")
    if destination.resolve() in (Path(old_pdf).resolve(), Path(new_pdf).resolve()):
        raise FileExistsError(f"Refusing to overwrite input file: {destination}")

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
                    # Draw through scratch document to handle rotation properly
                    with pymupdf.open() as scratch:
                        scratch.insert_pdf(old_document, from_page=mark.old_page, to_page=mark.old_page)
                        scratch[0].set_rotation(0)
                        # The area has the visible (rotated) width/height
                        page.show_pdf_page(left, scratch, 0, rotate=(360 - old_page.rotation) % 360)
                    _annotate(page, _report_rects(old_page, mark.old_rects, left), removed_color, style)

                if new_page:
                    # Draw through scratch document to handle rotation properly
                    with pymupdf.open() as scratch:
                        scratch.insert_pdf(new_document, from_page=mark.new_page, to_page=mark.new_page)
                        scratch[0].set_rotation(0)
                        page.show_pdf_page(right, scratch, 0, rotate=(360 - new_page.rotation) % 360)
                    _annotate(page, _report_rects(new_page, mark.new_rects, right), added_color, style)

        _safe_save(report, destination)
    finally:
        report.close()

    with pymupdf.open(destination):
        pass
    return destination