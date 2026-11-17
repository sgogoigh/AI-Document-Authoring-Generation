from typing import Literal

from pydantic import BaseModel, Field


class OutlineSuggestionSchema(BaseModel):
    """Structured LLM output for the AI-Suggest Outline bonus workflow."""

    recommended_title: str = Field(description="A crisp executive document or presentation title.")
    rationale: str = Field(description="One-sentence explanation of why this structure fits the topic.")
    items: list[str] = Field(
        min_length=3,
        max_length=12,
        description="Ordered list of section headers (for Word) or slide titles (for PowerPoint).",
    )


class DocxBulletPoint(BaseModel):
    label: str = Field(description="Short bold lead-in phrase (2-5 words).")
    detail: str = Field(description="Concise supporting explanation (1-2 sentences).")


class DocxDataTable(BaseModel):
    title: str = Field(default="", description="Short table title.")
    headers: list[str] = Field(min_length=2, max_length=4)
    rows: list[list[str]] = Field(min_length=1, max_length=6)


class DocxSectionSchema(BaseModel):
    """Structured content schema for a Microsoft Word (.docx) section."""

    summary_callout: str = Field(
        description="1-2 sentence executive takeaway highlighted in a callout box."
    )
    paragraphs: list[str] = Field(
        min_length=1,
        max_length=4,
        description="Well-crafted analytical prose paragraphs tailored to the section.",
    )
    bullet_points: list[DocxBulletPoint] = Field(
        default_factory=list,
        max_length=6,
        description="Structured key points with bold lead-in labels.",
    )
    data_table: DocxDataTable | None = Field(
        default=None,
        description="Optional compact comparison or metrics table (max 4 cols x 6 rows).",
    )
    should_generate_image: bool = Field(
        default=False,
        description="True when a custom conceptual visual/diagram meaningfully enhances this section.",
    )
    image_prompt: str = Field(
        default="",
        description="Clean visual prompt without text overlays if should_generate_image is true.",
    )
    image_caption: str = Field(
        default="",
        description="Short figure caption if an image is included.",
    )


class PptxMetricCard(BaseModel):
    value: str = Field(description="Short metric value, e.g. '42%', '$1.8T', '3.2x'.")
    label: str = Field(description="Short 2-5 word metric label.")


class PptxSlideSchema(BaseModel):
    """Structured content schema for a PowerPoint (.pptx) slide."""

    layout_variant: Literal["bullets_only", "bullets_with_visual", "two_column", "metrics_cards"] = (
        Field(description="Visual slide layout selected for best presentation clarity.")
    )
    kicker: str = Field(
        description="Short 2-4 word uppercase eyebrow label (e.g., 'MARKET DYNAMICS')."
    )
    subtitle: str = Field(
        description="Single-line slide takeaway headline (max 15 words)."
    )
    bullets: list[str] = Field(
        min_length=2,
        max_length=5,
        description="Concise presentation bullets (max 18 words per bullet, no walls of text).",
    )
    secondary_column_title: str = Field(
        default="",
        description="Heading for right column when layout_variant is 'two_column'.",
    )
    secondary_bullets: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="Right-column bullets when layout_variant is 'two_column'.",
    )
    metric_cards: list[PptxMetricCard] = Field(
        default_factory=list,
        max_length=3,
        description="Up to 3 KPI stat cards when layout_variant is 'metrics_cards'.",
    )
    speaker_notes: str = Field(
        description="Detailed 2-4 sentence presenter talking points for PowerPoint notes pane."
    )
    should_generate_image: bool = Field(
        default=False,
        description="True when layout_variant is 'bullets_with_visual' or a visual strengthens the slide.",
    )
    image_prompt: str = Field(
        default="",
        description="Clean visual illustration prompt without embedded text if should_generate_image is true.",
    )
    image_caption: str = Field(
        default="",
        description="Concise caption for slide visual.",
    )
