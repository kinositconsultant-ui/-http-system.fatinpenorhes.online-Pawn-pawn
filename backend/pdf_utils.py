"""PDF generation — Fatin Penhores (logo + header/footer + Tetum articles)."""
from io import BytesIO
from pathlib import Path

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
    Image as RLImage,
    KeepTogether,
)


# === Brand colors derived from the logo ===
NAVY = colors.HexColor("#1B2D5C")
NAVY_DARK = colors.HexColor("#0F1B3A")
SILVER = colors.HexColor("#B8B8B8")
INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#475569")
RULE = colors.HexColor("#E2E8F0")

COMPANY_NAME = "FATIN PENHORES UNIPESSOAL, LDA"
COMPANY_ADDR = "Caicoli, Dili, Timor-Leste"
COMPANY_TEL = "Tel: 78372678"
COMPANY_EMAIL = "Email: fatinpenhores@gmail.com"
COMPANY_FOOTER = "© 2026 Fatin Penhores. All Rights Reserved."

LOGO_PATH = Path(__file__).parent / "assets" / "logo.jpg"


def _styles():
    base = getSampleStyleSheet()
    return {
        "Brand": ParagraphStyle("BrandX", parent=base["Title"], fontName="Helvetica-Bold",
                                fontSize=15, textColor=NAVY, spaceAfter=2, leading=18),
        "Sub": ParagraphStyle("SubX", parent=base["Normal"], fontSize=8.5,
                              textColor=MUTED, spaceAfter=2, leading=11),
        "DocTitle": ParagraphStyle("DocTitle", parent=base["Title"], fontName="Helvetica-Bold",
                                   fontSize=14, alignment=1, textColor=INK,
                                   spaceBefore=8, spaceAfter=10),
        "Article": ParagraphStyle("Article", parent=base["Heading3"], fontName="Helvetica-Bold",
                                  fontSize=10, textColor=NAVY,
                                  spaceBefore=10, spaceAfter=4),
        "Body": ParagraphStyle("BodyX", parent=base["Normal"], fontSize=9.5,
                               textColor=INK, leading=13, spaceAfter=4),
        "Small": ParagraphStyle("Sml", parent=base["Normal"], fontSize=8,
                                textColor=MUTED),
        "Center": ParagraphStyle("Center", parent=base["Normal"], fontSize=9, alignment=1,
                                 textColor=INK),
        "FooterText": ParagraphStyle("Ft", parent=base["Normal"], fontSize=7.5,
                                     textColor=MUTED, alignment=1),
    }


def _money(v):
    return f"USD ${float(v or 0):,.2f}"


def _logo_flowable(width_cm=2.4):
    if LOGO_PATH.exists():
        try:
            img = RLImage(str(LOGO_PATH))
            ratio = img.imageWidth / max(img.imageHeight, 1)
            w = width_cm * cm
            img.drawWidth = w
            img.drawHeight = w / ratio if ratio else w
            return img
        except Exception:
            return None
    return None


def _branded_header(s):
    """Logo + company info table, with a navy underline."""
    logo = _logo_flowable() or Paragraph("<b>FP</b>", s["Brand"])
    company = [
        Paragraph(COMPANY_NAME, s["Brand"]),
        Paragraph(COMPANY_ADDR, s["Small"]),
        Paragraph(f"{COMPANY_TEL}  ·  {COMPANY_EMAIL}", s["Small"]),
    ]
    t = Table([[logo, company]], colWidths=[3.2 * cm, 13.6 * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 1.0, NAVY),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _on_page(canvas, doc):
    """Canvas hook: draws a thin navy bar on left edge + footer line + footer text."""
    width, height = doc.pagesize
    canvas.saveState()
    # Left brand accent (thin navy bar)
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, 6, height, fill=1, stroke=0)
    # Silver thin accent
    canvas.setFillColor(SILVER)
    canvas.rect(6, 0, 2, height, fill=1, stroke=0)
    # Footer rule
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(0.6)
    canvas.line(1.8 * cm, 1.2 * cm, width - 1.8 * cm, 1.2 * cm)
    # Footer text
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(width / 2, 0.9 * cm, COMPANY_FOOTER)
    canvas.drawString(1.8 * cm, 0.55 * cm, f"{COMPANY_NAME} · {COMPANY_ADDR}")
    canvas.drawRightString(width - 1.8 * cm, 0.55 * cm, f"{COMPANY_TEL} · {COMPANY_EMAIL}")
    # Page number
    canvas.drawRightString(width - 1.8 * cm, 0.9 * cm, f"Page {doc.page}")
    canvas.restoreState()


def _header_box(s, contract: dict, client: dict, total_due: float):
    money = _money
    item_kind = contract.get("item_type", "").lower()
    type_label_map = {"car": "VEHICLE - CAR", "motorcycle": "VEHICLE - MOTORCYCLE", "electronic": "ELECTRONIC"}
    rows = [
        ["Nú Kontratu", contract.get("contract_number", ""),
         "Tipo Kontratu", type_label_map.get(item_kind, item_kind.upper())],
        ["Montante Empréstimu", money(contract.get("loan_amount", 0)),
         "Taxa Interese", f"{float(contract.get('interest_rate', 0)):.2f}%"],
        ["Total Selu", money(total_due),
         "Status", str(contract.get("status", "active")).upper()],
        ["Data Hahu", contract.get("contract_date", ""),
         "Data Remata", contract.get("due_date", "")],
        ["Naran Kliente", client.get("full_name", ""),
         "Telefone", client.get("phone", "")],
    ]
    t = Table(rows, colWidths=[3.6 * cm, 5.2 * cm, 3.6 * cm, 4.6 * cm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
        ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 9),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("TEXTCOLOR", (2, 0), (2, -1), MUTED),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ("BOX", (0, 0), (-1, -1), 0.5, NAVY),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, RULE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _article(s, title: str, body_lines: list[str]):
    parts = [Paragraph(title, s["Article"])]
    for line in body_lines:
        parts.append(Paragraph(line, s["Body"]))
    return KeepTogether(parts)


def _item_table(s, item_kind: str, item: dict, loan: float):
    money = _money
    rows = [
        ["Deskrisaun:", item.get("description") or "—"],
        ["Brand:", item.get("brand") or "—"],
        ["Model:", item.get("model") or "—"],
    ]
    if item_kind in ("car", "motorcycle"):
        rows += [
            ["Tinan Fabrika:", str(item.get("manufacture_year") or "—")],
            ["Kolór:", item.get("color") or "—"],
            ["Plate Number:", item.get("plate") or "—"],
            ["Chassis Number:", item.get("chassis") or "—"],
            ["Fuel %:", f"{item.get('fuel_percent', 0)}%"],
        ]
    elif item_kind == "electronic":
        rows += [
            ["Kategoría:", item.get("category") or "—"],
            ["Serial Number:", item.get("serial") or "—"],
            ["Tinan Fabrika:", str(item.get("manufacture_year") or "—")],
            ["Kondisaun:", item.get("condition") or "—"],
        ]
    rows += [
        ["Fatin:", item.get("location") or "—"],
        ["Valor Merkadu:", money(item.get("market_value", 0))],
        ["Loan Amount:", money(loan)],
    ]
    t = Table(rows, colWidths=[4.5 * cm, 12 * cm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def build_contract_pdf(contract: dict, client: dict, item: dict, settings: dict | None = None) -> bytes:
    s = _styles()
    sett = settings or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.4 * cm, bottomMargin=1.6 * cm,
    )

    loan = float(contract.get("loan_amount", 0) or 0)
    rate = float(contract.get("interest_rate", 0) or 0)
    interest_amount = round(loan * rate / 100.0, 2)
    total_due = float(contract.get("total_due", loan + interest_amount))
    item_kind = contract.get("item_type", "").lower()
    start = contract.get("contract_date", "")
    end = contract.get("due_date", "")

    story = []
    story.append(_branded_header(s))
    story.append(Paragraph("Pawn Management System · Pawn Agreement Contract", s["Sub"]))
    story.append(Paragraph("KONTRATU PENHOR", s["DocTitle"]))
    story.append(_header_box(s, contract, client, total_due))
    story.append(Spacer(1, 0.3 * cm))

    story.append(_article(s, "Artigu 1º — Objetu Kontratu", [
        "Kredor fó empréstimu osan ba kliente. Atu garante pagamentu dívida, kliente entrega sasán hanesan garantia penhor."
    ]))
    story.append(_article(s, "Artigu 2º — Montante Empréstimu ho Interese", [
        f"Montante empréstimu mak: USD ${loan:,.2f}.",
        f"Taxa interese: {rate:.2f}% kada fulan.",
        f"Prazu kontratu: {start} to'o {end}.",
        f"Total selu inklui interese mak: USD ${total_due:,.2f}.",
    ]))
    story.append(_article(s, "Artigu 3º — Interese", [
        f"Kliente konkorda selu interese ho taxa: {rate:.2f}% kada fulan. Interese sei kalkula durante tempu empréstimu.",
        "Maski kliente selu loan iha loron seluk depois data hahu, taxa interese minimu ida sei aplika.",
    ]))
    story.append(_article(s, "Artigu 4º — Prazu Kontratu", [
        f"Prazu kontratu hahu husi {start} to'o {end}.",
        "Prazu maximu ida ne'e mak fulan rua (2). Aluga ka ekstensaun bele halo se parte rua konkorda.",
    ]))

    item_label_map = {"car": "Karreta", "motorcycle": "Motorizada", "electronic": "Eletróniku"}
    story.append(Paragraph(
        f"Artigu 5º — Deskrisaun Detalhado Sasán Penhor ({item_label_map.get(item_kind, item_kind)})",
        s["Article"]))
    story.append(_item_table(s, item_kind, item, loan))

    story.append(_article(s, "Artigu 6º — Responsabilidade Legal Kliente", [
        "Kliente garante katak sasán ne'e ninia propriedade legal, la iha disputa legal, no la iha penhor iha fatin seluk. Se deklarasaun ida ne'e falsu, kredor bele hato'o keixa penal.",
    ]))
    story.append(_article(s, "Artigu 7º — Proibisaun Alienasaun", [
        "Durante kontratu, kliente la bele vende, transfere propriedade, penhor iha fatin seluk, sconde ka muda sasán.",
    ]))
    story.append(_article(s, "Artigu 8º — Multa Atrasu", [
        "Se kliente la selu tuir prazu kontratu, sei aplika multa 10% husi montante empréstimu orijinál (la inklui taxa interese).",
        f"Multa estimada: USD ${(loan * 0.10):,.2f}.",
    ]))
    story.append(_article(s, "Artigu 9º — Sasán, Ekipamentus Pezadu, Veikulu no Patrimonio", [
        "Dokumentus orizinal husi sasán, ekipamentus pezadu, veikulu no patrimonio sei sai garantia no kompania mak sei rai.",
        "Kompania sei la uza sasán penhor ba interese privadu.",
    ]))
    story.append(_article(s, "Artigu 10º — Direitu Venda Sasán", [
        "Se dívida la selu to'o prazu final, kredor bele vende sasán penhor atu cobre dívida.",
    ]))
    story.append(_article(s, "Artigu 11º — Força Executiva", [
        "Kontratu ida ne'e iha força executiva no bele uza diretamente iha tribunal.",
    ]))
    story.append(_article(s, "Artigu 12º — Despeza Legal", [
        "Se mosu prosesu tribunal, kliente responsabiliza selu despeza legal, apreensaun no indemnizasaun.",
    ]))
    story.append(_article(s, "Artigu 13º — Jurisdisaun", [
        "Disputa hotu sei resolve iha Tribunal Distrital Díli, tuir lei vigór iha República Demokrátika de Timor-Leste.",
    ]))
    story.append(_article(s, "Artigu 14º — Deklarasaun Final", [
        "Parte rua deklara katak lee ona kontratu, komprende kondisaun hotu no konkorda voluntariamente.",
    ]))

    tnc_en = (sett.get("terms_and_conditions_en") or "").strip()
    if tnc_en:
        story.append(Paragraph("Additional Terms (English)", s["Article"]))
        for line in tnc_en.split("\n"):
            if line.strip():
                story.append(Paragraph(line.strip(), s["Body"]))

    story.append(Spacer(1, 0.8 * cm))
    sign = Table(
        [
            ["_______________________", "_______________________", "_______________________"],
            ["Diretor / Manager", "Witness / Testemunha", "Kliente Penhor"],
            ["Fatin Penhor Management", "Naran: ____________________", client.get("full_name", "")],
        ],
        colWidths=[5.5 * cm, 5.5 * cm, 5.5 * cm],
    )
    sign.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR", (0, 1), (-1, -1), MUTED),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
    ]))
    story.append(sign)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


def build_receipt_pdf(payment: dict, contract: dict, client: dict, remaining: float) -> bytes:
    s = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.4 * cm, bottomMargin=1.6 * cm,
    )
    story = []
    story.append(_branded_header(s))
    story.append(Paragraph("Resibu Pagamentu · Payment Receipt", s["Sub"]))
    story.append(Spacer(1, 0.3 * cm))

    money = _money
    box1 = Table([
        ["Receipt No.", payment.get("receipt_number", ""), "Payment Date", payment.get("date", "")],
        ["Payment Type", str(payment.get("type", "")).replace("_", " ").title(),
         "Contract No.", contract.get("contract_number", "")],
        ["Client", client.get("full_name", ""), "Phone", client.get("phone", "")],
    ], colWidths=[3.5 * cm, 5.2 * cm, 3.5 * cm, 4.8 * cm])
    box1.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9.5),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9.5),
        ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("TEXTCOLOR", (2, 0), (2, -1), MUTED),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ("BOX", (0, 0), (-1, -1), 0.5, NAVY),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, RULE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(box1)
    story.append(Spacer(1, 0.5 * cm))

    amt = float(payment.get("amount", 0))
    loan = float(contract.get("loan_amount", 0))
    rate = float(contract.get("interest_rate", 0))
    box2 = Table([
        ["Original Loan", money(loan)],
        ["Interest Rate", f"{rate:.2f}%"],
        ["Amount Paid (this receipt)", money(amt)],
        ["Principal Remaining", money(contract.get("principal_remaining", 0))],
        ["Interest Remaining", money(contract.get("interest_remaining", 0))],
        ["Penalty (if overdue)", money(contract.get("penalty", 0))],
        ["Total Remaining Balance", money(remaining)],
    ], colWidths=[6.5 * cm, 10.5 * cm])
    box2.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 10),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(box2)

    story.append(Spacer(1, 1.2 * cm))
    sign = Table(
        [["_______________________", "_______________________"],
         ["Asinatura Kliente · Client", "Ofisiál Autorizadu · Officer"]],
        colWidths=[8 * cm, 8 * cm],
    )
    sign.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR", (0, 1), (-1, 1), MUTED),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
    ]))
    story.append(sign)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


def build_report_pdf(report_type: str, data: dict) -> bytes:
    """Branded report PDF used by /api/reports/v2/{type}/export?format=pdf."""
    from reportlab.lib.pagesizes import landscape
    s = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=1.2 * cm, rightMargin=1.2 * cm,
        topMargin=1.4 * cm, bottomMargin=1.6 * cm,
    )
    story = [
        _branded_header(s),
        Paragraph(f"{report_type.replace('-', ' ').title()} Report", s["DocTitle"]),
    ]
    kpi_pairs = [(k.replace("_", " ").title(), str(v))
                 for k, v in (data.get("kpis") or {}).items() if not isinstance(v, dict)]
    if kpi_pairs:
        kpi_tbl = Table([list(pair) for pair in kpi_pairs], colWidths=[5 * cm, 5 * cm])
        kpi_tbl.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
            ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ("BOX", (0, 0), (-1, -1), 0.25, NAVY),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, RULE),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(kpi_tbl)
        story.append(Spacer(1, 0.4 * cm))
    columns = data.get("columns", [])
    rows = data.get("rows", [])[:300]
    if columns:
        tbl_data = [[c.replace("_", " ").title() for c in columns]]
        for r in rows:
            tbl_data.append([str(r.get(c, "") or "") for c in columns])
        tbl = Table(tbl_data, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("LINEBELOW", (0, 1), (-1, -1), 0.2, RULE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


# Keep default bilingual T&C (used by Settings UI)
DEFAULT_TNC_EN = """1. The Client pledges the item described above as security for the loan amount stated.
2. Maximum contract term is 2 months from the contract date.
3. The Client may repay the loan in full, in part, or pay interest-only at any time within the term.
4. Even if the loan is repaid the day after contract date, the minimum agreed interest still applies.
5. Standard interest rates: Car 10%, Motorcycle 15%, Electronic 15%.
6. Partial payments reduce the principal first; interest is then calculated only on the remaining principal.
7. Late payment penalty: 10% of the original loan amount (does not include the interest fee).
8. If unpaid after the due date, the item may be moved to public auction or the contract may be reactivated by the Officer."""

DEFAULT_TNC_TET = """1. Kliente entrega sasán ne'ebé deskreve iha leten nudar garantia ba osan empréstimu.
2. Prazu maximu kontratu mak fulan rua (2) hahu husi data kontratu.
3. Kliente bele selu kompletu, parsiál, ka selu juru deit iha tempu ne'ebé deit durante prazu.
4. Maski selu loan iha loron tuir mai ba data kontratu, taxa interese minimu sei aplika.
5. Taxa juru padraun: Karreta 10%, Motorizada 15%, Eletróniku 15%.
6. Pagamentu parsiál hamenus uluk principal; interese kalkula tan iha balansu principal ne'ebé restu.
7. Multa atrasu: 10% husi montante empréstimu orijinál (la inklui taxa interese).
8. Se la selu kompleta to'o data limite, sasán bele hatama ba leilaun ka kontratu bele halo aktivu fali husi Ofisiál."""
