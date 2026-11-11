import json
from pathlib import Path

import pymupdf
import pytest

from smart_pdf_compare import (
    ComparisonOptions,
    InvalidOptionError,
    compare_pdfs,
    highlight_differences,
)
from smart_pdf_compare.cli import main


def make_page_pdf(path: Path, pages: list[dict], width: float = 300, height: float = 300) -> Path:
    """Create a PDF with explicit header, body, and footer placements."""
    doc = pymupdf.open()
    for page_spec in pages:
        p = doc.new_page(width=width, height=height)
        rotation = page_spec.get("rotation", 0)
        if rotation:
            p.set_rotation(rotation)

        # Header: placed at visual top (e.g. y=15 on 300pt page)
        if "header" in page_spec and page_spec["header"]:
            p.insert_text(page_spec.get("header_pos", (36, 18)), page_spec["header"], fontsize=10)

        # Body: placed in visual middle (e.g. y=150)
        if "body" in page_spec and page_spec["body"]:
            p.insert_text(page_spec.get("body_pos", (36, 150)), page_spec["body"], fontsize=11)

        # Footer: placed at visual bottom (e.g. y=285)
        if "footer" in page_spec and page_spec["footer"]:
            p.insert_text(page_spec.get("footer_pos", (36, 285)), page_spec["footer"], fontsize=10)

    doc.save(path)
    doc.close()
    return path


def test_footer_datetime_differs_option_off_vs_on(tmp_path):
    """Footer date/time differs, everything else equal:
    option off -> differences reported; option on -> identical, words_ignored > 0, no annotations written.
    """
    old = make_page_pdf(
        tmp_path / "old.pdf",
        [{"header": "Company Report", "body": "Quarterly financial summary content", "footer": "06/27/2025 06:08PM | Page 2"}],
    )
    new = make_page_pdf(
        tmp_path / "new.pdf",
        [{"header": "Company Report", "body": "Quarterly financial summary content", "footer": "10/15/2025 06:22PM | Page 2"}],
    )

    # Option OFF: differences must be detected
    res_off = compare_pdfs(old, new)
    assert not res_off.is_identical
    assert res_off.summary.differences > 0
    assert res_off.words_ignored == 0

    # Option ON: identical, words_ignored > 0, no annotations written
    opts = ComparisonOptions(ignore_header_footer_dates=True)
    res_on = compare_pdfs(old, new, options=opts)
    assert res_on.is_identical
    assert res_on.summary.differences == 0
    assert res_on.words_ignored > 0
    assert res_on.summary.words_ignored > 0

    # Verify no annotations are written to output files
    out_dir = tmp_path / "highlight_out"
    outputs = highlight_differences(old, new, out_dir, result=res_on)
    with pymupdf.open(outputs.original) as doc_orig:
        assert doc_orig[0].first_annot is None
    with pymupdf.open(outputs.revised) as doc_rev:
        assert doc_rev[0].first_annot is None
    assert outputs.report is None


def test_body_date_changes_still_reported(tmp_path):
    """Same, but a date in the body text changes: still reported with the option on."""
    old = make_page_pdf(
        tmp_path / "old.pdf",
        [{"body": "Effective date of agreement is 06/27/2025 between parties", "footer": "06/27/2025"}],
    )
    new = make_page_pdf(
        tmp_path / "new.pdf",
        [{"body": "Effective date of agreement is 10/15/2025 between parties", "footer": "10/15/2025"}],
    )

    opts = ComparisonOptions(ignore_header_footer_dates=True)
    res = compare_pdfs(old, new, options=opts)
    # The body date modification MUST still be reported!
    assert not res.is_identical
    assert res.summary.modified_pages == 1
    assert any("06/27/2025" in d.old_text for d in res.differences)
    assert any("10/15/2025" in d.new_text for d in res.differences)
    # But the footer date was ignored
    assert res.words_ignored > 0


def test_header_date_ignored_and_footer_non_date_reported(tmp_path):
    """Header date ignored; footer changes in non-date text still reported."""
    old = make_page_pdf(
        tmp_path / "old.pdf",
        [{"header": "Generated on 2025-06-27", "body": "Document main content", "footer": "Version 1.0 Release"}],
    )
    new = make_page_pdf(
        tmp_path / "new.pdf",
        [{"header": "Generated on 2025-10-15", "body": "Document main content", "footer": "Version 2.0 Release"}],
    )

    opts = ComparisonOptions(ignore_header_footer_dates=True)
    res = compare_pdfs(old, new, options=opts)
    assert not res.is_identical
    # Header date difference was ignored
    assert not any("2025-06-27" in d.old_text for d in res.differences)
    # Footer version difference was reported
    assert any("1.0" in d.old_text for d in res.differences)
    assert res.words_ignored > 0


def test_time_with_split_ampm_handled(tmp_path):
    """'06:08 PM' split into two words handled."""
    old = make_page_pdf(
        tmp_path / "old.pdf",
        [{"header": "Report printed at 06:08 PM", "body": "Consistent content"}],
    )
    new = make_page_pdf(
        tmp_path / "new.pdf",
        [{"header": "Report printed at 11:45 AM", "body": "Consistent content"}],
    )

    opts = ComparisonOptions(ignore_header_footer_dates=True)
    res = compare_pdfs(old, new, options=opts)
    assert res.is_identical
    assert res.words_ignored >= 4  # 06:08, PM, 11:45, AM


def test_page_number_option(tmp_path):
    """Page-number option: 'Page 2' vs 'Page 3' ignored only when enabled."""
    old = make_page_pdf(
        tmp_path / "old.pdf",
        [{"body": "Same body paragraph", "footer": "Page 2"}],
    )
    new = make_page_pdf(
        tmp_path / "new.pdf",
        [{"body": "Same body paragraph", "footer": "Page 3"}],
    )

    # Option OFF (default)
    res_off = compare_pdfs(old, new)
    assert not res_off.is_identical

    # Dates only ON: page numbers still differ
    res_dates_only = compare_pdfs(old, new, options=ComparisonOptions(ignore_header_footer_dates=True))
    assert not res_dates_only.is_identical

    # Page numbers ON: identical
    res_pages_on = compare_pdfs(old, new, options=ComparisonOptions(ignore_header_footer_page_numbers=True))
    assert res_pages_on.is_identical
    assert res_pages_on.words_ignored > 0


def test_ignore_patterns_zone_only_and_validation(tmp_path):
    """ignore_patterns works only inside zones; invalid regex raises InvalidOptionError."""
    # Validation tests
    with pytest.raises(InvalidOptionError):
        ComparisonOptions(ignore_patterns=("[invalid regex",))

    with pytest.raises(InvalidOptionError):
        ComparisonOptions(header_height=-0.1)

    with pytest.raises(InvalidOptionError):
        ComparisonOptions(footer_height=-10.0)

    # Zone-only enforcement test
    old = make_page_pdf(
        tmp_path / "old.pdf",
        [{"header": "CONFIDENTIAL DRAFT", "body": "Draft agreement section one", "footer": "INTERNAL"}],
    )
    new = make_page_pdf(
        tmp_path / "new.pdf",
        [{"header": "CONFIDENTIAL FINAL", "body": "Final agreement section one", "footer": "INTERNAL"}],
    )

    opts = ComparisonOptions(ignore_patterns=(r"DRAFT|FINAL",))
    res = compare_pdfs(old, new, options=opts)

    # Header change ("DRAFT" vs "FINAL") was in zone, so ignored
    # Body change ("Draft" vs "Final") was OUTSIDE zone, so MUST be reported
    assert not res.is_identical
    assert any("draft" in d.old_text.lower() for d in res.differences)
    # The header difference was ignored
    assert not any("confidential" in d.old_text.lower() for d in res.differences)


def test_rotated_pages_footer_ignored_middle_not(tmp_path):
    """Rotated pages (90/270): footer date at the visual bottom is ignored; a date in the visual middle is not."""
    # Unrotated 400x300 page rotated 90 degrees clockwise -> visual width=300, visual height=400.
    # In rot=90: visual y = unrotated x.
    # To place in visual footer zone (visual y >= 330): unrotated x=330.
    # To place in visual body (visual y ~ 180): unrotated x=180.

    doc_old = pymupdf.open()
    p_old = doc_old.new_page(width=400, height=300)
    p_old.set_rotation(90)
    # Visual footer (visual y ~ 330-385)
    p_old.insert_text((330, 30), "06/27/2025")
    # Visual body (visual y ~ 180)
    p_old.insert_text((180, 30), "Fixed Body Text")
    old_path = tmp_path / "rot_old.pdf"
    doc_old.save(old_path)
    doc_old.close()

    doc_new = pymupdf.open()
    p_new = doc_new.new_page(width=400, height=300)
    p_new.set_rotation(90)
    # Visual footer differs
    p_new.insert_text((330, 30), "10/15/2025")
    p_new.insert_text((180, 30), "Fixed Body Text")
    new_path = tmp_path / "rot_new.pdf"
    doc_new.save(new_path)
    doc_new.close()

    opts = ComparisonOptions(ignore_header_footer_dates=True, footer_height=0.20)
    res = compare_pdfs(old_path, new_path, options=opts)
    assert res.is_identical
    assert res.words_ignored > 0

    # Now verify date in visual middle is NOT ignored on rotated page
    doc_mid = pymupdf.open()
    p_mid = doc_mid.new_page(width=400, height=300)
    p_mid.set_rotation(90)
    p_mid.insert_text((330, 30), "06/27/2025")
    # Visual middle date differs!
    p_mid.insert_text((180, 30), "Changed Date 12/12/2024")
    mid_path = tmp_path / "rot_mid.pdf"
    doc_mid.save(mid_path)
    doc_mid.close()

    res_mid = compare_pdfs(old_path, mid_path, options=opts)
    assert not res_mid.is_identical
    assert any("12/12/2024" in d.new_text for d in res_mid.differences)


def test_page_alignment_unaffected_by_differing_footer_dates(tmp_path):
    """Page alignment is unaffected by differing footer dates (pages still pair correctly when the option is on)."""
    old = make_page_pdf(
        tmp_path / "old.pdf",
        [
            {"header": "Doc Title", "body": "Alpha chapter content", "footer": "01/01/2025 | Page 1"},
            {"header": "Doc Title", "body": "Bravo chapter content", "footer": "01/01/2025 | Page 2"},
            {"header": "Doc Title", "body": "Charlie chapter content", "footer": "01/01/2025 | Page 3"},
        ],
    )
    new = make_page_pdf(
        tmp_path / "new.pdf",
        [
            {"header": "Doc Title", "body": "Alpha chapter content", "footer": "02/02/2025 | Page 1"},
            {"header": "Doc Title", "body": "Inserted chapter in between", "footer": "02/02/2025 | Page 2"},
            {"header": "Doc Title", "body": "Bravo chapter content", "footer": "02/02/2025 | Page 3"},
            {"header": "Doc Title", "body": "Charlie chapter content", "footer": "02/02/2025 | Page 4"},
        ],
    )

    opts = ComparisonOptions(
        ignore_header_footer_dates=True,
        ignore_header_footer_page_numbers=True,
    )
    res = compare_pdfs(old, new, options=opts)
    assert res.summary.added_pages == 1
    assert res.summary.removed_pages == 0
    assert res.summary.modified_pages == 0
    assert res.words_ignored > 0


def test_cli_flags_and_json_include_words_ignored(tmp_path):
    """CLI flags and JSON include words_ignored."""
    old = make_page_pdf(
        tmp_path / "cli_old.pdf",
        [{"body": "Body content text", "footer": "06/27/2025 | Page 2"}],
    )
    new = make_page_pdf(
        tmp_path / "cli_new.pdf",
        [{"body": "Body content text", "footer": "10/15/2025 | Page 2"}],
    )
    json_path = tmp_path / "result.json"

    exit_code = main([
        str(old),
        str(new),
        "--ignore-header-footer-dates",
        "--json",
        str(json_path),
    ])

    assert exit_code == 0
    assert json_path.is_file()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["is_identical"] is True
    assert "words_ignored" in data
    assert data["words_ignored"] > 0
    assert "words_ignored" in data["summary"]
    assert data["summary"]["words_ignored"] > 0
