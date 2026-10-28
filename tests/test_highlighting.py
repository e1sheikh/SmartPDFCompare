import pymupdf
import pytest

from smart_pdf_compare import compare_pdfs, highlight_differences


def _annotation_types(path):
    with pymupdf.open(path) as document:
        return [annotation.type[1] for page in document for annotation in (page.annots() or ())]


def _annotation_rects(path):
    with pymupdf.open(path) as document:
        return [annotation.rect for page in document for annotation in (page.annots() or ())]


def test_highlight_mode_uses_actual_highlight_annotations_in_all_outputs(pdf_factory, tmp_path):
    old = pdf_factory("old.pdf", ["old value"])
    new = pdf_factory("new.pdf", ["new value"])
    outputs = highlight_differences(old, new, tmp_path / "out", include_report=True, style="highlight")
    assert outputs.original.exists() and outputs.revised.exists() and outputs.report and outputs.report.exists()
    with pymupdf.open(old) as source, pymupdf.open(outputs.original) as marked:
        assert source[0].first_annot is None
        assert marked[0].first_annot is not None
    assert _annotation_types(outputs.original) == ["Highlight"]
    assert _annotation_types(outputs.revised) == ["Highlight"]
    assert _annotation_types(outputs.report) == ["Highlight", "Highlight"]
    report_rects = _annotation_rects(outputs.report)
    assert report_rects[0].x1 < 360
    assert report_rects[1].x0 > 360


def test_box_mode_uses_square_annotations_in_all_outputs(pdf_factory, tmp_path):
    old = pdf_factory("old.pdf", ["old value"])
    new = pdf_factory("new.pdf", ["new value"])
    outputs = highlight_differences(old, new, tmp_path / "out", include_report=True, style="box")
    assert outputs.report
    assert _annotation_types(outputs.original) == ["Square"]
    assert _annotation_types(outputs.revised) == ["Square"]
    assert _annotation_types(outputs.report) == ["Square", "Square"]


@pytest.mark.parametrize("style, expected", [("highlight", "Highlight"), ("box", "Square")])
@pytest.mark.parametrize("old_pages,new_pages", [(["kept"], ["inserted", "kept"]), (["removed", "kept"], ["kept"])])
def test_report_handles_unpaired_pages_in_both_modes(pdf_factory, tmp_path, style, expected, old_pages, new_pages):
    old = pdf_factory("old.pdf", old_pages)
    new = pdf_factory("new.pdf", new_pages)
    outputs = highlight_differences(old, new, tmp_path / style, include_report=True, style=style)
    assert outputs.report
    assert _annotation_types(outputs.report) == [expected]


def test_report_annotations_track_rotated_and_differently_sized_pages(pdf_factory, tmp_path):
    old = pdf_factory("old.pdf", ["old coordinate"], width=300, height=200)
    new = pdf_factory("new.pdf", ["new coordinate"], width=220, height=360, rotate=True)
    outputs = highlight_differences(old, new, tmp_path / "out", include_report=True, style="highlight")
    assert outputs.report
    with pymupdf.open(outputs.report) as report:
        page = report[0]
        annotations = list(page.annots() or ())
        words = {word[4]: pymupdf.Rect(word[:4]) for word in page.get_text("words")}
        assert len(annotations) == 2
        assert annotations[0].rect.intersects(words["old"])
        assert annotations[1].rect.intersects(words["new"])


def test_equal_documents_do_not_make_report(pdf_factory, tmp_path):
    old = pdf_factory("old.pdf", ["same"])
    new = pdf_factory("new.pdf", ["same"])
    outputs = highlight_differences(old, new, tmp_path / "out", include_report=True)
    assert outputs.report is None
