"""Structured .docx and .pptx document assembly builders."""

from app.services.doc_builder.docx_builder import build_docx_bytes
from app.services.doc_builder.pptx_builder import build_pptx_bytes

__all__ = ["build_docx_bytes", "build_pptx_bytes"]
