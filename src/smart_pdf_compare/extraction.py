"""Extraction of positioned PDF words using PyMuPDF."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pymupdf

from .exceptions import InvalidPDFError
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
        document = pymupdf.open(candidate)
    except (pymupdf.FileDataError, RuntimeError, OSError) as exc:
        raise InvalidPDFError(f"Cannot read PDF '{candidate}': {exc}") from exc
    if document.page_count == 0:
        document.close()
        raise InvalidPDFError(f"PDF has no pages: {candidate}")
    return document


def extract_document(document: pymupdf.Document, options: NormalizationOptions) -> list[ExtractedPage]:
    """Extract reading-order words and their coordinates from every page."""
    pages: list[ExtractedPage] = []
    for number, page in enumerate(document):
        raw_words: Sequence[tuple] = page.get_text("words", sort=True)
        words = tuple(
            Word(str(item[4]), normalize_token(str(item[4]), options), tuple(float(v) for v in item[:4]), int(item[5]), int(item[6]))
            for item in raw_words
            if str(item[4]).strip()
        )
        pages.append(ExtractedPage(number, words))
    return pages
