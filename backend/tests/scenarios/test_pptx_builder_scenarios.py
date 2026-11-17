import io
from pathlib import Path

import pytest
from PIL import Image
from pptx import Presentation

from app.services.doc_builder.pptx_builder import SLIDE_H, SLIDE_W, build_pptx_bytes


def _make_png(path: Path, size: tuple[int, int], color=(13, 148, 136)) -> Path:
    Image.new("RGB", size, color=color).save(path, format="PNG")
    return path


def _assert_all_shapes_in_bounds(prs: Presentation) -> None:
    assert prs.slide_width == SLIDE_W
    assert prs.slide_height == SLIDE_H
    for slide in prs.slides:
        for shape in slide.shapes:
            assert shape.left >= 0
            assert shape.top >= 0
            assert shape.left + shape.width <= SLIDE_W + 5000
            assert shape.top + shape.height <= SLIDE_H + 5000


@pytest.mark.parametrize(
    "palette",
    ["executive_navy", "emerald_slate", "obsidian_gold", "warm_editorial", "invalid_palette", None],
)
def test_pptx_all_palettes_and_fallback(palette):
    raw = build_pptx_bytes(
        title="Palette Deck",
        main_topic="Testing theme palettes",
        author_name="QA",
        theme_config={"palette": palette} if palette is not None else {},
        version=1,
        sections=[
            {
                "title": "Slide One",
                "content_json": {
                    "layout_variant": "bullets_only",
                    "kicker": "INTRO",
                    "subtitle": "Subtitle takeaway",
                    "bullets": ["Bullet one", "Bullet two"],
                    "speaker_notes": "Notes here",
                },
            }
        ],
    )
    prs = Presentation(io.BytesIO(raw))
    assert len(prs.slides) == 3
    _assert_all_shapes_in_bounds(prs)


@pytest.mark.parametrize("slide_count", [2, 5, 6, 12])
def test_pptx_agenda_single_and_two_column_scaling(slide_count):
    sections = [
        {
            "title": f"Slide {i + 1}: Operational Pillar",
            "content_json": {
                "layout_variant": "bullets_only",
                "kicker": f"SEC {i + 1}",
                "subtitle": f"Takeaway for slide {i + 1}",
                "bullets": [f"Key insight {i + 1}.1", f"Key insight {i + 1}.2"],
                "speaker_notes": f"Speaker notes for slide {i + 1}.",
            },
        }
        for i in range(slide_count)
    ]
    raw = build_pptx_bytes(
        title="Scaled Deck",
        main_topic="Agenda scaling",
        author_name="QA",
        theme_config={},
        version=1,
        sections=sections,
    )
    prs = Presentation(io.BytesIO(raw))
    assert len(prs.slides) == slide_count + 2
    _assert_all_shapes_in_bounds(prs)


@pytest.mark.parametrize(
    "scenario_name,sec_factory",
    [
        (
            "two_column_missing_secondary_falls_back_cleanly",
            lambda _tmp: {
                "title": "Comparison Fallback",
                "content_json": {
                    "layout_variant": "two_column",
                    "bullets": ["Left bullet 1", "Left bullet 2"],
                    "secondary_bullets": [],
                },
            },
        ),
        (
            "metrics_cards_empty_falls_back_cleanly",
            lambda _tmp: {
                "title": "KPI Fallback",
                "content_json": {
                    "layout_variant": "metrics_cards",
                    "metric_cards": [],
                    "bullets": ["Fallback bullet 1"],
                },
            },
        ),
        (
            "bullets_with_visual_missing_file_falls_back",
            lambda tmp: {
                "title": "Visual Missing Fallback",
                "content_json": {
                    "layout_variant": "bullets_with_visual",
                    "bullets": ["Fallback bullet A", "Fallback bullet B"],
                },
                "image_path": tmp / "missing.png",
            },
        ),
        (
            "extreme_text_overflow_clamping_and_bullet_cap",
            lambda _tmp: {
                "title": "X" * 200,
                "content_json": {
                    "layout_variant": "bullets_only",
                    "kicker": "K" * 100,
                    "subtitle": "S" * 300,
                    "bullets": [f"Bullet {i} " + ("word " * 50) for i in range(8)],
                },
            },
        ),
        (
            "unicode_and_currency_symbols",
            lambda _tmp: {
                "title": "Global Revenue: $4.2B / €3.8B / ¥600B 🚀",
                "content_json": {
                    "layout_variant": "metrics_cards",
                    "metric_cards": [
                        {"value": "€3.8B", "label": "EMEA ARR"},
                        {"value": "¥600B", "label": "APAC Volume"},
                        {"value": "+42%", "label": "YoY Velocity"},
                    ],
                    "bullets": ["Zürich & 東京 hubs outperformed Q4 targets."],
                },
            },
        ),
        (
            "content_json_none_uses_content_text_fallback",
            lambda _tmp: {
                "title": "Plain Text Slide",
                "content_json": None,
                "content_text": "- First bullet line\n- Second bullet line",
            },
        ),
    ],
)
def test_pptx_layout_fallbacks_and_overflow_guards(tmp_path: Path, scenario_name: str, sec_factory):
    sec = sec_factory(tmp_path)
    raw = build_pptx_bytes(
        title=f"Scenario: {scenario_name}",
        main_topic="Layout resilience test",
        author_name="QA",
        theme_config={},
        version=1,
        sections=[sec],
    )
    prs = Presentation(io.BytesIO(raw))
    assert len(prs.slides) == 3
    _assert_all_shapes_in_bounds(prs)


@pytest.mark.parametrize(
    "img_size",
    [(1400, 400), (400, 1200), (600, 600), (80, 80)],
)
def test_pptx_multi_aspect_ratio_image_fitting(tmp_path: Path, img_size: tuple[int, int]):
    img_path = _make_png(tmp_path / f"slide_{img_size[0]}x{img_size[1]}.png", img_size)
    raw = build_pptx_bytes(
        title="Image Fit Deck",
        main_topic="Aspect ratio test",
        author_name="QA",
        theme_config={},
        version=1,
        sections=[
            {
                "title": "Visual Slide",
                "content_json": {
                    "layout_variant": "bullets_with_visual",
                    "bullets": ["Point 1", "Point 2"],
                },
                "image_path": img_path,
                "image_caption": f"Fitted {img_size[0]}x{img_size[1]}",
            }
        ],
    )
    prs = Presentation(io.BytesIO(raw))
    _assert_all_shapes_in_bounds(prs)
    pics = [s for s in prs.slides[2].shapes if s.shape_type == 13]
    assert len(pics) == 1
