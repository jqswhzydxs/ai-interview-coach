from pathlib import Path

import fitz
import pytest
from docx import Document

from app.tools.file_parser import FileParserError, parse_file


def test_parse_text_file(tmp_path: Path) -> None:
    file_path = tmp_path / "resume.txt"
    file_path.write_text("Python backend project", encoding="utf-8")

    parsed = parse_file(file_path)

    assert "Python backend project" in parsed.text
    assert parsed.metadata["input_type"] == "text"


def test_parse_markdown_file(tmp_path: Path) -> None:
    file_path = tmp_path / "resume.md"
    file_path.write_text("# Resume\nFastAPI", encoding="utf-8")

    parsed = parse_file(file_path)

    assert "FastAPI" in parsed.text
    assert parsed.metadata["input_type"] == "markdown"


def test_parse_docx_file(tmp_path: Path) -> None:
    file_path = tmp_path / "resume.docx"
    document = Document()
    document.add_paragraph("Django backend internship")
    document.save(file_path)

    parsed = parse_file(file_path)

    assert "Django backend internship" in parsed.text
    assert parsed.metadata["input_type"] == "docx"


def test_parse_pdf_file(tmp_path: Path) -> None:
    file_path = tmp_path / "resume.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Go backend service")
    document.save(file_path)
    document.close()

    parsed = parse_file(file_path)

    assert "Go backend service" in parsed.text
    assert parsed.metadata["input_type"] == "pdf"


def test_parse_rejects_unsupported_file(tmp_path: Path) -> None:
    file_path = tmp_path / "resume.exe"
    file_path.write_text("nope", encoding="utf-8")

    with pytest.raises(FileParserError):
        parse_file(file_path)


def test_parse_rejects_large_file(tmp_path: Path) -> None:
    file_path = tmp_path / "large.txt"
    file_path.write_bytes(b"0" * (5 * 1024 * 1024 + 1))

    with pytest.raises(FileParserError):
        parse_file(file_path)

