"""Word-level diffs with source-coordinate tracking."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Sequence

from .extraction import Word
from .results import ChangeType, Difference


@dataclass(frozen=True)
class WordDiff:
    differences: list[Difference]
    old_indexes: list[int]
    new_indexes: list[int]
    added_words: int
    removed_words: int


def _text(words: Sequence[Word], start: int, end: int) -> str:
    return " ".join(word.text for word in words[start:end])


def _context(words: Sequence[Word], start: int, end: int) -> str:
    if not words or start >= len(words):
        return ""
    anchor = min(start, len(words) - 1)
    block, line = words[anchor].block, words[anchor].line
    return " ".join(word.text for word in words if word.block == block and word.line == line)


def compare_words(old: Sequence[Word], new: Sequence[Word], old_page: int, new_page: int) -> WordDiff:
    """Diff normalized word streams and retain ranges for PDF markup."""
    matcher = SequenceMatcher(None, [word.normalized for word in old], [word.normalized for word in new], autojunk=False)
    entries: list[Difference] = []
    old_indexes: list[int] = []
    new_indexes: list[int] = []
    added = removed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete":
            entries.append(Difference(ChangeType.REMOVED, old_page + 1, new_page + 1, _text(old, i1, i2), "", _context(old, i1, i2), ""))
            old_indexes.extend(range(i1, i2)); removed += i2 - i1
        elif tag == "insert":
            entries.append(Difference(ChangeType.ADDED, old_page + 1, new_page + 1, "", _text(new, j1, j2), "", _context(new, j1, j2)))
            new_indexes.extend(range(j1, j2)); added += j2 - j1
        else:
            entries.append(Difference(ChangeType.REPLACED, old_page + 1, new_page + 1, _text(old, i1, i2), _text(new, j1, j2), _context(old, i1, i2), _context(new, j1, j2)))
            old_indexes.extend(range(i1, i2)); new_indexes.extend(range(j1, j2))
            removed += i2 - i1; added += j2 - j1
    return WordDiff(entries, old_indexes, new_indexes, added, removed)
