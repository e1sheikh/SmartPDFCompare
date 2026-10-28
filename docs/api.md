# API reference

`compare_pdfs(old_pdf, new_pdf, options=None)` returns `ComparisonResult`. Configure `ComparisonOptions(alignment, similarity_threshold, lookahead, max_differences, normalization)`. Call `result.to_dict()` for JSON data.

`highlight_differences(old_pdf, new_pdf, output_dir, result=None, options=None, style="highlight", include_report=False)` returns paths for highlighted copies and optionally the report. `create_side_by_side_report` accepts an existing result and output path.

Invalid files raise `InvalidPDFError`; documents with no text layer raise `MissingTextLayerError`; unsupported choices raise `ConfigurationError`.
