from pathlib import Path

import pymupdf
import pytest


def make_pdf(path: Path, pages: list[str], *, rotate: bool = False) -> Path:
    document = pymupdf.open()
    for text in pages:
        page = document.new_page(width=360, height=240)
        if text:
            page.insert_text((36, 72), text, fontsize=12)
        if rotate:
            page.set_rotation(90)
    document.save(path)
    document.close()
    return path


@pytest.fixture
def pdf_factory(tmp_path):
    def create(name: str, pages: list[str], **kwargs) -> Path:
        return make_pdf(tmp_path / name, pages, **kwargs)
    return create
