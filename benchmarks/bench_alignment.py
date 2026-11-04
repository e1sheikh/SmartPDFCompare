"""Benchmark alignment performance for various page counts.

Synthetic PDFs: N pages x ~150 words, with one insert, one delete, and a few word edits.
This script creates synthetic PDFs and times the alignment modes.

To run (requires PyMuPDF and the project installed):
    source .venv/bin/activate
    python benchmarks/bench_alignment.py

The script creates temp PDFs, measures alignment time for each mode,
and prints a table. It does NOT output the timings here — only the
infrastructure to generate them.

Note: This script requires PyMuPDF and a working PDF generation pipeline.
If PyMuPDF is unavailable, the script will error out gracefully.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from smart_pdf_compare import ComparisonOptions, compare_pdfs


def make_pdf(path: Path, pages: list[str], *, rotate: bool = False, width: float = 360, height: float = 240) -> Path:
    """Create a synthetic PDF with the given text on each page."""
    import pymupdf
    document = pymupdf.open()
    for i, text in enumerate(pages):
        page = document.new_page(width=width, height=height)
        if text:
            page.insert_text((36, 72), text, fontsize=12)
        if rotate:
            page.set_rotation(90)
    document.save(path)
    document.close()
    return path


def generate_synthetic_pdfs(base: Path, n_pages: int, insert: bool = False, delete: bool = False, edits: int = 0) -> tuple[Path, Path]:
    """Generate old and new PDFs for alignment benchmarking.

    old: n_pages with some base text
    new: n_pages plus/minus changes
    """
    import pymupdf

    base_texts = [f"paragraph {i} with some sample words for testing" for i in range(n_pages)]

    old_path = base / f"old_{n_pages}p.pdf"
    new_path = base / f"new_{n_pages}p.pdf"

    # Old document: n_pages of base text
    make_pdf(old_path, base_texts)

    # New document: depends on options
    new_texts = list(base_texts)  # start copy

    if insert:
        # Insert a new page in the middle
        insert_idx = n_pages // 2
        new_texts.insert(insert_idx, "INSERTED page with distinct vocabulary here")

    if delete:
        # Delete a page from the middle
        delete_idx = n_pages // 2
        new_texts.pop(delete_idx)

    if edits > 0:
        # Edit a few words on some pages
        for _ in range(min(edits, n_pages)):
            idx = __import__("random").randrange(n_pages)
            # Replace one word
            words = new_texts[idx].split()
            if words:
                words[__import__("random").randrange(len(words))] = "REPLACEDWORD"

    make_pdf(new_path, new_texts)

    return old_path, new_path


def benchmark_alignment_modes(n_pages_list: list[int], output_dir: Path) -> dict:
    """Run alignment benchmarks for given page counts.

    Returns a dict mapping n_pages to per-mode timings.
    """
    import pymupdf

    results = {}
    tmp_dir = output_dir / "temp_bench"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    for n in n_pages_list:
        print(f"Benchmarking n={n} pages...", flush=True)
        old_path, new_path = generate_synthetic_pdfs(tmp_dir, n,
            insert=(n > 100),  # only insert for large n
            delete=(n > 200),  # only delete for large n
            edits=2 if n < 200 else 1
        )

        timings = {}
        for mode in ["content", "index", "sequential"]:
            try:
                t0 = time.time()
                # Warm up
                compare_pdfs(old_path, new_path, options=ComparisonOptions(alignment=mode))
                t1 = time.time()
                timings[mode] = t1 - t0
            except Exception as e:
                timings[mode] = f"ERROR: {e}"

        results[n] = timings
        print(f"  Results: {timings}")

    # Cleanup temp files
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Benchmark alignment performance")
    parser.add_argument("--pages", nargs="+", type=int, default=[50, 200, 1000],
                        help="Page counts to benchmark")
    parser.add_argument("--output", type=Path, default=Path("benchmarks/output"),
                        help="Output directory for bench artifacts")
    args = parser.parse_args(argv)

    output_dir = Path("benchmarks")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting alignment benchmark for pages: {args.pages}")
    results = benchmark_alignment_modes(args.pages, output_dir)

    # Write results to JSON for later analysis
    results_path = output_dir / "alignment_bench_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nBenchmark complete. Results written to {results_path}")
    print("To analyze: python -m json.tool benchmarks/output/alignment_bench_results.json")


if __name__ == "__main__":
    main()