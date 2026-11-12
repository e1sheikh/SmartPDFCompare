"""Deep edge case and regression suite for Smart-PDF-Compare."""
from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest

from smart_pdf_compare import (
    ChangeType,
    ComparisonOptions,
    ComparisonResult,
    ConfigurationError,
    InvalidOptionError,
    InvalidPDFError,
    VisualComparisonOptions,
    compare_pdfs,
    compare_visual_documents,
    compare_visual_pdfs,
    highlight_differences,
)
from smart_pdf_compare.alignment import FenwickTree, align_pages
from smart_pdf_compare.cli import main
from smart_pdf_compare.diff import compare_words
from smart_pdf_compare.exceptions import (
    EncryptedPDFError,
    InputOverwriteError,
    MissingTextLayerError,
    OutputExistsError,
    PDFComparisonError,
)
from smart_pdf_compare.extraction import ExtractedPage, Word, extract_document
from smart_pdf_compare.normalization import NormalizationOptions, normalize_token


def test_exception_hierarchy():
    """Verify all exceptions derive from PDFComparisonError appropriately."""
    assert issubclass(InvalidOptionError, ConfigurationError)
    assert issubclass(ConfigurationError, PDFComparisonError)
    assert issubclass(InvalidPDFError, PDFComparisonError)
    assert issubclass(EncryptedPDFError, InvalidPDFError)
    assert issubclass(MissingTextLayerError, PDFComparisonError)
    assert issubclass(OutputExistsError, PDFComparisonError)
    assert issubclass(OutputExistsError, FileExistsError)
    assert issubclass(InputOverwriteError, PDFComparisonError)


def test_fenwick_tree_weighted_lis():
    """Directly test FenwickTree query, update, and parent tracking."""
    bit = FenwickTree(5)
    # Query empty
    val, idx = bit.query(4)
    assert val == 0.0 and idx == -1

    # Update with increasing values
    bit.update(0, 1.5, 10)
    bit.update(2, 4.0, 20)
    bit.update(4, 2.0, 30)

    # Prefix query [0..0]
    val, idx = bit.query(0)
    assert val == 1.5 and idx == 10

    # Prefix query [0..1]
    val, idx = bit.query(1)
    assert val == 1.5 and idx == 10

    # Prefix query [0..3]
    val, idx = bit.query(3)
    assert val == 4.0 and idx == 20

    # Prefix query [0..4]
    val, idx = bit.query(4)
    assert val == 4.0 and idx == 20  # 4.0 is max among 1.5, 4.0, 2.0


def test_large_document_lis_alignment(pdf_factory):
    """Stress test alignment with 30 pages and middle insertions."""
    old_pages = [f"Chapter {i} contains specific details about section {i}" for i in range(1, 31)]
    new_pages = list(old_pages)
    # Insert at index 10 and 20
    new_pages.insert(10, "Inserted chapter between 10 and 11 with distinct text")
    new_pages.insert(21, "Second inserted chapter between 20 and 21 with new text")

    old_pdf = pdf_factory("large_old.pdf", old_pages)
    new_pdf = pdf_factory("large_new.pdf", new_pages)

    res = compare_pdfs(old_pdf, new_pdf, options=ComparisonOptions(alignment="content"))
    assert res.summary.added_pages == 2
    assert res.summary.removed_pages == 0
    assert res.summary.modified_pages == 0
    assert len(res.differences) == 2
    assert all(d.change_type == ChangeType.PAGE_ADDED for d in res.differences)


def test_header_footer_zone_height_in_points(tmp_path):
    """Verify header_height and footer_height > 1.0 are treated as absolute points."""
    doc = pymupdf.open()
    p = doc.new_page(width=300, height=500)
    # Visible height is 500.
    # If header_height is 50.0 points, y=30 is inside, y=70 is outside.
    p.insert_text((36, 30), "06/27/2025")
    p.insert_text((36, 70), "06/27/2025")  # body
    p.insert_text((36, 470), "18:08:30")   # footer inside (500 - 50 = 450)
    old_path = tmp_path / "pts_old.pdf"
    doc.save(old_path)
    doc.close()

    doc2 = pymupdf.open()
    p2 = doc2.new_page(width=300, height=500)
    p2.insert_text((36, 30), "10/15/2025")  # header differs
    p2.insert_text((36, 70), "06/27/2025")  # body same
    p2.insert_text((36, 470), "20:00:00")   # footer differs
    new_path = tmp_path / "pts_new.pdf"
    doc2.save(new_path)
    doc2.close()

    opts = ComparisonOptions(
        ignore_header_footer_dates=True,
        header_height=50.0,  # 50 points
        footer_height=50.0,  # 50 points
    )
    res = compare_pdfs(old_path, new_path, options=opts)
    assert res.is_identical
    assert res.words_ignored > 0


def test_header_footer_270_degree_rotation(tmp_path):
    """Test 270 degree rotated page zone detection."""
    # 270 degree rotation:
    # Visible width = 300, visible height = 400
    doc_old = pymupdf.open()
    p_old = doc_old.new_page(width=400, height=300)
    p_old.set_rotation(270)
    # Visible footer is near visible y=370..400
    # For rot=270: vis_x = unrotated_y, vis_y = 400 - unrotated_x
    # So unrotated_x = 400 - 370 = 30 gives visual y = 370!
    p_old.insert_text((30, 50), "06/27/2025")
    p_old.insert_text((200, 50), "Middle Body Content")
    old_path = tmp_path / "rot270_old.pdf"
    doc_old.save(old_path)
    doc_old.close()

    doc_new = pymupdf.open()
    p_new = doc_new.new_page(width=400, height=300)
    p_new.set_rotation(270)
    p_new.insert_text((30, 50), "10/15/2025")
    p_new.insert_text((200, 50), "Middle Body Content")
    new_path = tmp_path / "rot270_new.pdf"
    doc_new.save(new_path)
    doc_new.close()

    opts = ComparisonOptions(ignore_header_footer_dates=True, footer_height=0.15)
    res = compare_pdfs(old_path, new_path, options=opts)
    assert res.is_identical
    assert res.words_ignored > 0


def test_header_footer_zero_height(tmp_path):
    """header_height=0 and footer_height=0 effectively disables zone filtering."""
    doc = pymupdf.open()
    p = doc.new_page(width=300, height=300)
    p.insert_text((36, 15), "06/27/2025")
    old_p = tmp_path / "zero_old.pdf"
    doc.save(old_p)
    doc.close()

    doc2 = pymupdf.open()
    p2 = doc2.new_page(width=300, height=300)
    p2.insert_text((36, 15), "10/15/2025")
    new_p = tmp_path / "zero_new.pdf"
    doc2.save(new_p)
    doc2.close()

    opts = ComparisonOptions(
        ignore_header_footer_dates=True,
        header_height=0.0,
        footer_height=0.0,
    )
    res = compare_pdfs(old_p, new_p, options=opts)
    # Because zone height is 0, nothing was in zone -> differences reported!
    assert not res.is_identical
    assert res.words_ignored == 0


def test_output_overwrite_safeguards(pdf_factory, tmp_path):
    """Verify OutputExistsError and InputOverwriteError protections."""
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    old = pdf_factory("old.pdf", ["text a"])
    new = pdf_factory("new.pdf", ["text b"])

    existing_file = out_dir / "original_highlighted.pdf"
    existing_file.write_text("existing content")

    # Should refuse overwrite with overwrite=False
    with pytest.raises(FileExistsError):
        highlight_differences(old, new, out_dir, overwrite=False)

    # Should succeed with overwrite=True
    outputs = highlight_differences(old, new, out_dir, overwrite=True)
    assert outputs.original.exists()

    # Refuse to overwrite input files when an input file matches the target output path
    clashing_old = pdf_factory("original_highlighted.pdf", ["source text"])
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        highlight_differences(clashing_old, new, clashing_old.parent, overwrite=True)


def test_visual_dimension_insignificant_tolerance(pdf_factory):
    """1px or 2px differences do not falsely report visual differences."""
    # 300x200 vs 301x201 (difference of 1px is <= 2px tolerance)
    old = pdf_factory("v_old.pdf", ["identical visual text"], width=300, height=200)
    new = pdf_factory("v_new.pdf", ["identical visual text"], width=301, height=201)

    res = compare_visual_pdfs(old, new)
    assert res.pages[0].dimension_mismatch is True
    # Insignificant dimension difference should NOT trigger visually_different
    assert res.pages[0].visually_different is False
    assert res.is_identical is True

    # 300x200 vs 310x200 (difference of 10px is significant)
    new_big = pdf_factory("v_big.pdf", ["identical visual text"], width=310, height=200)
    res_big = compare_visual_pdfs(old, new_big)
    assert res_big.pages[0].dimension_mismatch is True
    assert res_big.pages[0].visually_different is True
    assert res_big.is_identical is False


def test_cli_error_and_stdout_json(pdf_factory, tmp_path, capsys):
    """Test CLI exit codes: 2 on invalid options, --json - writes only JSON to stdout."""
    old = pdf_factory("cli1.pdf", ["content 1"])
    new = pdf_factory("cli2.pdf", ["content 2"])

    # Invalid regex in --ignore-pattern
    ret = main([str(old), str(new), "--ignore-pattern", "[invalid"])
    assert ret == 2

    # Negative header height
    ret = main([str(old), str(new), "--header-height", "-0.5"])
    assert ret == 2

    # --json - writes valid JSON payload to stdout
    ret = main([str(old), str(new), "--json", "-"])
    captured = capsys.readouterr()
    assert ret == 1
    data = json.loads(captured.out)
    assert "is_identical" in data
    assert "summary" in data
    assert "words_ignored" in data
