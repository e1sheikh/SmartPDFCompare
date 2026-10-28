from smart_pdf_compare import highlight_differences

outputs = highlight_differences("original.pdf", "revised.pdf", "diff-output", include_report=True)
print(outputs)
