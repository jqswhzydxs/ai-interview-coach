from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz
from docx import Document


MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


class FileParserError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def parse_file(path: str | Path, max_size_bytes: int = MAX_FILE_SIZE_BYTES) -> ParsedDocument:
    file_path = Path(path)
    if not file_path.exists():
        raise FileParserError(f"File not found: {file_path}")

    size = file_path.stat().st_size
    if size > max_size_bytes:
        raise FileParserError("File exceeds 5MB limit")

    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(file_path, size)
    if suffix == ".docx":
        return _parse_docx(file_path, size)
    if suffix in {".md", ".markdown", ".txt"}:
        return _parse_text(file_path, size)

    raise FileParserError(f"Unsupported file type: {suffix}")


def _parse_text(file_path: Path, size: int) -> ParsedDocument:
    text = file_path.read_text(encoding="utf-8")
    return ParsedDocument(
        text=text,
        metadata={"input_type": _input_type(file_path), "size_bytes": size},
    )


def _parse_docx(file_path: Path, size: int) -> ParsedDocument:
    document = Document(str(file_path))
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
    return ParsedDocument(
        text="\n".join(paragraphs),
        metadata={
            "input_type": "docx",
            "size_bytes": size,
            "paragraph_count": len(paragraphs),
        },
    )


def _parse_pdf(file_path: Path, size: int) -> ParsedDocument:
    text_parts: list[str] = []
    with fitz.open(file_path) as document:
        for page in document:
            text_parts.append(page.get_text())
        page_count = document.page_count

    return ParsedDocument(
        text="\n".join(part.strip() for part in text_parts if part.strip()),
        metadata={"input_type": "pdf", "size_bytes": size, "page_count": page_count},
    )


def _input_type(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "markdown"
    return "text"

