"""The small public comparison API."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .alignment import AlignmentStrategy, align_pages
from .diff import compare_words
from .exceptions import ConfigurationError, MissingTextLayerError
from .extraction import ExtractedPage, extract_document, open_pdf
from .normalization import NormalizationOptions
from .results import ChangeType, ComparisonResult, ComparisonSummary, Difference, _PageMarkup


@dataclass(frozen=True)
class ComparisonOptions:
    """Options for :func:`compare_pdfs`.

    ``content`` alignment matches equivalent pages wherever they occur;
    ``sequential`` resynchronizes within ``lookahead`` pages; ``index`` pairs
    pages by position.  The default is a conservative content strategy.
    """

    alignment: AlignmentStrategy = "content"
    similarity_threshold: float = 0.60
    lookahead: int = 5
    max_differences: int | None = 1_000
    normalization: NormalizationOptions = NormalizationOptions()
    sort_words: bool = False  # False = native block/line order (preserves multi-column)


def compare_pdfs(
    old_pdf: str | Path,
    new_pdf: str | Path,
    *,
    options: ComparisonOptions | None = None,
) -> ComparisonResult:
    """Compare two text-based local PDFs and return structured changes.

    Textual identity means all extracted normalized words occur in the same page
    order.  It does not establish visual or pixel-perfect identity.
    """
    settings = options or ComparisonOptions()
    if settings.max_differences is not None and settings.max_differences < 0:
        raise ConfigurationError("max_differences must be non-negative or None")

    with open_pdf(old_pdf) as old_document, open_pdf(new_pdf) as new_document:
        old_pages = extract_document(old_document, settings.normalization, sort_words=settings.sort_words)
        new_pages = extract_document(new_document, settings.normalization, sort_words=settings.sort_words)

    old_has_text = any(page.words for page in old_pages)
    new_has_text = any(page.words for page in new_pages)
    reliable = old_has_text and new_has_text

    if not reliable:
        missing = []
        if not old_has_text:
            missing.append("original")
        if not new_has_text:
            missing.append("revised")
        warning_msg = f"Comparison unreliable: no extractable text in {', '.join(missing)} PDF(s); OCR and visual comparison are not supported."
        warnings = [warning_msg]
        # Return a result with reliable=False instead of raising
        summary = ComparisonSummary(
            len(old_pages), len(new_pages), 0, 0, 0, 0, 0, 0, 0
        )
        return ComparisonResult(
            is_identical=False,
            summary=summary,
            differences=[],
            reliable=False,
            warnings=warnings,
            truncated=False,
            markup=[],
        )

    pairs = align_pages(
        old_pages, new_pages, settings.alignment, settings.similarity_threshold, settings.lookahead
    )
    entries: list[Difference] = []
    markup: list[_PageMarkup] = []
    added_pages = removed_pages = moved_pages = modified_pages = added_words = removed_words = 0

    for pair in pairs:
        if pair.old is None:
            page = new_pages[pair.new]  # type: ignore[index]
            entries.append(
                Difference(
                    ChangeType.PAGE_ADDED,
                    None,
                    pair.new + 1,
                    "",
                    " ".join(word.text for word in page.words),
                )
            )
            markup.append(
                _PageMarkup(
                    None,
                    pair.new,
                    new_rects=[word.rect for word in page.words],
                    changed=True,
                )
            )
            added_pages += 1
            added_words += len(page.words)
            continue
        if pair.new is None:
            page = old_pages[pair.old]
            entries.append(
                Difference(
                    ChangeType.PAGE_REMOVED,
                    pair.old + 1,
                    None,
                    " ".join(word.text for word in page.words),
                    "",
                )
            )
            markup.append(
                _PageMarkup(
                    pair.old,
                    None,
                    old_rects=[word.rect for word in page.words],
                    changed=True,
                )
            )
            removed_pages += 1
            removed_words += len(page.words)
            continue
        old_page, new_page = old_pages[pair.old], new_pages[pair.new]
        word_diff = compare_words(old_page.words, new_page.words, pair.old, pair.new)
        entries.extend(word_diff.differences)
        changed = bool(word_diff.differences)
        markup.append(
            _PageMarkup(
                pair.old,
                pair.new,
                [old_page.words[index].rect for index in word_diff.old_indexes],
                [new_page.words[index].rect for index in word_diff.new_indexes],
                changed,
            )
        )
        added_words += word_diff.added_words
        removed_words += word_diff.removed_words
        if changed:
            modified_pages += 1
        elif pair.moved:
            entries.append(Difference(ChangeType.PAGE_MOVED, pair.old + 1, pair.new + 1))
            moved_pages += 1

    total = len(entries)
    truncated = settings.max_differences is not None and total > settings.max_differences
    visible = entries[:settings.max_differences] if truncated else entries
    summary = ComparisonSummary(
        len(old_pages),
        len(new_pages),
        added_pages,
        removed_pages,
        moved_pages,
        modified_pages,
        added_words,
        removed_words,
        total,
    )
    warnings = []
    # reliable already checked; only blank pages warning remains
    if any(not page.words for page in old_pages + new_pages):
        warnings.append("One or more blank or textless pages could not be compared word by word.")

    return ComparisonResult(
        is_identical=not entries,
        summary=summary,
        differences=visible,
        warnings=warnings,
        truncated=truncated,
        markup=markup,
        reliable=reliable,
    )