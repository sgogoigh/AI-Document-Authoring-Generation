import io
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from app.services.doc_builder.theme import DocTheme, get_theme, hex_to_rgb_tuple

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def _rgb(hex_str: str) -> RGBColor:
    r, g, b = hex_to_rgb_tuple(hex_str)
    return RGBColor(r, g, b)


def _clamp(text: str, max_chars: int) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 1].rstrip() + "…"


def _add_run(paragraph, text: str, *, font_name: str, size_pt: int, bold: bool = False,
             italic: bool = False, color: RGBColor):
    run = paragraph.add_run()
    run.text = text
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return run


def _add_rect(slide, left, top, width, height, fill_hex: str, border_hex: str | None = None):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill_hex)
    if border_hex:
        shape.line.color.rgb = _rgb(border_hex)
        shape.line.width = Pt(1)
    else:
        shape.line.fill.background()
    return shape


def _add_rounded_card(slide, left, top, width, height, fill_hex: str, border_hex: str):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.adjustments[0] = 0.03
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill_hex)
    shape.line.color.rgb = _rgb(border_hex)
    shape.line.width = Pt(1)
    return shape


def _add_title_slide(
    prs: Presentation,
    *,
    title: str,
    main_topic: str,
    author_name: str,
    audience: str,
    version: int,
    theme: DocTheme,
) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = _rgb(theme.dark_bg_hex)

    _add_rect(slide, Inches(0), Inches(0), Inches(0.28), SLIDE_H, theme.accent_hex)
    _add_rect(slide, Inches(9.4), Inches(0.7), Inches(3.2), Inches(0.08), theme.accent_hex)

    tb = slide.shapes.add_textbox(Inches(0.95), Inches(1.45), Inches(11.3), Inches(4.5))
    tf = tb.text_frame
    tf.word_wrap = True

    p_eyebrow = tf.paragraphs[0]
    p_eyebrow.space_after = Pt(14)
    _add_run(
        p_eyebrow,
        "EXECUTIVE PRESENTATION",
        font_name=theme.font_family,
        size_pt=12,
        bold=True,
        color=_rgb(theme.accent_hex),
    )

    p_title = tf.add_paragraph()
    p_title.space_after = Pt(16)
    _add_run(
        p_title,
        _clamp(title, 95),
        font_name=theme.font_family,
        size_pt=38,
        bold=True,
        color=RGBColor(255, 255, 255),
    )

    p_sub = tf.add_paragraph()
    _add_run(
        p_sub,
        _clamp(main_topic, 180),
        font_name=theme.font_family,
        size_pt=17,
        color=RGBColor(203, 213, 225),
    )

    _add_rect(slide, Inches(0.95), Inches(6.25), Inches(11.4), Inches(0.02), theme.accent_hex)
    meta_tb = slide.shapes.add_textbox(Inches(0.95), Inches(6.42), Inches(11.4), Inches(0.5))
    mp = meta_tb.text_frame.paragraphs[0]
    _add_run(
        mp,
        (
            f"Prepared by {author_name}   •   Audience: {_clamp(audience, 45)}   •   "
            f"{datetime.now(timezone.utc).strftime('%b %d, %Y')} (v{version})"
        ),
        font_name=theme.font_family,
        size_pt=11,
        color=RGBColor(148, 163, 184),
    )


def _add_header_chrome(
    slide, *, kicker: str, title: str, subtitle: str, theme: DocTheme
) -> None:
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor(248, 250, 252)

    _add_rect(slide, Inches(0), Inches(0), SLIDE_W, Inches(0.1), theme.primary_hex)
    _add_rect(slide, Inches(0), Inches(0), Inches(3.2), Inches(0.1), theme.accent_hex)

    tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.28), Inches(12.1), Inches(1.3))
    tf = tb.text_frame
    tf.word_wrap = True

    pk = tf.paragraphs[0]
    pk.space_after = Pt(3)
    _add_run(
        pk,
        _clamp(kicker.upper(), 40),
        font_name=theme.font_family,
        size_pt=10,
        bold=True,
        color=_rgb(theme.accent_hex),
    )

    pt = tf.add_paragraph()
    pt.space_after = Pt(4)
    _add_run(
        pt,
        _clamp(title, 75),
        font_name=theme.font_family,
        size_pt=24,
        bold=True,
        color=_rgb(theme.primary_hex),
    )

    if subtitle:
        ps = tf.add_paragraph()
        _add_run(
            ps,
            _clamp(subtitle, 120),
            font_name=theme.font_family,
            size_pt=13,
            color=_rgb(theme.muted_text_hex),
        )


def _add_footer_chrome(
    slide, deck_title: str, slide_num: int, total_slides: int, theme: DocTheme
) -> None:
    _add_rect(slide, Inches(0.6), Inches(6.98), Inches(12.1), Inches(0.015), theme.border_hex)
    tb_l = slide.shapes.add_textbox(Inches(0.6), Inches(7.04), Inches(9.5), Inches(0.32))
    _add_run(
        tb_l.text_frame.paragraphs[0],
        _clamp(deck_title, 70),
        font_name=theme.font_family,
        size_pt=9,
        color=_rgb(theme.muted_text_hex),
    )

    tb_r = slide.shapes.add_textbox(Inches(10.5), Inches(7.04), Inches(2.2), Inches(0.32))
    p_r = tb_r.text_frame.paragraphs[0]
    p_r.alignment = PP_ALIGN.RIGHT
    _add_run(
        p_r,
        f"Slide {slide_num} of {total_slides}",
        font_name=theme.font_family,
        size_pt=9,
        bold=True,
        color=_rgb(theme.primary_hex),
    )


def _add_agenda_slide(
    prs: Presentation, deck_title: str, sections: list[dict], theme: DocTheme
) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_header_chrome(
        slide,
        kicker="AGENDA & STRUCTURE",
        title="Presentation Roadmap",
        subtitle=f"Structured overview for {_clamp(deck_title, 70)}",
        theme=theme,
    )

    items = sections[:12]
    cols = 2 if len(items) > 5 else 1
    rows_per_col = (len(items) + cols - 1) // cols

    for idx, sec in enumerate(items):
        col = idx // rows_per_col if cols == 2 else 0
        row = idx % rows_per_col
        card_w = Inches(5.85) if cols == 2 else Inches(12.1)
        left = Inches(0.6) + col * Inches(6.25)
        top = Inches(1.85) + row * Inches(0.86)

        _add_rounded_card(slide, left, top, card_w, Inches(0.72), "FFFFFF", theme.border_hex)
        _add_rect(slide, left, top, Inches(0.12), Inches(0.72), theme.accent_hex)

        tb = slide.shapes.add_textbox(
            left + Inches(0.25), top + Inches(0.12), card_w - Inches(0.4), Inches(0.5)
        )
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        _add_run(
            p,
            f"{idx + 1:02d}   ",
            font_name=theme.font_family,
            size_pt=13,
            bold=True,
            color=_rgb(theme.accent_hex),
        )
        _add_run(
            p,
            _clamp(sec["title"], 55),
            font_name=theme.font_family,
            size_pt=14,
            bold=True,
            color=_rgb(theme.primary_hex),
        )

    _add_footer_chrome(slide, deck_title, 2, len(sections) + 2, theme)


def _write_bullets_into_box(
    slide, left, top, width, height, bullets: list[str], theme: DocTheme, font_size: int = 14
) -> None:
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP

    clean_bullets = [b for b in bullets if isinstance(b, str) and b.strip()][:5]
    if not clean_bullets:
        clean_bullets = ["Structured slide content ready for review."]

    for idx, text in enumerate(clean_bullets):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.space_after = Pt(12)
        p.line_spacing = 1.18
        _add_run(
            p,
            "▸  ",
            font_name=theme.font_family,
            size_pt=font_size,
            bold=True,
            color=_rgb(theme.accent_hex),
        )
        _add_run(
            p,
            _clamp(text, 155),
            font_name=theme.font_family,
            size_pt=font_size,
            color=_rgb(theme.body_text_hex),
        )


def _add_fitted_picture(slide, image_path: Path, left, top, max_w, max_h) -> None:
    with Image.open(image_path) as im:
        iw, ih = im.size
    if iw <= 0 or ih <= 0:
        return
    ratio = min(max_w / iw, max_h / ih)
    draw_w = int(iw * ratio)
    draw_h = int(ih * ratio)
    offset_x = left + int((max_w - draw_w) / 2)
    offset_y = top + int((max_h - draw_h) / 2)
    slide.shapes.add_picture(str(image_path), offset_x, offset_y, width=draw_w, height=draw_h)


def build_pptx_bytes(
    *,
    title: str,
    main_topic: str,
    author_name: str,
    theme_config: dict,
    version: int,
    sections: list[dict],
) -> bytes:
    """Assemble a crisp 16:9 widescreen .pptx deck with layout safeguards and speaker notes."""
    theme = get_theme((theme_config or {}).get("palette"))
    audience = (theme_config or {}).get("audience", "Business leadership & stakeholders")

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    _add_title_slide(
        prs,
        title=title,
        main_topic=main_topic,
        author_name=author_name,
        audience=audience,
        version=version,
        theme=theme,
    )
    _add_agenda_slide(prs, title, sections, theme)

    total_slides = len(sections) + 2

    for idx, sec in enumerate(sections):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        content = sec.get("content_json") or {}
        kicker = content.get("kicker") or f"SECTION {idx + 1:02d}"
        subtitle = content.get("subtitle") or ""
        bullets = content.get("bullets") or []
        if not bullets and sec.get("content_text"):
            bullets = [
                line.lstrip("- ").strip()
                for line in sec["content_text"].splitlines()
                if line.strip()
            ][:5]

        _add_header_chrome(
            slide,
            kicker=kicker,
            title=sec["title"],
            subtitle=subtitle,
            theme=theme,
        )

        image_path: Path | None = sec.get("image_path")
        has_image = bool(image_path and image_path.exists())
        variant = content.get("layout_variant", "bullets_only")

        if has_image:
            _add_rounded_card(
                slide, Inches(0.6), Inches(1.8), Inches(6.75), Inches(4.9), "FFFFFF", theme.border_hex
            )
            _write_bullets_into_box(
                slide, Inches(0.88), Inches(2.05), Inches(6.2), Inches(4.4), bullets, theme, font_size=14
            )

            _add_rounded_card(
                slide, Inches(7.6), Inches(1.8), Inches(5.1), Inches(4.9), "FFFFFF", theme.border_hex
            )
            _add_fitted_picture(
                slide, image_path, Inches(7.8), Inches(1.98), Inches(4.7), Inches(4.05)
            )
            cap_text = sec.get("image_caption") or content.get("image_caption") or sec["title"]
            cap_tb = slide.shapes.add_textbox(Inches(7.75), Inches(6.15), Inches(4.8), Inches(0.45))
            cap_p = cap_tb.text_frame.paragraphs[0]
            cap_p.alignment = PP_ALIGN.CENTER
            _add_run(
                cap_p,
                _clamp(cap_text, 70),
                font_name=theme.font_family,
                size_pt=10,
                italic=True,
                color=_rgb(theme.muted_text_hex),
            )

        elif variant == "two_column" and content.get("secondary_bullets"):
            _add_rounded_card(
                slide, Inches(0.6), Inches(1.8), Inches(5.88), Inches(4.9), "FFFFFF", theme.border_hex
            )
            _add_rect(slide, Inches(0.6), Inches(1.8), Inches(5.88), Inches(0.46), theme.primary_hex)
            lh = slide.shapes.add_textbox(Inches(0.82), Inches(1.86), Inches(5.4), Inches(0.35))
            _add_run(
                lh.text_frame.paragraphs[0],
                "Key Insights",
                font_name=theme.font_family,
                size_pt=12,
                bold=True,
                color=RGBColor(255, 255, 255),
            )
            _write_bullets_into_box(
                slide, Inches(0.82), Inches(2.42), Inches(5.45), Inches(4.1), bullets, theme, font_size=13
            )

            _add_rounded_card(
                slide, Inches(6.85), Inches(1.8), Inches(5.88), Inches(4.9), "FFFFFF", theme.border_hex
            )
            _add_rect(slide, Inches(6.85), Inches(1.8), Inches(5.88), Inches(0.46), theme.accent_hex)
            rh = slide.shapes.add_textbox(Inches(7.07), Inches(1.86), Inches(5.4), Inches(0.35))
            col2_title = content.get("secondary_column_title") or "Strategic Implications"
            _add_run(
                rh.text_frame.paragraphs[0],
                _clamp(col2_title, 45),
                font_name=theme.font_family,
                size_pt=12,
                bold=True,
                color=RGBColor(255, 255, 255),
            )
            _write_bullets_into_box(
                slide,
                Inches(7.07),
                Inches(2.42),
                Inches(5.45),
                Inches(4.1),
                content["secondary_bullets"],
                theme,
                font_size=13,
            )

        elif variant == "metrics_cards" and content.get("metric_cards"):
            cards = content["metric_cards"][:3]
            gap = Inches(0.35)
            total_w = Inches(12.1)
            card_w = int((total_w - gap * (len(cards) - 1)) / len(cards))
            for c_i, card in enumerate(cards):
                c_left = Inches(0.6) + c_i * (card_w + gap)
                _add_rounded_card(
                    slide, c_left, Inches(1.8), card_w, Inches(1.65), theme.soft_tint_hex, theme.border_hex
                )
                _add_rect(slide, c_left, Inches(1.8), card_w, Inches(0.08), theme.accent_hex)
                ctb = slide.shapes.add_textbox(
                    c_left + Inches(0.22), Inches(2.0), card_w - Inches(0.44), Inches(1.3)
                )
                ctf = ctb.text_frame
                ctf.word_wrap = True
                pv = ctf.paragraphs[0]
                pv.space_after = Pt(4)
                _add_run(
                    pv,
                    _clamp(str(card.get("value", "—")), 18),
                    font_name=theme.font_family,
                    size_pt=30,
                    bold=True,
                    color=_rgb(theme.primary_hex),
                )
                pl = ctf.add_paragraph()
                _add_run(
                    pl,
                    _clamp(str(card.get("label", "")), 45),
                    font_name=theme.font_family,
                    size_pt=12,
                    color=_rgb(theme.muted_text_hex),
                )

            _add_rounded_card(
                slide, Inches(0.6), Inches(3.7), Inches(12.1), Inches(3.0), "FFFFFF", theme.border_hex
            )
            _write_bullets_into_box(
                slide, Inches(0.9), Inches(3.9), Inches(11.5), Inches(2.65), bullets, theme, font_size=14
            )

        else:
            _add_rounded_card(
                slide, Inches(0.6), Inches(1.8), Inches(12.1), Inches(4.9), "FFFFFF", theme.border_hex
            )
            _add_rect(slide, Inches(0.6), Inches(1.8), Inches(0.14), Inches(4.9), theme.accent_hex)
            _write_bullets_into_box(
                slide, Inches(1.0), Inches(2.1), Inches(11.35), Inches(4.35), bullets, theme, font_size=15
            )

        _add_footer_chrome(slide, title, idx + 3, total_slides, theme)

        if notes := content.get("speaker_notes"):
            notes_slide = slide.notes_slide
            notes_slide.notes_text_frame.text = str(notes)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
