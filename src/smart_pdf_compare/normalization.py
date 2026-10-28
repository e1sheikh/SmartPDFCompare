"""Conservative normalization applied only to comparison tokens."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizationOptions:
    """Policy for comparison tokens.

    Punctuation is retained by default: removing it can hide meaningful values
    such as ``1.2`` versus ``12``.  Original PDF text is never altered.
    """

    ignore_case: bool = True
    ignore_punctuation: bool = False
    normalize_quotes: bool = True


_DASHES = str.maketrans({
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
})
_QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"'})
_PUNCTUATION = re.compile(r"[^\w\s'-]", re.UNICODE)


def normalize_token(text: str, options: NormalizationOptions = NormalizationOptions()) -> str:
    """Return a comparison key while preserving numeric signs and contractions."""
    value = unicodedata.normalize("NFKC", text).translate(_DASHES).replace("\u00a0", " ").strip()
    if options.normalize_quotes:
        value = value.translate(_QUOTES)
    if options.ignore_case:
        value = value.casefold()
    if options.ignore_punctuation:
        value = _PUNCTUATION.sub("", value)
    return value


def normalized_text(words: list[str], options: NormalizationOptions) -> str:
    """Create a stable page signature from extracted words."""
    return " ".join(token for word in words if (token := normalize_token(word, options)))
