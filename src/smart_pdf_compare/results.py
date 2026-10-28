"""Public, JSON-friendly comparison result models."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    REPLACED = "replaced"
    PAGE_ADDED = "page_added"
    PAGE_REMOVED = "page_removed"
    PAGE_MOVED = "page_moved"


@dataclass(frozen=True)
class Difference:
    """A readable text or page-level difference (page numbers are one-based)."""

    change_type: ChangeType
    old_page: Optional[int]
    new_page: Optional[int]
    old_text: str = ""
    new_text: str = ""
    old_context: str = ""
    new_context: str = ""


@dataclass(frozen=True)
class ComparisonSummary:
    old_pages: int
    new_pages: int
    added_pages: int
    removed_pages: int
    moved_pages: int
    modified_pages: int
    added_words: int
    removed_words: int
    differences: int


@dataclass
class _PageMarkup:
    """Internal coordinate data shared by comparison and rendering."""

    old_page: Optional[int]
    new_page: Optional[int]
    old_rects: list[tuple[float, float, float, float]] = field(default_factory=list)
    new_rects: list[tuple[float, float, float, float]] = field(default_factory=list)
    changed: bool = False


@dataclass
class ComparisonResult:
    """Structured result of :func:`smart_pdf_compare.compare_pdfs`."""

    is_identical: bool
    summary: ComparisonSummary
    differences: list[Difference]
    warnings: list[str] = field(default_factory=list)
    truncated: bool = False
    _markup: list[_PageMarkup] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-compatible data without internal geometry."""
        return {
            "is_identical": self.is_identical,
            "summary": asdict(self.summary),
            "differences": [{**asdict(item), "change_type": item.change_type.value} for item in self.differences],
            "warnings": list(self.warnings),
            "truncated": self.truncated,
        }
