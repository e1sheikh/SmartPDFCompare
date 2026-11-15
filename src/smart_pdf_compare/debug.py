"""Debug utilities for PDF comparison diagnostics."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .extraction import ExtractedPage, Word
from .results import Difference


@dataclass
class DebugInfo:
    """Detailed debug information for a word/token."""
    text: str
    normalized: str
    repr_text: str
    codepoints: List[Dict[str, Any]]
    font_name: Optional[str]
    font_size: Optional[float]
    flags: Optional[int]
    color: Optional[tuple]
    bbox: tuple
    normalized_form: str
    neighbours: List[str]


def unicode_name(char: str) -> str:
    """Get Unicode name for a character."""
    try:
        return unicodedata.name(char)
    except ValueError:
        return f"U+{ord(char):04X}"


def analyze_word(word: Word, page_words: List[Word], index: int) -> DebugInfo:
    """Analyze a word in detail."""
    codepoints = []
    for ch in word.text:
        codepoints.append({
            'char': ch,
            'codepoint': f"U+{ord(ch):04X}",
            'name': unicode_name(ch),
            'repr': repr(ch),
        })

    # Get neighbours
    neighbours = []
    if index > 0:
        neighbours.append(page_words[index - 1].text)
    if index < len(page_words) - 1:
        neighbours.append(page_words[index + 1].text)

    return DebugInfo(
        text=word.text,
        normalized=word.normalized,
        repr_text=repr(word.text),
        codepoints=codepoints,
        font_name=None,
        font_size=None,
        flags=None,
        color=None,
        bbox=word.rect,
        normalized_form=word.normalized,
        neighbours=neighbours,
    )


def explain_difference(diff: Difference, old_page: ExtractedPage, new_page: ExtractedPage) -> Dict[str, Any]:
    """Explain a difference in detail."""
    explanation = {
        'change_type': diff.change_type.value,
        'old_page': diff.old_page,
        'new_page': diff.new_page,
        'old_text': diff.old_text,
        'new_text': diff.new_text,
        'old_context': diff.old_context,
        'new_context': diff.new_context,
        'old_debug': [],
        'new_debug': [],
    }

    # Find matching words in pages
    old_words = [w for w in old_page.words if w.text in diff.old_text.split() or diff.old_text in w.text]
    new_words = [w for w in new_page.words if w.text in diff.new_text.split() or diff.new_text in w.text]

    for word in old_words:
        idx = list(old_page.words).index(word)
        explanation['old_debug'].append(analyze_word(word, list(old_page.words), idx))

    for word in new_words:
        idx = list(new_page.words).index(word)
        explanation['new_debug'].append(analyze_word(word, list(new_page.words), idx))

    return explanation


def dump_diffs(result: Any, old_pages: List[ExtractedPage], new_pages: List[ExtractedPage], output_path: str) -> None:
    """Dump detailed diff information to file."""
    import json

    all_explanations = []
    for diff in result.differences:
        if diff.old_page and diff.new_page:
            try:
                old_page = old_pages[diff.old_page - 1]
                new_page = new_pages[diff.new_page - 1]
                explanation = explain_difference(diff, old_page, new_page)
                all_explanations.append(explanation)
            except IndexError:
                continue

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_explanations, f, indent=2, ensure_ascii=False)
