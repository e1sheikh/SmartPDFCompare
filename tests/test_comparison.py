import pytest

from smart_pdf_compare import ChangeType, ComparisonOptions, MissingTextLayerError, compare_pdfs


def test_added_removed_and_replaced_words(pdf_factory):
    old = pdf_factory("old.pdf", ["The price is -1.5 dollars"])
    new = pdf_factory("new.pdf", ["The price is 2 dollars today"])
    result = compare_pdfs(old, new, options=ComparisonOptions(similarity_threshold=0.5))
    assert result.summary.added_words == 2
    assert result.summary.removed_words == 1
    assert any(item.change_type is ChangeType.REPLACED for item in result.differences)
    assert result.to_dict()["summary"]["modified_pages"] == 1


def test_identical_after_case_normalization(pdf_factory):
    old = pdf_factory("old.pdf", ["HELLO World"])
    new = pdf_factory("new.pdf", ["hello world"])
    assert compare_pdfs(old, new).is_identical


def test_scanned_or_textless_documents_return_unreliable(pdf_factory):
    old = pdf_factory("old.pdf", [""])
    new = pdf_factory("new.pdf", [""])
    result = compare_pdfs(old, new)
    assert result.reliable is False
    assert result.is_identical is False
    assert result.summary.differences == 0
    assert len(result.warnings) > 0
    assert "no extractable text" in result.warnings[0].lower()


def test_one_document_textless_returns_unreliable(pdf_factory):
    old = pdf_factory("old.pdf", ["some text here"])
    new = pdf_factory("new.pdf", [""])
    result = compare_pdfs(old, new)
    assert result.reliable is False
    assert result.is_identical is False
    assert len(result.warnings) > 0


def test_result_collection_can_be_truncated_but_counts_are_not(pdf_factory):
    old = pdf_factory("old.pdf", ["one two three four"])
    new = pdf_factory("new.pdf", ["a b c d"])
    result = compare_pdfs(old, new, options=ComparisonOptions(max_differences=0))
    assert result.truncated and not result.differences
    assert result.summary.differences > 0
