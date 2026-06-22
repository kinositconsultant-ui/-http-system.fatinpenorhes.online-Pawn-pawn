"""PDF generation utilities — pawn contracts and payment receipts."""
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


def _styles():
    base = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "TitleX",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            textColor=colors.HexColor("#2F4F4F"),
            spaceAfter=4,
        ),
        "Sub": ParagraphStyle(
            "SubX",
            parent=base["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#57534E"),
            spaceAfter=12,
        ),
        "H2": ParagraphStyle(
            "H2X",
            parent=base["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#1C1917"),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "Body": ParagraphStyle(
            "BodyX",
            parent=base["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#1C1917"),
            leading=14,
        ),
        "Small": ParagraphStyle(
            "SmallX",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#57534E"),
        ),
    }


def _kv_table(rows):
    t = Table(rows, colWidths=[5 * cm, 11 * cm])
    t.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 10),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#57534E")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1C1917")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#E7E5E4")),
            ]
        )
    )
    return t


def build_contract_pdf(contract: dict, client: dict, item: dict) -> bytes:
    s = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
    )
    story = []
    story.append(Paragraph("FATIN PENHORES", s["Title"]))
    story.append(Paragraph("Pawn Contract — Contratu Penhór", s["Sub"]))

    story.append(_kv_table([
        ["Contract No.", contract.get("contract_number", "")],
        ["Contract Date", contract.get("contract_date", "")],
        ["Due Date", contract.get("due_date", "")],
        ["Status", contract.get("status", "").upper()],
    ]))

    story.append(Paragraph("Client / Kliente", s["H2"]))
    story.append(_kv_table([
        ["Full Name", client.get("full_name", "")],
        ["ID Type", client.get("id_type", "")],
        ["ID Number", client.get("id_number", "")],
        ["Phone", client.get("phone", "")],
        ["Address", client.get("address", "")],
        ["Municipality", client.get("municipality", "")],
        ["Posto", client.get("posto", "")],
        ["Suco", client.get("suco", "")],
        ["Aldeia", client.get("aldeia", "")],
    ]))

    item_kind = contract.get("item_type", "")
    story.append(Paragraph(f"Pawned Item — {item_kind.title()}", s["H2"]))
    base_rows = [
        ["Brand", item.get("brand", "")],
        ["Model", item.get("model", "")],
        ["Description", item.get("description", "")],
    ]
    if item_kind in ("car", "motorcycle"):
        base_rows.extend([
            ["Plate", item.get("plate", "")],
            ["Chassis", item.get("chassis", "")],
            ["Fuel %", str(item.get("fuel_percent", ""))],
        ])
    elif item_kind == "electronic":
        base_rows.extend([
            ["Serial No.", item.get("serial", "")],
            ["Category", item.get("category", "")],
        ])
    story.append(_kv_table(base_rows))

    story.append(Paragraph("Loan Terms — Termus Empréstimu", s["H2"]))
    loan = float(contract.get("loan_amount", 0))
    rate = float(contract.get("interest_rate", 0))
    interest = loan * rate / 100.0
    total_due = loan + interest
    story.append(_kv_table([
        ["Loan Amount", f"USD {loan:,.2f}"],
        ["Interest Rate", f"{rate:.0f}%"],
        ["Interest Amount", f"USD {interest:,.2f}"],
        ["Total Due", f"USD {total_due:,.2f}"],
    ]))

    story.append(Spacer(1, 1.5 * cm))
    sign = Table(
        [["_______________________", "_______________________"],
         ["Client Signature", "Authorized Officer"]],
        colWidths=[8 * cm, 8 * cm],
    )
    sign.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#57534E")),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
    ]))
    story.append(sign)

    doc.build(story)
    return buf.getvalue()


def build_receipt_pdf(payment: dict, contract: dict, client: dict, remaining: float) -> bytes:
    s = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
    )
    story = []
    story.append(Paragraph("FATIN PENHORES", s["Title"]))
    story.append(Paragraph("Payment Receipt — Resibu Pagamentu", s["Sub"]))

    story.append(_kv_table([
        ["Receipt No.", payment.get("receipt_number", "")],
        ["Payment Date", payment.get("date", "")],
        ["Payment Type", payment.get("type", "").replace("_", " ").title()],
        ["Contract No.", contract.get("contract_number", "")],
    ]))

    story.append(Paragraph("Client / Kliente", s["H2"]))
    story.append(_kv_table([
        ["Full Name", client.get("full_name", "")],
        ["Phone", client.get("phone", "")],
        ["ID Number", client.get("id_number", "")],
    ]))

    story.append(Paragraph("Payment Details", s["H2"]))
    amt = float(payment.get("amount", 0))
    loan = float(contract.get("loan_amount", 0))
    rate = float(contract.get("interest_rate", 0))
    story.append(_kv_table([
        ["Original Loan", f"USD {loan:,.2f}"],
        ["Interest Rate", f"{rate:.0f}%"],
        ["Amount Paid", f"USD {amt:,.2f}"],
        ["Remaining Balance", f"USD {remaining:,.2f}"],
    ]))

    story.append(Spacer(1, 1.5 * cm))
    sign = Table(
        [["_______________________", "_______________________"],
         ["Client Signature", "Authorized Officer"]],
        colWidths=[8 * cm, 8 * cm],
    )
    sign.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#57534E")),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
    ]))
    story.append(sign)

    doc.build(story)
    return buf.getvalue()
