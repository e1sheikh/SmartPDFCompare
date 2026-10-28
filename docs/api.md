# API reference

`compare_pdfs(old_pdf, new_pdf, options=None)` returns `ComparisonResult`. Configure `ComparisonOptions(alignment, similarity_threshold, lookahead, max_differences, normalization)`. Call `result.to_dict()` for JSON data.

`highlight_differences(old_pdf, new_pdf, output_dir, result=None, options=None, style="highlight", include_report=False)` returns paths for highlighted copies and optionally the report. `create_side_by_side_report` accepts an existing result and output path.

Invalid files raise `InvalidPDFError`; documents with no text layer raise `MissingTextLayerError`; unsupported choices raise `ConfigurationError`.

## Visual comparison

`compare_visual_pdfs(old_pdf, new_pdf, options=None, output_dir=None)` returns `VisualComparisonResult`. Configure `VisualComparisonOptions(dpi=144, pixel_threshold=8, min_changed_pixels=1, min_difference_ratio=0.0, output_mode="none")`. Output modes are `none`, `side_by_side`, and `diff_image`; an `output_dir` is required for either image-producing mode.

`compare_visual_documents(pdf_paths, reference=0, ...)` uses explicit reference-based semantics: every non-reference document is compared with the chosen input. Visual pages are paired by index and unequal page counts are returned as unmatched, visually different page results. If an artifact mode is selected, an unmatched page is rendered beside a blank canvas and receives its own artifact.

## Optional desktop viewer

Run `smart-pdf-compare-viewer original.pdf revised.pdf` on a desktop Python installation with Tk support. The viewer is isolated in `smart_pdf_compare.viewer`; importing the core package never imports Tk or opens a window. It displays the current changed page pair, has synchronized pane scrolling/zoom controls, mouse-wheel zoom and drag panning, next/previous-change navigation, and a save action that delegates to `highlight_differences`. It deliberately renders only the current page pair to remain lightweight; it is not a full-document thumbnail browser.
