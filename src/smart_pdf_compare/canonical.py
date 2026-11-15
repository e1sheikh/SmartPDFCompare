"""Glyph-level canonicalization for PDF comparison.

Phase 1 implementation: per-character canonicalization with mapping back to glyphs.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class CanonicalChar:
    """A single character with canonical form and source index."""
    source_char: str
    canonical_char: str
    source_index: int
    glyph_index: int


@dataclass(frozen=True)
class CanonicalToken:
    """Token with canonical form and character mappings."""
    original: str
    canonical: str
    chars: Tuple[CanonicalChar, ...]


# Hyphen class mappings
_HYPHEN_VARIANTS = {
    '-',  # hyphen-minus
    '­',  # soft hyphen
    '‐',  # hyphen
    '‑',  # non-breaking hyphen
    '‒',  # figure dash
    '–',  # en dash
    '—',  # em dash
    '―',  # horizontal bar
    '−',  # minus sign
    '﹘',  # small em dash
    '﹣',  # small hyphen-minus
    '－',  # fullwidth hyphen-minus
    '⁃',  # hyphen bullet
}

# Bullet/list marker class
_BULLET_VARIANTS = {
    '•',  # bullet
    '·',  # middle dot
    '●',  # black circle
    '○',  # white circle
    '▪',  # black small square
    '■',  # black square
    '‣',  # triangular bullet
    '⁃',  # hyphen bullet
    '․',  # one dot leader
    '∙',  # bullet operator
}


class Canonicalizer:
    """Per-character canonicalizer with glyph mapping."""

    def __init__(self, ignore_case: str = "auto"):
        self.ignore_case = ignore_case
        # Symbol font PUA mappings (Symbol font code points to Unicode)
        self.symbol_pua = {
            '': '°',  # degree
            '': 'θ',  # theta
            '': 'μ',  # micro
            '': 'Ω',  # omega
        }

    def canonicalize_char(self, char: str, font_name: str = "", is_line_end: bool = False) -> str:
        """Canonicalize a single character."""
        if not char:
            return char

        # Handle soft hyphen at line end (de-hyphenation)
        if char == '­' and is_line_end:
            return ''  # Remove discretionary hyphen

        # Hyphen class
        if char in _HYPHEN_VARIANTS:
            return '-'

        # Bullet class
        if char in _BULLET_VARIANTS:
            return '•'

        # Symbol font PUA
        if font_name and ('Symbol' in font_name or 'symbol' in font_name):
            if char in self.symbol_pua:
                return self.symbol_pua[char]
            # Unknown PUA - hash it
            if ord(char) >= 0xF000 and ord(char) <= 0xF8FF:
                return f'￿{hash(char):x}'

        # Degree variants
        if char in '°˚∘ʰ':
            return '°'

        # Theta variants
        if char in 'θϑϴɾ':
            return 'θ'

        # Micro variants
        if char in 'µμ':
            return 'μ'

        # Ohm variants
        if char in 'Ω':
            return 'Ω'

        # Normalize Unicode
        normalized = unicodedata.normalize('NFC', char)

        # Replace spaces
        if unicodedata.category(normalized) == 'Zs':
            return ' '

        # Case handling
        if self.ignore_case == "safe":
            # Case-insensitive only for alphabetic tokens >= 4 chars
            # This is handled at token level, not char level
            pass
        elif self.ignore_case:
            normalized = normalized.casefold()

        # Remove zero-width and control characters
        cat = unicodedata.category(normalized)
        if cat.startswith('C'):
            return ''

        return normalized

    def canonicalize_token(self, text: str, font_name: str = "", is_line_end: bool = False) -> CanonicalToken:
        """Canonicalize a token character by character."""
        chars = []
        canonical_parts = []

        for i, ch in enumerate(text):
            canon = self.canonicalize_char(ch, font_name, is_line_end and i == len(text) - 1)
            if canon:
                chars.append(CanonicalChar(
                    source_char=ch,
                    canonical_char=canon,
                    source_index=i,
                    glyph_index=i
                ))
                canonical_parts.append(canon)

        canonical_str = ''.join(canonical_parts)

        # Handle case policy at token level
        if self.ignore_case == "safe":
            # Check if token has digits, units, or is acronym
            has_digits = any(c.isdigit() for c in text)
            has_units = any(c in '°C°FKμMΩÅ' for c in text)
            is_acronym = len(text) <= 3 and text.isupper()

            if not (has_digits or has_units or is_acronym):
                # Case-insensitive for purely alphabetic
                canonical_str = canonical_str.casefold()

        return CanonicalToken(
            original=text,
            canonical=canonical_str,
            chars=tuple(chars)
        )
