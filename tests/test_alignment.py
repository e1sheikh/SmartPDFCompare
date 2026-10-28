from smart_pdf_compare import ChangeType, ComparisonOptions, compare_pdfs


def test_content_alignment_handles_middle_insertion(pdf_factory):
    old = pdf_factory("old.pdf", ["alpha", "bravo", "charlie"])
    new = pdf_factory("new.pdf", ["alpha", "inserted", "bravo", "charlie"])
    result = compare_pdfs(old, new)
    assert result.summary.added_pages == 1
    assert [item.change_type for item in result.differences] == [ChangeType.PAGE_ADDED]


def test_sequential_and_index_alignment(pdf_factory):
    old = pdf_factory("old.pdf", ["alpha", "bravo"])
    new = pdf_factory("new.pdf", ["alpha", "inserted", "bravo"])
    sequential = compare_pdfs(old, new, options=ComparisonOptions(alignment="sequential"))
    indexed = compare_pdfs(old, new, options=ComparisonOptions(alignment="index"))
    assert sequential.summary.added_pages == 1
    assert indexed.summary.modified_pages >= 1


def test_moved_page_is_reported_not_hidden(pdf_factory):
    old = pdf_factory("old.pdf", ["alpha", "bravo", "charlie"])
    new = pdf_factory("new.pdf", ["bravo", "alpha", "charlie"])
    result = compare_pdfs(old, new)
    assert result.summary.moved_pages >= 1
    assert not result.is_identical
    assert any(item.change_type is ChangeType.PAGE_MOVED for item in result.differences)
