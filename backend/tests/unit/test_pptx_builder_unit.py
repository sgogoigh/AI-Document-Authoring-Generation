import io
from pathlib import Path

from PIL import Image
from pptx import Presentation

from app.services.doc_builder.pptx_builder import SLIDE_H, SLIDE_W, build_pptx_bytes


def _sample_png(path: Path) -> Path:
    Image.new("RGB", (800, 500), color=(13, 148, 136)).save(path, format="PNG")
    return path


def test_pptx_builder_all_layout_variants_bounds_and_notes(tmp_path: Path):
    img_path = _sample_png(tmp_path / "slide_visual.png")

    sections = [
        {
            "title": "Market Inflection Point",
            "content_json": {
                "layout_variant": "bullets_with_visual",
                "kicker": "MARKET DYNAMICS",
                "subtitle": "EV adoption surpassed 22% global market share in 2025",
                "bullets": [
                    "Battery pack costs dropped below $95/kWh globally.",
                    "Fast-charging infrastructure expanded 45% YoY.",
                    "Fleet electrification led commercial adoption.",
                ],
                "speaker_notes": "Highlight the $95/kWh inflection point for mass-market parity.",
            },
            "image_path": img_path,
            "image_caption": "EV Adoption Trajectory",
        },
        {
            "title": "Regional Comparison",
            "content_json": {
                "layout_variant": "two_column",
                "kicker": "GEOGRAPHIES",
                "subtitle": "Divergent regulatory drivers across China, Europe, and North America",
                "bullets": ["China leads in LFP scale", "Europe leads in fleet mandates"],
                "secondary_column_title": "North America Outlook",
                "secondary_bullets": ["Localized battery tax credits", "Highway DCFC buildout"],
                "speaker_notes": "Contrast subsidy structures across regions.",
            },
            "image_path": None,
        },
        {
            "title": "Financial & Operational KPIs",
            "content_json": {
                "layout_variant": "metrics_cards",
                "kicker": "KEY METRICS",
                "subtitle": "Unit economics improved sharply across Tier-1 OEMs",
                "metric_cards": [
                    {"value": "28%", "label": "YoY Volume Growth"},
                    {"value": "$92/kWh", "label": "Avg Pack Cost"},
                    {"value": "1.8x", "label": "Charger Utilization"},
                ],
                "bullets": ["Gross margin expansion of 320 bps", "Software recurring revenue rising"],
                "speaker_notes": "Walk through each KPI card.",
            },
            "image_path": None,
        },
        {
            "title": "Strategic Recommendations",
            "content_json": {
                "layout_variant": "bullets_only",
                "kicker": "ACTION PLAN",
                "subtitle": "Three immediate priorities for H1 execution",
                "bullets": ["Lock in LFP supply contracts", "Co-invest in urban charging hubs"],
                "speaker_notes": "Close with executive ask.",
            },
            "image_path": None,
        },
    ]

    raw = build_pptx_bytes(
        title="EV Transformation Strategy",
        main_topic="2025 Executive Strategy Briefing",
        author_name="Bob Strategist",
        theme_config={"palette": "emerald_slate", "audience": "Executive Committee"},
        version=2,
        sections=sections,
    )
    assert len(raw) > 8000

    prs = Presentation(io.BytesIO(raw))
    assert prs.slide_width == SLIDE_W
    assert prs.slide_height == SLIDE_H
    # Cover + Agenda + 4 content slides = 6
    assert len(prs.slides) == 6

    # Check every shape remains within slide bounds
    for slide in prs.slides:
        for shape in slide.shapes:
            assert shape.left >= 0
            assert shape.top >= 0
            assert shape.left + shape.width <= SLIDE_W + 5000
            assert shape.top + shape.height <= SLIDE_H + 5000

    # Verify picture shape on content slide 1 (prs.slides[2])
    pic_shapes = [s for s in prs.slides[2].shapes if s.shape_type == 13]
    assert len(pic_shapes) == 1

    # Verify speaker notes populated on all content slides
    assert "inflection point" in prs.slides[2].notes_slide.notes_text_frame.text
    assert "Contrast subsidy" in prs.slides[3].notes_slide.notes_text_frame.text
    assert "KPI card" in prs.slides[4].notes_slide.notes_text_frame.text
    assert "executive ask" in prs.slides[5].notes_slide.notes_text_frame.text
