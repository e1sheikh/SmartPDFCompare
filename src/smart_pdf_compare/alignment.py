"""Page correspondence strategies."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal, Optional, Sequence

from .exceptions import ConfigurationError
from .extraction import ExtractedPage

AlignmentStrategy = Literal["content", "index", "sequential"]


@dataclass(frozen=True)
class PagePair:
    old: Optional[int]
    new: Optional[int]
    moved: bool = False


def _similarity(left: ExtractedPage, right: ExtractedPage) -> float:
    if not left.words and not right.words:
        return 1.0
    if not left.words or not right.words:
        return 0.0
    return SequenceMatcher(None, left.signature.split(), right.signature.split(), autojunk=False).ratio()


def align_pages(old: Sequence[ExtractedPage], new: Sequence[ExtractedPage], strategy: AlignmentStrategy, threshold: float, lookahead: int) -> list[PagePair]:
    """Return one-to-one page correspondence, including unpaired pages."""
    if strategy not in ("content", "index", "sequential"):
        raise ConfigurationError("alignment must be 'content', 'index', or 'sequential'")
    if not 0.0 <= threshold <= 1.0:
        raise ConfigurationError("similarity_threshold must be between 0 and 1")
    if lookahead < 1:
        raise ConfigurationError("lookahead must be at least 1")
    if strategy == "index":
        pairs = [PagePair(i, i) for i in range(min(len(old), len(new)))]
        pairs.extend(PagePair(i, None) for i in range(len(new), len(old)))
        pairs.extend(PagePair(None, j) for j in range(len(old), len(new)))
        return pairs
    if strategy == "sequential":
        return _sequential(old, new, threshold, lookahead)
    return _content(old, new, threshold)


def _content(old: Sequence[ExtractedPage], new: Sequence[ExtractedPage], threshold: float) -> list[PagePair]:
    # Exact fingerprints are paired first.  Pairing repeated pages in source order
    # is deterministic, while a unique matching page can be recognized as moved.
    by_signature: dict[str, deque[int]] = defaultdict(deque)
    for j, page in enumerate(new):
        by_signature[page.signature].append(j)
    matched: dict[int, int] = {}
    used: set[int] = set()
    for i, page in enumerate(old):
        candidates = by_signature[page.signature]
        if candidates:
            j = candidates.popleft()
            matched[i], used = j, used | {j}
    # Pair sufficiently similar unmatched pages.  This bounded greedy pass avoids
    # a large stored matrix and makes every page participate at most once.
    candidates: list[tuple[float, int, int]] = []
    for i, left in enumerate(old):
        if i in matched:
            continue
        for j, right in enumerate(new):
            if j not in used:
                score = _similarity(left, right)
                if score >= threshold:
                    candidates.append((score, i, j))
    for _score, i, j in sorted(candidates, key=lambda item: (-item[0], abs(item[1] - item[2]), item[1], item[2])):
        if i not in matched and j not in used:
            matched[i], used = j, used | {j}
    # A changed page may have no similarity above the threshold.  When the only
    # remaining pages are positional counterparts, keep them paired as a change.
    remaining_old = [i for i in range(len(old)) if i not in matched]
    remaining_new = [j for j in range(len(new)) if j not in used]
    if len(remaining_old) == len(remaining_new):
        for i, j in zip(remaining_old, remaining_new):
            matched[i], used = j, used | {j}
    # A changed index alone is not a move: an insertion shifts every later page.
    # A move is only reported when two matched pages reverse their relative order.
    inverted: set[int] = set()
    ordered_matches = sorted(matched.items())
    for position, (i, j) in enumerate(ordered_matches):
        for other_i, other_j in ordered_matches[position + 1:]:
            if j > other_j:
                inverted.update((i, other_i))
    keyed: list[tuple[float, PagePair]] = []
    reverse = {j: i for i, j in matched.items()}
    for i in range(len(old)):
        if i in matched:
            j = matched[i]
            keyed.append((float(i), PagePair(i, j, moved=i in inverted and old[i].signature == new[j].signature)))
        else:
            keyed.append((float(i), PagePair(i, None)))
    for j in range(len(new)):
        if j not in used:
            before = [reverse[k] for k in range(j - 1, -1, -1) if k in reverse]
            keyed.append(((before[0] + 0.5) if before else -0.5, PagePair(None, j)))
    return [pair for _, pair in sorted(keyed, key=lambda item: item[0])]


def _sequential(old: Sequence[ExtractedPage], new: Sequence[ExtractedPage], threshold: float, lookahead: int) -> list[PagePair]:
    pairs: list[PagePair] = []
    i = j = 0
    while i < len(old) and j < len(new):
        if _similarity(old[i], new[j]) >= threshold:
            pairs.append(PagePair(i, j)); i += 1; j += 1; continue
        new_anchor = next((k for k in range(j + 1, min(len(new), j + lookahead + 1)) if _similarity(old[i], new[k]) >= threshold), None)
        old_anchor = next((k for k in range(i + 1, min(len(old), i + lookahead + 1)) if _similarity(old[k], new[j]) >= threshold), None)
        if new_anchor is not None and (old_anchor is None or new_anchor - j <= old_anchor - i):
            pairs.extend(PagePair(None, k) for k in range(j, new_anchor)); j = new_anchor
        elif old_anchor is not None:
            pairs.extend(PagePair(k, None) for k in range(i, old_anchor)); i = old_anchor
        else:
            pairs.append(PagePair(i, j)); i += 1; j += 1
    pairs.extend(PagePair(k, None) for k in range(i, len(old)))
    pairs.extend(PagePair(None, k) for k in range(j, len(new)))
    return pairs
