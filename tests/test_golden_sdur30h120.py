import pytest
from pathlib import Path
from smart_pdf_compare import compare_pdfs

def test_sdur30h120_golden():
    gold_dir = Path(__file__).parent / "golden"
    old_path = gold_dir / "SDUR30H120_old.pdf"
    new_path = gold_dir / "SDUR30H120_new.pdf"
    if not (old_path.exists() and new_path.exists()):
        pytest.skip("Golden PDFs for SDUR30H120 are missing; skipping golden test")
    result = compare_pdfs(old_path, new_path)

    # Page 2 (index 1) holds the Maximum Ratings / Electrical Characteristics
    # tables; after canonicalization every glyph table value must match byte-for-byte
    # between the two datasheet revisions.
    page2_diffs = [d for d in result.differences if d.old_page == 2]
    msg = f"Page2 diffs (should be none - glyph/table values match): {page2_diffs}"
    assert len(page2_diffs) == 0, msg

    # Page 1 (index 0) holds Applications/Features boilerplate plus the genuine
    # content changes between revisions (package marking position, spelling).
    page1_diffs = [d for d in result.differences if d.old_page == 1]
    msg = f"Unexpected page1 diffs: {page1_diffs}"
    # Token grouping merges adjacent words on one line, so the expected diffs may
    # be reported as grouped replacements rather than single-token edits.
    expected_page1_texts = [
        # "ITO-220AC Anti parallel" -> "Antiparallel" (marking moved + spelling)
        ("replaced", "ITO-220AC Anti parallel", "Antiparallel"),
        # "- Free" -> "−free" (hyphenation/spacing change; minus sign U+2212)
        ("replaced", "- Free", "−free"),
        # Package marking added at new location
        ("added", "", "ITO-220AC"),
    ]
    for change_type, old_text, new_text in expected_page1_texts:
        assert any(
            d.change_type.value == change_type
            and d.old_text == old_text
            and d.new_text == new_text
            for d in page1_diffs
        ), f"Missing expected page-1 diff ({change_type}, {old_text!r}, {new_text!r}); got {page1_diffs}"
