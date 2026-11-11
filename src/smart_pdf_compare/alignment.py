"""Page correspondence strategies."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal, Optional, Sequence

from .exceptions import ConfigurationError
from .normalization import NormalizationOptions, normalize_token
from .extraction import ExtractedPage

AlignmentStrategy = Literal["content", "index", "sequential"]


@dataclass(frozen=True)
class PagePair:
    old: Optional[int]
    new: Optional[int]
    moved: bool = False


class FenwickTree:
    """Max Fenwick tree for Weighted LIS with parent tracking.

    Each node stores ``(value, pair_index)`` so that the LIS chain can be
    reconstructed in O(E log E) time instead of O(E²).
    """

    def __init__(self, size: int):
        self.size = size
        # Each element is (max_dp_value, pair_index_that_achieved_it)
        self.tree: list[tuple[float, int]] = [(0.0, -1)] * (size + 1)

    def update(self, idx: int, val: float, pair_idx: int) -> None:
        """Update position *idx* with *(val, pair_idx)* if *val* is larger."""
        i = idx + 1
        while i <= self.size:
            if val > self.tree[i][0]:
                self.tree[i] = (val, pair_idx)
            i += i & (-i)

    def query(self, idx: int) -> tuple[float, int]:
        """Return ``(max_value, pair_index)`` for the prefix ``[0 .. idx]``."""
        i = idx + 1
        res_val = 0.0
        res_idx = -1
        while i > 0:
            stored_val, stored_idx = self.tree[i]
            if stored_val > res_val:
                res_val = stored_val
                res_idx = stored_idx
            i -= i & (-i)
        return res_val, res_idx


def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def _page_word_list(page: ExtractedPage) -> list[str]:
    """Return the ordered list of normalized words for a page."""
    return [w.normalized for w in page.words if w.normalized]


def _page_word_set(page: ExtractedPage) -> set[str]:
    # Return set of normalized words for page
    return {w.normalized for w in page.words if w.normalized}


def _page_similarity(
    set_a: set[str],
    set_b: set[str],
    words_a: list[str],
    words_b: list[str],
) -> float:
    """Weighted similarity combining Jaccard (set overlap) with sequence ratio.

    Jaccard handles vocabulary overlap; the sequence component captures word
    order so that pages with identical vocabularies but different arrangements
    receive lower scores.  The blend is 60 % Jaccard + 40 % sequence ratio.
    """
    jac = _jaccard_similarity(set_a, set_b)
    if jac == 0.0:
        return 0.0
    # Compute lightweight sequence ratio only when Jaccard is non-trivial
    if not words_a or not words_b:
        return jac
    # SequenceMatcher is expensive for very long pages; cap input length
    max_words = 200
    seq_a = words_a[:max_words]
    seq_b = words_b[:max_words]
    seq_ratio = SequenceMatcher(None, seq_a, seq_b, autojunk=False).ratio()
    return 0.6 * jac + 0.4 * seq_ratio


def align_pages(
    old: Sequence[ExtractedPage],
    new: Sequence[ExtractedPage],
    strategy: AlignmentStrategy,
    threshold: float,
    lookahead: int,
) -> list[PagePair]:
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
    n, m = len(old), len(new)

    # 1. Exact fingerprints are paired first (greedy left-to-right)
    by_signature: dict[str, deque[int]] = defaultdict(deque)
    for j, page in enumerate(new):
        by_signature[page.signature].append(j)

    matched: dict[int, int] = {}
    used: set[int] = set()

    for i, page in enumerate(old):
        candidates = by_signature[page.signature]
        if candidates:
            j = candidates.popleft()
            matched[i] = j
            used.add(j)

    # Pre-compute word sets and word lists
    old_sets = [_page_word_set(p) for p in old]
    new_sets = [_page_word_set(p) for p in new]
    old_words = [_page_word_list(p) for p in old]
    new_words = [_page_word_list(p) for p in new]

    # 2. Candidate generation for unmatched pages
    unmatched_old = [i for i in range(n) if i not in matched]
    unmatched_new = [j for j in range(m) if j not in used]

    candidates_list: list[tuple[float, int, int]] = []

    if n * m <= 100_000:
        # Small doc: Exhaustive pairwise Jaccard
        for i in unmatched_old:
            set_i = old_sets[i]
            for j in unmatched_new:
                score = _jaccard_similarity(set_i, new_sets[j])
                if score >= threshold:
                    candidates_list.append((score, i, j))
    else:
        # Large doc: Inverted index candidate generation
        # Document frequency over new pages
        df: dict[str, int] = defaultdict(int)
        for j in range(m):
            for w in new_sets[j]:
                df[w] += 1

        max_df = max(10, m // 20)
        rare_words_index: dict[str, list[int]] = defaultdict(list)
        for j in range(m):
            for w in new_sets[j]:
                if df[w] <= max_df:
                    rare_words_index[w].append(j)

        # Adaptive window: scale with document size difference
        window = max(10, abs(n - m) + 5)

        for i in unmatched_old:
            cand_j: set[int] = set()
            # Inverted index search
            for w in old_sets[i]:
                if df[w] <= max_df:
                    for j in rare_words_index[w]:
                        if j not in used:
                            cand_j.add(j)

            # Adaptive index window around position i
            window_start = max(0, i - window)
            window_end = min(m, i + window)
            for j in range(window_start, window_end):
                if j not in used:
                    cand_j.add(j)

            # Sort candidates deterministically, prioritize closeness
            cand_j_list = sorted(cand_j, key=lambda j: (abs(i - j), j))[:50]
            set_i = old_sets[i]
            for j in cand_j_list:
                score = _jaccard_similarity(set_i, new_sets[j])
                if score >= threshold:
                    candidates_list.append((score, i, j))

    # Pair candidates greedily by score desc, distance asc, old_i asc, new_j asc
    candidates_list.sort(key=lambda item: (-item[0], abs(item[1] - item[2]), item[1], item[2]))
    for score, i, j in candidates_list:
        if i not in matched and j not in used:
            matched[i] = j
            used.add(j)

    # NO POSITIONAL FALLBACK PAIRING (as required by Fix 1)

    # 3. Weighted Longest Increasing Subsequence (LIS) for Move Detection
    # Matched pairs sorted by old index i ascending
    matched_pairs = sorted(matched.items())
    pair_scores: list[tuple[int, int, float]] = []
    for i, j in matched_pairs:
        # Use the improved page_similarity that blends Jaccard + sequence order
        sim = _page_similarity(old_sets[i], new_sets[j], old_words[i], new_words[j])
        w = sim ** 4
        pair_scores.append((i, j, w))

    # O(E log E) Weighted LIS using Fenwick Tree with parent tracking
    n_pairs = len(pair_scores)
    dp = [0.0] * n_pairs
    parent = [-1] * n_pairs

    if n_pairs > 0:
        # Coordinate compression on new_j values
        unique_j = sorted(set(j for _, j, _ in pair_scores))
        j_to_rank = {j: r for r, j in enumerate(unique_j)}
        num_ranks = len(unique_j)

        # Fenwick Tree with (value, pair_index) tracking
        bit = FenwickTree(num_ranks)

        for idx in range(n_pairs):
            i, j, w = pair_scores[idx]
            rank = j_to_rank[j]

            # Query max DP for all ranks strictly less than current rank
            if rank > 0:
                best_prev_val, best_prev_idx = bit.query(rank - 1)
            else:
                best_prev_val, best_prev_idx = 0.0, -1

            dp[idx] = w + best_prev_val
            parent[idx] = best_prev_idx

            # Update Fenwick tree at current rank with (dp[idx], idx)
            bit.update(rank, dp[idx], idx)

    # Reconstruct LIS chain
    in_chain: set[int] = set()  # set of old_i that are in the LIS chain
    if n_pairs > 0:
        best_end = max(range(n_pairs), key=lambda x: dp[x])
        curr = best_end
        while curr != -1:
            in_chain.add(pair_scores[curr][0])
            curr = parent[curr]

    # Matched pairs NOT in the LIS chain are flagged as moved!
    keyed: list[tuple[float, PagePair]] = []
    reverse_matched = {j: i for i, j in matched.items()}

    for i in range(n):
        if i in matched:
            j = matched[i]
            is_moved = (i not in in_chain)
            keyed.append((float(i), PagePair(i, j, moved=is_moved)))
        else:
            keyed.append((float(i), PagePair(i, None)))

    for j in range(m):
        if j not in used:
            before = [reverse_matched[k] for k in range(j - 1, -1, -1) if k in reverse_matched]
            keyed.append(((before[0] + 0.5) if before else -0.5, PagePair(None, j)))

    return [pair for _, pair in sorted(keyed, key=lambda item: item[0])]


def _sequential(old: Sequence[ExtractedPage], new: Sequence[ExtractedPage], threshold: float, lookahead: int) -> list[PagePair]:
    pairs: list[PagePair] = []
    i = j = 0
    old_sets = [_page_word_set(p) for p in old]
    new_sets = [_page_word_set(p) for p in new]

    while i < len(old) and j < len(new):
        if _jaccard_similarity(old_sets[i], new_sets[j]) >= threshold:
            pairs.append(PagePair(i, j)); i += 1; j += 1; continue
        new_anchor = next((k for k in range(j + 1, min(len(new), j + lookahead + 1)) if _jaccard_similarity(old_sets[i], new_sets[k]) >= threshold), None)
        old_anchor = next((k for k in range(i + 1, min(len(old), i + lookahead + 1)) if _jaccard_similarity(old_sets[k], new_sets[j]) >= threshold), None)
        if new_anchor is not None and (old_anchor is None or new_anchor - j <= old_anchor - i):
            pairs.extend(PagePair(None, k) for k in range(j, new_anchor)); j = new_anchor
        elif old_anchor is not None:
            pairs.extend(PagePair(k, None) for k in range(i, old_anchor)); i = old_anchor
        else:
            pairs.append(PagePair(i, j)); i += 1; j += 1
    pairs.extend(PagePair(k, None) for k in range(i, len(old)))
    pairs.extend(PagePair(None, k) for k in range(j, len(new)))
    return pairs
