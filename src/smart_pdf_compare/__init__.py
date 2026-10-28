"""SmartPDFCompare: structured text comparison and PDF highlighting."""
from .api import ComparisonOptions, compare_pdfs
from .exceptions import ConfigurationError, InvalidPDFError, MissingTextLayerError, PDFComparisonError
from .highlighting import HighlightOutputs, create_side_by_side_report, highlight_differences
from .normalization import NormalizationOptions
from .results import ChangeType, ComparisonResult, ComparisonSummary, Difference

__version__ = "0.1.0"

__all__ = [
    "ChangeType", "ComparisonOptions", "ComparisonResult", "ComparisonSummary", "ConfigurationError",
    "Difference", "HighlightOutputs", "InvalidPDFError", "MissingTextLayerError", "NormalizationOptions",
    "PDFComparisonError", "compare_pdfs", "create_side_by_side_report", "highlight_differences",
]
