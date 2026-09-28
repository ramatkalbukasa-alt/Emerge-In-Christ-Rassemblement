"""Scoped tabular exports. XLSX uses the standard library (no new dependency)."""
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

from django.http import HttpResponse


def column_name(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def xlsx_bytes(title, headers, rows, subtitle):
    def text(value):
        return escape("".join(c for c in str(value) if ord(c) >= 32 or c in "\t\n\r"))
    xml_rows = []
    for number, row in enumerate([[title], [subtitle], headers, *rows], 1):
        cells = []
        for col, value in enumerate(row, 1):
            address = f"{column_name(col)}{number}"
            if isinstance(value, (date, datetime)):
                value = (value.date() if isinstance(value, datetime) else value) - date(1899, 12, 30)
                cells.append(f'<c r="{address}" s="2"><v>{value.days}</v></c>')
            elif isinstance(value, (int, float, Decimal)):
                cells.append(f'<c r="{address}" s="{0 if isinstance(value, int) else 3}"><v>{value}</v></c>')
            else:
                # inlineStr cannot execute formulas, even for names beginning with '='.
                cells.append(f'<c r="{address}" t="inlineStr" s="{1 if number == 3 else 0}"><is><t xml:space="preserve">{text(value or "")}</t></is></c>')
        xml_rows.append(f'<row r="{number}">{"".join(cells)}</row>')
    width = len(headers)
    sheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetViews><sheetView workbookViewId="0"><pane ySplit="3" topLeftCell="A4" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
<cols><col min="1" max="{width}" width="24" customWidth="1"/></cols>
<sheetData>{''.join(xml_rows)}</sheetData><autoFilter ref="A3:{column_name(width)}{max(3, len(xml_rows))}"/>
<pageSetup paperSize="9" orientation="landscape" fitToWidth="1" fitToHeight="0"/></worksheet>'''
    parts = {
        "[Content_Types].xml": '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>''',
        "_rels/.rels": '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>''',
        "xl/workbook.xml": '''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Rapport" sheetId="1" r:id="rId1"/></sheets><definedNames><definedName name="_xlnm.Print_Titles" localSheetId="0">'Rapport'!$1:$3</definedName></definedNames></workbook>''',
        "xl/_rels/workbook.xml.rels": '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>''',
        "xl/styles.xml": '''<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF166534"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="4"><xf fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment wrapText="1"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="4" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>''',
        "xl/worksheets/sheet1.xml": sheet,
    }
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content.encode("utf-8"))
    return buffer.getvalue()


def export_table(file_format, title, headers, rows, subtitle=""):
    if file_format == "xlsx":
        content = xlsx_bytes(title, headers, rows, subtitle)
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif file_format == "pdf":
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=24, leftMargin=24, topMargin=28, bottomMargin=28)
        styles = getSampleStyleSheet()
        cell_style = ParagraphStyle("cell", parent=styles["BodyText"], fontSize=8, leading=11, wordWrap="CJK")
        def cell(value):
            if isinstance(value, (date, datetime)):
                value = value.strftime("%d/%m/%Y")
            elif isinstance(value, Decimal):
                value = f"{value:,.2f}".replace(",", " ")
            return Paragraph(escape(str(value if value is not None else "")), cell_style)
        table = LongTable([[cell(v) for v in headers], *[[cell(v) for v in row] for row in rows]], repeatRows=1, colWidths=[doc.width / len(headers)] * len(headers))
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce8df")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f5f3")]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7)]))
        def footer(canvas, document):
            canvas.setFont("Helvetica", 8)
            canvas.drawRightString(landscape(A4)[0] - 24, 14, f"Ecclessia Manager · {document.page}")
        doc.build([Paragraph(escape(title), styles["Title"]), Paragraph(escape(subtitle), styles["BodyText"]), Spacer(1, 12), table], onFirstPage=footer, onLaterPages=footer)
        content = buffer.getvalue()
        content_type = "application/pdf"
    else:
        return None
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="rapport.{file_format}"'
    return response
