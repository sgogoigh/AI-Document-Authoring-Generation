import io
from pathlib import Path

from docx import Document
from PIL import Image

from app.services.doc_builder.docx_builder import build_docx_bytes


def _create_sample_png(path: Path) -> Path:
    img = Image.new("RGB", (640, 420), color=(15, 41, 66))
    img.save(path, format="PNG")
    return path


def test_docx_builder_generates_structured_document_with_tables_and_images(tmp_path: Path):
    img_path = _create_sample_png(tmp_path / "chart.png")

    sections = [
        {
            "title": "Executive Summary",
            "content_json": {
                "summary_callout": "Global EV adoption accelerated 28% in 2025.",
                "paragraphs": [
                    "Battery cost declines drove mainstream price parity across key markets.",
                    "Charging corridor investments doubled in Europe and North America.",
                ],
                "bullet_points": [
                    {"label": "Market Share", "detail": "EVs crossed 22% of new passenger sales."},
                    {"label": "Margin Gains", "detail": "LFP packs lowered BOM costs by 18%."},
                ],
                "data_table": {
                    "title": "2025 Regional Adoption",
                    "headers": ["Region", "EV Share", "YoY Growth"],
                    "rows": [
                        ["China", "41%", "+24%"],
                        ["Europe", "26%", "+19%"],
                    ],
                },
            },
            "image_path": img_path,
            "image_caption": "Figure 1: EV Charging Architecture",
        },
        {
            "title": "Supply Chain Risks",
            "content_json": {
                "summary_callout": "Refining concentration remains a strategic bottleneck.",
                "paragraphs": ["Diversified cathode sourcing mitigates geopolitical exposure."],
                "bullet_points": [],
                "data_table": None,
            },
            "image_path": None,
        },
    ]

    raw = build_docx_bytes(
        title="EV Market Analysis 2025",
        main_topic="Comprehensive EV industry market review",
        author_name="Alice Analyst",
        theme_config={"palette": "executive_navy", "tone": "executive", "audience": "Board"},
        version=3,
        sections=sections,
    )
    assert len(raw) > 5000

    doc = Document(io.BytesIO(raw))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Document Outline" in full_text
    assert "Executive Summary" in full_text
    assert "Supply Chain Risks" in full_text
    assert "Battery cost declines drove mainstream price parity" in full_text
    assert "Figure 1: EV Charging Architecture" in full_text

    # Cover banner + metadata + callouts + data table
    assert len(doc.tables) >= 5
    # Verify embedded image count
    assert len(doc.inline_shapes) == 1
    # Verify header text
    assert "EV Market Analysis 2025" in doc.sections[0].header.paragraphs[0].text
