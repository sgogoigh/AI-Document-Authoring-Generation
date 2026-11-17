import io
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor

from app.services.doc_builder.theme import DocTheme, get_theme, hex_to_rgb_tuple


def _rgb(hex_str: str) -> RGBColor:
    r, g, b = hex_to_rgb_tuple(hex_str)
    return RGBColor(r, g, b)


def _set_cell_shading(cell, fill_hex: str) -> None:
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def _set_cell_margins(cell, top=100, bottom=100, left=140, right=140) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = OxmlElement("w:tcMar")
    for side, val in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        node = OxmlElement(f"w:{side}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tc_mar.append(node)
    tc_pr.append(tc_mar)


def _set_callout_borders(cell, accent_hex: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="none"/>'
        f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{accent_hex}"/>'
        f'<w:bottom w:val="none"/>'
        f'<w:right w:val="none"/>'
        f"</w:tcBorders>"
    )
    tc_pr.append(borders)


def _prevent_row_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tr_pr.append(OxmlElement("w:cantSplit"))


def _mark_header_row(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tr_pr.append(OxmlElement("w:tblHeader"))
    tr_pr.append(OxmlElement("w:cantSplit"))
    for cell in row.cells:
        for p in cell.paragraphs:
            p.paragraph_format.keep_with_next = True


def _set_table_borders(table, border_hex: str) -> None:
    tbl_pr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="6" w:space="0" w:color="{border_hex}"/>'
        f'<w:bottom w:val="single" w:sz="8" w:space="0" w:color="{border_hex}"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="{border_hex}"/>'
        f'<w:left w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'<w:insideV w:val="none"/>'
        f"</w:tblBorders>"
    )
    tbl_pr.append(borders)


def _add_bottom_border_to_paragraph(paragraph, color_hex: str) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = parse_xml(
        f'<w:pBdr {nsdecls("w")}>'
        f'<w:bottom w:val="single" w:sz="12" w:space="4" w:color="{color_hex}"/>'
        f"</w:pBdr>"
    )
    p_pr.append(p_bdr)


def _add_page_number_field(run) -> None:
    fld_char1 = parse_xml(r'<w:fldChar %s w:fldCharType="begin"/>' % nsdecls("w"))
    instr_text = parse_xml(r'<w:instrText %s xml:space="preserve"> PAGE </w:instrText>' % nsdecls("w"))
    fld_char2 = parse_xml(r'<w:fldChar %s w:fldCharType="separate"/>' % nsdecls("w"))
    fld_char3 = parse_xml(r'<w:fldChar %s w:fldCharType="end"/>' % nsdecls("w"))
    run._r.append(fld_char1)
    run._r.append(instr_text)
    run._r.append(fld_char2)
    run._r.append(fld_char3)


def _configure_base_styles(doc: Document, theme: DocTheme) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = theme.font_family
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = _rgb(theme.body_text_hex)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.22

    for section in doc.sections:
        section.top_margin = Inches(0.85)
        section.bottom_margin = Inches(0.85)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)
        section.different_first_page_header_footer = True


def _add_cover_page(
    doc: Document,
    *,
    title: str,
    main_topic: str,
    author_name: str,
    audience: str,
    tone: str,
    version: int,
    theme: DocTheme,
) -> None:
    banner_tbl = doc.add_table(rows=1, cols=1)
    banner_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = banner_tbl.cell(0, 0)
    cell.width = Inches(6.7)
    _set_cell_shading(cell, theme.primary_hex)
    _set_cell_margins(cell, top=320, bottom=320, left=260, right=260)

    p_kicker = cell.paragraphs[0]
    p_kicker.paragraph_format.space_after = Pt(8)
    r_k = p_kicker.add_run("EXECUTIVE DOCUMENT REPORT")
    r_k.bold = True
    r_k.font.size = Pt(9.5)
    r_k.font.color.rgb = _rgb(theme.accent_hex)

    p_title = cell.add_paragraph()
    p_title.paragraph_format.space_after = Pt(10)
    r_t = p_title.add_run(title)
    r_t.bold = True
    r_t.font.size = Pt(24)
    r_t.font.color.rgb = RGBColor(255, 255, 255)

    p_topic = cell.add_paragraph()
    p_topic.paragraph_format.space_after = Pt(2)
    r_sub = p_topic.add_run(main_topic)
    r_sub.font.size = Pt(11.5)
    r_sub.font.color.rgb = RGBColor(226, 232, 240)

    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_before = Pt(36)

    meta_tbl = doc.add_table(rows=4, cols=2)
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_table_borders(meta_tbl, theme.border_hex)
    meta_rows = [
        ("Prepared By", author_name),
        ("Target Audience", audience),
        ("Editorial Tone", tone.capitalize()),
        ("Generated Date & Version", f"{datetime.now(timezone.utc).strftime('%B %d, %Y')} • v{version}"),
    ]
    for idx, (label, val) in enumerate(meta_rows):
        row = meta_tbl.rows[idx]
        c0, c1 = row.cells[0], row.cells[1]
        c0.width = Inches(2.2)
        c1.width = Inches(4.5)
        _set_cell_shading(c0, theme.soft_tint_hex)
        _set_cell_margins(c0, top=110, bottom=110, left=140, right=140)
        _set_cell_margins(c1, top=110, bottom=110, left=140, right=140)
        r0 = c0.paragraphs[0].add_run(label)
        r0.bold = True
        r0.font.size = Pt(9.5)
        r0.font.color.rgb = _rgb(theme.primary_hex)
        r1 = c1.paragraphs[0].add_run(val)
        r1.font.size = Pt(10)
        r1.font.color.rgb = _rgb(theme.body_text_hex)

    doc.add_page_break()


def _add_outline_overview(doc: Document, sections: list[dict], theme: DocTheme) -> None:
    p_h = doc.add_paragraph()
    p_h.paragraph_format.space_after = Pt(10)
    r_h = p_h.add_run("Document Outline")
    r_h.bold = True
    r_h.font.size = Pt(16)
    r_h.font.color.rgb = _rgb(theme.primary_hex)
    _add_bottom_border_to_paragraph(p_h, theme.accent_hex)

    for idx, sec in enumerate(sections):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(5)
        p.paragraph_format.left_indent = Inches(0.15)
        r_num = p.add_run(f"{idx + 1:02d}   ")
        r_num.bold = True
        r_num.font.color.rgb = _rgb(theme.accent_hex)
        r_title = p.add_run(sec["title"])
        r_title.bold = True
        r_title.font.color.rgb = _rgb(theme.body_text_hex)

    doc.add_page_break()


def _configure_headers_and_footers(doc: Document, title: str, version: int, theme: DocTheme) -> None:
    sec = doc.sections[0]
    header_p = sec.header.paragraphs[0]
    header_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_h = header_p.add_run(title)
    r_h.font.size = Pt(8.5)
    r_h.font.color.rgb = _rgb(theme.muted_text_hex)

    footer_p = sec.footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_f1 = footer_p.add_run(f"AI Document Authoring Platform • v{version}   |   Page ")
    r_f1.font.size = Pt(8.5)
    r_f1.font.color.rgb = _rgb(theme.muted_text_hex)
    r_pg = footer_p.add_run()
    r_pg.font.size = Pt(8.5)
    r_pg.font.color.rgb = _rgb(theme.primary_hex)
    r_pg.bold = True
    _add_page_number_field(r_pg)


def build_docx_bytes(
    *,
    title: str,
    main_topic: str,
    author_name: str,
    theme_config: dict,
    version: int,
    sections: list[dict],
) -> bytes:
    """Assemble a cleanly styled, structured .docx report from latest section content and assets."""
    theme = get_theme((theme_config or {}).get("palette"))
    audience = (theme_config or {}).get("audience", "Business leadership & stakeholders")
    tone = (theme_config or {}).get("tone", "executive")

    doc = Document()
    _configure_base_styles(doc, theme)
    _configure_headers_and_footers(doc, title, version, theme)

    _add_cover_page(
        doc,
        title=title,
        main_topic=main_topic,
        author_name=author_name,
        audience=audience,
        tone=tone,
        version=version,
        theme=theme,
    )
    _add_outline_overview(doc, sections, theme)

    for idx, sec in enumerate(sections):
        if idx > 0:
            doc.add_paragraph().paragraph_format.space_before = Pt(8)

        # Numbered Section Heading
        p_head = doc.add_paragraph()
        p_head.paragraph_format.keep_with_next = True
        p_head.paragraph_format.space_before = Pt(6)
        p_head.paragraph_format.space_after = Pt(10)
        r_idx = p_head.add_run(f"{idx + 1:02d}  |  ")
        r_idx.bold = True
        r_idx.font.size = Pt(14)
        r_idx.font.color.rgb = _rgb(theme.accent_hex)
        r_sec_title = p_head.add_run(sec["title"])
        r_sec_title.bold = True
        r_sec_title.font.size = Pt(15)
        r_sec_title.font.color.rgb = _rgb(theme.primary_hex)
        _add_bottom_border_to_paragraph(p_head, theme.border_hex)

        content = sec.get("content_json") or {}

        # Summary Callout Box
        if summary := content.get("summary_callout"):
            callout_tbl = doc.add_table(rows=1, cols=1)
            callout_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
            _prevent_row_split(callout_tbl.rows[0])
            c_cell = callout_tbl.cell(0, 0)
            c_cell.width = Inches(6.7)
            _set_cell_shading(c_cell, theme.soft_tint_hex)
            _set_callout_borders(c_cell, theme.accent_hex)
            _set_cell_margins(c_cell, top=120, bottom=120, left=180, right=160)
            cp = c_cell.paragraphs[0]
            cp.paragraph_format.space_after = Pt(0)
            r_lbl = cp.add_run("KEY TAKEAWAY: ")
            r_lbl.bold = True
            r_lbl.font.size = Pt(9)
            r_lbl.font.color.rgb = _rgb(theme.accent_hex)
            r_sum = cp.add_run(summary)
            r_sum.italic = True
            r_sum.font.size = Pt(10.5)
            r_sum.font.color.rgb = _rgb(theme.primary_hex)
            doc.add_paragraph().paragraph_format.space_after = Pt(2)

        # Body Paragraphs
        for para_text in content.get("paragraphs", []):
            if isinstance(para_text, str) and para_text.strip():
                p = doc.add_paragraph(para_text.strip())
                p.paragraph_format.space_after = Pt(7)

        # Fallback if raw text only
        if not content and sec.get("content_text"):
            doc.add_paragraph(sec["content_text"])

        # Structured Bullet Points
        for bullet in content.get("bullet_points", []):
            bp = doc.add_paragraph(style="List Bullet")
            bp.paragraph_format.space_after = Pt(4)
            if isinstance(bullet, dict):
                label = bullet.get("label", "").strip()
                detail = bullet.get("detail", "").strip()
                if label:
                    rl = bp.add_run(f"{label}: ")
                    rl.bold = True
                    rl.font.color.rgb = _rgb(theme.primary_hex)
                bp.add_run(detail)
            elif isinstance(bullet, str):
                bp.add_run(bullet)

        # Optional Structured Data Table
        data_table = content.get("data_table")
        if isinstance(data_table, dict) and data_table.get("headers") and data_table.get("rows"):
            headers = data_table["headers"][:4]
            rows = data_table["rows"][:6]
            if table_title := data_table.get("title"):
                pt = doc.add_paragraph()
                pt.paragraph_format.space_before = Pt(6)
                pt.paragraph_format.space_after = Pt(3)
                pt.paragraph_format.keep_with_next = True
                rt = pt.add_run(table_title)
                rt.bold = True
                rt.font.size = Pt(10)
                rt.font.color.rgb = _rgb(theme.primary_hex)

            tbl = doc.add_table(rows=len(rows) + 1, cols=len(headers))
            tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
            _set_table_borders(tbl, theme.border_hex)
            col_width = Inches(6.7 / max(1, len(headers)))

            for col_i, h_text in enumerate(headers):
                cell = tbl.cell(0, col_i)
                cell.width = col_width
                _set_cell_shading(cell, theme.primary_hex)
                _set_cell_margins(cell, top=90, bottom=90, left=110, right=110)
                rh = cell.paragraphs[0].add_run(str(h_text))
                rh.bold = True
                rh.font.size = Pt(9.5)
                rh.font.color.rgb = RGBColor(255, 255, 255)
            _mark_header_row(tbl.rows[0])

            for r_i, row_vals in enumerate(rows):
                _prevent_row_split(tbl.rows[r_i + 1])
                for col_i in range(len(headers)):
                    cell = tbl.cell(r_i + 1, col_i)
                    cell.width = col_width
                    if r_i % 2 == 1:
                        _set_cell_shading(cell, theme.zebra_hex)
                    _set_cell_margins(cell, top=80, bottom=80, left=110, right=110)
                    val_str = str(row_vals[col_i]) if col_i < len(row_vals) else ""
                    rc = cell.paragraphs[0].add_run(val_str)
                    rc.font.size = Pt(9.5)
                    rc.font.color.rgb = _rgb(theme.body_text_hex)

            doc.add_paragraph().paragraph_format.space_after = Pt(4)

        # Embedded Gemini-Generated Visual
        image_path: Path | None = sec.get("image_path")
        if image_path and image_path.exists():
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img.paragraph_format.space_before = Pt(8)
            p_img.paragraph_format.space_after = Pt(3)
            p_img.paragraph_format.keep_with_next = True
            p_img.add_run().add_picture(str(image_path), width=Inches(5.4))

            caption = sec.get("image_caption") or content.get("image_caption") or sec["title"]
            p_cap = doc.add_paragraph()
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.paragraph_format.space_after = Pt(8)
            r_cap = p_cap.add_run(caption)
            r_cap.italic = True
            r_cap.font.size = Pt(9)
            r_cap.font.color.rgb = _rgb(theme.muted_text_hex)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
