"""
Text extraction from file content for storage indexing.

Supported MIME types are listed in EXTRACTABLE_MIME_TYPES.
Unsupported types (images, video, audio, etc.) return an empty string.
"""
from io import BytesIO

EXTRACTABLE_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
    }
)


def extract_text_from_file(content: bytes, mime_type: str) -> str:
    """Extract plain text from file content.

    Args:
        content: Raw file bytes.
        mime_type: MIME type string, e.g. ``"application/pdf"`` or ``"text/plain"``.

    Returns:
        Extracted text as a UTF-8 string, or ``""`` if the MIME type is not supported.
    """
    if mime_type == "application/pdf":
        from pdfminer.high_level import extract_text  # noqa: PLC0415

        return extract_text(BytesIO(content)) or ""

    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from docx import Document  # noqa: PLC0415

        doc = Document(BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    if mime_type in ("text/plain", "text/markdown"):
        return content.decode("utf-8", errors="replace")

    return ""
