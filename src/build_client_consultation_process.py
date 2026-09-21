"""Build the revised Client Consultation Process PDF."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "client_consultation_and_data_workflow.pdf"

PAGE_W, PAGE_H = landscape(A4)
NAVY = colors.HexColor("#123B52")
TEAL = colors.HexColor("#16847A")
GOLD = colors.HexColor("#D69B31")
RED = colors.HexColor("#BA4A45")
INK = colors.HexColor("#17212B")
MUTED = colors.HexColor("#62717F")
PAPER = colors.HexColor("#F4F1EA")
CARD = colors.HexColor("#FFFEFA")
LINE = colors.HexColor("#DCD8CE")
PALE_TEAL = colors.HexColor("#E6F2EF")
PALE_GOLD = colors.HexColor("#F8EFD9")
PALE_BLUE = colors.HexColor("#E8EFF3")


def wrapped_lines(text: str, font: str, size: float, max_width: float) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_text(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    *,
    font: str = "Helvetica",
    size: float = 9,
    leading: float | None = None,
    color=INK,
    align: str = "left",
) -> float:
    leading = leading or size * 1.3
    c.setFont(font, size)
    c.setFillColor(color)
    lines = wrapped_lines(text, font, size, width)
    cursor = y
    for line in lines:
        if align == "center":
            tx = x + (width - stringWidth(line, font, size)) / 2
        elif align == "right":
            tx = x + width - stringWidth(line, font, size)
        else:
            tx = x
        c.drawString(tx, cursor, line)
        cursor -= leading
    return cursor


def footer(c: canvas.Canvas, page_number: int, section: str) -> None:
    c.setStrokeColor(LINE)
    c.line(34, 25, PAGE_W - 34, 25)
    c.setFont("Helvetica", 7.5)
    c.setFillColor(MUTED)
    c.drawString(34, 13, "Nubia Aparecida Silva Almeida | Operacao LegalTech")
    c.drawCentredString(PAGE_W / 2, 13, section)
    c.drawRightString(PAGE_W - 34, 13, str(page_number))


def page_header(c: canvas.Canvas, kicker: str, title: str, page_number: int) -> None:
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 84, PAGE_W, 84, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(34, PAGE_H - 26, kicker.upper())
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(34, PAGE_H - 59, title)
    c.setFont("Helvetica", 8)
    c.drawRightString(PAGE_W - 34, PAGE_H - 28, f"PAGE {page_number} OF 3")


def round_box(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    *,
    fill=CARD,
    stroke=LINE,
    font="Helvetica-Bold",
    size=8,
    text_color=INK,
) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, 7, fill=1, stroke=1)
    lines = wrapped_lines(text, font, size, w - 14)
    total = len(lines) * size * 1.25
    ty = y + (h + total) / 2 - size
    c.setFillColor(text_color)
    c.setFont(font, size)
    for line in lines:
        c.drawCentredString(x + w / 2, ty, line)
        ty -= size * 1.25


def arrow(c: canvas.Canvas, x1: float, y1: float, x2: float, y2: float, color=TEAL) -> None:
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(1.6)
    c.line(x1, y1, x2, y2)
    import math

    angle = math.atan2(y2 - y1, x2 - x1)
    length = 7
    spread = 0.48
    points = [
        (x2, y2),
        (x2 - length * math.cos(angle - spread), y2 - length * math.sin(angle - spread)),
        (x2 - length * math.cos(angle + spread), y2 - length * math.sin(angle + spread)),
    ]
    path = c.beginPath()
    path.moveTo(*points[0])
    path.lineTo(*points[1])
    path.lineTo(*points[2])
    path.close()
    c.drawPath(path, fill=1, stroke=0)


def label(c: canvas.Canvas, text: str, x: float, y: float, color=MUTED) -> None:
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(color)
    c.drawCentredString(x, y, text.upper())


def cover_page(c: canvas.Canvas) -> None:
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.rect(0, 0, 285, PAGE_H, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(34, PAGE_H - 75, 68, 5, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(34, PAGE_H - 102, "OPERACAO LEGALTECH")
    draw_text(
        c,
        "Client Consultation and Data Workflow",
        34,
        PAGE_H - 150,
        215,
        font="Helvetica-Bold",
        size=26,
        leading=30,
        color=colors.white,
    )
    draw_text(
        c,
        "A process and information-flow overview for a fictional legal services company.",
        34,
        PAGE_H - 260,
        210,
        size=10.5,
        leading=15,
        color=colors.HexColor("#D7E7E4"),
    )
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(34, 102, "PREPARED BY")
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(34, 81, "Nubia Aparecida Silva Almeida")
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#D7E7E4"))
    c.drawString(34, 62, "Educational data analytics project | 2026")

    x = 325
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, PAGE_H - 68, "FICTIONAL COMPANY PROFILE")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 21)
    c.drawString(x, PAGE_H - 98, "About the legal company")
    draw_text(
        c,
        "Operacao LegalTech represents a fictional, growing law firm that provides advisory and litigation services. Clients usually make first contact through WhatsApp, while assistants coordinate triage, lawyers conduct consultations and legal work, and finance staff manage invoices and payments. The firm uses synthetic educational records so its operational and financial processes can be analyzed without exposing real client information.",
        x,
        PAGE_H - 128,
        450,
        size=10.2,
        leading=15,
    )

    cards = [
        ("01", "Client journey", "From initial contact and triage to consultation, matter delivery, and closure."),
        ("02", "Decision points", "Working hours, clarity of need, consultation, acceptance, and litigation."),
        ("03", "Data lifecycle", "From operational records and CSV files to governed analytics and dashboards."),
    ]
    cy = 280
    for number, title, body in cards:
        c.setFillColor(CARD)
        c.setStrokeColor(LINE)
        c.roundRect(x, cy, 450, 65, 8, fill=1, stroke=1)
        c.setFillColor(GOLD)
        c.circle(x + 32, cy + 32.5, 18, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(x + 32, cy + 29.5, number)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x + 62, cy + 40, title)
        draw_text(c, body, x + 62, cy + 23, 370, size=8.5, leading=11, color=MUTED)
        cy -= 78

    c.setFillColor(PALE_GOLD)
    c.setStrokeColor(GOLD)
    c.roundRect(x, 39, 450, 38, 6, fill=1, stroke=1)
    draw_text(
        c,
        "Scope note: All names, records, amounts, and scenarios in the project are fictional or synthetic and are used for education and portfolio demonstration.",
        x + 12,
        61,
        426,
        size=7.8,
        leading=10,
        color=INK,
    )
    footer(c, 1, "Document overview")
    c.showPage()


def consultation_page(c: canvas.Canvas) -> None:
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    page_header(c, "Operational process", "Client consultation workflow", 2)

    margin = 32
    gap = 10
    lane_w = (PAGE_W - margin * 2 - gap * 3) / 4
    lane_x = [margin + i * (lane_w + gap) for i in range(4)]
    lane_titles = [
        ("1", "Contact and triage", PALE_BLUE),
        ("2", "Clarify and consult", PALE_TEAL),
        ("3", "Onboard the matter", PALE_GOLD),
        ("4", "Deliver and close", colors.HexColor("#F3E8E7")),
    ]
    lane_bottom = 46
    lane_top = PAGE_H - 101
    for i, (num, title, fill) in enumerate(lane_titles):
        x = lane_x[i]
        c.setFillColor(fill)
        c.setStrokeColor(LINE)
        c.roundRect(x, lane_bottom, lane_w, lane_top - lane_bottom, 8, fill=1, stroke=1)
        c.setFillColor(NAVY)
        c.circle(x + 19, lane_top - 20, 11, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x + 19, lane_top - 23, num)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 37, lane_top - 24, title)

    bw = lane_w - 28
    bx = [x + 14 for x in lane_x]
    bh = 34

    y0 = 410
    steps0 = [
        "Client sends a WhatsApp message",
        "Automated menu: new service, status, or consultation",
        "Check whether the office is open",
        "Assistant responds and identifies the service need",
    ]
    ys0 = [y0, 350, 287, 215]
    for text, y in zip(steps0, ys0):
        round_box(c, bx[0], y, bw, bh if y != 350 else 43, text, fill=CARD, stroke=NAVY)
    arrow(c, bx[0] + bw / 2, y0, bx[0] + bw / 2, 393)
    arrow(c, bx[0] + bw / 2, 350, bx[0] + bw / 2, 321)
    draw_text(
        c,
        "Mon-Fri 09:00-18:00. Closed: auto-reply; human response by 10:00 next working day.",
        bx[0] + 4,
        277,
        bw - 8,
        font="Helvetica-Bold",
        size=6.1,
        leading=7.5,
        color=MUTED,
        align="center",
    )
    arrow(c, bx[0] + bw / 2, 287, bx[0] + bw / 2, 249)

    round_box(c, bx[1], 410, bw, 38, "Is the client's situation clear?", fill=CARD, stroke=TEAL)
    round_box(c, bx[1], 342, bw, 38, "Collect details and answer questions", fill=CARD, stroke=TEAL)
    arrow(c, bx[1] + bw / 2, 410, bx[1] + bw / 2, 380)
    label(c, "No - clarify and reassess", bx[1] + bw / 2, 389)
    round_box(c, bx[1], 266, bw, 38, "Is a lawyer consultation needed?", fill=CARD, stroke=TEAL)
    arrow(c, bx[1] + bw / 2, 342, bx[1] + bw / 2, 304)
    label(c, "Yes / once clear", bx[1] + bw / 2, 313)
    round_box(c, bx[1], 190, bw, 43, "Schedule meeting and generate consultation fee", fill=CARD, stroke=TEAL)
    arrow(c, bx[1] + bw / 2, 266, bx[1] + bw / 2, 233)
    label(c, "Consultation required", bx[1] + bw / 2, 242)
    round_box(c, bx[1], 120, bw, 34, "Lawyer meeting and case review", fill=CARD, stroke=TEAL)
    arrow(c, bx[1] + bw / 2, 190, bx[1] + bw / 2, 154)
    round_box(c, bx[1], 61, bw, 34, "Case accepted by client and lawyer?", fill=CARD, stroke=TEAL)
    arrow(c, bx[1] + bw / 2, 120, bx[1] + bw / 2, 95)

    round_box(c, bx[2], 410, bw, 38, "Client decides to proceed", fill=CARD, stroke=GOLD)
    round_box(c, bx[2], 338, bw, 38, "Generate matter fees", fill=CARD, stroke=GOLD)
    round_box(c, bx[2], 266, bw, 38, "Sign contract and power of attorney", fill=CARD, stroke=GOLD)
    round_box(c, bx[2], 194, bw, 38, "Receive and check required documents", fill=CARD, stroke=GOLD)
    round_box(c, bx[2], 122, bw, 38, "Open the legal matter", fill=CARD, stroke=GOLD)
    for top, bottom in [(410, 376), (338, 304), (266, 232), (194, 160)]:
        arrow(c, bx[2] + bw / 2, top, bx[2] + bw / 2, bottom)
    label(c, "Accepted / proceed", bx[2] + bw / 2, 389)

    round_box(c, bx[3], 410, bw, 38, "Perform legal work and record updates", fill=CARD, stroke=RED)
    round_box(c, bx[3], 330, bw, 38, "Is litigation required?", fill=CARD, stroke=RED)
    arrow(c, bx[3] + bw / 2, 410, bx[3] + bw / 2, 368)
    round_box(c, bx[3], 250, bw, 38, "Litigation stage, when required", fill=CARD, stroke=RED)
    arrow(c, bx[3] + bw / 2, 330, bx[3] + bw / 2, 288)
    label(c, "Yes", bx[3] + bw / 2, 297)
    round_box(c, bx[3], 170, bw, 38, "Proceed to closure", fill=CARD, stroke=RED)
    arrow(c, bx[3] + bw / 2, 250, bx[3] + bw / 2, 208)
    label(c, "No also proceeds to closure", bx[3] + bw / 2, 218)
    round_box(c, bx[3], 90, bw, 38, "Close the matter", fill=NAVY, stroke=NAVY, text_color=colors.white)
    arrow(c, bx[3] + bw / 2, 170, bx[3] + bw / 2, 128)

    arrow(c, lane_x[0] + lane_w - 7, 232, lane_x[1] + 7, 429)
    arrow(c, lane_x[1] + lane_w - 7, 78, lane_x[2] + 7, 429)
    arrow(c, lane_x[2] + lane_w - 7, 141, lane_x[3] + 7, 429)

    c.setFillColor(colors.HexColor("#FFF7E8"))
    c.setStrokeColor(GOLD)
    c.roundRect(lane_x[1] + 10, 32, lane_w - 20, 22, 5, fill=1, stroke=1)
    c.setFillColor(INK)
    c.setFont("Helvetica", 6.6)
    c.drawCentredString(lane_x[1] + lane_w / 2, 40, "NO: close as consultation only")
    c.setFillColor(colors.HexColor("#FFF7E8"))
    c.roundRect(lane_x[2] + 10, 62, lane_w - 20, 35, 5, fill=1, stroke=1)
    draw_text(c, "NO: workflow ends or remains pending for follow-up", lane_x[2] + 18, 82, lane_w - 36, size=6.5, leading=8, align="center")

    footer(c, 2, "Client consultation workflow")
    c.showPage()


def data_page(c: canvas.Canvas) -> None:
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    page_header(c, "Information lifecycle", "How operational data becomes insight", 3)
    draw_text(
        c,
        "Every operational step creates a record. The project standardizes those records, validates them, connects related entities, and publishes decision-ready measures while preserving traceability.",
        34,
        PAGE_H - 109,
        PAGE_W - 68,
        size=9,
        leading=12,
        color=MUTED,
    )

    stages = [
        ("1", "Capture", "WhatsApp, email, spreadsheets, and synthetic CSV files", PALE_BLUE),
        ("2", "Prepare", "Clean names, dates, categories, IDs, and financial values", PALE_TEAL),
        ("3", "Stage", "Load raw text with batch IDs and preserve source traceability", PALE_GOLD),
        ("4", "Validate", "Check required fields, relationships, controlled values, and totals", colors.HexColor("#F3E8E7")),
        ("5", "Model", "Promote approved rows into linked core tables", PALE_BLUE),
        ("6", "Analyze", "Create analytics views and publish the static Plotly dashboard", PALE_TEAL),
    ]
    sx = 34
    sy = 352
    gap = 9
    sw = (PAGE_W - 68 - gap * 5) / 6
    sh = 112
    for i, (num, title, body, fill) in enumerate(stages):
        x = sx + i * (sw + gap)
        c.setFillColor(fill)
        c.setStrokeColor(LINE)
        c.roundRect(x, sy, sw, sh, 8, fill=1, stroke=1)
        c.setFillColor(NAVY)
        c.circle(x + 19, sy + sh - 19, 11, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x + 19, sy + sh - 22, num)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 36, sy + sh - 23, title)
        draw_text(c, body, x + 10, sy + sh - 48, sw - 20, size=7.6, leading=10, color=INK)
        if i < len(stages) - 1:
            arrow(c, x + sw + 1, sy + sh / 2, x + sw + gap - 1, sy + sh / 2, color=TEAL)

    blocks = [
        (34, 214, 238, 105, "OPERATIONAL ENTITIES", "Clients | Inquiries | Consultations | Matters\nDocuments | Invoices | Payments | Users", NAVY),
        (302, 214, 238, 105, "DATABASE LAYERS", "staging - controlled intake and issue logging\ncore - clean relational source of truth\nanalytics - KPI-ready views", TEAL),
        (570, 214, 238, 105, "PUBLISHED OUTPUTS", "Portfolio, service-demand, document, billing, payment, overdue-invoice, and consultation indicators", GOLD),
    ]
    for x, y, w, h, heading, body, accent in blocks:
        c.setFillColor(CARD)
        c.setStrokeColor(LINE)
        c.roundRect(x, y, w, h, 8, fill=1, stroke=1)
        c.setFillColor(accent)
        c.rect(x, y + h - 6, w, 6, fill=1, stroke=0)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x + 13, y + h - 29, heading)
        ty = y + h - 48
        for paragraph in body.split("\n"):
            ty = draw_text(c, paragraph, x + 13, ty, w - 26, size=8, leading=11, color=INK) - 3

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(34, 183, "Governance controls across the entire flow")
    controls = [
        ("Ownership", "Named responsibility for operational, technical, and reporting decisions."),
        ("Quality gates", "Critical errors stop promotion; warnings remain visible for review."),
        ("Privacy", "Synthetic public data only; credentials and real client information stay private."),
        ("Auditability", "Batch IDs, file hashes, validation results, and versioned migrations preserve history."),
    ]
    cw = (PAGE_W - 68 - 12 * 3) / 4
    for i, (title, body) in enumerate(controls):
        x = 34 + i * (cw + 12)
        c.setFillColor(CARD)
        c.setStrokeColor(LINE)
        c.roundRect(x, 64, cw, 98, 7, fill=1, stroke=1)
        c.setFillColor(TEAL)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 11, 140, title)
        draw_text(c, body, x + 11, 121, cw - 22, size=7.4, leading=10, color=MUTED)

    footer(c, 3, "Data workflow and governance")
    c.showPage()


def build() -> Path:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT), pagesize=landscape(A4))
    c.setTitle("Client Consultation and Data Workflow")
    c.setAuthor("Nubia Aparecida Silva Almeida")
    c.setSubject("Operacao LegalTech fictional company, consultation workflow, and data workflow")
    cover_page(c)
    consultation_page(c)
    data_page(c)
    c.save()
    return OUTPUT


if __name__ == "__main__":
    print(build())
