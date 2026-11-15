"""Synthetic PDF test corpus generator for SmartPDFCompare.

Generates paired PDFs for testing equivalence transforms and real differences.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List, Tuple, Callable

import pymupdf


def make_pdf(path: Path, pages: List[str], *,
             rotate: List[int] | None = None,
             width: float = 360,
             height: float = 240,
             font_size: int = 12,
             font_name: str = "helv") -> Path:
    """Create a PDF with given page texts."""
    document = pymupdf.open()
    rotate = rotate or [0] * len(pages)

    for i, text in enumerate(pages):
        page = document.new_page(width=width, height=height)
        if text:
            # Wrap text
            y = 72
            for line in text.split('\n'):
                page.insert_text((36, y), line, fontsize=font_size, fontname=font_name)
                y += font_size + 4
        if rotate[i]:
            page.set_rotation(rotate[i])

    document.save(path)
    document.close()
    return path


def create_equivalence_pair(tmp_path: Path, test_name: str,
                          old_texts: List[str],
                          new_texts: List[str]) -> Tuple[Path, Path]:
    """Create paired PDFs for equivalence testing."""
    old_path = tmp_path / f"{test_name}_old.pdf"
    new_path = tmp_path / f"{test_name}_new.pdf"
    make_pdf(old_path, old_texts)
    make_pdf(new_path, new_texts)
    return old_path, new_path


def test_corpus_generator(tmp_path: Path) -> None:
    """Generate test corpus covering all equivalence and difference cases."""
    corpus = {}

    # Test 1: Hyphen variations
    # U+002D vs U+00AD vs U+2010/2011/2013
    corpus['hyphen_variations'] = create_equivalence_pair(
        tmp_path,
        'hyphen',
        ["ITO-220AC", "RθJC"],
        ["ITO­220AC", "RθJC"]  # Soft hyphen
    )

    # Test 2: Bullet variations
    corpus['bullet_variations'] = create_equivalence_pair(
        tmp_path,
        'bullet',
        ["• Item one", "• Item two"],
        ["· Item one", "● Item two"]  # Different bullets
    )

    # Test 3: Degree symbol variations
    corpus['degree_variations'] = create_equivalence_pair(
        tmp_path,
        'degree',
        ["25°C", "150°C/W"],
        ["25ºC", "150˚C/W"]  # Different degree symbols
    )

    # Test 4: Different tokenization (kerning gaps)
    corpus['tokenization'] = create_equivalence_pair(
        tmp_path,
        'tokenization',
        ["25°C", "Anti parallel"],
        ["25° C", "Antiparallel"]  # Should detect real space change only
    )

    # Test 5: Content stream order
    corpus['content_order'] = create_equivalence_pair(
        tmp_path,
        'content_order',
        ["Line 1\nLine 2\nLine 3"],
        ["Line 1\nLine 2\nLine 3"]  # Same content, different order if rendered
    )

    # Test 6: Line-end hyphenation
    corpus['hyphenation'] = create_equivalence_pair(
        tmp_path,
        'hyphenation',
        ["This is a long\nword-split here"],
        ["This is a long\nwordsplit here"]  # De-hyphenation
    )

    # Test 7: Page rotation
    corpus['rotation'] = create_equivalence_pair(
        tmp_path,
        'rotation',
        ["Page 1 content"],
        ["Page 1 content"]
    )
    # Rotate second PDF page
    doc = pymupdf.open(corpus['rotation'][1])
    doc[0].set_rotation(90)
    temp_path = tmp_path / "rotation_temp.pdf"
    doc.save(temp_path)
    doc.close()
    corpus['rotation'] = (corpus['rotation'][0], temp_path)

    # Test 8: Case sensitivity (mA vs MA)
    corpus['case_sensitivity'] = create_equivalence_pair(
        tmp_path,
        'case_sensitivity',
        ["mA current", "mV voltage"],
        ["MA current", "MV voltage"]  # Real technical change
    )

    # Test 9: Superscript/subscript preservation
    corpus['superscripts'] = create_equivalence_pair(
        tmp_path,
        'superscripts',
        ["m²", "H₂O", "E=mc²"],
        ["m²", "H₂O", "E=mc²"]  # Same superscripts
    )

    # Test 10: Real character changes
    corpus['real_changes'] = create_equivalence_pair(
        tmp_path,
        'real_changes',
        ["1.2", "25", "150°C", "°C", "mA"],
        ["12", "26", "125°C", "°F", "MA"]  # Real changes
    )

    # Test 11: Whitespace changes
    corpus['whitespace'] = create_equivalence_pair(
        tmp_path,
        'whitespace',
        ["Anti parallel", "sales@smc-diodes.com"],
        ["Antiparallel", "sales@ smc-diodes.com"]  # Space changes
    )

    # Test 12: Multi-page with alignment
    corpus['multi_page'] = create_equivalence_pair(
        tmp_path,
        'multi_page',
        ["Page 1", "Page 2", "Page 3"],
        ["Page 1", "Page 3", "Page 2"]  # Page reorder
    )

    # Test 13: Text additions/deletions
    corpus['additions'] = create_equivalence_pair(
        tmp_path,
        'additions',
        ["The price is $100"],
        ["The price is $100 today"]  # Addition
    )

    # Test 14: Symbol font variations (simulated)
    corpus['symbol_font'] = create_equivalence_pair(
        tmp_path,
        'symbol_font',
        ["RθJC", "μs", "Ω"],
        ["RθJC", "μs", "Ω"]  # Same symbols, different encoding
    )

    return corpus


def generate_all(tmp_path: Path = None) -> dict:
    """Generate complete test corpus."""
    if tmp_path is None:
        tmp_path = Path(tempfile.mkdtemp(prefix="smartpdf_test_corpus_"))

    return test_corpus_generator(tmp_path)
