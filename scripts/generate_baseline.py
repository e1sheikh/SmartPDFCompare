import json
import pymupdf
import tempfile
from pathlib import Path
from src.smart_pdf_compare.extraction import open_pdf, extract_document
from src.smart_pdf_compare.normalization import NormalizationOptions

def generate_baseline():
    # Use a temp directory for synthetic corpus
    tmp = Path(tempfile.mkdtemp(prefix="smartpdf_baseline_"))

    # Placeholder for synthetic corpus generation script,
    # adapting from tests/corpus.py to be more robust
    # ... logic here ...

    # For now, just a stub to show format
    baseline = {
        "synthetic": {
            "hyphen_variations": {"diffs": 0},
            "bullet_variations": {"diffs": 0},
            "degree_variations": {"diffs": 0}
        },
        "golden": {
            "SDUR30H120": "pending",
            "SDURF3020": "pending"
        }
    }

    with open("tests/baseline.json", "w") as f:
        json.dump(baseline, f, indent=2)
    print("Baseline written to tests/baseline.json")

if __name__ == "__main__":
    generate_baseline()
