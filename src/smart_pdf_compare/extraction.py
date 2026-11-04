"""Extraction of positioned PDF words using PyMuPDF."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pymupdf

from .exceptions import EncryptedPDFError, InvalidPDFError
from .normalization import NormalizationOptions, normalize_token


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

    @property
    def signature(self) -> str:
        return " ".join(word.normalized for word in self.words if word.normalized)


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


def extract_document(
    document: pymupdf.Document,
    options: NormalizationOptions,
    sort_words: bool = False,
) -> list[ExtractedPage]:
    """Extract reading-order words and their coordinates from every page.

    Args:
        document: Open PyMuPDF document.
        options: Normalization options.
        sort_words: If True, words are sorted by (y, x) within the page
            (PyMuPDF's default 'sort=True'). If False, words are in
            native block/line order (preserves multi-column reading order).
            Default False.
    """
    pages: list[ExtractedPage] = []
    for number, page in enumerate(document):
        # sort=False preserves block/line reading order for multi-column pages
        raw_words: Sequence[tuple] = page.get_text("words", sort=sort_words)
        words = tuple(
            Word(
                str(item[4]),
                normalize_token(str(item[4]), options),
                tuple(float(v) for v in item[:4]),
                int(item[5]),
                int(item[6]),
            )
            for item in raw_words
            if str(item[4]).strip()
        )
        pages.append(ExtractedPage(number, words))
    return pages