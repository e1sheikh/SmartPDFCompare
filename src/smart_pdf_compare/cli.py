"""Command-line interface backed entirely by the public library API."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .api import ComparisonOptions, compare_pdfs
from .exceptions import InvalidPDFError, PDFComparisonError
from .highlighting import highlight_differences
from .visual import VisualComparisonOptions, compare_visual_documents, compare_visual_pdfs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smart-pdf-compare",
        description="Compare the extracted text of two PDFs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit codes:\n  0  Identical\n  1  Differences found\n  2  Error (invalid input, extraction, or configuration)\n  3  Unreliable comparison (document lacks text layer)",
    )
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
    parser.add_argument("--visual", action="store_true", help="also compare rendered page pixels")
    parser.add_argument("--visual-only", action="store_true", help="run rendered-page comparison without text extraction")
    parser.add_argument("--visual-mode", choices=("none", "side_by_side", "diff_image"), default="none")
    parser.add_argument("--visual-dpi", type=int, default=144)
    parser.add_argument("--visual-pixel-threshold", type=int, default=8)
    parser.add_argument("--visual-output-dir", type=Path, help="directory for visual PNG artifacts")
    parser.add_argument("--visual-input", action="append", default=[], help="additional PDF to compare against the visual reference")
    parser.add_argument("--visual-reference", type=int, default=0, help="zero-based reference index for --visual-input sets")
    parser.add_argument("--overwrite", action="store_true", help="overwrite existing output files")
    parser.add_argument("--ignore-header-footer-dates", action="store_true", help="ignore dates and times inside header and footer zones")
    parser.add_argument("--ignore-header-footer-page-numbers", action="store_true", help="ignore page numbers inside header and footer zones")
    parser.add_argument("--header-height", type=float, default=0.08, help="header zone height as fraction (<=1.0) or points (>1.0)")
    parser.add_argument("--footer-height", type=float, default=0.08, help="footer zone height as fraction (<=1.0) or points (>1.0)")
    parser.add_argument("--ignore-pattern", action="append", default=[], help="additional regex to ignore inside header/footer zones (repeatable)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        visual_requested = args.visual or args.visual_only or args.visual_mode != "none" or bool(args.visual_input)
        visual_result = None
        if visual_requested:
            visual_options = VisualComparisonOptions(
                dpi=args.visual_dpi,
                pixel_threshold=args.visual_pixel_threshold,
                output_mode=args.visual_mode,
            )
            visual_target = args.visual_output_dir or args.output_dir
            visual_inputs = [args.original, args.revised, *args.visual_input]
            if len(visual_inputs) == 2:
                visual_result = compare_visual_pdfs(
                    args.original, args.revised, options=visual_options, output_dir=visual_target
                )
                print("Visually identical." if visual_result.is_identical else "Visual differences detected.", file=sys.stderr)
            else:
                visual_result = compare_visual_documents(
                    visual_inputs,
                    reference=args.visual_reference,
                    options=visual_options,
                    output_dir=visual_target,
                )
                print(f"Compared {len(visual_result.comparisons)} PDF(s) against the visual reference.", file=sys.stderr)
            if args.visual_only:
                if args.json_path:
                    args.json_path.parent.mkdir(parents=True, exist_ok=True)
                    args.json_path.write_text(json.dumps(visual_result.to_dict(), indent=2), encoding="utf-8")
                identical = visual_result.is_identical if hasattr(visual_result, "is_identical") else all(
                    item.is_identical for item in visual_result.comparisons
                )
                return 0 if identical else 1
        options = ComparisonOptions(
            alignment=args.alignment,
            similarity_threshold=args.threshold,
            lookahead=args.lookahead,
            max_differences=args.max_differences,
            ignore_header_footer_dates=args.ignore_header_footer_dates,
            ignore_header_footer_page_numbers=args.ignore_header_footer_page_numbers,
            header_height=args.header_height,
            footer_height=args.footer_height,
            ignore_patterns=tuple(args.ignore_pattern),
        )
        result = compare_pdfs(args.original, args.revised, options=options)

        # JSON output to stdout ONLY if --json - is used
        json_output_to_stdout = args.json_path == Path("-")

        if json_output_to_stdout:
            # Only JSON to stdout
            payload = result.to_dict() if visual_result is None else {"text": result.to_dict(), "visual": visual_result.to_dict()}
            print(json.dumps(payload, indent=2))
            # Human-readable to stderr
            print(json.dumps(result.summary.__dict__, indent=2), file=sys.stderr)
            print("Textually identical." if result.is_identical else f"{result.summary.differences} difference(s) detected.", file=sys.stderr)
        else:
            # Normal output: human-readable to stdout
            print(json.dumps(result.summary.__dict__, indent=2))
            print("Textually identical." if result.is_identical else f"{result.summary.differences} difference(s) detected.")
            if args.json_path:
                args.json_path.parent.mkdir(parents=True, exist_ok=True)
                payload = result.to_dict() if visual_result is None else {"text": result.to_dict(), "visual": visual_result.to_dict()}
                args.json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        if args.output_dir:
            outputs = highlight_differences(
                args.original, args.revised, args.output_dir, result=result, style=args.style,
                include_report=args.report, overwrite=args.overwrite
            )
            print(f"Highlighted PDFs: {outputs.original}, {outputs.revised}")
            if outputs.report:
                print(f"Difference report: {outputs.report}")

        visual_identical = True if visual_result is None else (
            visual_result.is_identical if hasattr(visual_result, "is_identical") else all(
                item.is_identical for item in visual_result.comparisons
            )
        )

        # Check for unreliable comparison (no text layer)
        if not result.reliable:
            return 3

        return 0 if result.is_identical and visual_identical else 1
    except (PDFComparisonError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        # Map specific exceptions to exit codes
        if isinstance(exc, InvalidPDFError):
            return 2
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
