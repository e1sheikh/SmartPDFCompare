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


# Dash/minus variants to map to ASCII "-"
_DASHES = str.maketrans({
    "‐": "-",  # hyphen
    "‑": "-",  # non-breaking hyphen
    "‒": "-",  # figure dash
    "–": "-",  # en dash
    "—": "-",  # em dash
    "―": "-",  # horizontal bar
    "−": "-",  # minus sign
    "﹘": "-",  # small em dash
    "﹣": "-",  # small hyphen-minus
    "－": "-",  # fullwidth hyphen-minus
})

# Curly quotes/apostrophes to ASCII
_QUOTES = str.maketrans({
    "‘": "'",  # left single quotation mark
    "’": "'",  # right single quotation mark
    "‚": "'",  # single low-9 quotation mark
    "‛": "'",  # single high-reversed-9 quotation mark
    "“": '"',  # left double quotation mark
    "”": '"',  # right double quotation mark
    "„": '"',  # double low-9 quotation mark
    "‟": '"',  # double high-reversed-9 quotation mark
})

# Zero-width and soft hyphen characters to remove
_ZERO_WIDTH_CHARS = {
    "­",   # soft hyphen
    "​",   # zero width space
    "‌",   # zero width non-joiner
    "‍",   # zero width joiner
    "⁠",   # word joiner
    "﻿",   # zero width no-break space (BOM)
}

# Pattern for punctuation that is NOT inside numbers/words
# We strip punctuation at edges, but preserve:
# - Decimal points inside numbers (e.g., 1.2)
# - Thousands separators inside numbers (e.g., 1,000)
# - Signs at start of numbers (e.g., -80, +80)
# - Apostrophes inside words (e.g., isn't)
_PUNCTUATION_EDGE = re.compile(r"^[^\w\s'-]+|[^\w\s'-]+$", re.UNICODE)


def normalize_token(text: str, options: NormalizationOptions = NormalizationOptions()) -> str:
    """Return a comparison key while preserving numeric signs and contractions."""
    # NFKC normalization, then handle special characters
    value = unicodedata.normalize("NFKC", text)

    # Remove zero-width and soft hyphen characters
    if _ZERO_WIDTH_CHARS:
        value = "".join(ch for ch in value if ch not in _ZERO_WIDTH_CHARS)

    # Replace NBSP with regular space
    value = value.replace(" ", " ")

    # Map dash/minus variants to ASCII "-"
    value = value.translate(_DASHES)

    # Map curly quotes/apostrophes to ASCII if enabled
    if options.normalize_quotes:
        value = value.translate(_QUOTES)

    value = value.strip()

    if options.ignore_case:
        value = value.casefold()

    if options.ignore_punctuation:
        # Strip punctuation only at word edges, not inside numbers/words
        value = _PUNCTUATION_EDGE.sub("", value)

    return value


def normalized_text(words: list[str], options: NormalizationOptions) -> str:
    """Create a stable page signature from extracted words."""
    return " ".join(token for word in words if (token := normalize_token(word, options)))