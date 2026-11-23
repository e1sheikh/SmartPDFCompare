import pymupdf

def dump_page_text(pdf_path: str, page_num: int):
    doc = pymupdf.open(pdf_path)
    page = doc[page_num]
    # Simple area check
    text = page.get_text("text")
    print(f"--- {pdf_path} Page {page_num+1} ---")
    print("Header/Footer snippet (raw):")
    # Show first 300 chars to cover header, last 300 to cover footer
    print(text[:300])
    print("...")
    print(text[-300:])
    doc.close()

# These paths are what I expect to see once the user adds them
pdf_old = "tests/golden/SDUR30H120_old.pdf"
pdf_new = "tests/golden/SDUR30H120_new.pdf"

import os
if os.path.exists(pdf_old) and os.path.exists(pdf_new):
    dump_page_text(pdf_old, 0)
    dump_page_text(pdf_new, 0)
else:
    print("Golden PDFs not found in tests/golden/")
