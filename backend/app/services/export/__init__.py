"""Report exports: Excel (gradebook / ведомость / analysis), PDF report with charts, Word report."""
import io
from datetime import date

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.services.analytics import ERROR_LABELS, LEVEL_LABELS
from app.services.templates import register_fonts

TYPE_LABELS = {"BZhB": "БЖБ", "TZhB": "ТЖБ", "AB": "АБ"}
MARK_LABELS = {5: "Өте жақсы", 4: "Жақсы", 3: "Қанағаттанарлық", 2: "Қанағаттанарлықсыз"}
HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="C9D2DC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _header(ws, row: int, values: list) -> None:
    for i, v in enumerate(values, 1):
        c = ws.cell(row=row, column=i, value=v)
        c.fill, c.font, c.border = HEADER_FILL, HEADER_FONT, BORDER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _title(ws, text: str, meta: str, width: int) -> None:
    ws.cell(row=1, column=1, value=text).font = Font(bold=True, size=14)
    ws.cell(row=2, column=1, value=meta).font = Font(color="5B6B7C")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(2, width))


def _autowidth(ws, widths: dict[int, int]) -> None:
    for col, w in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = w


def excel_report(data: dict, school: str, teacher: str, kind: str = "full") -> bytes:
    a = data["assessment"]
    meta = (f"{school} · {a['subject']} · {a['class_name']} · {TYPE_LABELS.get(a['type'], a['type'])} · "
            f"{a['date'] or ''} · Мұғалім: {teacher}")
    wb = Workbook()
    qnums = data["heatmap"]["questions"]
    qmax = {q["number"]: q["max_score"] for q in data["questions"]}

    # 1. Gradebook: № | Оқушы | 1..n | Барлығы | %
    ws = wb.active
    ws.title = "Нәтижелер"
    _title(ws, a["title"], meta, len(qnums) + 5)
    _header(ws, 4, ["№", "Оқушы", *[str(n) for n in qnums], "Барлығы", "%"])
    _header(ws, 5, ["", "Макс.", *[qmax[n] for n in qnums], a["max_score"], 100])
    for i, s in enumerate(data["students"], 1):
        row = [i, s["name"], *[s["scores"].get(n) for n in qnums], s["total"], s["percent"]]
        for j, v in enumerate(row, 1):
            c = ws.cell(row=5 + i, column=j, value=v)
            c.border = BORDER
            if j > 2:
                c.alignment = Alignment(horizontal="center")
    last = 5 + len(data["students"])
    if data["students"]:
        pct_col = get_column_letter(len(qnums) + 4)
        ws.conditional_formatting.add(f"{pct_col}6:{pct_col}{last}", ColorScaleRule(
            start_type="num", start_value=0, start_color="F8696B", mid_type="num", mid_value=60, mid_color="FFEB84",
            end_type="num", end_value=100, end_color="63BE7B"))
        avg_row = last + 1
        ws.cell(row=avg_row, column=2, value="Орташа").font = Font(bold=True)
        for j in range(3, len(qnums) + 5):
            col = get_column_letter(j)
            ws.cell(row=avg_row, column=j, value=f"=ROUND(AVERAGE({col}6:{col}{last}),1)").font = Font(bold=True)
    ws.freeze_panes = "C6"
    _autowidth(ws, {1: 5, 2: 30, **{i: 7 for i in range(3, len(qnums) + 3)}, len(qnums) + 3: 10, len(qnums) + 4: 8})
    if kind == "gradebook":
        return _save(wb)

    # 2. Ведомость
    ws = wb.create_sheet("Ведомость")
    _title(ws, f"{TYPE_LABELS.get(a['type'], a['type'])} ведомосы — {a['title']}", meta, 7)
    _header(ws, 4, ["№", "Оқушы", "Балл", "Макс.", "%", "Деңгей", "Баға"])
    for i, s in enumerate(data["students"], 1):
        for j, v in enumerate([i, s["name"], s["total"], s["max"], s["percent"], LEVEL_LABELS.get(s["level"], s["level"]),
                               f"{s['mark']} ({MARK_LABELS[s['mark']]})"], 1):
            ws.cell(row=4 + i, column=j, value=v).border = BORDER
    r = 6 + len(data["students"])
    sm = data["summary"]
    for label, val in [("Оқушы саны", sm["students_total"]), ("Жазғандар", sm["submitted"]),
                       ("Орташа балл", sm["avg_score"]), ("Орташа %", sm["avg_percent"]),
                       ("Үлгерім, %", sm["success_rate"]), ("Білім сапасы, %", sm["quality_rate"]),
                       *[(f"«{m}» саны", sm["marks"][str(m)]) for m in (5, 4, 3, 2)]]:
        ws.cell(row=r, column=2, value=label).font = Font(bold=True)
        ws.cell(row=r, column=3, value=val)
        r += 1
    _autowidth(ws, {1: 5, 2: 30, 3: 10, 4: 8, 5: 8, 6: 14, 7: 24})

    # 3. Analysis (task / descriptor / objective / errors)
    ws = wb.create_sheet(f"{TYPE_LABELS.get(a['type'], a['type'])} талдауы")
    _title(ws, f"{TYPE_LABELS.get(a['type'], a['type'])} талдауы", meta, 6)
    _header(ws, 4, ["Тапсырма", "Макс.", "Орташа балл", "%", "Толық дұрыс", "Оқу мақсаты"])
    for i, q in enumerate(data["questions"], 5):
        for j, v in enumerate([q["number"], q["max_score"], q["avg_score"], q["percent"], q["correct"], q["objective"]], 1):
            ws.cell(row=i, column=j, value=v).border = BORDER
    end = 4 + len(data["questions"])
    if data["questions"]:
        ch = BarChart()
        ch.title, ch.y_axis.title = "Тапсырма бойынша орындалу, %", "%"
        ch.add_data(Reference(ws, min_col=4, min_row=4, max_row=end), titles_from_data=True)
        ch.set_categories(Reference(ws, min_col=1, min_row=5, max_row=end))
        ch.height, ch.width = 7, 16
        ws.add_chart(ch, "H4")
    r = end + 2
    _header(ws, r, ["Дескриптор", "Мәтін", "%"])
    for d in data["descriptors"]:
        r += 1
        for j, v in enumerate([d["label"], d["text"], d["percent"]], 1):
            ws.cell(row=r, column=j, value=v).border = BORDER
    r += 2
    _header(ws, r, ["Оқу мақсаты", "Сипаттамасы", "%"])
    for o in data["objectives"]:
        r += 1
        for j, v in enumerate([o["code"], o["description"], o["percent"]], 1):
            ws.cell(row=r, column=j, value=v).border = BORDER
    r += 2
    _header(ws, r, ["Қате түрі", "Саны"])
    for e in data["errors"]:
        r += 1
        ws.cell(row=r, column=1, value=e["label"]).border = BORDER
        ws.cell(row=r, column=2, value=e["count"]).border = BORDER
    r += 2
    ws.cell(row=r, column=1, value="Қорытынды").font = Font(bold=True)
    for line in data["insights"]:
        r += 1
        ws.cell(row=r, column=1, value="• " + line)
    _autowidth(ws, {1: 14, 2: 50, 3: 12, 4: 8, 5: 12, 6: 14})

    # 4. Class journal (marks only)
    ws = wb.create_sheet("Сынып журналы")
    _title(ws, f"Сынып журналы — {a['class_name']}", meta, 3)
    _header(ws, 4, ["№", "Оқушы", f"{TYPE_LABELS.get(a['type'], a['type'])} ({a['date'] or ''})"])
    for i, s in enumerate(data["students"], 1):
        ws.cell(row=4 + i, column=1, value=i)
        ws.cell(row=4 + i, column=2, value=s["name"])
        ws.cell(row=4 + i, column=3, value=f"{s['total']:g}/{s['max']:g}")
    _autowidth(ws, {1: 5, 2: 30, 3: 18})
    return _save(wb)


def _save(wb: Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------- PDF ----------------
def pdf_report(data: dict, school: str, teacher: str) -> bytes:
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    register_fonts()
    a, sm = data["assessment"], data["summary"]
    base = ParagraphStyle("b", fontName="Sans", fontSize=9.5, leading=13)
    h1 = ParagraphStyle("h1", parent=base, fontName="Sans-Bold", fontSize=16, leading=20, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=base, fontName="Sans-Bold", fontSize=12, leading=16, spaceBefore=10, spaceAfter=4)
    muted = ParagraphStyle("m", parent=base, textColor=colors.HexColor("#5B6B7C"))
    primary = colors.HexColor("#1F3A5F")

    hdr = ParagraphStyle("hdr", parent=base, fontName="Sans-Bold", fontSize=7.5, leading=9.5,
                         textColor=colors.white, alignment=1)

    def table(rows, widths, zebra=True):
        # header cells wrap instead of overflowing narrow columns
        rows = [[Paragraph(str(c), hdr) if isinstance(c, str) else c for c in rows[0]], *rows[1:]]
        t = Table(rows, colWidths=widths, repeatRows=1)
        st = [("FONT", (0, 0), (-1, -1), "Sans", 8.5), ("FONT", (0, 0), (-1, 0), "Sans-Bold", 8.5),
              ("LEFTPADDING", (0, 0), (-1, 0), 2), ("RIGHTPADDING", (0, 0), (-1, 0), 2),
              ("BACKGROUND", (0, 0), (-1, 0), primary), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D2DC")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("ALIGN", (2, 0), (-1, -1), "CENTER")]
        if zebra:
            st += [("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F9")])]
        t.setStyle(TableStyle(st))
        return t

    def bar(values, labels, title, w=170 * mm, h=60 * mm):
        d = Drawing(w, h)
        c = VerticalBarChart()
        c.x, c.y, c.width, c.height = 30, 25, w - 45, h - 45
        c.data = [values or [0]]
        c.categoryAxis.categoryNames = labels or [""]
        c.categoryAxis.labels.fontName = c.valueAxis.labels.fontName = "Sans"
        c.categoryAxis.labels.fontSize = c.valueAxis.labels.fontSize = 7
        c.valueAxis.valueMin, c.valueAxis.valueMax, c.valueAxis.valueStep = 0, 100, 20
        c.bars[0].fillColor = colors.HexColor("#2F6FDE")
        c.barWidth = 6
        d.add(c)
        d.add(String(w / 2, h - 10, title, fontName="Sans-Bold", fontSize=9, textAnchor="middle"))
        return d

    story = [Paragraph(a["title"], h1),
             Paragraph(f"{school} · {a['subject']} · {a['class_name']} сынып · "
                       f"{TYPE_LABELS.get(a['type'], a['type'])} · {a['date'] or date.today().isoformat()}", muted),
             Paragraph(f"Мұғалім: {teacher}", muted), Spacer(1, 8)]
    kpi = [["Оқушы саны", "Жазғандар", "Орташа балл", "Орташа %", "Жоғары", "Төмен", "Үлгерім", "Сапа"],
           [sm["students_total"], sm["submitted"], f"{sm['avg_score']}/{a['max_score']:g}", f"{sm['avg_percent']}%",
            f"{sm['max_percent']}%", f"{sm['min_percent']}%", f"{sm['success_rate']}%", f"{sm['quality_rate']}%"]]
    story.append(table(kpi, [21 * mm] * 8, zebra=False))
    story.append(Paragraph("Қорытынды", h2))
    for line in data["insights"] or ["Деректер жеткіліксіз."]:
        story.append(Paragraph("• " + line, base))
    if data.get("main_problem"):
        story.append(Paragraph(f"<b>Негізгі проблема:</b> {data['main_problem']}", base))

    story.append(Paragraph("Тапсырмалар бойынша талдау", h2))
    story.append(bar([q["percent"] for q in data["questions"]], [str(q["number"]) for q in data["questions"]],
                     "Тапсырманың орындалуы, %"))
    story.append(table([["№", "Макс.", "Орташа", "%", "Толық дұрыс", "Оқу мақсаты"]] +
                       [[q["number"], f"{q['max_score']:g}", q["avg_score"], f"{q['percent']}%", q["correct"],
                         q["objective"] or "—"] for q in data["questions"]],
                       [15 * mm, 18 * mm, 22 * mm, 20 * mm, 25 * mm, 40 * mm]))
    if data["descriptors"]:
        story.append(Paragraph("Дескрипторлар бойынша талдау", h2))
        story.append(table([["Дескриптор", "Мәтін", "%"]] +
                           [[d["label"], Paragraph(d["text"], base), f"{d['percent']}%"] for d in data["descriptors"]],
                           [24 * mm, 120 * mm, 20 * mm]))
    if data["objectives"]:
        story.append(Paragraph("Оқу мақсаттары бойынша", h2))
        story.append(table([["Код", "Оқу мақсаты", "%"]] +
                           [[o["code"], Paragraph(o["description"], base), f"{o['percent']}%"] for o in data["objectives"]],
                           [24 * mm, 120 * mm, 20 * mm]))
    if data["errors"]:
        story.append(Paragraph("Қателер категориялары", h2))
        d = Drawing(170 * mm, 55 * mm)
        pie = Pie()
        pie.x, pie.y, pie.width, pie.height = 10, 5, 45 * mm, 45 * mm
        pie.data = [e["count"] for e in data["errors"]]
        pie.labels = [f"{e['label']} ({e['count']})" for e in data["errors"]]
        pie.simpleLabels = 0
        pie.slices.fontName = "Sans"
        pie.slices.fontSize = 7
        palette = ["#2F6FDE", "#F2994A", "#27AE60", "#EB5757", "#9B51E0", "#56CCF2", "#F2C94C", "#828282"]
        for i in range(len(pie.data)):
            pie.slices[i].fillColor = colors.HexColor(palette[i % len(palette)])
        d.add(pie)
        story.append(d)

    story += [PageBreak(), Paragraph("Оқушылар нәтижелері", h2)]
    qn = data["heatmap"]["questions"]
    rows = [["№", "Оқушы", *[str(n) for n in qn], "Балл", "%", "Баға"]]
    for i, s in enumerate(data["students"], 1):
        rows.append([i, s["name"], *[f"{s['scores'].get(n, 0):g}" for n in qn], f"{s['total']:g}", f"{s['percent']}%",
                     s["mark"]])
    qw = max(6 * mm, min(10 * mm, (100 * mm) / max(1, len(qn))))
    story.append(table(rows, [8 * mm, 45 * mm, *[qw] * len(qn), 13 * mm, 14 * mm, 11 * mm]))
    story.append(Spacer(1, 10))
    story.append(bar([h["count"] * 100 / max(1, sm["submitted"]) for h in data["histogram"]],
                     [h["range"] for h in data["histogram"]], "Нәтижелердің таралуы (оқушылар үлесі, %)"))

    buf = io.BytesIO()

    def footer(c, doc):
        c.setFont("Sans", 7)
        c.setFillColor(colors.HexColor("#8795A1"))
        c.drawString(15 * mm, 10 * mm, f"Planit · {a['title']}")
        c.drawRightString(195 * mm, 10 * mm, f"{doc.page}-бет")

    SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                      bottomMargin=16 * mm, title=a["title"], author="Planit").build(story, onFirstPage=footer,
                                                                                         onLaterPages=footer)
    return buf.getvalue()


def docx_report(data: dict, school: str, teacher: str) -> bytes:
    from docx import Document
    from docx.shared import Pt

    a, sm = data["assessment"], data["summary"]
    doc = Document()
    doc.styles["Normal"].font.name = "Arial"
    doc.styles["Normal"].font.size = Pt(10)
    doc.add_heading(a["title"], 0)
    doc.add_paragraph(f"{school} · {a['subject']} · {a['class_name']} · {TYPE_LABELS.get(a['type'], a['type'])} · "
                      f"{a['date'] or ''}\nМұғалім: {teacher}")
    doc.add_heading("Жалпы көрсеткіштер", 1)
    t = doc.add_table(rows=1, cols=2)
    t.style = "Light Grid Accent 1"
    t.rows[0].cells[0].text, t.rows[0].cells[1].text = "Көрсеткіш", "Мәні"
    for k, v in [("Оқушы саны", sm["students_total"]), ("Жазғандар", sm["submitted"]),
                 ("Орташа балл", f"{sm['avg_score']}/{a['max_score']:g}"), ("Орташа нәтиже", f"{sm['avg_percent']}%"),
                 ("Жоғары нәтиже", f"{sm['max_percent']}%"), ("Төмен нәтиже", f"{sm['min_percent']}%"),
                 ("Үлгерім", f"{sm['success_rate']}%"), ("Білім сапасы", f"{sm['quality_rate']}%")]:
        r = t.add_row().cells
        r[0].text, r[1].text = k, str(v)
    doc.add_heading("Қорытынды", 1)
    for line in data["insights"]:
        doc.add_paragraph(line, style="List Bullet")
    doc.add_heading("Тапсырмалар", 1)
    t = doc.add_table(rows=1, cols=4)
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(["№", "Макс.", "Орташа", "%"]):
        t.rows[0].cells[i].text = h
    for q in data["questions"]:
        r = t.add_row().cells
        r[0].text, r[1].text, r[2].text, r[3].text = str(q["number"]), f"{q['max_score']:g}", str(q["avg_score"]), f"{q['percent']}%"
    doc.add_heading("Оқушылар", 1)
    t = doc.add_table(rows=1, cols=4)
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(["Оқушы", "Балл", "%", "Деңгей"]):
        t.rows[0].cells[i].text = h
    for s in data["students"]:
        r = t.add_row().cells
        r[0].text, r[1].text, r[2].text, r[3].text = s["name"], f"{s['total']:g}/{s['max']:g}", f"{s['percent']}%", \
            LEVEL_LABELS.get(s["level"], s["level"])
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


__all__ = ["excel_report", "pdf_report", "docx_report", "ERROR_LABELS"]
