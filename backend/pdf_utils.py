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
    PageBreak,
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
            fontSize=12,
            textColor=colors.HexColor("#1C1917"),
            spaceBefore=12,
            spaceAfter=6,
        ),
        "Body": ParagraphStyle(
            "BodyX",
            parent=base["Normal"],
            fontSize=9.5,
            textColor=colors.HexColor("#1C1917"),
            leading=14,
        ),
        "Small": ParagraphStyle(
            "SmallX",
            parent=base["Normal"],
            fontSize=8.5,
            textColor=colors.HexColor("#57534E"),
            leading=12,
        ),
    }


def _kv_table(rows, col1=5.0, col2=11.0):
    t = Table(rows, colWidths=[col1 * cm, col2 * cm])
    t.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9.5),
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9.5),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#57534E")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1C1917")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#E7E5E4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return t


def build_contract_pdf(contract: dict, client: dict, item: dict, settings: dict | None = None) -> bytes:
    s = _styles()
    sett = settings or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
    )
    story = []
    story.append(Paragraph("FATIN PENHORES", s["Title"]))
    story.append(Paragraph("Pawn Contract · Kontratu Penhór", s["Sub"]))

    story.append(_kv_table([
        ["Contract No.", contract.get("contract_number", "")],
        ["Contract Date", contract.get("contract_date", "")],
        ["Due Date", contract.get("due_date", "")],
        ["Status", str(contract.get("status", "")).upper()],
    ]))

    # Client section
    story.append(Paragraph("Client · Kliente", s["H2"]))
    story.append(_kv_table([
        ["Full Name", client.get("full_name", "")],
        ["ID Type", client.get("id_type", "")],
        ["ID Number", client.get("id_number", "")],
        ["Phone", client.get("phone", "")],
        ["Address", client.get("address", "")],
        ["Municipality / Posto", f"{client.get('municipality','')} / {client.get('posto','')}"],
        ["Suco / Aldeia", f"{client.get('suco','')} / {client.get('aldeia','')}"],
    ]))

    # Item section
    item_kind = contract.get("item_type", "")
    story.append(Paragraph(f"Pawned Item · Sasán Penhór ({item_kind.title()})", s["H2"]))
    base_rows = [
        ["Brand · Marka", item.get("brand", "")],
        ["Model · Modelu", item.get("model", "")],
        ["Description · Deskrisaun", item.get("description", "") or "—"],
    ]
    if item_kind in ("car", "motorcycle"):
        base_rows.extend([
            ["Year · Tinan", str(item.get("year", "") or "—")],
            ["Color · Kolór", item.get("color", "") or "—"],
            ["Plate · Matrícula", item.get("plate", "") or "—"],
            ["Chassis", item.get("chassis", "") or "—"],
            ["Fuel %", f"{item.get('fuel_percent', 0)}%"],
        ])
    elif item_kind == "electronic":
        base_rows.extend([
            ["Category · Kategoría", item.get("category", "") or "—"],
            ["Serial No.", item.get("serial", "") or "—"],
            ["Condition", item.get("condition", "") or "—"],
        ])
    story.append(_kv_table(base_rows))

    # Loan details
    story.append(Paragraph("Loan Terms · Termus Empréstimu", s["H2"]))
    loan = float(contract.get("loan_amount", 0) or 0)
    rate = float(contract.get("interest_rate", 0) or 0)
    interest = loan * rate / 100.0
    total_due = loan + interest
    paid = float(contract.get("paid_amount", 0) or 0)
    remaining = float(contract.get("remaining_balance", total_due - paid) or 0)
    story.append(_kv_table([
        ["Loan Amount", f"USD {loan:,.2f}"],
        ["Interest Rate", f"{rate:.0f}%"],
        ["Interest Amount", f"USD {interest:,.2f}"],
        ["Total Due", f"USD {total_due:,.2f}"],
        ["Paid So Far", f"USD {paid:,.2f}"],
        ["Remaining", f"USD {remaining:,.2f}"],
    ]))

    # Terms & Conditions
    tnc_en = sett.get("terms_and_conditions_en") or DEFAULT_TNC_EN
    tnc_tet = sett.get("terms_and_conditions_tet") or DEFAULT_TNC_TET
    story.append(Paragraph("Terms & Conditions", s["H2"]))
    for line in [ln for ln in tnc_en.split("\n") if ln.strip()]:
        story.append(Paragraph(line.strip(), s["Body"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Termus no Kondisaun", s["H2"]))
    for line in [ln for ln in tnc_tet.split("\n") if ln.strip()]:
        story.append(Paragraph(line.strip(), s["Body"]))

    # Signatures
    story.append(Spacer(1, 1.2 * cm))
    sign = Table(
        [["_______________________", "_______________________"],
         ["Client Signature · Asinatura Kliente", "Authorized Officer · Ofisiál Autorizadu"]],
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
    story.append(Paragraph("Payment Receipt · Resibu Pagamentu", s["Sub"]))

    story.append(_kv_table([
        ["Receipt No.", payment.get("receipt_number", "")],
        ["Payment Date", payment.get("date", "")],
        ["Payment Type", str(payment.get("type", "")).replace("_", " ").title()],
        ["Contract No.", contract.get("contract_number", "")],
    ]))

    story.append(Paragraph("Client · Kliente", s["H2"]))
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

    story.append(Spacer(1, 1.2 * cm))
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


# Default bilingual T&C — admin can override in Settings.
DEFAULT_TNC_EN = """1. The Client pledges the item described above as security for the loan amount stated.
2. The Client may repay the loan in full, in part, or pay interest only at any time between the contract date and the due date.
3. Interest is applied at the agreed rate on the original loan amount and is non-refundable once the contract is signed.
4. Standard interest rates: Car 10%, Motorcycle 15%, Electronic 15% (unless agreed otherwise on the contract).
5. If the loan and interest are not fully repaid by the due date, Fatin Penhores may move the item to public auction without further notice.
6. The Client must present a valid identification document (BI, Electoral Card or Passport) to redeem the item.
7. Fatin Penhores is not responsible for any pre-existing damage or undisclosed defects in the item.
8. Both parties confirm the item description, loan amount and due date stated above are correct."""

DEFAULT_TNC_TET = """1. Kliente hatama sasán iha leten ne'e nudar garantia ba empréstimu osan ne'ebé hatama tiha.
2. Kliente bele selu kompletu, parsiál, ka selu juru deit iha tempu ne'ebé deit entre data kontratu ho data limite.
3. Juru aplika ho taxa ne'ebé akorda ona ba osan empréstimu orijinál, no la fila fali bainhira kontratu asina ona.
4. Taxa juru padraun: Karreta 10%, Motorizada 15%, Eletróniku 15% (se la akorda buat seluk iha kontratu).
5. Se osan empréstimu ho juru la selu kompleta to'o data limite, Fatin Penhores bele hatama sasán ba leilaun públiku sein avizu tan.
6. Kliente tenke hatudu BI, Kartaun Eleitorál ka Pasaporte atu foti sasán fali.
7. Fatin Penhores la responsabiliza ba estragu ne'ebé iha ona ka difeitu ne'ebé la deklara husi kliente.
8. Parte rua konfirma katak deskrisaun sasán, osan empréstimu no data limite iha leten ne'e los."""
