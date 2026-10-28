import pymupdf

from smart_pdf_compare import compare_pdfs, highlight_differences


def test_highlights_are_valid_and_sources_unchanged(pdf_factory, tmp_path):
    old = pdf_factory("old.pdf", ["old value"])
    new = pdf_factory("new.pdf", ["new value"])
    outputs = highlight_differences(old, new, tmp_path / "out", include_report=True)
    assert outputs.original.exists() and outputs.revised.exists() and outputs.report and outputs.report.exists()
    with pymupdf.open(old) as source, pymupdf.open(outputs.original) as marked:
        assert source[0].first_annot is None
        assert marked[0].first_annot is not None
    with pymupdf.open(outputs.report) as report:
        assert report.page_count == 1


def test_equal_documents_do_not_make_report(pdf_factory, tmp_path):
    old = pdf_factory("old.pdf", ["same"])
    new = pdf_factory("new.pdf", ["same"])
    outputs = highlight_differences(old, new, tmp_path / "out", include_report=True)
    assert outputs.report is None
