"""Rendered-page PDF comparison without third-party image-processing packages."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Sequence

import pymupdf

from .exceptions import ConfigurationError
from .extraction import open_pdf

VisualOutputMode = Literal["none", "side_by_side", "diff_image"]


@dataclass(frozen=True)
class VisualComparisonOptions:
    """Policy for rendered-page visual comparison.

    Pages are paired by index, not textual content. Rendered canvases are
    top-left aligned and padded with ``background``; unequal page dimensions
    are always reported as a visual difference.
    """

    dpi: int = 144
    pixel_threshold: int = 8
    min_changed_pixels: int = 1
    min_difference_ratio: float = 0.0
    output_mode: VisualOutputMode = "none"
    background: tuple[int, int, int] = (255, 255, 255)


@dataclass(frozen=True)
class VisualPageResult:
    """Visual-comparison information for one paired or unmatched page."""

    old_page: int | None
    new_page: int | None
    old_dimensions: tuple[int, int] | None
    new_dimensions: tuple[int, int] | None
    visually_different: bool
    dimension_mismatch: bool = False
    changed_pixels: int | None = None
    total_pixels: int | None = None
    difference_ratio: float | None = None
    side_by_side_path: str | None = None
    diff_image_path: str | None = None


@dataclass
class VisualComparisonResult:
    """Result of comparing two PDFs by rendered pixels."""

    original: str
    revised: str
    is_identical: bool
    pages: list[VisualPageResult]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "revised": self.revised,
            "is_identical": self.is_identical,
            "pages": [asdict(page) for page in self.pages],
            "warnings": list(self.warnings),
        }


@dataclass
class VisualBatchResult:
    """Reference-based visual comparisons for several PDFs."""

    reference: str
    comparisons: list[VisualComparisonResult]

    @property
    def is_identical(self) -> bool:
        """Whether every reference-based comparison is visually identical."""
        return all(item.is_identical for item in self.comparisons)

    def to_dict(self) -> dict:
        return {
            "reference": self.reference,
            "is_identical": self.is_identical,
            "comparisons": [item.to_dict() for item in self.comparisons],
        }


@dataclass(frozen=True)
class _Raster:
    width: int
    height: int
    samples: bytes


def _validate(options: VisualComparisonOptions) -> None:
    if not 36 <= options.dpi <= 600:
        raise ConfigurationError("dpi must be between 36 and 600")
    if not 0 <= options.pixel_threshold <= 255:
        raise ConfigurationError("pixel_threshold must be between 0 and 255")
    if options.min_changed_pixels < 1:
        raise ConfigurationError("min_changed_pixels must be at least 1")
    if not 0.0 <= options.min_difference_ratio <= 1.0:
        raise ConfigurationError("min_difference_ratio must be between 0 and 1")
    if options.output_mode not in ("none", "side_by_side", "diff_image"):
        raise ConfigurationError("output_mode must be 'none', 'side_by_side', or 'diff_image'")
    if len(options.background) != 3 or any(not 0 <= value <= 255 for value in options.background):
        raise ConfigurationError("background must contain three RGB values between 0 and 255")


def _render(page: pymupdf.Page, dpi: int) -> _Raster:
    scale = dpi / 72
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False)
    return _Raster(pixmap.width, pixmap.height, bytes(pixmap.samples))


def _canvas(raster: _Raster, width: int, height: int, background: tuple[int, int, int]) -> bytes:
    data = bytearray(bytes(background) * (width * height))
    row_width = raster.width * 3
    for row in range(raster.height):
        start = row * width * 3
        source_start = row * row_width
        data[start:start + row_width] = raster.samples[source_start:source_start + row_width]
    return bytes(data)


def _save_png(path: Path, width: int, height: int, samples: bytes) -> None:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, width, height, samples, False)
    pixmap.save(path)


def _side_by_side(left: _Raster, right: _Raster, background: tuple[int, int, int]) -> tuple[int, int, bytes]:
    separator = 12
    width, height = left.width + separator + right.width, max(left.height, right.height)
    data = bytearray(bytes(background) * (width * height))
    for raster, offset in ((left, 0), (right, left.width + separator)):
        row_width = raster.width * 3
        for row in range(raster.height):
            destination = (row * width + offset) * 3
            source = row * row_width
            data[destination:destination + row_width] = raster.samples[source:source + row_width]
    return width, height, bytes(data)


def _blank(width: int, height: int, background: tuple[int, int, int]) -> _Raster:
    return _Raster(width, height, bytes(background) * (width * height))


def _difference_image(left: bytes, right: bytes, width: int, height: int, threshold: int) -> tuple[int, bytes]:
    changed = 0
    output = bytearray(len(left))
    for index in range(0, len(left), 3):
        delta = max(abs(left[index] - right[index]), abs(left[index + 1] - right[index + 1]), abs(left[index + 2] - right[index + 2]))
        if delta > threshold:
            output[index:index + 3] = b"\xff3<"
            changed += 1
        else:
            shade = (left[index] + left[index + 1] + left[index + 2]) // 9 + 170
            output[index:index + 3] = bytes((shade, shade, shade))
    return changed, bytes(output)


def _compare_pair(old_pdf: str | Path, new_pdf: str | Path, options: VisualComparisonOptions, output_dir: Path | None, prefix: str) -> VisualComparisonResult:
    pages: list[VisualPageResult] = []
    with open_pdf(old_pdf) as old_document, open_pdf(new_pdf) as new_document:
        page_count = max(old_document.page_count, new_document.page_count)
        for index in range(page_count):
            old_page = old_document[index] if index < old_document.page_count else None
            new_page = new_document[index] if index < new_document.page_count else None
            if old_page is None or new_page is None:
                image = _render(old_page or new_page, options.dpi)
                blank = _blank(image.width, image.height, options.background)
                old_image, new_image = (image, blank) if old_page else (blank, image)
                changed, diff_samples = _difference_image(
                    old_image.samples, new_image.samples, image.width, image.height, options.pixel_threshold
                )
                side_path = diff_path = None
                if output_dir and options.output_mode == "side_by_side":
                    side = output_dir / f"{prefix}-page-{index + 1:04d}-side-by-side.png"
                    side_width, side_height, side_samples = _side_by_side(old_image, new_image, options.background)
                    _save_png(side, side_width, side_height, side_samples)
                    side_path = str(side)
                elif output_dir and options.output_mode == "diff_image":
                    diff = output_dir / f"{prefix}-page-{index + 1:04d}-diff.png"
                    _save_png(diff, image.width, image.height, diff_samples)
                    diff_path = str(diff)
                pages.append(VisualPageResult(
                    index + 1 if old_page else None,
                    index + 1 if new_page else None,
                    (image.width, image.height) if old_page else None,
                    (image.width, image.height) if new_page else None,
                    True,
                    changed_pixels=changed,
                    total_pixels=image.width * image.height,
                    difference_ratio=changed / (image.width * image.height),
                    side_by_side_path=side_path,
                    diff_image_path=diff_path,
                ))
                continue
            old_image, new_image = _render(old_page, options.dpi), _render(new_page, options.dpi)
            width, height = max(old_image.width, new_image.width), max(old_image.height, new_image.height)
            old_canvas = _canvas(old_image, width, height, options.background)
            new_canvas = _canvas(new_image, width, height, options.background)
            changed, diff_samples = _difference_image(old_canvas, new_canvas, width, height, options.pixel_threshold)
            total = width * height
            ratio = changed / total
            dimension_mismatch = (old_image.width, old_image.height) != (new_image.width, new_image.height)
            different = dimension_mismatch or (changed >= options.min_changed_pixels and ratio >= options.min_difference_ratio)
            side_path = diff_path = None
            if output_dir and options.output_mode == "side_by_side":
                side = output_dir / f"{prefix}-page-{index + 1:04d}-side-by-side.png"
                side_width, side_height, side_samples = _side_by_side(old_image, new_image, options.background)
                _save_png(side, side_width, side_height, side_samples)
                side_path = str(side)
            elif output_dir and options.output_mode == "diff_image":
                diff = output_dir / f"{prefix}-page-{index + 1:04d}-diff.png"
                _save_png(diff, width, height, diff_samples)
                diff_path = str(diff)
            pages.append(VisualPageResult(
                index + 1,
                index + 1,
                (old_image.width, old_image.height),
                (new_image.width, new_image.height),
                different,
                dimension_mismatch,
                changed,
                total,
                ratio,
                side_path,
                diff_path,
            ))
    warning = "Visual pages are paired by index; text-aware page alignment is not applied."
    return VisualComparisonResult(str(Path(old_pdf)), str(Path(new_pdf)), not any(page.visually_different for page in pages), pages, [warning])


def compare_visual_pdfs(old_pdf: str | Path, new_pdf: str | Path, *, options: VisualComparisonOptions | None = None, output_dir: str | Path | None = None) -> VisualComparisonResult:
    """Compare rendered pages of two PDFs and optionally write PNG artifacts."""
    settings = options or VisualComparisonOptions()
    _validate(settings)
    target = Path(output_dir) if output_dir is not None else None
    if settings.output_mode != "none" and target is None:
        raise ConfigurationError("output_dir is required when output_mode generates images")
    if target:
        target.mkdir(parents=True, exist_ok=True)
    return _compare_pair(old_pdf, new_pdf, settings, target, "visual")


def compare_visual_documents(pdf_paths: Sequence[str | Path], *, reference: int = 0, options: VisualComparisonOptions | None = None, output_dir: str | Path | None = None) -> VisualBatchResult:
    """Compare every document after ``reference`` against the designated PDF.

    This reference-based API avoids ambiguous all-pairs output when callers
    provide more than two documents.
    """
    if len(pdf_paths) < 2:
        raise ConfigurationError("at least two PDF paths are required")
    if not 0 <= reference < len(pdf_paths):
        raise ConfigurationError("reference must identify one of the supplied PDF paths")
    settings = options or VisualComparisonOptions()
    _validate(settings)
    target = Path(output_dir) if output_dir is not None else None
    if settings.output_mode != "none" and target is None:
        raise ConfigurationError("output_dir is required when output_mode generates images")
    if target:
        target.mkdir(parents=True, exist_ok=True)
    reference_path = pdf_paths[reference]
    comparisons = [
        _compare_pair(reference_path, candidate, settings, target, f"reference-{reference + 1}-to-{index + 1}")
        for index, candidate in enumerate(pdf_paths)
        if index != reference
    ]
    return VisualBatchResult(str(Path(reference_path)), comparisons)
