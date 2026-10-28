from smart_pdf_compare import compare_pdfs

result = compare_pdfs("original.pdf", "revised.pdf")
print(result.to_dict())
