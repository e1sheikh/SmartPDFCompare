"""SmartPDFCompare: structured text comparison and PDF highlighting."""
from .api import ComparisonOptions, compare_pdfs
from .exceptions import (
    ConfigurationError,
    InvalidOptionError,
    InvalidPDFError,
    MissingTextLayerError,
    PDFComparisonError,
)
from .highlighting import HighlightOutputs, create_side_by_side_report, highlight_differences
from .normalization import NormalizationOptions
from .results import ChangeType, ComparisonResult, ComparisonSummary, Difference
from .visual import (
    VisualBatchResult,
    VisualComparisonOptions,
    VisualComparisonResult,
    VisualPageResult,
    compare_visual_documents,
    compare_visual_pdfs,
)

__version__ = "0.2.2"

__all__ = [
    "ChangeType", "ComparisonOptions", "ComparisonResult", "ComparisonSummary", "ConfigurationError",
    "Difference", "HighlightOutputs", "InvalidOptionError", "InvalidPDFError", "MissingTextLayerError",
    "NormalizationOptions", "PDFComparisonError", "compare_pdfs", "create_side_by_side_report",
    "highlight_differences", "VisualBatchResult", "VisualComparisonOptions", "VisualComparisonResult",
    "VisualPageResult", "compare_visual_documents", "compare_visual_pdfs",
]
