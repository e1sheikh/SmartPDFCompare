import pymupdf
import pytest

from smart_pdf_compare import ConfigurationError, VisualComparisonOptions, compare_visual_documents, compare_visual_pdfs


def test_identical_rendered_pages_are_identical(pdf_factory):
    old = pdf_factory("old.pdf", ["same rendering"])
    new = pdf_factory("new.pdf", ["same rendering"])
    result = compare_visual_pdfs(old, new)
    assert result.is_identical
    assert result.pages[0].changed_pixels == 0


@pytest.mark.parametrize("mode, field", [("side_by_side", "side_by_side_path"), ("diff_image", "diff_image_path")])
def test_visual_artifacts_and_changed_word(pdf_factory, tmp_path, mode, field):
    old = pdf_factory("old.pdf", ["old value"])
    new = pdf_factory("new.pdf", ["new value"])
    result = compare_visual_pdfs(old, new, options=VisualComparisonOptions(output_mode=mode), output_dir=tmp_path)
    page = result.pages[0]
    artifact = getattr(page, field)
    assert not result.is_identical and page.changed_pixels and page.difference_ratio
    assert artifact and __import__("pathlib").Path(artifact).exists()
    with pymupdf.open(artifact) as image_document:
        assert image_document.page_count == 1


def test_different_dimensions_and_unmatched_pages_are_reported(pdf_factory):
    old = pdf_factory("old.pdf", ["same", "removed"], width=300, height=200)
    new = pdf_factory("new.pdf", ["same"], width=360, height=240)
    result = compare_visual_pdfs(old, new)
    assert result.pages[0].dimension_mismatch
    assert result.pages[0].visually_different
    assert result.pages[1].old_page == 2 and result.pages[1].new_page is None


@pytest.mark.parametrize("mode, field", [("side_by_side", "side_by_side_path"), ("diff_image", "diff_image_path")])
def test_unmatched_pages_get_requested_visual_artifacts(pdf_factory, tmp_path, mode, field):
    old = pdf_factory("old.pdf", ["kept", "removed"])
    new = pdf_factory("new.pdf", ["kept"])
    result = compare_visual_pdfs(old, new, options=VisualComparisonOptions(output_mode=mode), output_dir=tmp_path)
    artifact = getattr(result.pages[1], field)
    assert artifact and __import__("pathlib").Path(artifact).is_file()
    assert result.pages[1].changed_pixels and result.pages[1].difference_ratio


def test_changed_graphics_are_detected(pdf_factory, tmp_path):
    old = pdf_factory("old.pdf", ["same"])
    new = pdf_factory("new.pdf", ["same"])
    graphic = tmp_path / "graphic.pdf"
    with pymupdf.open(new) as document:
        document[0].draw_line((30, 150), (260, 150), color=(1, 0, 0), width=3)
        document.save(graphic)
    result = compare_visual_pdfs(old, graphic)
    assert not result.is_identical
    assert result.pages[0].changed_pixels


def test_rotated_page_is_compared_and_dimension_change_is_explicit(pdf_factory):
    old = pdf_factory("old.pdf", ["same"], width=300, height=200)
    new = pdf_factory("new.pdf", ["same"], width=300, height=200, rotate=True)
    result = compare_visual_pdfs(old, new)
    assert result.pages[0].dimension_mismatch
    assert result.pages[0].visually_different


def test_threshold_and_reference_based_multi_document_comparison(pdf_factory):
    reference = pdf_factory("reference.pdf", ["base"])
    same = pdf_factory("same.pdf", ["base"])
    changed = pdf_factory("changed.pdf", ["changed"])
    options = VisualComparisonOptions(pixel_threshold=255)
    assert compare_visual_pdfs(reference, changed, options=options).is_identical
    batch = compare_visual_documents([reference, same, changed], options=VisualComparisonOptions())
    assert len(batch.comparisons) == 2
    assert batch.comparisons[0].is_identical and not batch.comparisons[1].is_identical
    assert not batch.is_identical


def test_output_mode_requires_output_directory(pdf_factory):
    old = pdf_factory("old.pdf", ["one"])
    new = pdf_factory("new.pdf", ["two"])
    with pytest.raises(ConfigurationError, match="output_dir"):
        compare_visual_pdfs(old, new, options=VisualComparisonOptions(output_mode="diff_image"))
