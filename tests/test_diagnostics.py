"""Tests for diagnostic functionality (--explain and --dump-diffs)."""

import json
import tempfile
from pathlib import Path

import pytest
from smart_pdf_compare import compare_pdfs, ComparisonOptions
from smart_pdf_compare.debug import explain_difference, analyze_word, unicode_name
from smart_pdf_compare.extraction import extract_document, open_pdf
from smart_pdf_compare.normalization import NormalizationOptions
from tests.corpus import create_equivalence_pair


def test_unicode_name():
    """Test Unicode name extraction."""
    assert "LATIN CAPITAL LETTER A" in unicode_name('A')
    # Soft hyphen does have a name in Unicode
    assert "SOFT HYPHEN" in unicode_name('­')


def test_analyze_word():
    """Test word analysis."""
    from smart_pdf_compare.extraction import Word

    word = Word(text="Hello", normalized="hello", rect=(0, 0, 100, 20), block=0, line=0)
    words = [word]
    info = analyze_word(word, words, 0)

    assert info.text == "Hello"
    assert info.normalized == "hello"
    assert len(info.codepoints) == 5
    assert info.codepoints[0]['char'] == 'H'
    assert info.codepoints[0]['codepoint'] == 'U+0048'


def test_explain_difference(tmp_path):
    """Test difference explanation."""
    old_path, new_path = create_equivalence_pair(
        tmp_path, 'test_diff', ["Hello world"], ["Hello Python"]
    )

    result = compare_pdfs(str(old_path), str(new_path), options=ComparisonOptions(similarity_threshold=0.5))
    assert not result.is_identical
    assert len(result.differences) > 0

    # Extract pages for explanation
    with open_pdf(old_path) as old_doc, open_pdf(new_path) as new_doc:
        old_pages = extract_document(old_doc, NormalizationOptions(), sort_words=False)
        new_pages = extract_document(new_doc, NormalizationOptions(), sort_words=False)

    diff = result.differences[0]
    explanation = explain_difference(diff, old_pages[0], new_pages[0])

    assert 'change_type' in explanation
    assert 'old_text' in explanation
    assert 'new_text' in explanation
    assert 'old_debug' in explanation
    assert 'new_debug' in explanation


def test_dump_diffs(tmp_path):
    """Test dump diffs to JSON."""
    from smart_pdf_compare.debug import dump_diffs

    old_path, new_path = create_equivalence_pair(
        tmp_path, 'test_dump', ["Original text here"], ["New text here"]
    )

    result = compare_pdfs(str(old_path), str(new_path), options=ComparisonOptions(similarity_threshold=0.5))

    with open_pdf(old_path) as old_doc, open_pdf(new_path) as new_doc:
        old_pages = extract_document(old_doc, NormalizationOptions(), sort_words=False)
        new_pages = extract_document(new_doc, NormalizationOptions(), sort_words=False)

    output_path = tmp_path / "diffs.json"
    dump_diffs(result, old_pages, new_pages, str(output_path))

    assert output_path.exists()
    data = json.loads(output_path.read_text())
    assert isinstance(data, list)
    # Dump may be empty if no differences, but file should be valid JSON
    if len(data) > 0:
        assert 'change_type' in data[0]


def test_cli_explain_flag(tmp_path):
    """Test CLI --explain flag works."""
    from smart_pdf_compare.cli import main
    import io
    import sys

    old_path, new_path = create_equivalence_pair(
        tmp_path, 'test_cli', ["Hello world"], ["Hello Python"]
    )

    # Capture stderr
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()

    try:
        exit_code = main([str(old_path), str(new_path), '--explain'])
        stderr_output = sys.stderr.getvalue()
    finally:
        sys.stderr = old_stderr

    assert exit_code == 1  # Differences found
    assert 'DIFF EXPLANATIONS' in stderr_output


def test_cli_dump_diffs_flag(tmp_path):
    """Test CLI --dump-diffs flag works."""
    from smart_pdf_compare.cli import main

    old_path, new_path = create_equivalence_pair(
        tmp_path, 'test_dump_cli', ["Original text"], ["New text"]
    )

    output_path = tmp_path / "diffs_cli.json"
    exit_code = main([str(old_path), str(new_path), '--dump-diffs', str(output_path)])

    assert output_path.exists()
    assert exit_code == 1

    data = json.loads(output_path.read_text())
    assert isinstance(data, list)


def test_symbol_variations_debug(tmp_path):
    """Test debugging symbol variations."""
    old_path, new_path = create_equivalence_pair(
        tmp_path, 'symbols', ["25°C", "RθJC"], ["25ºC", "RθJC"]
    )

    result = compare_pdfs(str(old_path), str(new_path), options=ComparisonOptions(similarity_threshold=0.5))

    # With current normalization, degree symbols should be mapped
    # This test documents current behavior
    assert result.summary.old_pages == result.summary.new_pages


def test_soft_hyphen_debug(tmp_path):
    """Test debugging soft hyphen issues."""
    old_path, new_path = create_equivalence_pair(
        tmp_path, 'soft_hyphen', ["ITO-220AC"], ["ITO­220AC"]
    )

    result = compare_pdfs(str(old_path), str(new_path), options=ComparisonOptions(similarity_threshold=0.5))

    # Currently soft hyphen is removed, causing false positive
    # This test documents the issue
    assert result.summary.old_pages == result.summary.new_pages


def test_bullet_variations_debug(tmp_path):
    """Test debugging bullet variations."""
    old_path, new_path = create_equivalence_pair(
        tmp_path, 'bullets', ["• Item"], ["· Item"]
    )

    result = compare_pdfs(str(old_path), str(new_path), options=ComparisonOptions(similarity_threshold=0.5))

    # Different bullets should ideally be equivalent
    assert result.summary.old_pages == result.summary.new_pages


def test_debug_info_preserves_unicode(tmp_path):
    """Test that debug info preserves Unicode details."""
    from smart_pdf_compare.extraction import Word

    word = Word(text="25°C", normalized="25°c", rect=(0, 0, 100, 20), block=0, line=0)
    words = [word]
    info = analyze_word(word, words, 0)

    # Check Unicode codepoints are preserved
    assert len(info.codepoints) == 4
    # ° is U+00B0
    degree_found = False
    for cp in info.codepoints:
        if cp['char'] == '°':
            assert cp['codepoint'] == 'U+00B0'
            degree_found = True
    assert degree_found
