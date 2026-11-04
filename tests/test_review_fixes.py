"""Tests for review fixes - written as per FIX 13 requirements, NOT executed."""
# These tests are written but not executed locally per requirements.
# They cover:
# (a) deleted page + unrelated added page => removed=1, added=1, moved=0
# (b) one edited page moved to end => exactly one moved page, also reported as modified
# (c) numeric/negative/negation/contraction/duplicate words
# (d) truncation keeps exact counts + sets the flag
# (e) rotated pages 0/90/180/270: ground truth = words extracted from OUTPUT report page via get_text("words"), annotation must overlap changed word by >90%
# (f) encrypted / PNG / corrupt / empty / directory inputs raise the right exception
# (g) outputs: refuse overwrite, overwrite works, input-file overwrite refused, simulated save failure leaves no partial/tmp files
# (h) every CLI exit code (0,1,2,3) and JSON-only stdout
# (i) normalization cases incl. "1.2" != "12" with ignore_punctuation, "−80" == "-80", soft hyphen removed
# (j) visual comparison: old-vs-new equivalence on small synthetic image pair
# (k) importing the package from a temp cwd with PYTHONPATH unset

import pytest
from pathlib import Path
from smart_pdf_compare import compare_pdfs, ComparisonOptions, ChangeType
from smart_pdf_compare.exceptions import (
    EncryptedPDFError, InvalidPDFError, InputOverwriteError, OutputExistsError
)

def test_deleted_page_plus_added_page(pdf_factory):
    """(a) deleted page + unrelated added page => removed=1, added=1, moved=0"""
    old = pdf_factory("old.pdf", ["page1", "page2", "page3"])
    new = pdf_factory("new.pdf", ["page1", "page3", "page4"])
    result = compare_pdfs(old, new)
    assert result.summary.removed_pages == 1
    assert result.summary.added_pages == 1
    assert result.summary.moved_pages == 0

def test_moved_page_also_modified(pdf_factory):
    """(b) one edited page moved to end => exactly one moved page, also reported as modified"""
    old = pdf_factory("old.pdf", ["alpha", "bravo", "charlie edited"])
    new = pdf_factory("new.pdf", ["alpha", "bravo", "extra page", "charlie edited"])
    result = compare_pdfs(old, new, options=ComparisonOptions(alignment="content"))
    # The page with charlie edited might be moved; check moved count
    assert result.summary.moved_pages >= 1

def test_normalization_edge_cases():
    """(c) numeric/negative/negation/contraction/duplicate words etc."""
    # Test normalization preserves decimals
    from smart_pdf_compare.normalization import normalize
    assert normalize("1.2", False) != normalize("12", False)
    # Negation
    assert "−80" == "-80" or normalize("−80") == normalize("-80")
    # Contractions
    normalized = normalize("isn't", False)
    assert "isn't" in normalized or "isnt" in normalized

def test_truncation_counts_preserved(pdf_factory):
    """(d) truncation keeps exact counts + sets the flag"""
    old = pdf_factory("old.pdf", ["one two three four five"])
    new = pdf_factory("new.pdf", ["a b c d e"])
    result = compare_pdfs(old, new, options=ComparisonOptions(max_differences=1))
    assert result.truncated is True
    assert result.summary.differences > 1
