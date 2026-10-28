"""Command-line interface backed entirely by the public library API."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .api import ComparisonOptions, compare_pdfs
from .exceptions import PDFComparisonError
from .highlighting import highlight_differences


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="smart-pdf-compare", description="Compare the extracted text of two PDFs.")
    parser.add_argument("original", help="original PDF")
    parser.add_argument("revised", help="revised PDF")
    parser.add_argument("--alignment", choices=("content", "index", "sequential"), default="content")
    parser.add_argument("--threshold", type=float, default=0.60, help="page similarity threshold (0..1)")
    parser.add_argument("--lookahead", type=int, default=5, help="sequential resynchronization window")
    parser.add_argument("--max-differences", type=int, default=1000)
    parser.add_argument("--json", dest="json_path", type=Path, help="write JSON result")
    parser.add_argument("--output-dir", type=Path, help="write highlighted PDFs here")
    parser.add_argument("--style", choices=("highlight", "box"), default="highlight")
    parser.add_argument("--report", action="store_true", help="also write a side-by-side report")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        options = ComparisonOptions(args.alignment, args.threshold, args.lookahead, args.max_differences)
        result = compare_pdfs(args.original, args.revised, options=options)
        print(json.dumps(result.summary.__dict__, indent=2))
        print("Textually identical." if result.is_identical else f"{result.summary.differences} difference(s) detected.")
        if args.json_path:
            args.json_path.parent.mkdir(parents=True, exist_ok=True)
            args.json_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        if args.output_dir:
            outputs = highlight_differences(args.original, args.revised, args.output_dir, result=result, style=args.style, include_report=args.report)
            print(f"Highlighted PDFs: {outputs.original}, {outputs.revised}")
            if outputs.report:
                print(f"Difference report: {outputs.report}")
        return 0 if result.is_identical else 1
    except (PDFComparisonError, OSError, ValueError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
