"""Exceptions raised by SmartPDFCompare."""


class PDFComparisonError(Exception):
    """Base class for comparison and output errors."""


class InvalidPDFError(PDFComparisonError):
    """A supplied file is missing, unreadable, or is not a PDF."""


class MissingTextLayerError(PDFComparisonError):
    """A document has no extractable text and cannot be safely compared."""


class ConfigurationError(PDFComparisonError):
    """An unsupported comparison or rendering option was requested."""
