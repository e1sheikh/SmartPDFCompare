import sys
sys.path.insert(0, 'src')
import pymupdf
import json
from pathlib import Path
from smart_pdf_compare.extraction import open_pdf, extract_document
from smart_pdf_compare.normalization import NormalizationOptions

def dump_page_info(pdf_path):
    doc = open_pdf(pdf_path)
    opts = NormalizationOptions()
    pages = extract_document(doc, opts, sort_words=False)
    doc.close()
    return pages

old_path = "tests/golden/SDUR30H120_old.pdf"
new_path = "tests/golden/SDUR30H120_new.pdf"

old_pages = dump_page_info(old_path)
new_pages = dump_page_info(new_path)

output = {"old": len(old_pages), "new": len(new_pages)}
# just store first page words count
output["old_words"] = len(old_pages[0].words)
output["new_words"] = len(new_pages[0].words)

with open("phase0_page_info.json","w",encoding="utf-8") as f:
    json.dump(output,f,indent=2)

print("Wrote phase0_page_info.json")
