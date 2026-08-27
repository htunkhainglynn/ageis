from __future__ import annotations

"""Build the ten Aegis report chapters from verified repository evidence.

The document is intentionally generated as one chapter per file so each chapter
can be reviewed independently by the tutor. Diagrams and terminal captures are
generated from the current system and the locally observed test output.
"""

from pathlib import Path
import re
from datetime import date

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_SECTION, WD_ORIENT
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path("/Users/htunkhainglynn/Projects/aegis")
DOCS = ROOT / "docs"
REPORT = DOCS / "report"
DIAGRAMS = DOCS / "diagrams"
EVIDENCE = DOCS / "evidence"
REPORT.mkdir(exist_ok=True)
DIAGRAMS.mkdir(exist_ok=True)
EVIDENCE.mkdir(exist_ok=True)

BLUE = "2E74B5"
DARK = "0B2545"
MUTED = "666666"
LIGHT_BLUE = "E8EEF5"
LIGHT_GREY = "F2F4F7"
GREEN = "1F6D4C"
RED = "9B1C1C"


def font(size: int, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


FONT_S = font(25)
FONT_M = font(31, True)
FONT_L = font(39, True)
FONT_XL = font(47, True)


def text_box(draw, box, title, lines, fill="#FFFFFF", outline="#2E74B5", title_fill="#E8EEF5", title_color="#0B2545", body_size=25):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=22, fill=fill, outline=outline, width=4)
    title_height = 55
    draw.rounded_rectangle((x1, y1, x2, y1 + title_height), radius=22, fill=title_fill)
    draw.rectangle((x1, y1 + 28, x2, y1 + title_height), fill=title_fill)
    draw.text((x1 + 18, y1 + 10), title, font=FONT_M, fill=title_color)
    y = y1 + title_height + 16
    body_font = font(body_size)
    for line in lines:
        draw.text((x1 + 18, y), line, font=body_font, fill="#1F2937")
        y += body_size + 11


def arrow(draw, start, end, label=None, color="#355C7D", width=5, dashed=False):
    x1, y1 = start
    x2, y2 = end
    if dashed:
        steps = 14
        for i in range(steps):
            if i % 2 == 0:
                a = i / steps
                b = (i + 1) / steps
                draw.line((x1 + (x2-x1)*a, y1 + (y2-y1)*a, x1 + (x2-x1)*b, y1 + (y2-y1)*b), fill=color, width=width)
    else:
        draw.line((x1, y1, x2, y2), fill=color, width=width)
    import math
    theta = math.atan2(y2-y1, x2-x1)
    p1 = (x2 - 18*math.cos(theta-0.45), y2 - 18*math.sin(theta-0.45))
    p2 = (x2 - 18*math.cos(theta+0.45), y2 - 18*math.sin(theta+0.45))
    draw.polygon([(x2, y2), p1, p2], fill=color)
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        bb = draw.textbbox((0, 0), label, font=FONT_S)
        draw.rounded_rectangle((mx-8, my-4, mx+(bb[2]-bb[0])+8, my+(bb[3]-bb[1])+4), 5, fill="#FFFFFF")
        draw.text((mx, my), label, font=FONT_S, fill=color)


def generate_architecture():
    path = DIAGRAMS / "figure_7_1_current_architecture.png"
    im = Image.new("RGB", (2400, 1500), "#FFFFFF")
    d = ImageDraw.Draw(im)
    d.text((80, 55), "Aegis — implemented system architecture", font=FONT_XL, fill="#0B2545")
    text_box(d, (100, 300, 510, 500), "API client", ["X-API-Key + Bearer JWT", "HTTP requests"], title_fill="#EDF7F2", outline="#1F6D4C")
    text_box(d, (720, 240, 1250, 600), "Go Reverse Proxy (data plane)", ["IP block → threat rule", "API key cache / Control Plane", "JWT + route-scope checks", "Redis rate limit", "strip credentials → forward", "non-blocking security events"], title_fill="#E8EEF5")
    text_box(d, (1580, 300, 2250, 500), "Protected upstream service", ["Existing backend service", "Echo POC used in testing"], title_fill="#EDF7F2", outline="#1F6D4C")
    text_box(d, (100, 920, 510, 1120), "React dashboard", ["Admin / Viewer / Consumer", "REST management UI"], title_fill="#FFF5E5", outline="#A56B00")
    text_box(d, (720, 820, 1250, 1370), "FastAPI Control Plane", ["Users, API keys and policies", "Internal validation/config/event APIs", "gRPC policy stream", "RBAC and encrypted key material"], title_fill="#E8EEF5")
    text_box(d, (1580, 780, 2050, 1015), "PostgreSQL", ["Policy + audit", "source of truth"], title_fill="#F2F4F7", outline="#64748B")
    text_box(d, (1580, 1120, 2050, 1355), "Redis", ["Rate counters", "token revocation"], title_fill="#F2F4F7", outline="#64748B")
    arrow(d, (510, 400), (720, 400))
    d.text((535, 415), "protected request", font=FONT_S, fill="#355C7D")
    arrow(d, (1250, 400), (1580, 400))
    d.text((1375, 415), "allowed only", font=FONT_S, fill="#355C7D")
    arrow(d, (510, 1020), (720, 1020))
    d.text((525, 1035), "HTTPS / REST", font=FONT_S, fill="#355C7D")
    arrow(d, (1250, 900), (1580, 900))
    d.text((1310, 915), "async SQL", font=FONT_S, fill="#355C7D")
    arrow(d, (1580, 1250), (1250, 1250))
    d.text((1330, 1265), "sessions / cache", font=FONT_S, fill="#355C7D")
    arrow(d, (1180, 820), (1180, 600), color="#6C4C9C", dashed=True)
    d.text((1025, 690), "gRPC policy snapshots", font=FONT_S, fill="#6C4C9C")
    arrow(d, (800, 600), (800, 820), color="#6C4C9C", dashed=True)
    d.text((520, 700), "internal REST: key validation + events", font=FONT_S, fill="#6C4C9C")
    arrow(d, (1250, 530), (1580, 1230), color="#A56B00", dashed=True)
    d.text((1265, 710), "atomic rate-limit", font=FONT_S, fill="#A56B00")
    d.text((1265, 745), "scripts", font=FONT_S, fill="#A56B00")
    d.text((90, 1400), "Solid arrows are request/data paths; dashed arrows are internal policy or enforcement dependencies.", font=FONT_S, fill="#475569")
    im.save(path)
    return path


def generate_domain():
    path = DIAGRAMS / "figure_7_2_domain_model.png"
    im = Image.new("RGB", (2600, 1940), "#FFFFFF")
    d = ImageDraw.Draw(im)
    d.text((70, 45), "Aegis — current persisted domain model", font=FONT_XL, fill="#0B2545")
    # boxes based on actual SQLAlchemy models. Each entity also inherits id/created_at/updated_at.
    boxes = {
        "User": (960, 180, 1530, 480, ["id, email (unique), full_name", "hashed_password, is_active", "role: admin | viewer | api_consumer"]),
        "APIKey": (80, 690, 620, 1050, ["id, key_hash, key_prefix", "owner_id → User", "name, scopes (JSON)", "status, expires_at, last_used_at"]),
        "RateLimitRule": (690, 650, 1260, 1080, ["id, created_by → User", "scope_type + scope_value", "algorithm, limit_count, window_seconds", "burst_allowance, status", "one active rule per scope"]),
        "JWTConfig": (1370, 650, 1935, 1070, ["id, created_by → User", "algorithm, encrypted signing_key", "public_key, issuer, audience", "access/refresh TTL, status", "one active config"]),
        "ThreatRule": (2020, 700, 2520, 1040, ["id, created_by → User", "name, RE2 pattern", "severity, status"]),
        "IPBlock": (190, 1290, 720, 1650, ["id, created_by → User?", "ip_address (exact), reason", "source: manual | auto", "status", "one active IP"]),
        "RoutePermission": (910, 1320, 1490, 1650, ["id, created_by → User", "method, path_pattern (exact)", "required_scope", "status"]),
        "SecurityEvent": (1690, 1270, 2480, 1660, ["id, event_type, source_ip", "api_key_id → APIKey?", "rule_id?, method, path", "status_code", "sanitised: no raw credentials"]),
    }
    for title, (x1, y1, x2, y2, lines) in boxes.items():
        text_box(d, (x1, y1, x2, y2), title, lines, body_size=24)
    # relationships (read from models/migrations)
    # Sparse connectors keep the diagram readable; FK fields are named inside each entity.
    arrow(d, (1020, 480), (370, 690))
    d.text((560, 525), "owns 1..*", font=FONT_S, fill="#355C7D")
    arrow(d, (1120, 480), (980, 650))
    d.text((1140, 540), "creates 1..*", font=FONT_S, fill="#355C7D")
    arrow(d, (1250, 480), (1650, 650))
    d.text((1430, 535), "creates 1..*", font=FONT_S, fill="#355C7D")
    arrow(d, (1400, 480), (2270, 700))
    d.text((1870, 550), "creates 1..*", font=FONT_S, fill="#355C7D")
    d.text((75, 1795), "All entities inherit audit fields: id, created_at and updated_at. Lower-row FK relationships are shown in entity fields", font=FONT_S, fill="#475569")
    d.text((75, 1835), "to avoid crossing connectors. SecurityEvent retains an optional API-key ID; rule_id is deliberately not a database foreign key.", font=FONT_S, fill="#475569")
    im.save(path)
    return path


def generate_sequence():
    path = DIAGRAMS / "figure_7_3_enforcement_sequence.png"
    im = Image.new("RGB", (2450, 2240), "#FFFFFF")
    d = ImageDraw.Draw(im)
    d.text((70, 45), "Aegis — actual request validation and enforcement sequence", font=FONT_XL, fill="#0B2545")
    participants = [(120, "Client"), (520, "Go Reverse Proxy"), (1030, "Policy snapshot"), (1460, "Control Plane"), (1840, "Redis"), (2160, "Upstream")]
    for x, label in participants:
        d.rounded_rectangle((x-125, 150, x+125, 220), 12, fill="#E8EEF5", outline="#2E74B5", width=3)
        bb = d.textbbox((0, 0), label, font=FONT_S)
        d.text((x-(bb[2]-bb[0])/2, 170), label, font=FONT_S, fill="#0B2545")
        d.line((x, 220, x, 2150), fill="#AAB7C4", width=2)
    y = 310
    def msg(a, b, label, color="#355C7D", dashed=False, note=None):
        nonlocal y
        xs = {label_: x for x, label_ in participants}
        arrow(d, (xs[a], y), (xs[b], y), color=color, width=4, dashed=dashed)
        bb = d.textbbox((0, 0), label, font=FONT_S)
        mid = (xs[a] + xs[b]) / 2
        d.rounded_rectangle((mid-(bb[2]-bb[0])/2-8, y-48, mid+(bb[2]-bb[0])/2+8, y-10), 4, fill="#FFFFFF")
        d.text((mid-(bb[2]-bb[0])/2, y-44), label, font=FONT_S, fill=color)
        y += 95
        if note:
            d.text((540, y-20), note, font=FONT_S, fill="#9B1C1C")
            y += 58
    # Main path is based directly on Handler.ServeHTTP order.
    msg("Client", "Go Reverse Proxy", "1. HTTP request: API key + Bearer JWT")
    msg("Go Reverse Proxy", "Policy snapshot", "2. exact direct-IP block lookup", note="If blocked → 403 IP_BLOCKED; stop before credential validation")
    msg("Go Reverse Proxy", "Policy snapshot", "3. RE2 match against METHOD + path?query", note="If threat matches → 403 THREAT_DETECTED; stop")
    msg("Go Reverse Proxy", "Control Plane", "4. validate API key (local cache; internal REST on miss)", color="#6C4C9C", dashed=True)
    msg("Control Plane", "Go Reverse Proxy", "key status, expiry and scopes", color="#6C4C9C", dashed=True)
    y += 15
    d.text((540, y-20), "Missing/invalid/revoked/expired key → 401 or 403; stop", font=FONT_S, fill="#9B1C1C")
    y += 58
    msg("Go Reverse Proxy", "Policy snapshot", "5. locally validate JWT signature, exp, issuer/audience", note="Invalid/missing JWT → 401; stop")
    msg("Go Reverse Proxy", "Policy snapshot", "6. exact method/path route permission → required scope", note="Missing required scope → 403 INSUFFICIENT_SCOPE; unmatched route allowed")
    msg("Go Reverse Proxy", "Redis", "7. select rule: API key > route > global; run atomic algorithm", color="#A56B00")
    msg("Redis", "Go Reverse Proxy", "allow/remaining/retry", color="#A56B00")
    y += 15
    d.text((540, y-20), "Limit exceeded → 429 + Retry-After; stop", font=FONT_S, fill="#9B1C1C")
    y += 58
    msg("Go Reverse Proxy", "Upstream", "8. strip X-API-Key + Authorization; forward request", color="#1F6D4C")
    msg("Upstream", "Go Reverse Proxy", "response", color="#1F6D4C")
    msg("Go Reverse Proxy", "Client", "9. return upstream response", color="#1F6D4C")
    msg("Go Reverse Proxy", "Control Plane", "10. asynchronously enqueue sanitised security event", color="#6C4C9C", dashed=True)
    d.text((70, 2180), "Policy snapshots arrive by authenticated gRPC stream after REST bootstrap; the last valid in-memory snapshot remains usable across a transient Control Plane outage.", font=FONT_S, fill="#475569")
    im.save(path)
    return path


def cleaned_terminal(path: Path, wanted: list[str] | None = None) -> list[str]:
    text = path.read_text(errors="replace")
    text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text).replace("\x08", "").replace("^D", "")
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if wanted:
        selected = []
        for line in lines:
            if any(term in line for term in wanted):
                selected.append(line)
        return selected
    return lines


def terminal_capture(source: Path, destination: Path, title: str, wanted=None):
    lines = cleaned_terminal(source, wanted)
    if not lines:
        lines = ["No terminal output was available."]
    canvas = Image.new("RGB", (1900, max(360, 170 + len(lines) * 52)), "#101827")
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((0, 0, 1900, 78), radius=0, fill="#263346")
    d.ellipse((34, 27, 50, 43), fill="#FF5F57")
    d.ellipse((61, 27, 77, 43), fill="#FEBC2E")
    d.ellipse((88, 27, 104, 43), fill="#28C840")
    d.text((135, 22), title, font=FONT_M, fill="#F8FAFC")
    y = 112
    monofont = font(31)
    for line in lines:
        color = "#D8E3F0"
        if "passed" in line.lower() or "HTTP 200" in line or "FORWARDED" in line:
            color = "#8EE0A8"
        elif "HTTP 4" in line or "EXCEEDED" in line or "INSUFFICIENT" in line:
            color = "#FFD28A"
        d.text((42, y), line[:118], font=monofont, fill=color)
        y += 52
    canvas.save(destination)
    return destination


def shade(cell, color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)


def set_cell_width(cell, width_inches):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(int(width_inches * 1440)))
    tc_w.set(qn("w:type"), "dxa")


def add_page_number(paragraph):
    run = paragraph.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char1)
    run._r.append(instr)
    run._r.append(fld_char2)


def setup_doc(chapter_no, title):
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = sec.bottom_margin = sec.left_margin = sec.right_margin = Inches(1)
    sec.header_distance = sec.footer_distance = Inches(0.49)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(8)
    normal.paragraph_format.line_spacing = 1.333
    for style_name, size, color, before, after in [("Heading 1",16,BLUE,18,10),("Heading 2",13,BLUE,12,6),("Heading 3",12,"1F4D78",8,4)]:
        style = doc.styles[style_name]
        style.font.name = "Calibri"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True
    header = sec.header.paragraphs[0]
    header.text = f"AEGIS PROJECT REPORT  |  CHAPTER {chapter_no}"
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header.runs[0].font.size = Pt(8)
    header.runs[0].font.color.rgb = RGBColor.from_string(MUTED)
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = footer.add_run("Aegis Project Report  |  Page ")
    r.font.size = Pt(8)
    r.font.color.rgb = RGBColor.from_string(MUTED)
    add_page_number(footer)
    # chapter cover
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(115)
    p.paragraph_format.space_after = Pt(18)
    run = p.add_run("AEGIS PROJECT REPORT")
    run.bold = True; run.font.size = Pt(14); run.font.color.rgb = RGBColor.from_string(BLUE)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(15)
    run = p.add_run(f"Chapter {chapter_no}")
    run.bold = True; run.font.size = Pt(30); run.font.color.rgb = RGBColor.from_string(DARK)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(30)
    run = p.add_run(title)
    run.bold = True; run.font.size = Pt(20); run.font.color.rgb = RGBColor.from_string(BLUE)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run("Htun Khaing Lynn  |  Student ID: 001557481")
    run.font.size = Pt(11); run.font.color.rgb = RGBColor.from_string(MUTED)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Aegis: API Security and Management System")
    run.italic = True; run.font.size = Pt(11); run.font.color.rgb = RGBColor.from_string(MUTED)
    doc.add_page_break()
    return doc


def add_heading(doc, text, level=1):
    return doc.add_paragraph(text, style=f"Heading {level}")


def add_para(doc, text, italic=False):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(text)
    r.italic = italic
    return p


def add_bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(4)
        p.add_run(item)


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = False
    table.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = header
        shade(cell, LIGHT_BLUE)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.size = Pt(9)
        if widths: set_cell_width(cell, widths[i])
    tr_pr = table.rows[0]._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    tr_pr.append(repeat)
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value)
            cells[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            for p in cells[i].paragraphs:
                p.paragraph_format.space_after = Pt(2)
                for run in p.runs: run.font.size = Pt(9)
            if widths: set_cell_width(cells[i], widths[i])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def add_figure(doc, path, caption, width=6.2):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Inches(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(10)
    run = cap.add_run(caption)
    run.italic = True
    run.font.size = Pt(9)


def landscape_figure_page(doc, path, caption, width):
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Inches(11)
    section.page_height = Inches(8.5)
    section.top_margin = Inches(0.2)
    section.bottom_margin = Inches(0.2)
    section.left_margin = Inches(0.45)
    section.right_margin = Inches(0.45)
    # Landscape pages carry a large diagram and its caption as one unit.  The
    # deliberately tight paragraph spacing prevents Word from orphaning the
    # caption onto an otherwise blank following page.
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(1)
    p.add_run().add_picture(str(path), width=Inches(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_before = Pt(0)
    cap.paragraph_format.space_after = Pt(0)
    run = cap.add_run(caption)
    run.italic = True
    run.font.size = Pt(8)
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    section.orientation = WD_ORIENT.PORTRAIT
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = Inches(1)


def add_references(doc, references):
    add_heading(doc, "References", 1)
    for ref in references:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.first_line_indent = Inches(-0.3)
        p.paragraph_format.space_after = Pt(5)
        p.add_run(ref)


REFS_CORE = [
    "Agile Business Consortium (2014) The DSDM Agile Project Framework. Tunbridge Wells: Agile Business Consortium.",
    "Fielding, R.T. (2000) Architectural Styles and the Design of Network-based Software Architectures. PhD thesis. University of California, Irvine.",
    "Indrasiri, K. and Kuruppu, D. (2020) gRPC: Up and Running. Sebastopol: O’Reilly Media.",
    "Jones, M., Bradley, J. and Sakimura, N. (2015) JSON Web Token (JWT). RFC 7519. Internet Engineering Task Force. Available at: https://www.rfc-editor.org/rfc/rfc7519 (Accessed: 2 August 2026).",
    "Newman, S. (2021) Building Microservices: Designing Fine-grained Systems. 2nd edn. Sebastopol: O’Reilly Media.",
    "OWASP Foundation (2023) OWASP API Security Top 10 2023. Available at: https://owasp.org/www-project-api-security/ (Accessed: 2 August 2026).",
    "W3C (2018) Web Content Accessibility Guidelines (WCAG) 2.1. Available at: https://www.w3.org/TR/WCAG21/ (Accessed: 2 August 2026).",
]


def chapter_1():
    doc = setup_doc(1, "Introduction")
    add_heading(doc, "1.1 Background", 1)
    add_para(doc, "Application Programming Interfaces (APIs) are now a normal boundary between browsers, mobile clients, internal services and third-party integrations. In a distributed architecture, each exposed endpoint is also a potential security decision point. When each backend implements authentication, authorisation, rate limiting and logging independently, controls can become inconsistent and teams lose a single view of how their APIs are being used. This is the problem context described in the Project Proposal and is consistent with the API-specific risks catalogued by OWASP (OWASP Foundation, 2023).")
    add_para(doc, "Aegis addresses this problem by placing a reverse proxy in front of protected HTTP services. The proxy decides whether a request may proceed before the upstream service sees it. A separate Control Plane owns the policy and a React dashboard gives operators a role-restricted way to configure and observe that policy. This separation is important: the configuration interface is not on the performance-critical forwarding path.")
    add_heading(doc, "1.2 Problem Statement", 1)
    add_para(doc, "The Project Proposal identified a gap between feature-rich commercial gateway products, which can bring cost or platform dependency, and small custom proxies that often omit distributed limits, auditability and central policy management. The specific engineering problem is therefore to provide a self-hosted, understandable security layer that validates requests consistently without requiring changes in every protected backend.")
    add_heading(doc, "1.3 Aim and Objectives", 1)
    add_para(doc, "The proposal aim is to design and develop a production-ready API security and management system that centrally protects backend services through intelligent request validation, rate limiting and threat detection, while demonstrating full-stack development using Python/FastAPI, Go and React. The report evaluates that aim against a working implementation rather than treating the proposal as evidence that a feature exists.")
    add_table(doc, ["Objective from proposal", "Report evidence"], [
        ("Central request validation", "Go proxy validates IP, threat policy, API key, JWT and route scope before forwarding."),
        ("Distributed rate limiting", "Redis-backed fixed-window, sliding-window and token-bucket enforcement with documented rule precedence."),
        ("Central management", "FastAPI Control Plane, PostgreSQL policy store and React role-aware dashboard."),
        ("Threat detection and blocking", "RE2 request-target rules, exact IP blocks, automatic blocks and sanitised security events."),
        ("Full-stack proficiency", "Python async APIs, Go data-plane code, React UI, Docker Compose, gRPC policy stream and automated tests."),
    ], [2.35, 4.15])
    add_heading(doc, "1.4 Actual System Scope", 1)
    add_bullets(doc, [
        "User registration, login, refresh/logout, Redis-backed token lifecycle and Admin, Viewer and API Consumer roles.",
        "One-time API-key issuance with bcrypt storage, scoped keys, ownership controls and soft revocation.",
        "Policy configuration for JWT validation, exact route-to-scope permissions, rate limits, threat rules and IP blocks.",
        "Go proxy enforcement with local policy snapshots, gRPC updates, Redis counters and credential stripping before upstream forwarding.",
        "Sanitised events and analytics, plus a local echo-service/attack-console proof of concept.",
    ])
    add_para(doc, "The implementation deliberately remains limited to HTTP, an online Control Plane and a web dashboard. Non-HTTP protocol support, air-gapped operation and native mobile administration remain explicit exclusions from the proposal and the MoSCoW scope.")
    add_heading(doc, "1.5 Report Structure", 1)
    add_para(doc, "Chapters 2 and 3 position the project against comparable products and technical literature. Chapters 4 and 5 explain the DSDM schedule and LSEP considerations. Chapter 6 analyses users and requirements. Chapter 7 documents the actual design, Chapters 8 and 9 explain and verify the implementation, and Chapter 10 evaluates the result and reflects on the development process.")
    add_references(doc, REFS_CORE)
    return doc


def chapter_2():
    doc = setup_doc(2, "Product Research")
    add_heading(doc, "2.1 Research Purpose and Method", 1)
    add_para(doc, "This chapter compares practical gateway products rather than repeating the academic discussion in Chapter 3. The comparison uses the needs stated in the proposal: API and JWT authentication, traffic control, route-level policy, operational visibility, deployment model and the ease of adding project-specific detection logic. The aim is not to claim that Aegis is universally better than mature gateways; it is to establish the design niche that justified a focused self-hosted build.")
    add_heading(doc, "2.2 Products Considered", 1)
    add_heading(doc, "Kong Gateway", 2)
    add_para(doc, "Kong provides gateway functionality through configurable plugins. Its official documentation presents rate limiting at global, service, route and consumer levels, with different window and storage approaches. This makes Kong a useful benchmark for policy-driven traffic governance. However, an implementation built around Kong is mainly an exercise in operating and composing its plugin ecosystem, whereas Aegis was deliberately built to demonstrate the Control Plane/data-plane split and a small, auditable enforcement pipeline (Kong, 2026).")
    add_heading(doc, "Apache APISIX", 2)
    add_para(doc, "APISIX exposes authentication, security and traffic-control plugins, including JWT authentication and fixed-window count limiting. Its rate-limit documentation also describes Redis-backed counters and response headers. It is therefore a strong open-source reference for route-based gateway controls. Aegis adopts the same practical concern—shared counters for multiple proxies—but implements three explicit algorithms and its own policy distribution path (Apache APISIX, 2026).")
    add_heading(doc, "Tyk and Amazon API Gateway", 2)
    add_para(doc, "Tyk represents a configurable API-management platform, while Amazon API Gateway represents a cloud-managed option. AWS documents route-level JWT authorisation scopes and token-bucket throttling. These products reduce implementation work but bind operational decisions to a product model or cloud account. Aegis instead keeps policy tables and enforcement behaviour visible in source code and deployable with PostgreSQL, Redis and Docker Compose (Amazon Web Services, 2026; Tyk Technologies, 2026).")
    add_heading(doc, "2.3 Comparative Analysis", 1)
    add_table(doc, ["Capability", "Kong", "APISIX", "AWS API Gateway", "Aegis"], [
        ("Deployment model", "Self-hosted gateway", "Self-hosted gateway", "Managed cloud service", "Self-hosted Docker Compose stack"),
        ("API/JWT authentication", "Plugin based", "Plugin based", "JWT authorizer", "API key plus JWT in Go proxy"),
        ("Rate limiting", "Plugin and policies", "Traffic plugins / Redis option", "Token-bucket throttling", "Redis fixed, sliding and token bucket"),
        ("Route authorisation", "Route/plugin configuration", "Route/plugin configuration", "JWT scopes per route", "Exact method/path → API-key scope mapping"),
        ("Threat rule in project core", "Composed via plugins/integrations", "Composed via plugins/integrations", "Uses adjacent AWS services", "RE2 request-target rules in proxy"),
        ("Learning focus", "Operate platform", "Operate platform", "Configure cloud service", "Implement policy and enforcement separation"),
    ], [1.25, 1.3, 1.35, 1.35, 1.25])
    add_heading(doc, "2.4 Findings and Design Consequences", 1)
    add_para(doc, "The comparison validates the proposal’s central premise: mature gateways already solve many generic problems. Aegis therefore should not be evaluated as a replacement for their breadth. Its value is a transparent, smaller system that makes the security decisions inspectable: a rule lives in PostgreSQL, is exposed in the Control Plane, arrives in the proxy snapshot and has a specific enforcement point in Go.")
    add_bullets(doc, [
        "Use route policies rather than infer a resource name from a URL; this mirrors the explicit route-scope approach of managed gateways.",
        "Use Redis for shared rate-limit state, avoiding a per-process counter that would fail in a multi-proxy deployment.",
        "Keep threat matching narrowly defined as method plus path/query, which protects streaming request bodies and avoids collecting unnecessary content.",
        "Keep the dashboard outside the enforcement path so an unavailable UI does not stop proxy traffic.",
    ])
    add_references(doc, REFS_CORE + [
        "Amazon Web Services (2026) Control access to HTTP APIs with JWT authorizers in API Gateway. Available at: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html (Accessed: 2 August 2026).",
        "Apache APISIX (2026) Rate Limiting by Count (limit-count). Available at: https://apisix.apache.org/docs/apisix/plugins/limit-count/ (Accessed: 2 August 2026).",
        "Kong (2026) Rate Limiting. Available at: https://docs.konghq.com/gateway/latest/get-started/rate-limiting/ (Accessed: 2 August 2026).",
        "Tyk Technologies (2026) Rate Limiting. Available at: https://tyk.io/docs/api-management/rate-limit/ (Accessed: 2 August 2026).",
    ])
    return doc


def chapter_3():
    doc = setup_doc(3, "Literature Review")
    add_heading(doc, "3.1 API Security and the Reverse-proxy Boundary", 1)
    add_para(doc, "REST describes an architectural style rather than a security mechanism (Fielding, 2000). Modern API systems must therefore decide how a request is authenticated, authorised, rate controlled and monitored. The OWASP API Security Top 10 identifies broken authentication, broken object-level authorisation and unrestricted resource consumption as important API risks (OWASP Foundation, 2023). A reverse proxy gives Aegis an early enforcement boundary: denied traffic does not reach the protected service.")
    add_heading(doc, "3.2 Authentication and Authorisation", 1)
    add_para(doc, "Aegis uses two separate credentials for the POC request path. The API key identifies the caller and carries its configured scopes; the JWT provides a signed, time-limited authentication token. JWT validation checks the signing algorithm, signature and expiry, and can check issuer and audience when configured. This is grounded in RFC 7519’s compact signed claims format (Jones, Bradley and Sakimura, 2015).")
    add_para(doc, "Authentication is not enough to decide which endpoint a caller may use. The current implementation therefore stores exact method/path policies such as GET /api/echo → echo:read. The proxy compares the configured required scope with the API key’s scopes after both credentials validate. It does not guess that a path segment called echo is a resource. This explicit mapping is more predictable, auditable and safer to evolve.")
    add_heading(doc, "3.3 Secure Credential Handling", 1)
    add_para(doc, "Passwords and API keys are not recoverable application data. Aegis hashes them with bcrypt; only the raw API key is displayed at creation. JWT signing material has a different requirement: it must be available to sign or verify tokens, so it is Fernet-encrypted at rest and operator APIs return masked values. These choices separate a one-way verifier from protected but recoverable configuration material.")
    add_heading(doc, "3.4 Rate-limiting Algorithms", 1)
    add_para(doc, "Fixed windows are simple and efficient but can allow a burst across a boundary. Sliding windows more accurately represent recent activity but require timestamp state. Token buckets allow controlled bursts while replenishing capacity over time. Rather than presenting one algorithm as universally best, Aegis exposes fixed-window, sliding-window and token-bucket policy options and runs each with Redis atomic scripts. Shared Redis state is significant because different proxy instances must see the same counter.")
    add_heading(doc, "3.5 Policy Synchronisation and Resilience", 1)
    add_para(doc, "A Control Plane/data-plane split supports operator control without requiring a database query for every user request. The Control Plane creates policy snapshots from active rows. The proxy bootstraps through an authenticated REST snapshot and then accepts gRPC server-streamed updates. The proxy keeps the last valid snapshot if the stream disconnects, which is a deliberate availability decision: a brief Control Plane outage should not turn off existing protection (Indrasiri and Kuruppu, 2020).")
    add_heading(doc, "3.6 Threat Detection, Logging and Privacy", 1)
    add_para(doc, "Regular expressions can identify known suspicious request targets, but unbounded backtracking can itself become a denial-of-service risk. Aegis accepts only patterns compatible with Go’s RE2 engine and evaluates them against METHOD plus path/query. Request bodies and arbitrary headers are intentionally not inspected or persisted. The associated event model retains outcome, direct source IP, optional policy identifiers, method, path and status code, providing a useful audit trail while avoiding raw API keys, JWTs and request bodies.")
    add_heading(doc, "3.7 Literature-to-design Traceability", 1)
    add_table(doc, ["Source concept", "Aegis design decision"], [
        ("API threat categories (OWASP)", "Pre-forward validation, rate limits, route scope checks and threat policies."),
        ("JWT signed claims (RFC 7519)", "Algorithm-pinned JWT validation with expiry and optional issuer/audience."),
        ("Distributed systems separation", "FastAPI Control Plane defines policy; Go proxy enforces cached policy."),
        ("Rate-control trade-offs", "Policy-selected fixed/sliding/token bucket Redis scripts."),
        ("Privacy by minimisation", "Sanitised security events; no raw credentials, bodies or arbitrary headers."),
    ], [2.35, 4.15])
    add_references(doc, REFS_CORE)
    return doc


def chapter_4():
    doc = setup_doc(4, "Project Timeline")
    add_heading(doc, "4.1 DSDM Delivery Approach", 1)
    add_para(doc, "The Project Proposal selected Agile DSDM because it combines fixed timeboxes, incremental delivery, MoSCoW prioritisation and regular review. This chapter applies the tutor feedback to make the plan a DSDM timebox plan only: it starts with design work rather than separate research, analysis or planning phases; activities are multi-day; and the final testing date is 9 October 2026. Research and analysis inform the work but are not presented as standalone timeline phases.")
    add_para(doc, "Each timebox includes a short foundation/checkpoint, development, test, review and retrospective activity. The work is ordered so that the Control Plane policy model is available before the proxy enforces it, and the POC and end-to-end tests follow a usable full-stack path.")
    add_heading(doc, "4.2 Timebox Schedule", 1)
    rows = [
        ("TB1", "16–27 Mar", "Architecture and data-model design", "Component boundaries, initial schema, key workflows"),
        ("TB2", "30 Mar–10 Apr", "Security and interface design", "API contract, authentication and enforcement sequence"),
        ("TB3", "13–24 Apr", "Control Plane foundation", "Async FastAPI, migrations, user/auth foundations"),
        ("TB4", "27 Apr–8 May", "Identity and API-key delivery", "RBAC, key issue/revoke, ownership controls"),
        ("TB5", "11–22 May", "Policy configuration", "Rate-limit and JWT configuration workflows"),
        ("TB6", "25 May–5 Jun", "Proxy core", "Go forwarding, internal key validation and cache"),
        ("TB7", "8–19 Jun", "Traffic enforcement", "Redis limits, JWT validation and response contracts"),
        ("TB8", "22 Jun–3 Jul", "Policy distribution", "REST snapshot, gRPC stream and resilience checks"),
        ("TB9", "6–17 Jul", "Security controls", "Threat rules, manual/automatic IP blocking"),
        ("TB10", "20–31 Jul", "Observability", "Sanitised events, analytics and dashboard integration"),
        ("TB11", "3–14 Aug", "Route authorisation", "Exact route-permission policy and scope enforcement"),
        ("TB12", "17–28 Aug", "Integration hardening", "Docker Compose, policy refresh and regression fixes"),
        ("TB13", "31 Aug–11 Sep", "System test timebox", "Component, integration and coverage checks"),
        ("TB14", "14–25 Sep", "POC and acceptance timebox", "Attack console, user-path checks and defect correction"),
        ("TB15", "28 Sep–9 Oct", "Final test and report timebox", "Regression, evaluation, documentation and submission preparation"),
    ]
    add_table(doc, ["Timebox", "Dates", "Primary focus", "Multi-day outputs"], rows, [0.7, 1.15, 1.75, 2.9])
    add_heading(doc, "4.3 Timebox Controls", 1)
    add_bullets(doc, [
        "At the start of each timebox, confirm the MoSCoW scope and dependencies; do not move unfinished optional features ahead of an unverified security baseline.",
        "During development, maintain small increments that can be tested at the Control Plane, proxy and dashboard boundaries.",
        "At the end, run relevant automated tests, review acceptance evidence, record defects and use the retrospective to adjust the following timebox.",
        "Treat quality as non-negotiable: a feature is not complete merely because it has a screen or endpoint; it needs an enforcement and test path where applicable.",
    ])
    add_heading(doc, "4.4 Milestones and Dependencies", 1)
    add_para(doc, "The critical chain is policy model → authenticated Control Plane API → proxy policy retrieval → enforcement → cross-component testing. The analytics and dashboard work depends on the proxy reporting an event safely, but it must not delay the security decision itself. The final two timeboxes are deliberately reserved for evidence-led testing and documentation, rather than adding a new functional phase outside the DSDM structure.")
    add_references(doc, [REFS_CORE[0]])
    return doc


def chapter_5():
    doc = setup_doc(5, "Legal, Social, Ethical and Professional Issues")
    add_heading(doc, "5.1 Legal Issues", 1)
    add_para(doc, "Aegis handles account data, source IP addresses, endpoint paths and security-event metadata. In a real deployment, these can be personal data or operationally sensitive information. The project is a technical implementation, not a claim of legal compliance, but it applies practical safeguards: bcrypt hashes for passwords/API keys, encrypted JWT signing material, one-time raw-key disclosure and sanitised events that omit raw credentials, bodies and arbitrary headers.")
    add_para(doc, "Data retention, lawful basis, data-subject rights, processor contracts and breach procedures remain deployment responsibilities. A production operator should define event-retention periods, access controls and deletion workflows in line with the jurisdiction in which it operates. Dependencies also need licence review before redistribution; the project should keep attribution for FastAPI, SQLAlchemy, Go, React, Redis clients, Docker and other third-party components.")
    add_heading(doc, "5.2 Social Issues", 1)
    add_para(doc, "A security product can help small teams by centralising controls that otherwise require every service to implement them. The self-hosted Docker Compose development path reduces the hardware and cloud-account barrier for learning and local experimentation. However, a dashboard that is difficult to understand can exclude non-specialist operators. Labels, structured errors, visible status and role-restricted navigation are therefore part of the social usability goal.")
    add_para(doc, "Accessibility should be treated as an ongoing quality requirement rather than a final visual check. The dashboard should support keyboard use, readable contrast, semantic controls and useful error messages in line with WCAG 2.1 principles (W3C, 2018). Localization and broader assistive-technology evaluation are valid future work rather than claims made by the current implementation.")
    add_heading(doc, "5.3 Ethical Issues", 1)
    add_para(doc, "Aegis can deny a request, throttle a client or automatically block an IP address. Those controls are valuable but can create false positives, particularly when several legitimate users share an address. The implementation limits its manual block model to one exact IPv4/IPv6 address, uses the direct peer instead of trusting a spoofable X-Forwarded-For header, and records source/reason/status for operator review. Automatic blocks are triggered only by recent threat-detected or rate-limited outcomes, not by every authentication mistake.")
    add_para(doc, "Threat rules require special care. They match a narrow textual surface (method plus path/query) using RE2-compatible patterns and should be reviewed, tested and disabled when unsuitable. Security testing must be confined to the project’s own local POC and explicitly authorised environments. The provided console is restricted to loopback targets and the fixed echo route, helping prevent accidental testing of third-party systems.")
    add_heading(doc, "5.4 Professional Issues", 1)
    add_para(doc, "Professional practice in this project means traceability from proposal to requirement to code and test evidence. The repository separates policy definition from proxy enforcement, uses forward database migrations, includes versioned APIs, and runs Python, Go and JavaScript checks. Honest reporting is important: a feature is described as implemented only where code and an observed test support it. The report also distinguishes current limitations from completed work instead of presenting a future intention as a result.")
    add_heading(doc, "5.5 Risk and Mitigation Summary", 1)
    add_table(doc, ["Area", "Risk", "Current mitigation / next action"], [
        ("Privacy", "Sensitive information appears in logs", "Persist only sanitised events; define production retention and access policy."),
        ("Authorisation", "Over-broad route access", "Exact method/path permissions; no URL-derived resource inference; test missing scope."),
        ("Availability", "Control Plane outage affects traffic", "REST bootstrap, gRPC updates and last-valid snapshot in proxy memory."),
        ("Fairness", "Legitimate user is throttled/blocked", "Specific policy scopes, audit metadata and soft-disable review path."),
        ("Security testing", "Traffic accidentally targets external system", "POC console permits loopback only and fixed /api/echo route."),
        ("Maintainability", "Policy/schema drift", "Migrations are source of truth; tests and code review after timeboxes."),
    ], [1.1, 2.05, 3.95])
    add_references(doc, REFS_CORE)
    return doc


def chapter_6():
    doc = setup_doc(6, "System Analysis")
    add_heading(doc, "6.1 Chapter Review and Verified Updates", 1)
    add_para(doc, "This chapter retains the requirements-led analysis established in the previous draft, but has been checked against the current migrations, API contract and Go proxy. The analysis is updated where the implementation has moved on: route-to-scope permissions are now a persisted policy, the proxy requires both an API key and Bearer JWT on protected POC requests, gRPC policy synchronisation and automatic IP blocking are implemented, and analytics is populated through sanitised proxy events.")
    add_heading(doc, "6.2 Stakeholders and Actors", 1)
    add_table(doc, ["Actor", "Primary needs", "Authorised actions"], [
        ("Administrator", "Define and review security policy", "Manage users, keys, JWT config, limits, threat rules, blocks, route permissions and analytics."),
        ("Viewer", "Observe system state without changing it", "Read analytics and permitted configuration views."),
        ("API Consumer", "Call a protected API safely", "Register/login and manage own API-key metadata; use issued key and JWT."),
        ("Reverse Proxy", "Enforce policy consistently", "Load trusted snapshots, validate requests, rate-limit, forward and report events."),
        ("Protected service", "Receive only allowed traffic", "Processes forwarded request without Aegis credentials."),
    ], [1.3, 2.3, 3.5])
    add_heading(doc, "6.3 Functional Requirements", 1)
    add_heading(doc, "6.3.1 Identity, Roles and API Keys", 2)
    add_para(doc, "The system shall register users, issue role-bearing login/refresh tokens and revoke a logout token in Redis. It shall generate cryptographically random API keys, show a raw value once only, retain a bcrypt hash and harmless prefix, enforce ownership/Admin checks and soft-revoke rather than delete a key.")
    add_heading(doc, "6.3.2 Policy Configuration", 2)
    add_para(doc, "Administrators shall configure one active JWT policy, active rate-limit rules, RE2-compatible threat rules, exact-address IP blocks and exact method/path route-permission policies. Active policy is returned only through authenticated internal contracts to the proxy. A route permission maps a path and method to a required API-key scope; it does not infer a resource name from the URL.")
    add_heading(doc, "6.3.3 Request Validation and Enforcement", 2)
    add_bullets(doc, [
        "Check the direct client IP against active exact-address blocks before credential validation.",
        "Match active threat patterns against METHOD plus path/query and reject a match before forwarding.",
        "Require a valid API key and a valid Bearer JWT; reject missing, invalid, revoked or expired credentials with structured errors.",
        "Apply a matching route-scope policy after identity validation; return INSUFFICIENT_SCOPE where the exact scope is absent.",
        "Select the most specific rate rule (API key, then route, then global) and enforce it through Redis.",
        "Remove API credentials from the forwarded request, return the upstream response and enqueue a sanitised outcome event asynchronously.",
    ])
    add_heading(doc, "6.3.4 Monitoring and Administration", 2)
    add_para(doc, "The system shall accept internal, sanitised proxy outcomes, make time-window summaries and history available to authorised Admin and Viewer users, and expose dashboard pages according to role. Automatic blocking shall be limited to repeated threat/rate-limit violations in the configured window and remain visible as an auto-sourced block that an Administrator can disable.")
    add_heading(doc, "6.4 Non-functional Requirements", 1)
    add_table(doc, ["Quality attribute", "Requirement and current design response"], [
        ("Security", "bcrypt/secret encryption, internal-token protection, RBAC, structured failures and credential stripping."),
        ("Performance", "No database hit on the proxy hot path for policy; cached key validation and in-memory policy snapshot."),
        ("Scalability", "Redis shares rate counters between proxy instances; policy snapshots are distributed over gRPC."),
        ("Reliability", "The proxy retains the last valid policy snapshot over a transient Control Plane interruption."),
        ("Maintainability", "FastAPI Control Plane/policy and Go enforcement are separate; migrations and tests document constraints."),
        ("Usability", "Role-aware dashboard and consistent error bodies; sensitive values are masked or one-time only."),
    ], [1.55, 5.05])
    add_heading(doc, "6.5 MoSCoW Prioritisation and Delivered Scope", 1)
    add_para(doc, "The proposal categorised core authentication, API-key management, rate limiting, JWT validation and RBAC as Must Have. Threat rules, analytics and gRPC were Should Have; automatic blocking was Could Have. The verified codebase has delivered all of these priority groups. This does not change their original rationale; it records that the iterative delivery completed beyond the minimum baseline. Non-HTTP support, offline/air-gapped deployment and native mobile administration remain Won’t Have scope.")
    add_heading(doc, "6.6 Conclusion", 1)
    add_para(doc, "The updated analysis describes a central policy system whose enforcement happens in a separate proxy. It introduces the exact route-permission policy that makes scope checks meaningful and preserves the original focus on secure, distributed and observable API protection. Chapter 7 turns these requirements into the verified current design.")
    add_references(doc, REFS_CORE)
    return doc


def chapter_7(fig1, fig2, fig3):
    doc = setup_doc(7, "System Design")
    add_heading(doc, "7.1 Design Overview", 1)
    add_para(doc, "The implemented design follows the proposal’s three-component direction but the details are now verified against the current codebase. FastAPI is the Control Plane and policy source of truth; Go is the data-plane enforcement layer; React is the dashboard. PostgreSQL stores durable policy/audit data and Redis is shared runtime state. The dashboard never directly configures the proxy, and the proxy does not query PostgreSQL on every request.")
    landscape_figure_page(doc, fig1, "Figure 7.1: Actual Aegis system architecture, derived from the current FastAPI, Go, React, Docker Compose and POC code.", width=9.0)
    add_heading(doc, "7.2 Component Responsibilities", 1)
    add_table(doc, ["Component", "Responsibility", "Important interface"], [
        ("Control Plane", "Defines policy, ownership, RBAC, active configuration and analytics.", "Versioned REST; internal token routes; gRPC PolicySync stream."),
        ("Reverse Proxy", "Enforces IP/threat/credential/scope/rate decisions then forwards allowed traffic.", "HTTP request path, policy snapshot, Redis scripts, async event post."),
        ("Dashboard", "Role-aware operator and consumer experience.", "REST calls to Control Plane only."),
        ("PostgreSQL", "Durable users, keys, policies, blocks and events.", "SQLAlchemy/Alembic source of truth."),
        ("Redis", "Shared rate counters and auth revocation support.", "Atomic Lua-style scripts through go-redis."),
    ], [1.25, 2.85, 2.5])
    add_heading(doc, "7.3 Database and Domain Design", 1)
    add_para(doc, "The domain diagram reflects the actual SQLAlchemy models and forward migrations, which take precedence over earlier prose documentation. Every model inherits audit fields. Soft status changes preserve records which a cached proxy may still refer to while a new snapshot is being distributed.")
    landscape_figure_page(doc, fig2, "Figure 7.2: Current Aegis persisted domain model, based on actual SQLAlchemy models and Alembic migrations.", width=8.7)
    add_table(doc, ["Constraint", "Design rationale"], [
        ("One active JWT configuration", "Avoids ambiguous verification policy; activation deactivates the previous policy."),
        ("One active rate rule per scope", "Removes conflict when the proxy selects the applicable rule."),
        ("One active IP block per address", "Retains history while preventing duplicate active records."),
        ("Exact route permission", "Method and path are explicit; wildcard/query route rules are rejected in current scope."),
        ("One-time raw API key", "A key hash cannot be re-exposed; prefix remains available for lookup/display."),
    ], [2.2, 4.4])
    add_heading(doc, "7.4 Policy Synchronisation", 1)
    add_para(doc, "The proxy first obtains a REST policy snapshot through the internal-token endpoint. After that it subscribes to authenticated server-streaming gRPC updates. The streaming provider holds a clone of the latest valid snapshot under a read/write lock. If the stream is unavailable after a snapshot was received, enforcement continues with that snapshot; before any stream update, the REST provider is the fallback. This deliberately prioritises safe continuity over a per-request Control Plane dependency.")
    add_heading(doc, "7.5 Request-validation Design", 1)
    add_para(doc, "Figure 7.3 records the order implemented by Handler.ServeHTTP. The order is consequential. A blocked IP or threat rule avoids expensive credential work. Scope authorization occurs only after both key and JWT validation. Rate limiting occurs before forwarding. Every termination path reports a sanitised event through the bounded event reporter, but event delivery is intentionally outside the latency-critical decision.")
    landscape_figure_page(doc, fig3, "Figure 7.3: Actual core request-validation and enforcement sequence, based on the Go Reverse Proxy handler and its collaborators.", width=7.2)
    add_heading(doc, "7.6 Security Design Decisions", 1)
    add_bullets(doc, [
        "The proxy strips X-API-Key and Authorization before forwarding, so the upstream POC service demonstrates it receives no Aegis credentials.",
        "Threat patterns are constrained to RE2-compatible syntax and inspect only method plus request URI, avoiding body scanning and arbitrary content collection.",
        "The direct peer address is used for IP decisions; X-Forwarded-For is deliberately ignored unless a future trusted-proxy model is designed.",
        "Route scope is explicit. GET /api/echo and POST /api/echo can require different scopes even though they share the same path.",
    ])
    add_references(doc, REFS_CORE)
    return doc


def chapter_8():
    doc = setup_doc(8, "System Implementation")
    add_heading(doc, "8.1 Implementation Approach", 1)
    add_para(doc, "Implementation followed the proposal’s technology choices while making a few verified practical refinements. The system is a monorepo with an asynchronous FastAPI Control Plane, Go reverse proxy, React 19 dashboard, PostgreSQL, Redis and Docker Compose. The dashboard uses the established Vinext/Vite runtime and local UI primitives rather than replacing a working implementation solely to match an early library intention in the proposal.")
    add_heading(doc, "8.2 Control Plane", 1)
    add_para(doc, "The Control Plane is structured into routers, schemas, services, repositories and SQLAlchemy models. Pydantic validates incoming configuration and FastAPI dependencies enforce roles. Alembic migrations create and extend the schema, including users/roles, API keys, rate-limit rules, JWT configurations, IP blocks, threat rules, security events and route permissions.")
    add_table(doc, ["Area", "Implemented behaviour"], [
        ("Identity/RBAC", "Login, refresh, logout and persisted roles; bootstrap Admin allowlisting and role-protected routes."),
        ("API keys", "Random issue, bcrypt hash/prefix persistence, metadata CRUD, owner/Admin checks and soft revocation."),
        ("JWT configuration", "HS256/RS256/ES256 validation policy; Fernet-encrypted signing key; masked operator responses; one active config."),
        ("Policy data", "Rate rules, RE2-compatible threat patterns, exact IP blocks and exact method/path route permissions."),
        ("Analytics", "Internal security-event ingestion and time-window summary/history APIs for permitted roles."),
    ], [1.55, 5.05])
    add_heading(doc, "8.3 Reverse Proxy", 1)
    add_para(doc, "The Go application uses net/http and httputil.ReverseProxy. Startup validates environment configuration, creates an HTTP client, key-validation cache, REST policy provider, gRPC policy subscriber, Redis client, blockers/detector/validators and bounded async event reporter. The final handler composes these services and exposes a single protected HTTP forwarding endpoint.")
    add_para(doc, "API-key validation is an authenticated Control Plane request on a cache miss; a successful response contains only enforcement metadata such as key ID, status, expiry and scopes. JWT validation uses policy material from the snapshot and pins supported algorithms. Rate-limit selection is API-key-scoped first, then exact route, then global. Fixed-window, sliding-window and token-bucket logic are Redis scripts so the counter operation is atomic across proxy instances.")
    add_heading(doc, "8.4 Route Scope Enforcement", 1)
    add_para(doc, "The implementation introduced a RoutePermission model after the original proposal. This closes a conceptual gap in an API-key scope such as echo:read: the proxy has a configured policy saying which exact request requires it. For a matching method/path the proxy compares the required string against the validated key’s scopes. A non-matching route is currently allowed by default, allowing incremental policy rollout; a matching route without the scope returns 403 INSUFFICIENT_SCOPE before reaching the upstream service.")
    add_heading(doc, "8.5 Dashboard, Deployment and POC", 1)
    add_para(doc, "The React dashboard calls only the Control Plane and uses role-aware navigation. Docker Compose supplies PostgreSQL and Redis locally and supports a production-like stack. The POC adds an echo service and a loopback-only attack/defense console. The echo response makes forwarding visible, while the console sends controlled GET/POST requests only to /api/echo and keeps generated credentials in browser memory rather than writing them to a file.")
    add_heading(doc, "8.6 Proposal-to-implementation Comparison", 1)
    add_table(doc, ["Proposal intention", "Implemented result"], [
        ("Control Plane, proxy and dashboard", "Delivered as FastAPI, Go and React components with clear policy/enforcement separation."),
        ("Real-time policy synchronisation", "Delivered as authenticated gRPC stream with REST bootstrap/fallback and last-valid snapshot retention."),
        ("IP blocking", "Manual exact blocks and automatic blocks from repeated threat/rate violations are implemented."),
        ("Analytics and metrics", "Sanitised async proxy event ingestion plus authenticated summary/history endpoints and dashboard page."),
        ("Security workflow", "Expanded with exact method/path-to-scope route permissions and credential stripping before forward."),
    ], [2.35, 4.15])
    add_heading(doc, "8.7 Implementation Limitations", 1)
    add_para(doc, "The current baseline intentionally does not perform body inspection, wildcard route permissions, CIDR IP blocks, non-HTTP traffic handling, offline synchronisation or mobile administration. Threat rules are a request-target control rather than a general web application firewall. These boundaries keep the system focused and should be made explicit to a deployment team.")
    add_references(doc, REFS_CORE)
    return doc


def chapter_9(test_capture, poc_capture, e2e_capture=None):
    doc = setup_doc(9, "Testing")
    add_heading(doc, "9.1 Testing Strategy", 1)
    add_para(doc, "Testing combines automated component checks, cross-component coverage gates, an isolated end-to-end stack and a live local proof of concept. This follows the proposal’s intention to test Python, Go and React components as well as integrations. The results reported below are observed in the workspace on 2 August 2026; screenshots are terminal captures created from the corresponding local command output, with generated development credentials deliberately excluded.")
    add_heading(doc, "9.2 Automated Quality Suite", 1)
    add_table(doc, ["Check", "Observed result", "What it covers"], [
        ("Control Plane pytest + coverage", "47 passed; 77% application coverage", "RBAC, API keys, rate rules, JWT config, threats, IP blocks, analytics, policy snapshot, gRPC and route permissions."),
        ("Go proxy", "go test -race, go vet and gofmt pass; 83.4% core coverage", "Concurrency/race checks and hand-written proxy enforcement core."),
        ("Dashboard", "Lint/build pass; 6 rendered HTML tests pass", "Login UI, role navigation, in-memory auth state, IP/threat/analytics views."),
        ("POC/tooling", "13 tests pass", "Echo service, console relay restrictions and development helpers."),
    ], [2.05, 1.85, 2.6])
    add_figure(doc, test_capture, "Figure 9.1: Extract of the actual local make check terminal output. It records passing component suites and coverage results.")
    add_heading(doc, "9.3 Live Attack/Defense POC", 1)
    add_para(doc, "The local console was seeded with fresh development-only data and used its constrained /__aegis_probe relay against the running loopback proxy. The relay permits only GET/POST probes to the local /api/echo endpoint. Consumer 1 has echo:read and Consumer 2 has echo:read plus echo:write. This makes the scope result meaningful rather than merely testing an error status.")
    add_figure(doc, poc_capture, "Figure 9.2: Actual local POC console relay evidence. The output confirms forwarding, scope denial, credential failures, rate limiting and per-consumer isolation.")
    add_table(doc, ["Scenario", "Expected/observed HTTP result", "Evidence of behaviour"], [
        ("Consumer 1 read", "200 / forwarded", "Valid key, JWT and echo:read scope reach upstream."),
        ("Consumer 1 write", "403 / INSUFFICIENT_SCOPE", "Exact POST route policy blocks an absent echo:write scope."),
        ("Consumer 2 write", "200 / forwarded", "Consumer 2 contains the required scope."),
        ("Revoked/missing/malformed key", "403 / 401 / 401", "The proxy rejects credentials before forwarding."),
        ("Five-request flood", "200, 200, 200, 429, 429", "Consumer 1’s 3 requests/10 seconds Redis rule is enforced."),
        ("Cross-consumer check", "200 / forwarded", "Consumer 2 is not charged against Consumer 1’s key-scoped counter."),
    ], [1.65, 2.1, 2.75])
    add_heading(doc, "9.4 End-to-end Verification", 1)
    if e2e_capture and e2e_capture.exists():
        add_para(doc, "The isolated Docker Compose end-to-end script was also run. It creates fresh ports, volumes and credentials, exercises Control Plane policy setup, gRPC policy propagation, proxy-to-upstream forwarding, manual and automatic IP blocks, threat detection, Redis limits and analytics, then removes its disposable stack.")
        add_figure(doc, e2e_capture, "Figure 9.3: Actual isolated end-to-end test output from scripts/e2e.sh.")
    else:
        add_para(doc, "The repository includes an isolated Docker Compose end-to-end script covering policy setup, gRPC propagation, proxy forwarding, blocks, threat detection, Redis limits and analytics. Its result is not asserted in this chapter until the script’s current run has completed; this protects the report from presenting an unverified integration claim as evidence.")
    add_heading(doc, "9.5 Findings and Defect Handling", 1)
    add_para(doc, "During the first live POC attempt, a pre-existing manual development block for 127.0.0.1 caused every scenario to return IP_BLOCKED. The record was verified through the local Control Plane, then soft-disabled as a development-only setup correction before the final evidence run. This was a useful integration finding: IP blocking correctly occurs before any credentials or scope check. It is recorded here rather than hidden because test environment state affects security evidence.")
    add_heading(doc, "9.6 Test Limitations", 1)
    add_para(doc, "The evidence demonstrates functional enforcement and cross-component behaviour, not a production load benchmark or independent penetration test. Future testing should add measured latency/throughput under controlled hardware, browser accessibility audits, trusted-load-balancer address handling, fuzzing of policy payloads and external security review. The automated coverage values are guardrails, not proof that every security issue has been eliminated.")
    add_references(doc, REFS_CORE)
    return doc


def chapter_10():
    doc = setup_doc(10, "Evaluation and Reflection")
    add_heading(doc, "10.1 Evaluation Against the Aim", 1)
    add_para(doc, "The proposal aimed to produce a production-ready API security and management system that provides central protection through request validation, rate limiting and threat detection while demonstrating Python/FastAPI, Go and React skills. The verified implementation meets the central architectural aim: policy is managed in FastAPI/PostgreSQL and enforced at a Go proxy before the upstream service. The local POC provides direct evidence that allowed traffic is forwarded and denied traffic is stopped at the proxy.")
    add_heading(doc, "10.2 Evaluation Against Objectives", 1)
    add_table(doc, ["Objective", "Evaluation"], [
        ("Research and technology justification", "Completed through product research and literature traceability; mature gateway products informed the focused Aegis niche."),
        ("Define requirements and roles", "Completed through MoSCoW scope, persisted Admin/Viewer/API Consumer roles and protected APIs."),
        ("Design system/data/workflows", "Completed with verified architecture, domain and enforcement-sequence diagrams in Chapter 7."),
        ("Implement full stack", "Completed across FastAPI, Go, React, PostgreSQL, Redis, gRPC and Docker Compose."),
        ("Test functionality/security", "Supported by passing component suites and live POC evidence for scope, revoked/missing keys and rate limit behaviour."),
        ("Evaluate against alternatives", "Aegis is narrower than gateway products but more transparent as a custom learning/security implementation."),
    ], [2.4, 4.1])
    add_heading(doc, "10.3 Strengths", 1)
    add_bullets(doc, [
        "Clear separation between policy definition and request enforcement, avoiding a per-request database lookup for common policy decisions.",
        "Defence-in-depth request order: IP block, threat rule, API key, JWT, route scope, rate limit and then forwarding.",
        "Explicit exact route permissions make API-key scopes meaningful without fragile URL-name inference.",
        "Redis-backed atomic rate limiting supports more than one proxy process and exposes standard response headers.",
        "Privacy-aware analytics event shape avoids raw credentials, body content and arbitrary request headers.",
        "A disposable POC lets the project demonstrate a real upstream rather than a mocked forwarding result.",
    ])
    add_heading(doc, "10.4 Limitations", 1)
    add_bullets(doc, [
        "Threat detection is limited to regex matching of method and request URI; it is not payload inspection or a full WAF.",
        "Route permissions use exact method/path matching; wildcard, parameterised and policy-combination semantics are not yet implemented.",
        "IP blocks are exact direct-peer addresses; trusted proxy chains and CIDR policies are intentionally deferred to avoid unsafe assumptions.",
        "The report’s test evidence is functional and integration-focused rather than a statistically rigorous performance benchmark.",
        "JWT verification material for an HS256 configuration must reach the proxy through the protected policy channel; production secret rotation and transport hardening warrant deeper operational review.",
    ])
    add_heading(doc, "10.5 Reflection on Development", 1)
    add_para(doc, "The project required learning across three different programming environments. Python/FastAPI made the Control Plane expressive through schemas, dependency injection and async database access. Go exposed the practical concerns of HTTP forwarding, context timeouts, concurrency safety and policy caching. React made role-specific workflows visible, but also demonstrated why the UI must not be treated as the final authority for access control.")
    add_para(doc, "A key learning point was the difference between authentication and authorisation. An API-key scope such as echo:read has no effect unless the system defines the exact request that requires it. The later RoutePermission addition made that relationship explicit and testable. Another learning point was the impact of test environment state: a stale loopback IP block correctly prevented the first POC run, proving that security controls can change the meaning of a test unless environment conditions are recorded.")
    add_heading(doc, "10.6 Future Enhancement", 1)
    add_bullets(doc, [
        "Add reviewed wildcard/parameter route policy semantics and deny-by-default rollout options.",
        "Add trusted-load-balancer configuration before considering forwarded address headers.",
        "Add benchmark scripts with documented hardware, latency percentiles and multi-proxy load profiles.",
        "Add richer dashboard accessibility testing, user feedback and operational documentation.",
        "Introduce key rotation workflows, policy version/audit history and alert integrations for production operation.",
        "Assess body-aware protections only with a clear privacy, performance and false-positive model.",
    ])
    add_heading(doc, "10.7 Final Conclusion", 1)
    add_para(doc, "Aegis demonstrates that a small custom reverse-proxy system can centralise meaningful API controls while remaining explainable. Its main contribution is not breadth comparable to a commercial gateway; it is a coherent, verified learning implementation in which every security decision can be traced from a policy record to an enforcement step and test result. The project provides a sound foundation for further hardening and measured production evaluation.")
    add_references(doc, REFS_CORE)
    return doc


def save(doc, name):
    path = REPORT / name
    doc.save(path)
    print(path)


def main():
    architecture = generate_architecture()
    domain = generate_domain()
    sequence = generate_sequence()
    test_capture = terminal_capture(EVIDENCE / "make-check-terminal.txt", EVIDENCE / "figure_9_1_make_check.png", "make check — observed local results", ["passed", "TOTAL", "Reverse proxy core coverage", "tests 6", "pass 6", "13 passed"])
    poc_capture = terminal_capture(EVIDENCE / "poc-console-live-terminal.txt", EVIDENCE / "figure_9_2_poc_console.png", "Attack / Defense Console — observed live relay", None)
    e2e_log = EVIDENCE / "e2e-terminal.txt"
    e2e_capture = None
    if e2e_log.exists() and "E2E passed:" in e2e_log.read_text(errors="replace"):
        e2e_capture = terminal_capture(e2e_log, EVIDENCE / "figure_9_3_e2e.png", "Isolated E2E — observed local results", ["E2E passed:"])
    save(chapter_1(), "Aegis_Report_Ch1.docx")
    save(chapter_2(), "Aegis_Report_Ch2.docx")
    save(chapter_3(), "Aegis_Report_Ch3.docx")
    save(chapter_4(), "Aegis_Report_Ch4.docx")
    save(chapter_5(), "Aegis_Report_Ch5.docx")
    save(chapter_6(), "Aegis_Report_Ch6.docx")
    save(chapter_7(architecture, domain, sequence), "Aegis_Report_Ch7.docx")
    save(chapter_8(), "Aegis_Report_Ch8.docx")
    save(chapter_9(test_capture, poc_capture, e2e_capture), "Aegis_Report_Ch9.docx")
    save(chapter_10(), "Aegis_Report_Ch10.docx")


if __name__ == "__main__":
    main()
