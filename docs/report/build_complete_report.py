from __future__ import annotations

"""Rebuild the uploaded Aegis report as one complete academic DOCX.

The uploaded document remains the layout authority.  Chapters 1-3 and 5-6 are
retained from it, Chapter 4 is replaced with the tutor-corrected DSDM-only
timeline, and Chapters 7-10/front matter/appendices are added from verified
repository evidence.
"""

from copy import deepcopy
from pathlib import Path
import importlib.util
import json
import re

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path("/Users/htunkhainglynn/Projects/aegis")
SOURCE = Path("/Users/htunkhainglynn/Downloads/Aegis_Report_Ch1-4.docx")
OUTPUT = ROOT / "docs/report/Aegis_Project_Report_Complete.docx"
DIAGRAMS = ROOT / "docs/diagrams"
EVIDENCE = ROOT / "docs/evidence"
SKILL = Path("/Users/htunkhainglynn/.codex/plugins/cache/openai-primary-runtime/documents/26.819.11345/skills/documents")

spec = importlib.util.spec_from_file_location("table_geometry", SKILL / "scripts/table_geometry.py")
table_geometry = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(table_geometry)

BLUE = "2E74B5"
DARK_BLUE = "1F4D78"
PALE_BLUE = "DCE6F1"
PALE_GREEN = "E2F0D9"
PALE_AMBER = "FFF2CC"
PALE_RED = "FCE4D6"
GREY = "666666"


def set_font(run, name="Arial", size=9, bold=None, italic=None, color=None):
    run.font.name = name
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:hAnsi"), name)
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    return run


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    marker = OxmlElement("w:tblHeader")
    marker.set(qn("w:val"), "true")
    tr_pr.append(marker)


def set_table_borders(table, color="A6A6A6", size="4"):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = qn(f"w:{edge}")
        border = borders.find(tag)
        if border is None:
            border = OxmlElement(f"w:{edge}")
            borders.append(border)
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), size)
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), color)


def keep_with_next(paragraph, enabled=True):
    paragraph.paragraph_format.keep_with_next = enabled


def body_text(element):
    return "".join(node.text or "" for node in element.iter(qn("w:t"))).strip()


def source_slices(doc):
    elements = [deepcopy(e) for e in doc._element.body if e.tag != qn("w:sectPr")]
    positions = {}
    for index, element in enumerate(elements):
        text = body_text(element)
        if text.startswith("Chapter "):
            positions[text] = index
    required = [
        "Chapter 1: Introduction",
        "Chapter 4: Project Timeline",
        "Chapter 5: Legal, Social, Ethical and Professional (LSEP) Issues",
        "Chapter 7: System Design",
    ]
    for heading in required:
        if heading not in positions:
            raise RuntimeError(f"Required source heading missing: {heading}")
    early = elements[positions[required[0]] : positions[required[1]]]
    analysis = elements[positions[required[2]] : positions[required[3]]]
    return early, analysis


def clear_body(doc):
    body = doc._element.body
    sect_pr = body.sectPr
    for child in list(body):
        if child is not sect_pr:
            body.remove(child)


def append_elements(doc, elements):
    body = doc._element.body
    sect_pr = body.sectPr
    for element in elements:
        body.insert(body.index(sect_pr), deepcopy(element))


def balance_preserved_chapter_pages(doc):
    """Keep Chapter 1's closing summary together instead of orphaning two lines."""
    for paragraph in doc.paragraphs:
        if " ".join(paragraph.text.split()) == "1.9 Summary":
            paragraph.paragraph_format.page_break_before = True
            break


def configure_styles(doc):
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Arial"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    normal.font.size = Pt(9)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.08

    for name, size, color in (
        ("Heading 1", 16, BLUE),
        ("Heading 2", 13, BLUE),
        ("Heading 3", 11, DARK_BLUE),
    ):
        style = styles[name]
        style.font.name = "Arial"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(10 if name != "Heading 1" else 0)
        style.paragraph_format.space_after = Pt(5)
        style.paragraph_format.keep_with_next = True
    styles["Heading 1"].paragraph_format.page_break_before = True

    for name in ("List Bullet", "List Number", "List Paragraph"):
        if name in styles:
            styles[name].font.name = "Arial"
            styles[name].font.size = Pt(9)
            styles[name].paragraph_format.space_after = Pt(3)

    if "Aegis Caption" not in styles:
        caption = styles.add_style("Aegis Caption", WD_STYLE_TYPE.PARAGRAPH)
    else:
        caption = styles["Aegis Caption"]
    caption.font.name = "Arial"
    caption.font.size = Pt(8)
    caption.font.italic = True
    caption.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.space_before = Pt(2)
    caption.paragraph_format.space_after = Pt(8)
    caption.paragraph_format.keep_with_next = False

    if "Aegis Code" not in styles:
        code = styles.add_style("Aegis Code", WD_STYLE_TYPE.PARAGRAPH)
    else:
        code = styles["Aegis Code"]
    code.font.name = "Menlo"
    code.font.size = Pt(7.5)
    code.paragraph_format.left_indent = Inches(0.18)
    code.paragraph_format.right_indent = Inches(0.12)
    code.paragraph_format.space_before = Pt(1)
    code.paragraph_format.space_after = Pt(1)
    code.paragraph_format.line_spacing = 1.0

    if "Front Matter Heading" not in styles:
        fm = styles.add_style("Front Matter Heading", WD_STYLE_TYPE.PARAGRAPH)
    else:
        fm = styles["Front Matter Heading"]
    fm.font.name = "Arial"
    fm.font.size = Pt(18)
    fm.font.bold = True
    fm.font.color.rgb = RGBColor.from_string(BLUE)
    fm.paragraph_format.space_after = Pt(12)
    fm.paragraph_format.keep_with_next = True


def paragraph(doc, text="", *, bold_lead=None, italic=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = doc.add_paragraph()
    p.alignment = align
    if bold_lead and text.startswith(bold_lead):
        set_font(p.add_run(bold_lead), bold=True)
        set_font(p.add_run(text[len(bold_lead) :]), italic=italic)
    else:
        set_font(p.add_run(text), italic=italic)
    return p


def bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Paragraph")
        p_pr = p._p.get_or_add_pPr()
        num_pr = OxmlElement("w:numPr")
        ilvl = OxmlElement("w:ilvl")
        ilvl.set(qn("w:val"), "0")
        num_id = OxmlElement("w:numId")
        num_id.set(qn("w:val"), "1")
        num_pr.append(ilvl)
        num_pr.append(num_id)
        p_pr.append(num_pr)
        set_font(p.add_run(item))


def numbered(doc, items):
    # The retained source contains bullet definitions only.  Keep this helper
    # semantically numbered without inventing a new numbering package.
    for index, item in enumerate(items, start=1):
        p = doc.add_paragraph(style="List Paragraph")
        set_font(p.add_run(f"{index}. {item}"))


def heading(doc, text, level=1):
    return doc.add_paragraph(text, style=f"Heading {level}")


def caption(doc, text):
    p = doc.add_paragraph(style="Aegis Caption")
    set_font(p.add_run(text), size=8, italic=True)
    return p


def add_table(doc, headers, rows, weights, caption_text=None, header_fill=PALE_BLUE):
    if caption_text:
        p = caption(doc, caption_text)
        p.paragraph_format.keep_with_next = True
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Normal Table"
    set_table_borders(table)
    table.autofit = False
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = ""
        set_cell_shading(cell, header_fill)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        set_font(p.add_run(str(header)), size=8, bold=True)
    repeat_table_header(table.rows[0])
    for row in rows:
        table_row = table.add_row()
        tr_pr = table_row._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
        cells = table_row.cells
        for index, value in enumerate(row):
            cell = cells[index]
            cell.text = ""
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if len(str(value)) < 28 else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            set_font(p.add_run(str(value)), size=8)
    width = table_geometry.section_content_width_dxa(doc.sections[-1])
    widths = table_geometry.column_widths_from_weights(weights, width)
    table_geometry.apply_table_geometry(table, widths)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def set_picture_alt(inline_shape, description):
    doc_pr = inline_shape._inline.docPr
    doc_pr.set("descr", description)
    doc_pr.set("title", description)


def add_figure(doc, path, caption_text, width=6.0, alt=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.keep_with_next = True
    shape = p.add_run().add_picture(str(path), width=Inches(width))
    set_picture_alt(shape, alt or caption_text)
    caption(doc, caption_text)


def add_landscape_figure(doc, path, caption_text, width, alt=None):
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width = Inches(11.69)
    sec.page_height = Inches(8.27)
    sec.left_margin = sec.right_margin = Inches(0.45)
    sec.top_margin = sec.bottom_margin = Inches(0.35)
    sec.header.is_linked_to_previous = True
    sec.footer.is_linked_to_previous = True
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.keep_with_next = True
    shape = p.add_run().add_picture(str(path), width=Inches(width))
    set_picture_alt(shape, alt or caption_text)
    caption(doc, caption_text)
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width = Inches(8.27)
    sec.page_height = Inches(11.69)
    sec.left_margin = sec.right_margin = Inches(1)
    sec.top_margin = sec.bottom_margin = Inches(1)
    sec.header.is_linked_to_previous = True
    sec.footer.is_linked_to_previous = True


def add_code(doc, code_text, label=None):
    if label:
        p = paragraph(doc, label, italic=True, align=WD_ALIGN_PARAGRAPH.LEFT)
        p.paragraph_format.keep_with_next = True
    for line in code_text.strip("\n").splitlines():
        p = doc.add_paragraph(style="Aegis Code")
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        set_font(p.add_run(line or " "), name="Menlo", size=7.5)
        p_pr = p._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:fill"), "F2F4F7")
        p_pr.append(shd)


def add_note(doc, label, text, fill=PALE_AMBER):
    table = doc.add_table(rows=1, cols=1)
    table.style = "Normal Table"
    set_table_borders(table)
    tr_pr = table.rows[0]._tr.get_or_add_trPr()
    tr_pr.append(OxmlElement("w:cantSplit"))
    cell = table.cell(0, 0)
    set_cell_shading(cell, fill)
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_font(p.add_run(label + ": "), bold=True, color=DARK_BLUE)
    set_font(p.add_run(text))
    width = table_geometry.section_content_width_dxa(doc.sections[-1])
    table_geometry.apply_table_geometry(table, [width])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_toc_field(doc):
    p = doc.add_paragraph()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    p._p.append(begin)
    p._p.append(instr)
    p._p.append(separate)
    r = p.add_run("The table of contents will update when opened in Microsoft Word.")
    set_font(r, size=9, italic=True, color=GREY)
    p._p.append(end)


def add_toc_entry(doc, text, page, level=0):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.22 * level)
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.tab_stops.add_tab_stop(
        Inches(6.0), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS
    )
    set_font(p.add_run(text), size=8, bold=(level == 0))
    set_font(p.add_run(f"\t{page}"), size=8, bold=(level == 0))


def add_static_toc_page(doc, entries, continue_heading=False):
    doc.add_paragraph(
        "Table of Contents (continued)" if continue_heading else "Table of Contents",
        style="Front Matter Heading",
    )
    for text, page, level in entries:
        add_toc_entry(doc, text, page, level)


def enable_field_updates(doc):
    settings = doc.settings._element
    update = settings.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        settings.append(update)
    update.set(qn("w:val"), "true")


def add_cover(doc):
    for _ in range(3):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("COMP 1682 PROJECT REPORT"), size=12, bold=True, color=DARK_BLUE)
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("Aegis"), size=30, bold=True, color=BLUE)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("API Security and Management System"), size=17, bold=True, color=DARK_BLUE)
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("Htun Khaing Lynn"), size=12, bold=True)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("Student ID: 001557481"), size=11)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("BSc (Hons) Computing"), size=10)
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("A code-grounded evaluation of a FastAPI Control Plane, Go Reverse Proxy, React dashboard, PostgreSQL and Redis"), size=10, italic=True, color=GREY)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("2026"), size=10)
    doc.add_page_break()


def add_front_matter(doc):
    doc.add_paragraph("Abstract", style="Front Matter Heading")
    paragraph(doc, "Modern applications depend on APIs, yet distributing authentication, authorisation, traffic control and audit logic across every backend creates inconsistent protection. The Project Proposal therefore defined Aegis as a central API security and management system built from a Python/FastAPI Control Plane, a Go Reverse Proxy and a React dashboard, with PostgreSQL and Redis supporting durable policy and runtime state. This report evaluates the implemented system rather than an idealised gateway template.")
    paragraph(doc, "The current implementation provides role-based administration, cryptographically generated API keys stored as hashes, JWT validation, exact route-to-scope permissions, three Redis-backed rate-limit algorithms, RE2-compatible threat rules, manual and automatic IP blocking, analytics, REST bootstrap and authenticated gRPC policy streaming. The Go proxy applies controls in a deliberate order before stripping credentials and forwarding an allowed request. The architecture, domain and sequence diagrams are derived from current models, migrations and handler code.")
    paragraph(doc, "Verification combined the repository quality gate, focused request-validation tests, a live local proof of concept and an isolated Docker Compose run. On 21 August 2026 the quality gate recorded 47 Control Plane tests at 77% application coverage, Go race/vet/format checks and 83.4% enforcement-core coverage, six dashboard tests, and thirteen POC/tooling tests. The isolated stack then verified health, authenticated gRPC policy distribution, upstream forwarding, credential rejection, threat and manual/automatic IP blocking, Redis rate limiting and analytics. The evaluation concludes that Aegis meets its learning and central enforcement aims while retaining limitations in wildcard routing, trusted-proxy address handling, body inspection and production benchmarking.")
    paragraph(doc, "Keywords: API security, reverse proxy, API gateway, FastAPI, Go, JWT, rate limiting, Redis, DSDM.", italic=True)
    doc.add_page_break()

    doc.add_paragraph("Acknowledgement", style="Front Matter Heading")
    paragraph(doc, "I would like to thank the module tutors and project supervisor for their guidance on project scope, academic structure and the DSDM timeline. Their feedback led to a design-first, timebox-only plan and encouraged stronger traceability between the Project Proposal, implementation decisions and test evidence. I also acknowledge the authors and maintainers of the open standards, research literature and open-source technologies referenced throughout this report.")
    doc.add_page_break()

    add_static_toc_page(doc, [
        ("Abstract", 2, 0), ("Acknowledgement", 3, 0), ("List of Figures and Tables", 7, 0),
        ("Chapter 1: Introduction", 8, 0),
        ("1.1 Background to API Security and Management", 8, 1),
        ("1.2 Challenges in Existing API Security Systems", 8, 1),
        ("1.3 SWOT Analysis of Existing API Security Systems", 9, 1),
        ("1.4 Key Characteristics of Effective API Security Systems", 10, 1),
        ("1.5 Problem Statement and Research Gap", 10, 1),
        ("1.6 Aim and Objectives", 11, 1),
        ("1.7 Proposed System Overview", 11, 1),
        ("1.8 Scope of the System", 12, 1),
        ("1.9 Summary", 12, 1),
        ("Chapter 2: Product Research", 14, 0),
        ("2.1 Overview", 14, 1), ("2.2 Commercial and Cloud-Managed Gateways", 14, 1),
        ("2.3 Open-Source and Self-Hosted Gateways", 14, 1),
        ("2.4 Comparative Analysis", 15, 1), ("2.5 Gaps Identified", 15, 1),
        ("2.6 Summary", 16, 1),
        ("Chapter 3: Literature Review", 17, 0),
        ("3.1 Introduction", 17, 1), ("3.2 API Security Threats and Standards", 17, 1),
        ("3.3 Authentication and Authorization Techniques", 17, 1),
        ("3.4 Rate Limiting Algorithms", 18, 1),
        ("3.5 Reverse Proxy and Gateway Architecture Patterns", 18, 1),
        ("3.6 Microservices Security Considerations", 18, 1),
        ("3.7 Summary and Research Gap Synthesis", 19, 1),
    ])
    doc.add_page_break()
    add_static_toc_page(doc, [
        ("Chapter 4: Project Timeline", 20, 0),
        ("4.1 DSDM Delivery Approach", 20, 1), ("4.2 DSDM Timebox Schedule", 20, 1),
        ("4.3 Timebox Control Rules", 20, 1), ("4.4 Milestones and Dependencies", 21, 1),
        ("4.5 Chapter Summary", 21, 1),
        ("Chapter 5: LSEP Issues", 22, 0),
        ("5.1 Introduction", 22, 1), ("5.2 Legal Issues", 22, 1),
        ("5.3 Social Issues", 23, 1), ("5.4 Ethical Issues", 23, 1),
        ("5.5 Professional Issues", 24, 1),
        ("5.6 Summary of LSEP Issues and Mitigations", 24, 1), ("5.7 Conclusion", 25, 1),
        ("Chapter 6: System Analysis", 26, 0),
        ("6.1 Introduction", 26, 1), ("6.2 User Roles and System Interactions", 26, 1),
        ("6.3 Functional Requirements", 28, 1),
        ("6.4 Non-Functional Requirements", 31, 1),
        ("6.5 Requirement Prioritisation Using MoSCoW", 32, 1),
        ("6.6 Conclusion", 35, 1),
        ("Chapter 7: System Design", 36, 0),
        ("7.1 Introduction", 36, 1), ("7.2 High-Level Architecture", 36, 1),
        ("7.3 Component Responsibilities", 38, 1),
        ("7.4 Domain and Database Design", 38, 1),
        ("7.5 Request Validation and Enforcement", 40, 1),
        ("7.6 Scope and Route-Permission Design", 42, 1),
        ("7.7 Policy Synchronisation and Resilience", 42, 1),
        ("7.8 Security Design Decisions and Trade-offs", 42, 1),
        ("7.9 Chapter Summary", 42, 1),
    ], continue_heading=True)
    doc.add_page_break()
    add_static_toc_page(doc, [
        ("Chapter 8: System Implementation", 43, 0),
        ("8.1 Introduction", 43, 1), ("8.2 Timebox 1 - Design Foundations", 43, 1),
        ("8.3 Timebox 2 - Control Plane Foundation", 43, 1),
        ("8.4 Timebox 3 - API Keys and Policy Resources", 43, 1),
        ("8.5 Timebox 4 - Reverse Proxy Enforcement", 44, 1),
        ("8.6 Timebox 5 - Rate Limiting, Threats and Policy Distribution", 44, 1),
        ("8.7 Timebox 6 - Dashboard, Documentation and POC", 44, 1),
        ("8.8 Proposal-to-Implementation Traceability", 46, 1),
        ("8.9 Implementation Challenges", 46, 1), ("8.10 Chapter Summary", 46, 1),
        ("Chapter 9: Testing", 47, 0),
        ("9.1 Introduction", 47, 1), ("9.2 Testing Strategy", 47, 1),
        ("9.3 Automated Quality Suite", 47, 1), ("9.4 Live Attack/Defence POC", 47, 1),
        ("9.5 Defect and Environment Handling", 48, 1),
        ("9.6 End-to-End Docker Verification", 48, 1),
        ("9.7 Limitations of Testing", 49, 1), ("9.8 Chapter Summary", 49, 1),
        ("Chapter 10: Evaluation and Reflection", 50, 0),
        ("10.1 Evaluation Against the Aim", 50, 1), ("10.2 Evaluation of Objectives", 50, 1),
        ("10.3 Comparison with Existing Products", 50, 1), ("10.4 Strengths", 50, 1),
        ("10.5 Limitations", 50, 1),
        ("10.6 Reflection on Development and Learning", 51, 1),
        ("10.7 Future Improvements", 51, 1), ("10.8 Final Conclusion", 51, 1),
        ("References", 52, 0),
        ("Appendix A: Valid Example JSON Payloads", 53, 0),
        ("Appendix B: Selected Test Case Matrix", 55, 0),
        ("Appendix C: Evidence and Reproducibility Index", 56, 0),
    ], continue_heading=True)
    doc.add_page_break()

    doc.add_paragraph("List of Figures", style="Front Matter Heading")
    figures = [
        "Figure 6.1  Aegis use-case model",
        "Figure 7.1  Current implemented system architecture",
        "Figure 7.2  Current persisted domain model",
        "Figure 7.3  Control Plane JSON validation and persistence sequence",
        "Figure 7.4  Reverse Proxy request validation and enforcement sequence",
        "Figure 7.5  Policy distribution and resilience flow",
        "Figure 7.6  Rate-limit rule and algorithm decision flow",
        "Figure 7.7  Security-event, analytics and automatic-block pipeline",
        "Figure 8.1  Actual dashboard login interface",
        "Figure 8.2  Actual FastAPI OpenAPI interface",
        "Figure 8.3  Actual Attack/Defence Console interface",
        "Figure 9.1  Actual automated quality-suite output",
        "Figure 9.2  Actual live POC relay output",
    ]
    for item in figures:
        paragraph(doc, item, align=WD_ALIGN_PARAGRAPH.LEFT)
    doc.add_paragraph("List of Tables", style="Front Matter Heading")
    tables = [
        "Table 2.1  Product capability comparison",
        "Table 4.1  DSDM timebox schedule",
        "Table 4.2  Timebox control rules",
        "Table 5.1  LSEP risk and mitigation summary",
        "Table 6.1  Role and permission summary",
        "Table 7.1  Component responsibilities",
        "Table 7.2  Domain constraints",
        "Table 8.1  Proposal-to-implementation traceability",
        "Table 9.1  Automated test results",
        "Table 9.2  Live POC results",
        "Table 10.1 Objective evaluation",
    ]
    for item in tables:
        paragraph(doc, item, align=WD_ALIGN_PARAGRAPH.LEFT)


def add_chapter4(doc):
    heading(doc, "Chapter 4: Project Timeline", 1)
    heading(doc, "4.1 DSDM Delivery Approach", 2)
    paragraph(doc, "The Project Proposal selected the Dynamic Systems Development Method (DSDM) because the project combines a fixed submission window with incremental delivery and MoSCoW prioritisation (Agile Business Consortium, 2014; Htun Khaing Lynn, 2026). Tutor feedback requires the report timeline to begin with Design, remove standalone Research, Analysis and Planning phases, use activities longer than one day, and end Testing on 9 October. The schedule below therefore presents only DSDM development timeboxes. Research and analysis remain continuing inputs inside each timebox rather than separate timeline phases.")
    paragraph(doc, "Each timebox follows the same internal rhythm: a short investigation and planning period, focused development, integrated testing, stakeholder review and retrospective. The timebox scope can be reprioritised, but the end date remains fixed. Must Have work is protected first; Should Have and Could Have work enters only when quality gates remain satisfied.")
    heading(doc, "4.2 DSDM Timebox Schedule", 2)
    rows = [
        ("TB1", "16 Mar-10 Apr", "Design foundations", "Architecture boundaries, schema, API contracts, threat model and validation sequence"),
        ("TB2", "13 Apr-8 May", "Control Plane foundation", "FastAPI structure, migrations, users, authentication, RBAC and API-key lifecycle"),
        ("TB3", "11 May-5 Jun", "Proxy and traffic controls", "Go forwarding, key/JWT validation, Redis rules and structured error contracts"),
        ("TB4", "8 Jun-3 Jul", "Policy distribution", "REST snapshot, authenticated gRPC stream, cached-policy resilience and route permissions"),
        ("TB5", "6-31 Jul", "Security and observability", "Threat rules, manual/automatic IP blocks, security events and analytics"),
        ("TB6", "3-28 Aug", "Dashboard and integration", "Role-aware React workflows, full-stack integration and POC console"),
        ("TB7", "31 Aug-25 Sep", "Hardening", "Cross-component tests, race/vet/lint gates, defect correction and documentation"),
        ("TB8", "28 Sep-9 Oct", "Final testing", "Regression, attack/defence evidence, evaluation inputs and submission-quality results"),
    ]
    add_table(doc, ["Timebox", "Dates", "Primary focus", "Multi-day outputs"], rows, [0.7, 1.2, 1.7, 3.0], "Table 4.1: DSDM timebox schedule from mid-March to the proposal testing end date.")
    heading(doc, "4.3 Timebox Control Rules", 2)
    controls = [
        ("Investigation/planning", "2-4 days", "Confirm acceptance criteria, dependencies and the exact Must Have slice."),
        ("Development", "6-12 days", "Implement a vertically testable increment across the components required by the timebox."),
        ("Integrated testing", "2-5 days", "Run unit/component checks continuously and a cross-component check before review."),
        ("Review", "2 days", "Demonstrate working software and compare results with the timebox acceptance criteria."),
        ("Retrospective", "2 days", "Record defects, design learning and changes to the next timebox backlog."),
    ]
    add_table(doc, ["Internal activity", "Minimum duration", "Control"], controls, [1.4, 1.1, 4.1], "Table 4.2: Repeated control structure inside every DSDM timebox.")
    add_note(doc, "Critical delivery chain", "Design foundations -> authenticated Control Plane -> proxy validation -> distributed policy -> security events -> dashboard/POC -> hardening -> final testing. A later feature cannot be accepted if it weakens an earlier enforcement invariant.", PALE_GREEN)
    heading(doc, "4.4 Milestones and Dependencies", 2)
    bullets(doc, [
        "TB1 ends only when component boundaries, database entities and the request-enforcement order are reviewable.",
        "TB2 establishes users, RBAC and API-key metadata before the proxy depends on internal validation endpoints.",
        "TB3 creates a safe request path before advanced configuration streaming or analytics is introduced.",
        "TB4 keeps REST bootstrap and the last valid snapshot as resilience mechanisms around gRPC synchronisation.",
        "TB5 and TB6 add visible controls and evidence without moving authority from the server to the browser.",
        "TB7 protects the final timebox from unresolved defects; TB8 ends on 9 October as required by the Project Proposal and tutor feedback.",
    ])
    heading(doc, "4.5 Chapter Summary", 2)
    paragraph(doc, "The corrected timeline is a DSDM timebox plan only. It starts with Design on 16 March, allocates multiple days to every activity, preserves an iterative review rhythm and ends final Testing on 9 October. This makes the report timeline consistent with tutor feedback while maintaining the proposal's methodology and technical dependencies.")


def add_chapter7(doc):
    heading(doc, "Chapter 7: System Design", 1)
    heading(doc, "7.1 Introduction", 2)
    paragraph(doc, "The Project Proposal defined three principal application components: a FastAPI Control Plane, a Go Reverse Proxy and a React dashboard. The implemented system retains that separation but adds concrete runtime dependencies and policy flows that were necessarily abstract in the proposal. This chapter therefore describes the system as built, using current Compose configuration, SQLAlchemy models, Alembic migrations, Go handler code and dashboard routes as the design authority.")
    heading(doc, "7.2 High-Level Architecture", 2)
    paragraph(doc, "Aegis separates management-plane concerns from data-plane enforcement. Administrators and viewers use the dashboard, which calls versioned Control Plane REST endpoints. Durable policy and audit records are held in PostgreSQL. Redis stores token revocation state and rate-limit counters. The proxy bootstraps policy through a protected internal REST endpoint, subscribes to authenticated gRPC snapshots, validates each protected request and forwards only after all applicable checks succeed. The upstream service is not changed to understand Aegis credentials.")
    add_landscape_figure(doc, DIAGRAMS / "figure_6_1_current_architecture.png", "Figure 7.1: Mermaid architecture of the current implemented Aegis components and their real management-plane and data-plane connections.", 10.2)
    heading(doc, "7.3 Component Responsibilities", 2)
    add_table(doc, ["Component", "Primary responsibility", "Key interfaces and state"], [
        ("FastAPI Control Plane", "User/RBAC management and the source of policy truth.", "REST API, internal-token endpoints, gRPC policy stream, SQLAlchemy/Alembic."),
        ("Go Reverse Proxy", "Latency-critical enforcement before upstream forwarding.", "net/http, httputil.ReverseProxy, in-memory policy snapshot, Redis scripts, event queue."),
        ("React dashboard", "Role-aware operator and API-consumer workflows.", "Versioned REST calls; in-memory session token; no direct database/proxy configuration."),
        ("PostgreSQL", "Durable identities, keys, rules, blocks and security events.", "Normalised relational schema and indexed lookup fields."),
        ("Redis", "Shared ephemeral enforcement state.", "Atomic rate counters and revoked-token state."),
        ("Protected upstream", "Existing business API behind Aegis.", "Receives allowed requests after Aegis credentials are stripped."),
    ], [1.3, 2.4, 2.9], "Table 7.1: Responsibilities of the implemented Aegis components.")
    heading(doc, "7.4 Domain and Database Design", 2)
    paragraph(doc, "The current persisted domain contains User, APIKey, RateLimitRule, JWTConfig, ThreatRule, IPBlock, SecurityEvent and RoutePermission. Every entity inherits an integer identifier plus created_at and updated_at audit timestamps. Several resources are soft-disabled instead of deleted so that policy history remains explainable while snapshots propagate. API-key rows contain a hash and non-sensitive prefix rather than the raw key; JWT signing material is encrypted at rest and masked in administrative responses.")
    add_landscape_figure(doc, DIAGRAMS / "figure_6_2_domain_model.png", "Figure 7.2: Mermaid entity-relationship diagram based on the current SQLAlchemy models and migration constraints.", 10.0)
    paragraph(doc, "Administrative JSON does not move directly into a database table. FastAPI first asks the declared Pydantic schema to parse types, required fields, enumerations and cross-field relationships. Authentication and reusable RBAC dependencies then establish who may call the operation. The service layer applies ownership, lifecycle and uniqueness rules before a repository opens the SQLAlchemy transaction. This separation explains why structurally invalid JSON returns 422 before persistence, while valid JSON can still be rejected by an authorisation or domain rule.")
    add_landscape_figure(doc, DIAGRAMS / "figure_6_4_control_plane_validation.png", "Figure 7.3: Mermaid sequence showing Control Plane JSON validation, RBAC, service rules and persistence boundaries.", 9.9)
    add_table(doc, ["Constraint", "Reason"], [
        ("One active JWT configuration", "Prevents ambiguous verification material and issuer/audience policy."),
        ("One active rate rule per scope", "Makes API-key > route > global selection deterministic."),
        ("One active block per exact IP", "Prevents duplicate active enforcement records while preserving history."),
        ("Exact route-permission path", "Keeps authorisation explainable; wildcard and query syntax is rejected."),
        ("resource:action scope format", "A scope such as echo:read becomes meaningful only when a route permission requires it."),
        ("Sanitised SecurityEvent", "Supports analytics without persisting raw credentials or request bodies."),
    ], [2.0, 4.6], "Table 7.2: Important domain constraints and their design rationale.")
    heading(doc, "7.5 Request Validation and Enforcement", 2)
    paragraph(doc, "The validation order is a security and performance decision. Direct client-IP blocking and request-URI threat detection are evaluated before credential work. API-key validation returns status, expiry and scopes. JWT validation checks signature, expiry, issuer and audience against the active policy. Exact method/path authorisation then determines whether the key contains the required scope. The most specific active rate rule is applied before the proxy removes Aegis credentials and forwards. Every terminal path creates a sanitised security event through a bounded asynchronous reporter.")
    add_landscape_figure(doc, DIAGRAMS / "figure_6_3_enforcement_sequence.png", "Figure 7.4: Mermaid sequence of the request-validation and enforcement order implemented by the Go proxy handler.", 6.3)
    heading(doc, "7.6 Scope and Route-Permission Design", 2)
    paragraph(doc, "The proxy does not infer that the word echo in echo:read refers to a resource. The relationship is explicit data: a RoutePermission states that GET /api/echo requires echo:read and POST /api/echo requires echo:write. When a request matches a permission, the proxy performs an exact string membership test against the validated key's scopes. An unmatched route is currently allowed after authentication; a future deny-by-default mode would require a planned migration to avoid unexpectedly blocking existing services.")
    add_code(doc, '''for _, permission := range snapshot.RoutePermissions {
    if permission.Method != r.Method || permission.PathPattern != r.URL.Path {
        continue
    }
    if hasScope(keyInfo.Scopes, permission.RequiredScope) {
        return nil
    }
    writeError(w, 403, "INSUFFICIENT_SCOPE", "This API key does not have permission...")
    return ErrKeyScopeForbidden
}
return nil''', "Extract 7.1: Current exact route-to-scope authorisation logic from reverse-proxy/internal/proxy/handler.go.")
    heading(doc, "7.7 Policy Synchronisation and Resilience", 2)
    paragraph(doc, "The proposal called for real-time gRPC synchronisation. In the implemented design, gRPC is not the only source of configuration. The proxy obtains an authenticated REST snapshot during bootstrap and can fall back to REST before its first stream update. The gRPC subscriber then stores a cloned latest snapshot behind a read/write lock. If the stream temporarily fails after a valid snapshot has been received, the proxy continues enforcing that snapshot rather than allowing an outage to remove policy. Internal REST, gRPC and event-reporting endpoints use a separate internal token rather than a user access token.")
    add_landscape_figure(doc, DIAGRAMS / "figure_6_5_policy_distribution.png", "Figure 7.5: Mermaid policy-bootstrap, authenticated gRPC streaming and last-valid-snapshot resilience flow.", 10.1)
    paragraph(doc, "Rate-limit policy is deterministic even when several configured rules could apply. The handler selects an API-key-specific rule first, then an exact route rule and finally a global rule. The selected fixed-window, sliding-window or token-bucket algorithm executes as one atomic Redis Lua operation, so concurrent proxy instances share a decision rather than racing through separate reads and writes.")
    add_landscape_figure(doc, DIAGRAMS / "figure_6_6_rate_limit_decision.png", "Figure 7.6: Mermaid decision flow for rule precedence, Redis algorithm selection and the 429 response boundary.", 10.0)
    paragraph(doc, "Every terminal handler path builds a sanitised event containing only the information needed for auditing and analytics. A bounded non-blocking queue separates reporting from request latency. The Control Plane validates and persists accepted events, aggregates them for authorised dashboard users and can create one active automatic IP block after repeated qualifying violations.")
    add_landscape_figure(doc, DIAGRAMS / "figure_6_7_event_analytics.png", "Figure 7.7: Mermaid security-event, analytics and automatic-IP-block pipeline.", 10.0)
    heading(doc, "7.8 Security Design Decisions and Trade-offs", 2)
    bullets(doc, [
        "The direct peer address is used for IP policy; X-Forwarded-For is ignored until a trusted-proxy model is explicitly configured.",
        "RE2-compatible threat patterns avoid unsupported backtracking constructs and match METHOD plus RequestURI rather than collecting bodies.",
        "The proxy strips X-API-Key and Authorization before upstream forwarding, reducing accidental credential exposure.",
        "Rate limiting uses atomic Redis operations so multiple proxy instances share the same counter state.",
        "The dashboard improves usability but never becomes the security authority; every mutation remains protected by server-side RBAC.",
        "The bounded event queue prevents an unavailable analytics path from indefinitely blocking request handling, accepting a documented observability trade-off under saturation.",
    ])
    heading(doc, "7.9 Chapter Summary", 2)
    paragraph(doc, "The implemented design fulfils the proposal's centralised policy and high-performance enforcement direction while making several important relationships explicit: scopes are connected to exact routes, policy is distributed as validated snapshots, and runtime rate state is separated from durable configuration. These decisions allow the behaviour shown in Chapter 9 to be traced to concrete design elements.")


def add_chapter8(doc):
    heading(doc, "Chapter 8: System Implementation", 1)
    heading(doc, "8.1 Introduction", 2)
    paragraph(doc, "Implementation followed the Project Proposal's technology allocation while adapting to current library and deployment realities. FastAPI and SQLAlchemy implement the management plane, Go's net/http and httputil packages implement the proxy, the dashboard uses React 19 with Vinext/Vite, PostgreSQL stores durable records, and Redis supports shared runtime state. Work is described using the DSDM timeboxes established in Chapter 4, matching the structural approach used by the corrected reference report.")
    heading(doc, "8.2 Timebox 1 - Design Foundations", 2)
    paragraph(doc, "The first increment established repository boundaries, configuration rules, normalised entities and the request-enforcement contract. Environment settings are validated at application startup, database evolution is captured in forward Alembic migrations, and API responses use a consistent status/message/data envelope. The resulting design kept the Control Plane authoritative without requiring the Go proxy to query PostgreSQL for every request.")
    heading(doc, "8.3 Timebox 2 - Control Plane Foundation", 2)
    paragraph(doc, "The Control Plane is organised into routers, Pydantic schemas, services, repositories and SQLAlchemy models. Routers handle HTTP concerns and dependencies; services apply ownership, role and lifecycle rules; repositories isolate asynchronous persistence. Passwords are hashed, access and refresh tokens are differentiated, and logout places the access token identifier in Redis. Admin, Viewer and API Consumer permissions are enforced through reusable dependencies rather than through client-side navigation alone.")
    add_figure(doc, EVIDENCE / "figure_8_1_dashboard_login.png", "Figure 8.1: Actual Aegis dashboard login interface captured from the running local application.", 6.0)
    heading(doc, "8.4 Timebox 3 - API Keys and Policy Resources", 2)
    paragraph(doc, "API keys are generated from cryptographically secure random material. Only the digest and a short prefix are persisted; the raw key is returned once in the create response. API Consumers can view and revoke their own keys, while Admins can manage broader policy resources. Rate-limit rules validate the relationship between scope_type and scope_value. JWT configurations validate algorithm/key combinations and require access-token TTL to be shorter than refresh-token TTL. Threat rules reject constructs outside the Go RE2 subset, and exact route permissions validate resource:action scope syntax.")
    add_code(doc, '''{
  "name": "echo-reader",
  "scopes": ["echo:read"],
  "expires_at": "2026-12-31T23:59:59Z"
}''', "Extract 8.1: Example API-key create payload accepted by the current Pydantic schema.")
    heading(doc, "8.5 Timebox 4 - Reverse Proxy Enforcement", 2)
    paragraph(doc, "The proxy uses a single Handler as the security boundary. A request-scoped timeout covers policy and validation work. Errors map to structured JSON codes such as API_KEY_MISSING, API_KEY_REVOKED, JWT_EXPIRED, INSUFFICIENT_SCOPE and RATE_LIMIT_EXCEEDED. Allowed responses expose standard rate-limit metadata; denied responses return before the upstream forwarder is invoked. Credentials are removed from a cloned header map so the original incoming request is not mutated unexpectedly.")
    add_code(doc, '''forwardRequest := r.Clone(r.Context())
forwardRequest.Header = r.Header.Clone()
forwardRequest.Header.Del(h.apiKeyHeader)
forwardRequest.Header.Del("Authorization")
h.forwarder.ServeHTTP(capture, forwardRequest)''', "Extract 8.2: Credential removal immediately before upstream forwarding.")
    heading(doc, "8.6 Timebox 5 - Rate Limiting, Threats and Policy Distribution", 2)
    paragraph(doc, "The Redis rate limiter implements fixed-window, sliding-window and token-bucket algorithms through atomic server-side scripts. Rule precedence is API-key scope, then route scope, then global scope. Threat detection compiles active RE2-compatible patterns and evaluates method plus request URI. Manual blocks are exact canonical IPv4/IPv6 values; automatic blocks are created from repeated qualifying security events when enabled. The gRPC service streams a JSON-encoded policy snapshot at a configured interval after constant-time internal-token authentication.")
    add_code(doc, '''metadata = dict(context.invocation_metadata())
supplied_token = metadata.get("x-aegis-internal-token", "")
if not secrets.compare_digest(supplied_token, self.internal_token):
    await context.abort(grpc.StatusCode.UNAUTHENTICATED, "internal authentication failed")

while not context.done():
    snapshot = await self.snapshot_loader()
    yield PolicySnapshot(json_payload=snapshot.model_dump_json().encode())''', "Extract 8.3: Authenticated Control Plane gRPC policy-stream pattern.")
    heading(doc, "8.7 Timebox 6 - Dashboard, Documentation and POC", 2)
    paragraph(doc, "The dashboard presents role-aware navigation for system health, analytics, users, API keys, rate limits, IP blocks, threat rules and JWT configuration. Access and refresh tokens are kept in React memory rather than browser persistence, reducing exposure to long-lived client storage at the cost of requiring login after reload. The Control Plane also publishes generated OpenAPI documentation, making the request and response contracts directly inspectable during development.")
    add_figure(doc, EVIDENCE / "figure_8_2_openapi_control_plane.png", "Figure 8.2: Actual FastAPI OpenAPI interface from the running Control Plane.", 6.0)
    paragraph(doc, "The POC consists of a deliberately simple echo upstream and a browser attack/defence console. The console relay is restricted to loopback, a fixed /api/echo target and GET/POST methods. Development helpers can seed fresh local-only credentials and load a sanitised summary. This bounded design demonstrates the security controls without turning the POC helper into an arbitrary HTTP proxy.")
    add_figure(doc, EVIDENCE / "figure_8_3_attack_console_ui.png", "Figure 8.3: Actual Aegis Attack/Defence Console interface captured from the running local POC.", 6.0)
    heading(doc, "8.8 Proposal-to-Implementation Traceability", 2)
    add_table(doc, ["Proposal commitment", "Implemented evidence", "Status"], [
        ("FastAPI Control Plane", "Versioned REST, RBAC, repositories, migrations, internal endpoints and analytics.", "Implemented"),
        ("Go Reverse Proxy", "Ordered request validation, httputil forwarding, credential stripping and event reporting.", "Implemented"),
        ("React dashboard", "Role-aware management and monitoring routes.", "Implemented"),
        ("Distributed rate limiting", "Three Redis-backed atomic algorithms with per-key/route/global precedence.", "Implemented"),
        ("JWT validation", "HS256/RS256/ES256 configuration with issuer, audience and expiry checks.", "Implemented"),
        ("IP/threat protection", "Exact blocks, automatic blocking option and RE2-compatible threat rules.", "Implemented"),
        ("Real-time configuration", "REST bootstrap plus authenticated gRPC server stream and last-valid snapshot.", "Implemented"),
        ("Analytics dashboard", "Sanitised events, summary views and role-protected UI.", "Implemented"),
    ], [1.7, 3.9, 1.0], "Table 8.1: Traceability from the Project Proposal to the current implementation.")
    heading(doc, "8.9 Implementation Challenges", 2)
    bullets(doc, [
        "Maintaining one policy meaning across Python schemas, persisted values, gRPC JSON and Go structures required explicit validation and integration tests.",
        "Caching improved resilience but required clear behaviour before the first snapshot and during later stream interruptions.",
        "The meaning of a scope was initially easy to treat as self-explanatory; exact RoutePermission records were needed to bind resource:action names to real requests.",
        "Client IP policy required rejecting convenient forwarded headers until a trusted reverse-proxy boundary could be configured safely.",
        "A stale development IP block affected the first POC evidence run, demonstrating why test-environment state must be recorded and controlled.",
    ])
    heading(doc, "8.10 Chapter Summary", 2)
    paragraph(doc, "The implementation converts the proposal's component diagram into a working management and enforcement path. The main achievement is traceability: user-facing configuration maps to persisted constraints, snapshot fields, Go checks, structured errors and observable tests. The next chapter evaluates those claims using completed local evidence.")


def add_chapter9(doc):
    heading(doc, "Chapter 9: Testing", 1)
    heading(doc, "9.1 Introduction", 2)
    paragraph(doc, "Testing validates the proposal's claim that Aegis can centralise request protection without relying on an unverified demonstration. The strategy combines component tests, static checks, race detection, coverage gates and a live local attack/defence flow. Results in this chapter were observed on 2 August 2026. Screenshots were created from the corresponding local outputs; raw API keys, passwords and JWT values were excluded.")
    heading(doc, "9.2 Testing Strategy", 2)
    bullets(doc, [
        "Control Plane: pytest tests for authentication, ownership, API keys, policy resources, analytics, internal snapshots and gRPC behaviour, with application coverage reporting.",
        "Reverse Proxy: Go unit/integration tests, the race detector, go vet, gofmt and an enforcement-core coverage threshold.",
        "Dashboard: lint/build checks plus rendered HTML tests for login, role navigation and key management/analytics views.",
        "POC/tooling: echo-service, console relay and development-helper tests.",
        "Live evidence: fresh seeded users/keys/JWT sent through the actual proxy to the actual echo upstream.",
    ])
    heading(doc, "9.3 Automated Quality Suite", 2)
    add_table(doc, ["Check", "Observed result", "Coverage of behaviour"], [
        ("Control Plane pytest", "47 passed; 77% application coverage", "RBAC, key lifecycle, rules, JWT, blocks, analytics, snapshots, gRPC and route permissions."),
        ("Go proxy", "race/vet/gofmt pass; 83.4% core coverage", "Concurrency, policy providers, handler outcomes, Redis algorithms and forwarding."),
        ("Dashboard", "lint/build pass; 6 rendered HTML tests", "Login, role-specific navigation and management views."),
        ("POC/tooling", "13 tests pass", "Echo upstream, restricted relay and dev-only helper behaviour."),
    ], [1.4, 2.0, 3.2], "Table 9.1: Completed automated checks and observed results.")
    add_figure(doc, EVIDENCE / "figure_9_1_make_check.png", "Figure 9.1: Extract of the actual local make check output showing passing suites and coverage results.", 6.0)
    heading(doc, "9.4 Live Attack/Defence POC", 2)
    paragraph(doc, "The live console was seeded with fresh development-only data and sent constrained /__aegis_probe requests through the running loopback proxy to /api/echo. Consumer 1 held echo:read; Consumer 2 held echo:read and echo:write. Exact RoutePermission records required echo:read for GET and echo:write for POST. This arrangement proves that the scope strings have enforceable meaning rather than merely appearing in JSON metadata.")
    add_figure(doc, EVIDENCE / "figure_9_2_poc_console.png", "Figure 9.2: Actual live POC relay evidence confirming forwarding, scope denial, credential failures, rate limiting and per-consumer isolation.", 6.0)
    add_table(doc, ["Scenario", "Observed HTTP result", "Interpretation"], [
        ("Consumer 1 GET", "200 FORWARDED", "Key, JWT and echo:read satisfy the exact GET permission."),
        ("Consumer 1 POST", "403 INSUFFICIENT_SCOPE", "The key lacks echo:write; the upstream is not called."),
        ("Consumer 2 POST", "200 FORWARDED", "The required write scope is present."),
        ("Revoked key", "403 API_KEY_REVOKED", "Lifecycle state is enforced after key lookup."),
        ("No/malformed key", "401 API_KEY_MISSING / API_KEY_INVALID", "Credential errors terminate before forwarding."),
        ("Five-request flood", "200, 200, 200, 429, 429", "The key-scoped Redis rule permits three requests per ten seconds."),
        ("Cross-consumer check", "200 FORWARDED", "Consumer 2 is isolated from Consumer 1's counter."),
    ], [1.5, 2.0, 3.1], "Table 9.2: Live POC scenarios and observed enforcement outcomes.")
    heading(doc, "9.5 Defect and Environment Handling", 2)
    paragraph(doc, "The first live attempt returned IP_BLOCKED for every case. Investigation found an active manual block for 127.0.0.1 in the local Control Plane. The record was soft-disabled through the authenticated administrative endpoint and the evidence was rerun with fresh seeded data. This was not treated as a proxy defect: the proxy correctly enforced existing policy. Recording the condition protects the validity of the test and demonstrates why reproducible security testing includes environment-state checks.")
    heading(doc, "9.6 End-to-End Docker Verification", 2)
    paragraph(doc, "The isolated Docker Compose end-to-end script completed successfully on 21 August 2026 using disposable ports, volumes and generated credentials. It confirmed Control Plane, PostgreSQL and Redis health; dashboard readiness; login and policy creation; authenticated gRPC snapshot delivery; a successful proxy-to-upstream request; invalid and revoked credential rejection; manual and automatic exact-IP blocking; request-target threat detection; a 200, 200, 429 Redis rate sequence; and analytics aggregation. The script removed its isolated stack after completion, while a redacted checkpoint log was retained as primary evidence.")
    add_figure(doc, EVIDENCE / "tb6_end_to_end_evidence.png", "Figure 9.3: Redacted output from the completed isolated Docker end-to-end verification on 21 August 2026.", 6.0)
    add_note(doc, "Evidence rule", "Only completed observations are claimed. The embedded E2E evidence is generated from the current run log and excludes generated credentials and secrets.", PALE_GREEN)
    heading(doc, "9.7 Limitations of Testing", 2)
    bullets(doc, [
        "The completed evidence validates functional enforcement and component behaviour but is not a statistically rigorous throughput benchmark.",
        "The POC uses loopback services and fresh development credentials; production TLS termination, orchestration and remote network behaviour require deployment testing.",
        "Threat matching tests cover method/request-URI patterns rather than payload inspection, consistent with the current design boundary.",
        "Dashboard checks validate rendered routes and important interactions but do not constitute a full accessibility study with representative users.",
        "The isolated Docker E2E validates one local Compose topology; remote TLS termination, orchestration, load, failure injection and long-running soak behaviour remain outside this evidence.",
    ])
    heading(doc, "9.8 Chapter Summary", 2)
    paragraph(doc, "The completed test evidence supports the core Aegis claim: policy records are converted into observable allow and deny decisions before the upstream service. The quality suite covers each technology component, while the live POC connects scopes, credentials and Redis state to real HTTP outcomes. Remaining integration and performance evidence is stated transparently rather than inferred.")


def add_chapter10(doc):
    heading(doc, "Chapter 10: Evaluation and Reflection", 1)
    heading(doc, "10.1 Evaluation Against the Aim", 2)
    paragraph(doc, "The Project Proposal aimed to design and develop a production-ready API security and management system that provides central protection through request validation, rate limiting and threat detection while demonstrating Python/FastAPI, Go and React skills (Htun Khaing Lynn, 2026). The current project achieves the central architectural and learning aim: policy is managed in the FastAPI Control Plane and enforced by the Go proxy before an upstream request is possible. The React dashboard and POC make that behaviour observable, and the completed isolated Compose run verifies the integrated local topology. The term production-ready should nevertheless be qualified because deployment-specific TLS, trusted-proxy handling, load benchmarking, operational rotation and long-running resilience testing remain future work.")
    heading(doc, "10.2 Evaluation of Objectives", 2)
    add_table(doc, ["Objective", "Evaluation", "Evidence"], [
        ("Research existing solutions", "Achieved", "Commercial/open-source comparison and literature synthesis in Chapters 2-3."),
        ("Define requirements and roles", "Achieved", "MoSCoW analysis, RBAC and current persisted policies in Chapter 6."),
        ("Design architecture and workflows", "Achieved", "Current architecture, domain and sequence diagrams in Chapter 7."),
        ("Implement the full stack", "Achieved", "FastAPI, Go, React, PostgreSQL, Redis, gRPC and POC described in Chapter 8."),
        ("Test security behaviour", "Achieved for the project scope", "Passing component suites, focused scope tests, live enforcement and completed isolated Docker E2E."),
        ("Evaluate the result", "Achieved with limitations", "Comparison, strengths, limitations, reflection and future work in this chapter."),
    ], [2.0, 1.3, 3.3], "Table 10.1: Evaluation of the Project Proposal objectives against current evidence.")
    heading(doc, "10.3 Comparison with Existing Products", 2)
    paragraph(doc, "Kong, APISIX, Tyk, AWS API Gateway and Cloudflare provide broader ecosystems, managed availability, extensive plugins and established operational tooling. Aegis does not replace those products. Its value is a focused, self-hosted and explainable implementation in which the student controls the policy model, request order, rate algorithms and audit shape. This makes security decisions easier to reverse-learn than in a platform where behaviour is distributed across plugins and vendor infrastructure.")
    heading(doc, "10.4 Strengths", 2)
    bullets(doc, [
        "Management-plane/data-plane separation prevents common policy decisions from depending on a per-request PostgreSQL query.",
        "The enforcement sequence applies inexpensive source/threat checks before credentials, authorisation and rate limiting.",
        "Exact RoutePermission records make scope semantics explicit and testable.",
        "Cryptographic key generation, one-time raw-key disclosure and hashed persistence reduce credential exposure.",
        "Atomic Redis algorithms support shared counters across proxy instances.",
        "Sanitised security events and credential stripping reduce unnecessary sensitive-data propagation.",
        "The POC demonstrates a real upstream outcome and per-consumer isolation rather than only mocked service calls.",
    ])
    heading(doc, "10.5 Limitations", 2)
    bullets(doc, [
        "Exact route matching does not yet support reviewed wildcard, parameter or deny-by-default policies.",
        "Threat detection is pattern matching over method and request URI, not request-body inspection or a complete web application firewall.",
        "Direct-peer IP handling is safe for the current topology but needs an explicit trusted-proxy configuration for load-balanced deployment.",
        "The current dashboard has automated route checks but limited formal usability and accessibility evaluation with end users.",
        "Performance has not been evaluated with controlled hardware, concurrent load profiles and percentile latency measurements.",
        "The completed Docker E2E proves the isolated local stack, but it does not replace production-like TLS, distributed deployment, failure-injection or throughput evidence.",
    ])
    heading(doc, "10.6 Reflection on Development and Learning", 2)
    paragraph(doc, "The most important technical learning was the difference between recognising a credential and authorising a resource operation. A key can validly contain [\"echo:read\"], but that string has no inherent knowledge of the echo service. The later route-permission model explicitly maps GET /api/echo to echo:read. This small data structure made the authorisation boundary clearer than embedding route names in handler conditions.")
    paragraph(doc, "Go required a more explicit approach to dependencies and failure paths than the initial Python work. Handler interfaces made policy providers, key validation, JWT validation, rate limiting, event reporting and forwarding independently testable. Context timeouts and cloned headers exposed practical HTTP concerns that are easy to miss when learning reverse proxies conceptually. Python/FastAPI made schema validation and REST organisation productive, but also reinforced that validation rules must remain consistent with Go's accepted snapshot values.")
    paragraph(doc, "The POC run also provided a process lesson. The unexpected loopback block was correct system behaviour caused by persistent environment state. Treating it as evidence, finding the policy record and rerunning after a traceable soft-disable was more valuable than forcing a green screenshot. The isolated Docker run was then repeated to completion with disposable state and redacted checkpoint logging. These decisions reflect professional responsibility and improve confidence in the report.")
    heading(doc, "10.7 Future Improvements", 2)
    bullets(doc, [
        "Design parameterised/wildcard route permissions with conflict analysis and a staged deny-by-default option.",
        "Add trusted-load-balancer configuration and CIDR policy only after defining exactly which forwarded headers are authoritative.",
        "Extend the completed reproducible Docker E2E with repeatable load benchmarks, failure injection and documented hardware and latency percentiles.",
        "Add signing-key rotation, policy version history, audit diffing and operational alert integrations.",
        "Conduct dashboard accessibility auditing and task-based usability sessions with Admin, Viewer and API Consumer participants.",
        "Assess body-aware detection separately, including privacy, memory/latency cost, payload limits and false-positive handling.",
    ])
    heading(doc, "10.8 Final Conclusion", 2)
    paragraph(doc, "Aegis demonstrates that a focused custom reverse proxy can centralise meaningful API security controls while remaining understandable from database record to HTTP result. The project does not claim the breadth or operational maturity of a commercial gateway. Its contribution is a coherent learning implementation whose main behaviours are inspectable, testable and connected to the original proposal. With the identified deployment hardening and evidence gaps addressed, it provides a credible foundation for further production-oriented development.")


def add_references(doc):
    heading(doc, "References", 1)
    refs = [
        "Agile Business Consortium (2014) The DSDM Agile Project Framework. Tunbridge Wells: Agile Business Consortium.",
        "Amazon Web Services (2026) Control access to HTTP APIs with JWT authorizers. Available at: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html (Accessed: 2 August 2026).",
        "Apache APISIX (2026) rate-limit and jwt-auth plugin documentation. Available at: https://apisix.apache.org/docs/apisix/plugins/ (Accessed: 2 August 2026).",
        "Cloudflare (2026) API Gateway and rate limiting documentation. Available at: https://developers.cloudflare.com/api-shield/ (Accessed: 2 August 2026).",
        "Docker Inc. (2026) Docker Compose documentation. Available at: https://docs.docker.com/compose/ (Accessed: 2 August 2026).",
        "Fielding, R.T. (2000) Architectural Styles and the Design of Network-based Software Architectures. PhD thesis. University of California, Irvine.",
        "Htun Khaing Lynn (2026) Aegis: API Security and Management System - Project Proposal. Unpublished project proposal.",
        "Indrasiri, K. and Kuruppu, D. (2020) gRPC: Up and Running. Sebastopol: O'Reilly Media.",
        "Jones, M., Bradley, J. and Sakimura, N. (2015) JSON Web Token (JWT). RFC 7519. Internet Engineering Task Force. Available at: https://www.rfc-editor.org/rfc/rfc7519 (Accessed: 2 August 2026).",
        "Kong Inc. (2026) Rate limiting plugin documentation. Available at: https://developer.konghq.com/plugins/rate-limiting/ (Accessed: 2 August 2026).",
        "Newman, S. (2021) Building Microservices: Designing Fine-grained Systems. 2nd edn. Sebastopol: O'Reilly Media.",
        "Oliveira, G. (2022) Rate-limiting algorithm discussion cited in the Aegis Project Proposal.",
        "OWASP Foundation (2023) OWASP API Security Top 10 2023. Available at: https://owasp.org/www-project-api-security/ (Accessed: 2 August 2026).",
        "PostgreSQL Global Development Group (2026) PostgreSQL documentation. Available at: https://www.postgresql.org/docs/ (Accessed: 2 August 2026).",
        "Redis Ltd. (2026) Redis command and scripting documentation. Available at: https://redis.io/docs/latest/ (Accessed: 2 August 2026).",
        "The Go Authors (2026) Package net/http and httputil documentation. Available at: https://pkg.go.dev/net/http (Accessed: 2 August 2026).",
        "Tyk Technologies (2026) Rate limiting documentation. Available at: https://tyk.io/docs/api-management/rate-limit/ (Accessed: 2 August 2026).",
        "W3C (2018) Web Content Accessibility Guidelines (WCAG) 2.1. Available at: https://www.w3.org/TR/WCAG21/ (Accessed: 2 August 2026).",
    ]
    for ref in refs:
        p = paragraph(doc, ref, align=WD_ALIGN_PARAGRAPH.LEFT)
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.first_line_indent = Inches(-0.3)


def add_appendices(doc):
    heading(doc, "Appendix A: Valid Example JSON Payloads", 1)
    paragraph(doc, "These examples match the current Pydantic request schemas. Values are illustrative development data, not secrets copied from the test environment.")
    examples = [
        ("A.1 Create API key", {"name": "echo-reader", "scopes": ["echo:read"], "expires_at": "2026-12-31T23:59:59Z"}),
        ("A.2 Create key-scoped fixed-window rule", {"name": "consumer-one-demo-limit", "scope_type": "api_key", "scope_value": "12", "algorithm": "fixed_window", "limit_count": 3, "window_seconds": 10, "burst_allowance": None, "status": "active"}),
        ("A.3 Create global sliding-window rule", {"name": "global-baseline", "scope_type": "global", "scope_value": None, "algorithm": "sliding_window", "limit_count": 120, "window_seconds": 60, "burst_allowance": None, "status": "active"}),
        ("A.4 Create exact route permission", {"method": "GET", "path_pattern": "/api/echo", "required_scope": "echo:read", "status": "active"}),
        ("A.5 Create threat rule", {"name": "basic-sql-union", "pattern": "(?i)(GET|POST)\\s+.*union(%20|\\+)select", "severity": "high", "status": "active"}),
        ("A.6 Create manual IP block", {"ip_address": "203.0.113.42", "reason": "Repeated prohibited requests during controlled test", "status": "active"}),
        ("A.7 Create HS256 JWT configuration", {"name": "development-jwt", "algorithm": "HS256", "signing_key": "replace-with-a-long-development-secret", "public_key": None, "issuer": "aegis-control-plane", "audience": "aegis-proxy", "access_token_ttl_seconds": 900, "refresh_token_ttl_seconds": 604800}),
    ]
    for title, payload in examples:
        if title.startswith("A.7"):
            doc.add_page_break()
        heading(doc, title, 2)
        add_code(doc, json.dumps(payload, indent=2))
    add_note(doc, "Why scopes look like [\"echo:read\"]", "scopes is an array because one key may hold several permissions. Each value uses resource:action naming for readability. The string is not automatic discovery: RoutePermission records explicitly bind a method/path to the required string.", PALE_GREEN)

    heading(doc, "Appendix B: Selected Test Case Matrix", 1)
    rows = [
        ("TC-01", "Register user", "Valid email/name/password", "201; password stored only as a hash"),
        ("TC-02", "Login", "Valid seeded user", "200; access and refresh tokens"),
        ("TC-03", "RBAC mutation", "Viewer creates rate rule", "403 forbidden"),
        ("TC-04", "Create API key", "name/scopes/expiry", "Raw key returned once; metadata persists"),
        ("TC-05", "List API keys", "Existing key", "Prefix/metadata only; no raw key/hash"),
        ("TC-06", "Revoke API key", "Active owned key", "Status revoked; proxy later returns 403"),
        ("TC-07", "JWT expiry", "Expired Bearer token", "401 JWT_EXPIRED"),
        ("TC-08", "Route scope", "POST with echo:read", "403 INSUFFICIENT_SCOPE"),
        ("TC-09", "Route scope", "POST with echo:write", "200 forwarded"),
        ("TC-10", "Missing API key", "No X-API-Key header", "401 API_KEY_MISSING"),
        ("TC-11", "Threat pattern", "Matching method/request URI", "403 THREAT_DETECTED"),
        ("TC-12", "Manual IP block", "Blocked direct peer", "403 IP_BLOCKED"),
        ("TC-13", "Fixed window", "Five requests; limit three", "200, 200, 200, 429, 429"),
        ("TC-14", "Counter isolation", "Second consumer after first floods", "200; separate key scope"),
        ("TC-15", "Credential stripping", "Allowed request", "Upstream receives neither Aegis credential"),
        ("TC-16", "gRPC authentication", "Wrong internal token", "UNAUTHENTICATED"),
        ("TC-17", "Policy resilience", "Stream interruption after snapshot", "Last valid snapshot remains available"),
        ("TC-18", "Threat schema", "Look-ahead/backreference regex", "422 RE2-incompatible pattern"),
        ("TC-19", "Route schema", "Wildcard/query path", "422 exact-path validation error"),
        ("TC-20", "Analytics privacy", "Proxy event", "No raw API key, JWT or body stored"),
    ]
    add_table(doc, ["ID", "Feature", "Input/condition", "Expected result"], rows, [0.7, 1.4, 2.1, 2.4], "Table B.1: Selected functional and security test cases derived from current automated and live checks.")

    heading(doc, "Appendix C: Evidence and Reproducibility Index", 1)
    add_table(doc, ["Evidence", "Command/source", "Result used in report"], [
        ("Automated quality gate", "make check", "47 Python tests; 77% app coverage; Go race/vet/gofmt; 83.4% core; 6 dashboard; 13 POC."),
        ("Live POC relay", "POST /__aegis_seed then /__aegis_probe", "Allowed/denied scopes, credential errors, rate limit and key isolation."),
        ("Architecture diagram", "Compose, app.main, proxy main/handler and dashboard routes", "Figure 7.1."),
        ("Domain diagram", "SQLAlchemy models plus Alembic migrations", "Figure 7.2."),
        ("Control Plane sequence", "FastAPI routers, Pydantic schemas, RBAC dependencies, services and repositories", "Figure 7.3."),
        ("Proxy sequence", "reverse-proxy/internal/proxy/handler.go", "Figure 7.4."),
        ("Policy/rate/event flows", "gRPC subscriber, policy provider, Redis limiter and event reporter", "Figures 7.5-7.7."),
        ("Dashboard/OpenAPI/POC UI", "Running localhost services", "Figures 8.1-8.3."),
        ("Docker E2E", "make e2e", "Completed on 21 August 2026; redacted checkpoints verify health, gRPC policy sync, proxy forwarding, denial controls, Redis limits and analytics."),
    ], [1.6, 2.4, 2.6], "Table C.1: Traceability from report claims to local evidence.")


def build():
    doc = Document(SOURCE)
    early, analysis = source_slices(doc)
    clear_body(doc)
    configure_styles(doc)
    enable_field_updates(doc)
    doc.core_properties.title = "Aegis: API Security and Management System - Complete Project Report"
    doc.core_properties.subject = "COMP 1682 Project Report"
    doc.core_properties.author = "Htun Khaing Lynn"

    add_cover(doc)
    add_front_matter(doc)
    append_elements(doc, early)
    balance_preserved_chapter_pages(doc)
    add_chapter4(doc)
    append_elements(doc, analysis)
    add_chapter7(doc)
    add_chapter8(doc)
    add_chapter9(doc)
    add_chapter10(doc)
    add_references(doc)
    add_appendices(doc)

    # Reassert consistent section geometry for all portrait sections and keep
    # the retained header/footer relationships across landscape figure pages.
    for section in doc.sections:
        if section.orientation == WD_ORIENT.PORTRAIT:
            section.page_width = Inches(8.27)
            section.page_height = Inches(11.69)
            section.left_margin = section.right_margin = Inches(1)
            section.top_margin = section.bottom_margin = Inches(1)

    # The retained early chapters include tables created before this builder;
    # make their first rows repeat and normalise legacy auto-width geometry.
    for table in doc.tables:
        if table.rows:
            repeat_table_header(table.rows[0])
        tbl_w = table._tbl.tblPr.find(qn("w:tblW"))
        if tbl_w is not None and tbl_w.get(qn("w:type")) != "dxa":
            grid_widths = [int(col.w) for col in table._tbl.tblGrid.gridCol_lst]
            if grid_widths and sum(grid_widths) > 0:
                target = table_geometry.section_content_width_dxa(doc.sections[0])
                scaled = [round(target * value / sum(grid_widths)) for value in grid_widths]
                scaled[-1] += target - sum(scaled)
                table_geometry.apply_table_geometry(table, scaled)

    # The single retained Chapter 6 use-case image predates the accessible
    # figure helpers, so supply descriptive text if its document property is empty.
    for shape in doc.inline_shapes:
        doc_pr = shape._inline.docPr
        if not doc_pr.get("descr"):
            description = "Aegis use-case model showing New User, API Consumer, Admin, Viewer and Reverse Proxy interactions."
            doc_pr.set("descr", description)
            doc_pr.set("title", description)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
