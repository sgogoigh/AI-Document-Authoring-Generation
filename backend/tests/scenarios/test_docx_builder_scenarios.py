import io
from pathlib import Path

import pytest
from docx import Document
from PIL import Image

from app.services.doc_builder.docx_builder import build_docx_bytes


def _make_png(path: Path, size: tuple[int, int], color=(15, 41, 66)) -> Path:
    Image.new("RGB", size, color=color).save(path, format="PNG")
    return path


@pytest.mark.parametrize(
    "palette",
    ["executive_navy", "emerald_slate", "obsidian_gold", "warm_editorial", "unknown_fallback", None],
)
def test_docx_all_palettes_and_fallback(palette):
    raw = build_docx_bytes(
        title="Palette Verification Report",
        main_topic="Theme resilience check",
        author_name="Scenario Runner",
        theme_config={"palette": palette} if palette is not None else {},
        version=1,
        sections=[
            {
                "title": "Section One",
                "content_json": {
                    "summary_callout": "Takeaway text.",
                    "paragraphs": ["Body paragraph."],
                    "bullet_points": [{"label": "Point", "detail": "Detail"}],
                },
            }
        ],
    )
    doc = Document(io.BytesIO(raw))
    assert "Section One" in "\n".join(p.text for p in doc.paragraphs)


@pytest.mark.parametrize("tone", ["executive", "analytical", "persuasive", "technical"])
def test_docx_all_editorial_tones_metadata(tone):
    raw = build_docx_bytes(
        title="Tone Metadata Check",
        main_topic="Testing tone rendering",
        author_name="Tester",
        theme_config={"tone": tone, "audience": "Engineering VP"},
        version=2,
        sections=[{"title": "Intro", "content_json": {"paragraphs": ["Hello world."]}}],
    )
    doc = Document(io.BytesIO(raw))
    tbl_text = "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert tone.capitalize() in tbl_text
    assert "Engineering VP" in tbl_text


@pytest.mark.parametrize("section_count", [1, 6, 12])
def test_docx_section_scale_bounds(section_count):
    sections = [
        {
            "title": f"Chapter {i + 1}: Strategic Pillar",
            "content_json": {
                "summary_callout": f"Summary {i + 1}",
                "paragraphs": [f"Paragraph for section {i + 1}."],
                "bullet_points": [{"label": "Key", "detail": f"Detail {i + 1}"}],
            },
        }
        for i in range(section_count)
    ]
    raw = build_docx_bytes(
        title="Scaled Report",
        main_topic="Scale test",
        author_name="Tester",
        theme_config={},
        version=1,
        sections=sections,
    )
    doc = Document(io.BytesIO(raw))
    all_text = "\n".join(p.text for p in doc.paragraphs)
    for i in range(section_count):
        assert f"Chapter {i + 1}: Strategic Pillar" in all_text


@pytest.mark.parametrize(
    "scenario_name,sections_factory",
    [
        (
            "unicode_emojis_and_xml_chars",
            lambda _tmp: [
                {
                    "title": "R&D <Budget> & 'Growth' — €1.5M 🚀",
                    "content_json": {
                        "summary_callout": "Tokyo (東京) & Zürich lead Q1 > Q2 targets.",
                        "paragraphs": ["Specs: A < B & C > D — \"quoted\" €500M."],
                        "bullet_points": [{"label": "KPI & ROI", "detail": "100% <target> met 🎯"}],
                    },
                }
            ],
        ),
        (
            "fallback_to_raw_content_text_when_json_none",
            lambda _tmp: [
                {
                    "title": "Legacy Plain Section",
                    "content_json": None,
                    "content_text": "Plain fallback text body.",
                }
            ],
        ),
        (
            "completely_empty_section_payload",
            lambda _tmp: [{"title": "Empty Placeholder", "content_json": {}, "content_text": ""}],
        ),
        (
            "string_only_bullets_fallback",
            lambda _tmp: [
                {
                    "title": "Simple Bullets",
                    "content_json": {
                        "paragraphs": ["Context paragraph."],
                        "bullet_points": ["Plain bullet one", "Plain bullet two"],
                    },
                }
            ],
        ),
        (
            "jagged_and_oversized_data_table",
            lambda _tmp: [
                {
                    "title": "Metrics Matrix",
                    "content_json": {
                        "paragraphs": ["Tabular overview."],
                        "data_table": {
                            "title": "Oversized & Jagged Table",
                            "headers": ["Col1", "Col2", "Col3", "Col4", "ExtraCol5"],
                            "rows": [
                                ["A1"],  # shorter row than headers
                                ["B1", "B2", "B3", "B4", "B5"],  # wider row than clamped 4 cols
                                ["C1", "C2", "C3", "C4"],
                                ["D1", "D2", "D3", "D4"],
                                ["E1", "E2", "E3", "E4"],
                                ["F1", "F2", "F3", "F4"],
                                ["G1_overflow_row", "G2", "G3", "G4"],  # row 7 clamped
                            ],
                        },
                    },
                }
            ],
        ),
        (
            "missing_image_path_graceful_skip",
            lambda tmp: [
                {
                    "title": "Visual Missing On Disk",
                    "content_json": {"paragraphs": ["Text remains intact."]},
                    "image_path": tmp / "does_not_exist.png",
                    "image_caption": "Missing caption",
                }
            ],
        ),
    ],
)
def test_docx_edge_case_scenarios(tmp_path: Path, scenario_name: str, sections_factory):
    sections = sections_factory(tmp_path)
    raw = build_docx_bytes(
        title=f"Scenario: {scenario_name}",
        main_topic="Edge case resilience",
        author_name="QA Bot",
        theme_config={"palette": "executive_navy"},
        version=1,
        sections=sections,
    )
    doc = Document(io.BytesIO(raw))
    assert len(doc.paragraphs) > 0
    if scenario_name == "jagged_and_oversized_data_table":
        data_tbl = doc.tables[-1]
        assert len(data_tbl.columns) == 4
        assert len(data_tbl.rows) == 7  # 1 header + max 6 rows
    if scenario_name == "missing_image_path_graceful_skip":
        assert len(doc.inline_shapes) == 0


@pytest.mark.parametrize(
    "img_size",
    [(1200, 300), (300, 1000), (512, 512), (64, 64)],
)
def test_docx_multi_aspect_ratio_images(tmp_path: Path, img_size: tuple[int, int]):
    img_path = _make_png(tmp_path / f"img_{img_size[0]}x{img_size[1]}.png", img_size)
    raw = build_docx_bytes(
        title="Aspect Ratio Check",
        main_topic="Image sizing",
        author_name="QA",
        theme_config={},
        version=1,
        sections=[
            {
                "title": "Visual Figure",
                "content_json": {"paragraphs": ["Figure below."]},
                "image_path": img_path,
                "image_caption": f"Size {img_size[0]}x{img_size[1]}",
            }
        ],
    )
    doc = Document(io.BytesIO(raw))
    assert len(doc.inline_shapes) == 1
    assert f"Size {img_size[0]}x{img_size[1]}" in "\n".join(p.text for p in doc.paragraphs)
