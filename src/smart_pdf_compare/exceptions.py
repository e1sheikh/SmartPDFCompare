"""Exceptions raised by SmartPDFCompare."""


class PDFComparisonError(Exception):
    """Base class for comparison and output errors."""


class InvalidPDFError(PDFComparisonError):
    """A supplied file is missing, unreadable, or is not a PDF."""


class EncryptedPDFError(InvalidPDFError):
    """A supplied PDF is encrypted and cannot be processed."""


class MissingTextLayerError(PDFComparisonError):
    """A document has no extractable text and cannot be safely compared.

    This exception is retained for backward compatibility but is no longer
    raised by compare_pdfs(). Instead, a ComparisonResult with reliable=False
    is returned. CLI exit code 3 is still used for unreliable comparisons.
    """


class ConfigurationError(PDFComparisonError):
    """An unsupported comparison or rendering option was requested."""


class OutputExistsError(FileExistsError, PDFComparisonError):
    """Output file already exists and overwrite is not enabled."""


class InputOverwriteError(PDFComparisonError):
    """Refusing to overwrite an input file with output."""