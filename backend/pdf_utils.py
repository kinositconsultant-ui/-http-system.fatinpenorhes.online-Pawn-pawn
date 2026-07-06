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
COMPANY_TEL = "WhatsApp: +670 78372678"
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


_LOGO_BYTES: bytes | None = None


def _logo_flowable(width_cm=2.4):
    global _LOGO_BYTES
    if _LOGO_BYTES is None and LOGO_PATH.exists():
        try:
            _LOGO_BYTES = LOGO_PATH.read_bytes()
        except Exception:
            _LOGO_BYTES = b""
    if not _LOGO_BYTES:
        return None
    try:
        img = RLImage(BytesIO(_LOGO_BYTES))
        ratio = img.imageWidth / max(img.imageHeight, 1)
        w = width_cm * cm
        img.drawWidth = w
        img.drawHeight = w / ratio if ratio else w
        return img
    except Exception:
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
        "Kontratu liu loron 1 konsidera fulan 1 — se kliente la selu iha loron limite, sei aplika interese ba fulan tomak tuir mai.",
        "Tolerasia 10 dias — wainhira liu loron 10, kompania sei halo leilaun ka faan sasán penhor (kareta, motor, pezadu).",
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


def build_receipt_pdf(payment: dict, contract: dict, client: dict, remaining: float, item: dict | None = None) -> bytes:
    s = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.4 * cm, bottomMargin=1.6 * cm,
    )
    is_disbursement = payment.get("type") == "disbursement"
    item = item or {}
    story = []
    story.append(_branded_header(s))
    if is_disbursement:
        story.append(Paragraph("Resibu Entrega Empréstimu · Loan Disbursement Receipt", s["Sub"]))
    else:
        story.append(Paragraph("Resibu Pagamentu · Payment Receipt", s["Sub"]))
    story.append(Spacer(1, 0.3 * cm))

    money = _money
    date_label = "Disbursement Date" if is_disbursement else "Payment Date"
    type_label = "Transaction Type" if is_disbursement else "Payment Type"
    box1 = Table([
        ["Receipt No.", payment.get("receipt_number", ""), date_label, payment.get("date", "")],
        [type_label, str(payment.get("type", "")).replace("_", " ").title(),
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
    if is_disbursement:
        # Disbursement receipt: focus on what the client received; no remaining/penalty section
        box2 = Table([
            ["Loan Amount", money(loan)],
            ["Amount Received by Client", money(amt)],
            ["Interest Rate (applies at maturity)", f"{rate:.2f}%"],
            ["Contract Start", contract.get("contract_date", "")],
            ["Contract Due Date", contract.get("due_date", "")],
        ], colWidths=[6.5 * cm, 10.5 * cm])
    else:
        box2 = Table([
            ["Original Loan", money(loan)],
            ["Interest Rate (per month)", f"{rate:.2f}%"],
            ["Months Billed So Far", str(int(contract.get("months_elapsed", 1)))],
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

    # Client-friendly "Next Payment" reminder — plain-language block that removes surprises
    # about when interest bumps up next. Skipped on disbursement receipts (no repayment context).
    next_date = contract.get("next_interest_date") or ""
    # Under Rule M1 the NEXT month's interest is computed on principal REMAINING
    # (not the current-month rate which was anchored on the original loan).
    # Fall back to per_month_interest for legacy contracts that don't emit
    # per_month_interest_next.
    per_month = float(contract.get("per_month_interest", 0) or 0)
    per_month_next = float(
        contract.get("per_month_interest_next", per_month) or per_month
    )
    principal_remaining_val = float(contract.get("principal_remaining", 0) or 0)
    interest_rate_val = float(contract.get("interest_rate", 0) or 0)
    # Defensive: use contract.remaining_balance if caller passed a stale `remaining`
    live_remaining = float(contract.get("remaining_balance", remaining) or remaining or 0)
    already_paid = live_remaining <= 0.01
    if not is_disbursement and next_date and per_month_next > 0 and not already_paid:
        current_total = live_remaining
        projected_next = round(current_total + per_month_next, 2)
        # Human-readable formula so the client can verify: "10% × $2,300 = $230"
        calc_hint = (
            f"{interest_rate_val:g}% × ${principal_remaining_val:,.2f} "
            f"= ${per_month_next:,.2f}"
        )
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(
            "Pagamentu Tuir Mai · Next Payment",
            ParagraphStyle(
                "NextPayHdr", parent=s["Sub"], fontSize=10,
                textColor=colors.HexColor("#1B2D5C"),
            ),
        ))
        note_box = Table([
            ["Next payment date", next_date],
            ["Current balance", _money(current_total)],
            ["Next month interest", f"+ {_money(per_month_next)}  ({calc_hint})"],
            ["If unpaid by that date, new total", _money(projected_next)],
        ], colWidths=[6.5 * cm, 10.5 * cm])
        note_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),  # warm amber
            ("FONT", (0, 0), (-1, -1), "Helvetica", 9.5),
            ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9.5),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#78350F")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(note_box)
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph(
            f"Favor selu iha loron {next_date} atu evita interese fulan tan "
            f"(${per_month_next:,.2f} = {interest_rate_val:g}% × saldu remanesenti). · "
            f"Please pay by {next_date} to avoid another month of interest "
            f"(${per_month_next:,.2f} = {interest_rate_val:g}% × remaining balance).",
            ParagraphStyle(
                "NextPayHint", parent=s["Body"], fontSize=8.5,
                textColor=MUTED, alignment=0,
            ),
        ))

        # Inline calculation example — explains WHY the interest is what it is.
        # Under Rule B (hybrid), if the client has made partial payments the
        # per-month breakdown is different across months, so we render an
        # itemized month-by-month table when `per_month_billed` is present.
        try:
            months = int(contract.get("months_elapsed", 1) or 1)
            paid_date = payment.get("date", "")
            start_date = contract.get("contract_date", "")
            per_month_billed = contract.get("per_month_billed") or []
            interest_total = float(contract.get("interest_amount") or round(per_month * months, 2))
            months_word_en = "month" if months == 1 else "months"
            months_word_tet = "fulan"

            hybrid = len(per_month_billed) > 1 and len(set(per_month_billed)) > 1
            if hybrid:
                # Multi-rate breakdown (Rule B kicked in via partial payments)
                calc_expr = " + ".join(f"${v:,.2f}" for v in per_month_billed) + f" = ${interest_total:,.2f}"
            else:
                calc_expr = f"{months} × ${per_month:,.2f} = ${interest_total:,.2f}"

            story.append(Spacer(1, 0.35 * cm))
            story.append(Paragraph(
                "Oinsá ami sura interese-nia · How your interest was calculated",
                ParagraphStyle(
                    "CalcHdr", parent=s["Sub"], fontSize=10,
                    textColor=colors.HexColor("#1B2D5C"),
                ),
            ))
            calc_rows = [
                ["Contract Start", start_date or "—"],
                ["Payment Date", paid_date or "—"],
                ["Billing Months (Article 4)", f"{months} {months_word_en} · {months} {months_word_tet}"],
            ]
            if hybrid:
                calc_rows.append(["Per-month (Rule B hybrid)",
                                  ", ".join(f"m{i+1}=${v:,.2f}" for i, v in enumerate(per_month_billed))])
            else:
                calc_rows.append(["Rate × Loan (per month)", f"${per_month:,.2f}"])
            calc_rows.append(["Interest Charged", calc_expr])
            calc_box = Table(calc_rows, colWidths=[6.5 * cm, 10.5 * cm])
            calc_box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF2FF")),  # soft indigo
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9.5),
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9.5),
                ("FONT", (1, -1), (1, -1), "Helvetica-Bold", 9.5),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#312E81")),
                ("TEXTCOLOR", (1, -1), (1, -1), colors.HexColor("#312E81")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(calc_box)
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph(
                "Regra Artigo 4: interese kobra tuir fulan-kompletu. Se selu iha aniversáriu, "
                "kobra deit fulan hanesan; se selu loron 1 liu, ami kobra fulan tuir mai. · "
                "Article 4: interest is billed per calendar month. Paying on the monthly "
                "anniversary charges the same month; one day past the anniversary starts a new month.",
                ParagraphStyle(
                    "CalcHint", parent=s["Body"], fontSize=8.5,
                    textColor=MUTED, alignment=0,
                ),
            ))
        except Exception:
            # Never let the explainer block break receipt generation
            pass

    # Pawn item description — shown on every receipt so the client/officer can verify
    # what was pledged. Extra useful on the disbursement receipt (proof of what was handed over).
    # Explicit truthiness on real fields so an empty {} passed from an orphaned contract skips cleanly.
    if item and (item.get("brand") or item.get("name") or item.get("model")):
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("Sasán Penhores · Pawn Item", s["Sub"]))
        story.append(Spacer(1, 0.15 * cm))
        item_type = contract.get("item_type") or item.get("item_type") or ""
        # Compose a friendly name — fall back to brand+model if no explicit name
        item_name = item.get("name") or f"{item.get('brand', '')} {item.get('model', '')}".strip() or "—"
        year = item.get("manufacture_year") or ""
        color = item.get("color") or ""
        rows = [
            ["Type", str(item_type).title() or "—", "Category", item.get("category", "") or "—"],
            ["Name / Model", item_name, "Year", str(year) or "—"],
            ["Brand", item.get("brand", "") or "—", "Color", color or "—"],
            ["Machine No.", item.get("machine_number", "") or "—", "Chassis", item.get("chassis", "") or "—"],
            ["Plate", item.get("plate", "") or "—", "Market Value", _money(item.get("market_value", 0))],
        ]
        # Description spans full width if present
        desc = item.get("description", "").strip()
        item_box = Table(rows, colWidths=[3.5 * cm, 5.2 * cm, 3.5 * cm, 4.8 * cm])
        item_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F1EA")),
            ("FONT", (0, 0), (-1, -1), "Helvetica", 9.5),
            ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9.5),
            ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 9.5),
            ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
            ("TEXTCOLOR", (2, 0), (2, -1), MUTED),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(item_box)
        if desc:
            story.append(Spacer(1, 0.2 * cm))
            story.append(Paragraph(
                f"<b>Deskrisaun:</b> {desc}",
                ParagraphStyle("ItemDesc", parent=s["Body"], fontSize=9.5, textColor=MUTED),
            ))

    story.append(Spacer(1, 1.2 * cm))

    # Signature block — client name auto-printed under the line so the client signs next to it.
    client_name = client.get("full_name", "") or "—"
    sign = Table(
        [
            ["_______________________", "_______________________"],
            [client_name, "Fatin Penhores"],
            ["Asinatura Kliente · Client Signature", "Ofisiál Autorizadu · Authorized Officer"],
        ],
        colWidths=[8 * cm, 8 * cm],
    )
    sign.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 1), (-1, 1), "Helvetica-Bold", 9.5),  # name row emphasized
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#1B2D5C")),
        ("TEXTCOLOR", (0, 2), (-1, 2), MUTED),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("TOPPADDING", (0, 2), (-1, 2), 0),
    ]))
    story.append(sign)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


def _fmt_money(v) -> str:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return str(v or "")
    return f"${n:,.2f}"


# Column type buckets used to compute proportional widths in report PDFs.
# Widths are expressed as *weights*; the final width = weight / sum(weights) * usable_width.
_MONEY_COLS = {
    "loan_amount", "interest_amount", "amount", "paid_amount", "principal_remaining",
    "interest_remaining", "penalty", "market_value", "starting_price", "sold_price",
    "total_loan", "total_payments", "interest_received", "total_penalty",
    "total_outstanding", "total_interest", "total_amount", "profit",
    "interest_expected", "paid",
}
_NUMERIC_COLS = {"interest_rate", "manufacture_year"}
_DATE_COLS = {"date", "due_date", "contract_date", "sold_at", "created_at", "start_date"}
_SHORT_COLS = {"status", "type", "kind", "item_type", "payment_method"}
_ID_COLS = {"contract_number", "receipt_number", "id"}
_WIDE_COLS = {
    "item", "description", "notes", "brand", "model", "buyer_name", "paid_to",
    "item_brand", "item_model", "item_category", "item_location", "location",
    "category", "sub_category",
}


def _col_weight(col: str) -> float:
    if col in _MONEY_COLS:
        return 1.1
    if col in _NUMERIC_COLS:
        return 0.9
    if col in _DATE_COLS:
        return 1.2
    if col in _SHORT_COLS:
        return 1.0
    if col in _ID_COLS:
        return 1.5
    if col in _WIDE_COLS:
        return 2.4
    return 1.4


def build_report_pdf(report_type: str, data: dict) -> bytes:
    """Branded report PDF used by /api/reports/v2/{type}/export?format=pdf.

    Layout:
    - Landscape A4 with tight margins.
    - Column widths are calculated proportionally so long text columns (item /
      description / notes) get more room and numeric columns stay compact.
    - Cell values are wrapped inside a Paragraph so long strings break onto
      multiple lines instead of blowing out the column.
    """
    from reportlab.lib.pagesizes import landscape
    s = _styles()
    buf = BytesIO()
    left_m = right_m = 1.0 * cm
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=left_m, rightMargin=right_m,
        topMargin=1.4 * cm, bottomMargin=1.6 * cm,
    )
    page_w, _ph = landscape(A4)
    usable_w = page_w - left_m - right_m

    story = [
        _branded_header(s),
        Paragraph(f"{report_type.replace('-', ' ').title()} Report", s["DocTitle"]),
    ]
    kpi_pairs = [(k.replace("_", " ").title(), _fmt_money(v) if k in _MONEY_COLS else str(v))
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
        # Proportional column widths
        weights = [_col_weight(c) for c in columns]
        total_w = sum(weights) or 1.0
        col_widths = [w / total_w * usable_w for w in weights]

        # Cell paragraph style — wraps long text
        cell_style = ParagraphStyle(
            "ReportCell", fontName="Helvetica", fontSize=7.5,
            leading=9.5, textColor=INK,
        )
        head_style = ParagraphStyle(
            "ReportHead", fontName="Helvetica-Bold", fontSize=8,
            leading=10, textColor=colors.white, alignment=1,
        )

        def _fmt_cell(col: str, val) -> str:
            if val is None or val == "":
                return ""
            if col in _MONEY_COLS:
                return _fmt_money(val)
            return str(val)

        tbl_data = [[Paragraph(c.replace("_", " ").title(), head_style) for c in columns]]
        for r in rows:
            tbl_data.append([
                Paragraph(_fmt_cell(c, r.get(c, "")), cell_style) for c in columns
            ])

        tbl = Table(tbl_data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("LINEBELOW", (0, 1), (-1, -1), 0.2, RULE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(tbl)
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


def _section_title(s, text):
    return Paragraph(text, ParagraphStyle(
        "Sec", parent=s["DocTitle"], fontSize=12, alignment=0, spaceBefore=2, spaceAfter=6,
    ))


def _kv_table(rows, col_widths=(5.5 * cm, 5.5 * cm)):
    t = Table(rows, colWidths=list(col_widths))
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9.5),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _data_table(columns, rows, col_widths=None, footer_row=None):
    """Branded data table. columns = list[str], rows = list[list[str]]."""
    header = [c for c in columns]
    body = [header] + [list(r) for r in rows]
    if footer_row:
        body.append(list(footer_row))
    t = Table(body, colWidths=col_widths, repeatRows=1)
    style = [
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LINEBELOW", (0, 1), (-1, -1), 0.2, RULE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if footer_row:
        last = len(body) - 1
        style += [
            ("FONT", (0, last), (-1, last), "Helvetica-Bold", 9),
            ("BACKGROUND", (0, last), (-1, last), colors.HexColor("#EEF2F7")),
            ("TEXTCOLOR", (0, last), (-1, last), NAVY),
            ("LINEABOVE", (0, last), (-1, last), 0.6, NAVY),
        ]
    t.setStyle(TableStyle(style))
    return t


def _new_doc(landscape_mode=False):
    from reportlab.lib.pagesizes import landscape as _ls
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=_ls(A4) if landscape_mode else A4,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        topMargin=1.4 * cm, bottomMargin=1.6 * cm,
    )
    return buf, doc


def build_invoice_pdf(invoice: dict, item: dict | None = None) -> bytes:
    """Single invoice PDF for sold auction items."""
    s = _styles()
    buf, doc = _new_doc()
    story = [_branded_header(s),
             Paragraph("Sales Invoice · Resibu Venda", s["Sub"]),
             Paragraph(f"INVOICE {invoice.get('invoice_number', '')}", s["DocTitle"])]

    meta = [
        ["Invoice No.", invoice.get("invoice_number", ""),
         "Date", invoice.get("date", "")],
        ["Contract No.", invoice.get("contract_number") or "—",
         "Status", str(invoice.get("status", "issued")).upper()],
        ["Item Type", str(invoice.get("item_type", "")).title(),
         "Item Ref.", (item or {}).get("brand", "") or (item or {}).get("description", "")[:30] or "—"],
    ]
    box = Table(meta, colWidths=[3.6 * cm, 5.2 * cm, 3.6 * cm, 4.6 * cm])
    box.setStyle(TableStyle([
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
    story.append(box)
    story.append(Spacer(1, 0.4 * cm))

    story.append(_section_title(s, "Bill To · Komprador"))
    buyer = [
        ["Name", invoice.get("buyer_name", "") or "—"],
        ["Phone", invoice.get("buyer_phone", "") or "—"],
        ["Email", invoice.get("buyer_email", "") or "—"],
        ["Address", invoice.get("buyer_address", "") or "—"],
        ["ID Number", invoice.get("buyer_id_number", "") or "—"],
    ]
    story.append(_kv_table(buyer, (4 * cm, 12 * cm)))
    story.append(Spacer(1, 0.5 * cm))

    # Line item
    desc_bits = []
    if item:
        if item.get("brand"):
            desc_bits.append(item["brand"])
        if item.get("model"):
            desc_bits.append(item["model"])
        if item.get("manufacture_year"):
            desc_bits.append(str(item["manufacture_year"]))
        if item.get("description"):
            desc_bits.append(item["description"])
    desc = " · ".join(desc_bits) or str(invoice.get("item_type", "")).title()
    line_rows = [
        ["1", f"{str(invoice.get('item_type', '')).title()} — {desc}", "1", _money(invoice.get("subtotal", 0))],
    ]
    line_tbl = _data_table(
        ["#", "Description", "Qty", "Amount"],
        line_rows,
        col_widths=[1 * cm, 11.4 * cm, 1.5 * cm, 3 * cm],
    )
    story.append(line_tbl)
    story.append(Spacer(1, 0.3 * cm))

    totals = [
        ["Subtotal", _money(invoice.get("subtotal", 0))],
        [f"Tax ({float(invoice.get('tax_percent', 0) or 0):.2f}%)", _money(invoice.get("tax_amount", 0))],
        ["TOTAL", _money(invoice.get("total", 0))],
    ]
    tot = Table(totals, colWidths=[12.9 * cm, 4 * cm])
    tot.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 10),
        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 11),
        ("BACKGROUND", (0, -1), (-1, -1), NAVY),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tot)

    if invoice.get("notes"):
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(f"<b>Notes:</b> {invoice['notes']}", s["Body"]))

    story.append(Spacer(1, 1.2 * cm))
    sign = Table(
        [["_______________________", "_______________________"],
         ["Buyer Signature · Komprador", "Authorized Officer"]],
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


def build_invoices_list_pdf(invoices: list[dict]) -> bytes:
    """List of all invoices."""
    s = _styles()
    buf, doc = _new_doc(landscape_mode=True)
    total = sum(float(i.get("total", 0) or 0) for i in invoices)
    story = [
        _branded_header(s),
        Paragraph("Invoices Register · Rejistu Resibu", s["DocTitle"]),
        Paragraph(f"Total Invoices: <b>{len(invoices)}</b> · Total Amount: <b>{_money(total)}</b>", s["Body"]),
        Spacer(1, 0.3 * cm),
    ]
    rows = []
    for inv in invoices:
        rows.append([
            inv.get("invoice_number", ""),
            inv.get("date", ""),
            inv.get("buyer_name", "") or "—",
            inv.get("contract_number") or "—",
            str(inv.get("item_type", "")).title(),
            _money(inv.get("subtotal", 0)),
            _money(inv.get("tax_amount", 0)),
            _money(inv.get("total", 0)),
            str(inv.get("status", "issued")).upper(),
        ])
    columns = ["Invoice No.", "Date", "Buyer", "Contract", "Item Type", "Subtotal", "Tax", "Total", "Status"]
    footer = ["", "", "", "", "TOTAL", "", "", _money(total), ""]
    story.append(_data_table(
        columns, rows,
        col_widths=[3.0 * cm, 2.2 * cm, 4.5 * cm, 3.0 * cm, 2.4 * cm, 2.4 * cm, 2.2 * cm, 2.6 * cm, 2.0 * cm],
        footer_row=footer,
    ))
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


def build_loan_terms_card_pdf(contract: dict, client: dict, item: dict) -> bytes:
    """One-page bilingual "Terms of your Loan" card, personalized for a specific contract.

    Printed alongside the contract at signing time. Contains the client's exact
    loan amount + rate + a worked example computed from THIS contract's numbers,
    so the client understands what "next month interest" will look like BEFORE
    signing. Signature block at the bottom → binding evidence they understood.
    """
    s = _styles()
    buf, doc = _new_doc(landscape_mode=False)
    NAVY = colors.HexColor("#1B2D5C")
    AMBER = colors.HexColor("#FEF3C7")
    INDIGO = colors.HexColor("#EEF2FF")

    loan = float(contract.get("loan_amount") or 0)
    rate = float(contract.get("interest_rate") or 0)  # e.g. 10 (percent)
    rate_frac = rate / 100.0
    month1_interest = round(loan * rate_frac, 2)

    # Simulate business-owner example USING THIS CONTRACT'S NUMBERS
    # 33% partial (rounded to nearest $10) so the numbers stay clean.
    sample_partial = max(50, round(loan * 0.33, -1))
    sample_int_paid = min(sample_partial, month1_interest)
    sample_princ_paid = max(0, sample_partial - month1_interest)
    sample_new_princ = round(loan - sample_princ_paid, 2)
    sample_next_int = round(sample_new_princ * rate_frac, 2)
    sample_new_total = round(sample_new_princ + sample_next_int, 2)

    client_name = client.get("full_name", "—") if client else "—"
    contract_num = contract.get("contract_number") or "—"
    contract_date = contract.get("contract_date") or "—"
    due_date = contract.get("due_date") or "—"
    item_name = (item.get("name") or item.get("brand") or "—") if item else "—"

    story = [
        _branded_header(s),
        Paragraph(
            "Termu Empréstimu · Terms of Your Loan",
            ParagraphStyle("Title", parent=s["DocTitle"], fontSize=15,
                           textColor=NAVY, alignment=1),
        ),
        Paragraph(
            f"Kontratu · Contract <b>{contract_num}</b>",
            ParagraphStyle("Sub", parent=s["Body"], fontSize=10,
                           textColor=colors.HexColor("#78350F"), alignment=1),
        ),
        Spacer(1, 0.5 * cm),

        # ─── Client + loan snapshot ───
        Paragraph(
            "1. Detalie ó nia empréstimu · Your Loan Details",
            ParagraphStyle("H1", parent=s["Sub"], fontSize=11, textColor=NAVY),
        ),
        Spacer(1, 0.2 * cm),
    ]
    detail_box = Table(
        [
            ["Kliente · Client", client_name],
            ["Item pauna · Pawn item", item_name],
            ["Osan empréstimu · Loan amount (L)", f"${loan:,.2f}"],
            ["Taxa fulan-fulan · Monthly rate (R)", f"{rate:g}%"],
            ["Data hahú · Contract start", contract_date],
            ["Data limit · Due date", due_date],
            ["Juru Fulan 1 · Month 1 interest (L × R)", f"${month1_interest:,.2f}"],
        ],
        colWidths=[7 * cm, 9.5 * cm],
    )
    detail_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), INDIGO),
        ("BACKGROUND", (1, 0), (1, -1), colors.white),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9.5),
        ("FONT", (1, 0), (1, -1), "Helvetica", 10),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#312E81")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C7D2FE")),
    ]))
    story.append(detail_box)
    story.append(Spacer(1, 0.4 * cm))

    # ─── The rule (short) ───
    story.append(Paragraph(
        "2. Oinsá interese kalkula · How interest is calculated",
        ParagraphStyle("H2", parent=s["Sub"], fontSize=11, textColor=NAVY),
    ))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph(
        f"• <b>Fulan 1 · Month 1:</b> Juru = L × R = ${loan:,.2f} × {rate:g}% = <b>${month1_interest:,.2f}</b>.<br/>"
        f"• <b>Fulan 2+ · Month 2 onward:</b> Juru = P × R (P = prinsipál rezidu · principal remaining).<br/>"
        f"• <b>Pagamentu · Payment allocation (M1):</b> juru dahuluk, sobra ba prinsipál · interest first, remainder to principal.<br/>"
        f"• <b>Sen ez pagamentu · No compound:</b> Juru fulan tuir mai kalkula husi prinsipál rezidu <b>deit</b> · next-month interest is 10% of the remaining <b>principal only</b>.",
        ParagraphStyle("RuleBody", parent=s["Body"], fontSize=9.5,
                       textColor=colors.HexColor("#374151"), leading=13),
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ─── Personalized worked example ───
    story.append(Paragraph(
        f"3. Ezemplu ho ó nia numeru · Your worked example",
        ParagraphStyle("H3", parent=s["Sub"], fontSize=11, textColor=NAVY),
    ))
    story.append(Spacer(1, 0.15 * cm))
    example_box = Table(
        [
            ["Fulan 1 anchor",
             f"L = ${loan:,.2f} · U = ${month1_interest:,.2f} · P = ${loan:,.2f}"],
            [f"Selu partial C = ${sample_partial:,.2f}",
             f"Interest paid = MIN({sample_partial:g}, {month1_interest:g}) = ${sample_int_paid:,.2f}\n"
             f"Principal paid = MAX({sample_partial:g} − {month1_interest:g}, 0) = ${sample_princ_paid:,.2f}\n"
             f"U = $0   ·   P = ${sample_new_princ:,.2f}"],
            ["Fulan 2 anchor",
             f"Juru = P × R = ${sample_new_princ:,.2f} × {rate:g}% = ${sample_next_int:,.2f}"],
            ["Total sedauk selu · If unpaid",
             f"${sample_new_princ:,.2f} + ${sample_next_int:,.2f} = ${sample_new_total:,.2f}"],
        ],
        colWidths=[6.5 * cm, 10 * cm],
    )
    example_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), AMBER),
        ("BACKGROUND", (1, 0), (1, -1), colors.white),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
        ("FONT", (1, 0), (1, -1), "Helvetica", 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#78350F")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#FCD34D")),
    ]))
    story.append(example_box)
    story.append(Spacer(1, 0.35 * cm))
    story.append(Paragraph(
        "<i>Ezemplu ne'e uza porsentu ida (~33%) husi ó nia empréstimu nu'udar "
        "pagamentu partial atu ilustra fórmula. Numero real depende ba kuandu ó selu. "
        "· This example uses a ~33% partial payment for illustration only — your actual numbers depend on when you pay.</i>",
        ParagraphStyle("Note", parent=s["Body"], fontSize=8.5,
                       textColor=colors.HexColor("#78716C"), leading=11),
    ))
    story.append(Spacer(1, 0.5 * cm))

    # ─── Signature block ───
    story.append(Paragraph(
        "4. Konfirmasaun · Acknowledgment",
        ParagraphStyle("H4", parent=s["Sub"], fontSize=11, textColor=NAVY),
    ))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph(
        "Hau <b>{name}</b> konfirma katak hau lee no komprende ona termu iha "
        "papel ida ne'e no fórmula juru molok hau asina kontratu. · "
        "I, <b>{name}</b>, confirm that I have read and understood the terms "
        "and interest formula on this card BEFORE signing the loan contract.".format(name=client_name),
        ParagraphStyle("Confirm", parent=s["Body"], fontSize=9.5,
                       textColor=colors.HexColor("#374151"), leading=13),
    ))
    story.append(Spacer(1, 0.7 * cm))
    sig_box = Table(
        [
            ["Asinatura Kliente · Client signature", "Asinatura Kasier · Cashier signature"],
            ["", ""],
            ["Data · Date: _______________", "Data · Date: _______________"],
        ],
        colWidths=[8.25 * cm, 8.25 * cm],
        rowHeights=[0.6 * cm, 1.6 * cm, 0.6 * cm],
    )
    sig_box.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("FONT", (0, 2), (-1, 2), "Helvetica", 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, 1), 0.6, NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(sig_box)
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


def build_rules_card_pdf() -> bytes:
    """One-page bilingual printable card explaining Rule M1 interest math.

    Designed to be printed A4 portrait and laminated at cashier stations —
    the same $3,000 example that appears in receipts + WhatsApp reminders,
    so staff can walk clients through the numbers without ambiguity.
    """
    s = _styles()
    buf, doc = _new_doc(landscape_mode=False)
    NAVY = colors.HexColor("#1B2D5C")
    GOLD = colors.HexColor("#F4C86D")
    AMBER = colors.HexColor("#FEF3C7")
    INDIGO = colors.HexColor("#EEF2FF")
    story = [
        _branded_header(s),
        Paragraph(
            "Nia Interese-nia oinsá kalkula · How your Interest is calculated",
            ParagraphStyle(
                "RulesTitle", parent=s["DocTitle"], fontSize=15,
                textColor=NAVY, alignment=1,  # center
            ),
        ),
        Spacer(1, 0.15 * cm),
        Paragraph(
            "Rejra M1 — Feb 2026 · Referensia interna, prezerva iha ekipa nia mesa. "
            "Reference card — keep at cashier station.",
            ParagraphStyle(
                "RulesSub", parent=s["Body"], fontSize=8.5,
                textColor=colors.HexColor("#78350F"), alignment=1,
            ),
        ),
        Spacer(1, 0.5 * cm),

        # ────── Formula block ──────
        Paragraph(
            "1. Formula · Fórmula",
            ParagraphStyle("H1", parent=s["Sub"], fontSize=11, textColor=NAVY),
        ),
        Spacer(1, 0.2 * cm),
        Table(
            [
                ["Sinbolu · Symbol", "Signifika · Meaning"],
                ["L", "Loan orijinál · Original loan amount"],
                ["R", "Taxa fulan-fulan · Monthly interest rate (10% = 0.10)"],
                ["P", "Prinsipál rezidu · Principal remaining"],
                ["U", "Juru nebe seida selu · Unpaid interest"],
                ["C", "Pagamentu klientenia · Customer payment"],
            ],
            colWidths=[3.5 * cm, 13 * cm],
        ).setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9.5),
            ("FONT", (0, 1), (0, -1), "Helvetica-Bold", 10),
            ("FONT", (1, 1), (1, -1), "Helvetica", 9.5),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F5F4F1")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D6D3D1")),
        ])) or Spacer(1, 0),  # noqa: E711  (Table.setStyle mutates in-place)
    ]
    tbl_symbol = Table(
        [
            ["Sinbolu · Symbol", "Signifika · Meaning"],
            ["L", "Loan orijinál · Original loan amount"],
            ["R", "Taxa fulan-fulan · Monthly interest rate (10% = 0.10)"],
            ["P", "Prinsipál rezidu · Principal remaining"],
            ["U", "Juru nebe seida selu · Unpaid interest"],
            ["C", "Pagamentu klientenia · Customer payment"],
        ],
        colWidths=[3.5 * cm, 13 * cm],
    )
    tbl_symbol.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9.5),
        ("FONT", (0, 1), (0, -1), "Helvetica-Bold", 10),
        ("FONT", (1, 1), (1, -1), "Helvetica", 9.5),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F5F4F1")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D6D3D1")),
    ]))
    story = [
        _branded_header(s),
        Paragraph(
            "Interese-nia oinsá kalkula · How your Interest is calculated",
            ParagraphStyle(
                "RulesTitle", parent=s["DocTitle"], fontSize=15,
                textColor=NAVY, alignment=1,
            ),
        ),
        Spacer(1, 0.1 * cm),
        Paragraph(
            "Rejra M1 — Feb 2026 · Cashier reference card",
            ParagraphStyle(
                "RulesSub", parent=s["Body"], fontSize=8.5,
                textColor=colors.HexColor("#78350F"), alignment=1,
            ),
        ),
        Spacer(1, 0.5 * cm),
        Paragraph("1. Sinbolu · Symbols",
                  ParagraphStyle("H1", parent=s["Sub"], fontSize=11, textColor=NAVY)),
        Spacer(1, 0.15 * cm),
        tbl_symbol,
        Spacer(1, 0.5 * cm),

        # ────── The 3 formulas ──────
        Paragraph("2. Fórmula Prinsipál · Core formulas",
                  ParagraphStyle("H2", parent=s["Sub"], fontSize=11, textColor=NAVY)),
        Spacer(1, 0.15 * cm),
    ]

    formula_box = Table(
        [
            ["Kada fulan · Each month anchor",
             "Fulan 1: interest = L × R\nFulan 2+: interest = P × R"],
            ["Pagamentu ne'e alokasaun · Payment allocation (M1)",
             "Interest paid  = MIN(C, U)\nPrincipal paid = MAX(C − U, 0)"],
            ["Fulan tuir mai · Next month forecast",
             "Next interest = P × R\nNew total if unpaid = P + U + Next interest"],
        ],
        colWidths=[6.5 * cm, 10 * cm],
    )
    formula_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), INDIGO),
        ("BACKGROUND", (1, 0), (1, -1), colors.white),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9.5),
        ("FONT", (1, 0), (1, -1), "Courier-Bold", 10),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#312E81")),
        ("TEXTCOLOR", (1, 0), (1, -1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C7D2FE")),
    ]))
    story.append(formula_box)
    story.append(Spacer(1, 0.5 * cm))

    # ────── Worked example ──────
    story.append(Paragraph(
        "3. Ezemplu · Worked example — Loan $3,000 @ 10%",
        ParagraphStyle("H3", parent=s["Sub"], fontSize=11, textColor=NAVY),
    ))
    story.append(Spacer(1, 0.15 * cm))
    example_box = Table(
        [
            ["Fulan 1 (Jan 10)", "L = $3,000 · U = $300 · P = $3,000"],
            ["Jan 20 — Klientenia selu C = $1,000 (partial)",
             "Interest paid = MIN(1000, 300) = $300\n"
             "Principal paid = MAX(1000 − 300, 0) = $700\n"
             "U = $0   ·   P = $3,000 − $700 = $2,300"],
            ["Fulan 2 anchor (Feb 10)",
             "Month interest = P × R = 2300 × 0.10 = $230"],
            ["Fulan tuir mai · Next month forecast",
             "Next interest = 2300 × 0.10 = $230\n"
             "Total sedauk selu · Total if unpaid = $2,300 + $230 = $2,530"],
        ],
        colWidths=[7 * cm, 9.5 * cm],
    )
    example_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), AMBER),
        ("BACKGROUND", (1, 0), (1, -1), colors.white),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
        ("FONT", (1, 0), (1, -1), "Helvetica", 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#78350F")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#FCD34D")),
    ]))
    story.append(example_box)
    story.append(Spacer(1, 0.5 * cm))

    # ────── Payment types quick-ref ──────
    story.append(Paragraph(
        "4. Tipu Pagamentu · Payment types",
        ParagraphStyle("H4", parent=s["Sub"], fontSize=11, textColor=NAVY),
    ))
    story.append(Spacer(1, 0.15 * cm))
    types_box = Table(
        [
            ["Tipu · Type", "Alokasaun · Allocation"],
            ["interest_only", "Juru dahuluk, sobra ba prinsipál · Interest first, excess to principal"],
            ["partial (M1)", "Juru dahuluk, sobra ba prinsipál · Interest first, remainder to principal"],
            ["full", "Juru dahuluk, sobra ba prinsipál — kontratu remata · Redeems contract"],
            ["overdue_full", "Pena → Juru → Prinsipál · Penalty → Interest → Principal"],
            ["overdue_interest_pen", "Pena → Juru deit · Penalty → Interest (no principal)"],
            ["overdue_penalty_only", "Pena deit · Penalty only"],
            ["disbursement", "Osan husik ba kliente · Loan handover — no allocation"],
        ],
        colWidths=[4.5 * cm, 12 * cm],
    )
    types_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9.5),
        ("FONT", (0, 1), (0, -1), "Courier-Bold", 8.5),
        ("FONT", (1, 1), (1, -1), "Helvetica", 8.5),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F5F4F1")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D6D3D1")),
    ]))
    story.append(types_box)
    story.append(Spacer(1, 0.4 * cm))

    # Footer note
    story.append(Paragraph(
        "<b>Nota importante · Important:</b> Ami la aplika juru compound. "
        "Se kliente la selu buat ida, fulan tuir mai nia interese kalkula "
        "husi prinsipál rezidu <b>deit</b> (P × R). "
        "· We do NOT compound interest. If a client pays nothing, next "
        "month's interest is still computed on the remaining <b>principal</b> only.",
        ParagraphStyle("Footer", parent=s["Body"], fontSize=8.5,
                       textColor=colors.HexColor("#57534E")),
    ))
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


def build_audit_log_pdf(rows: list[dict], filters: dict | None = None) -> bytes:
    """Branded PDF export of the audit log with active filter summary at the top."""
    s = _styles()
    buf, doc = _new_doc(landscape_mode=True)
    filters = filters or {}
    active = [f"{k}={v}" for k, v in filters.items() if v]
    filter_line = "Filters: " + " · ".join(active) if active else "Filters: (none — showing latest entries)"
    story = [
        _branded_header(s),
        Paragraph("Audit Log · Rejistu Atividade", s["DocTitle"]),
        Paragraph(f"Entries: <b>{len(rows)}</b> — {filter_line}", s["Body"]),
        Spacer(1, 0.3 * cm),
    ]
    data_rows = []
    for r in rows:
        details = r.get("details") or {}
        if isinstance(details, dict):
            det = ", ".join(f"{k}={v}" for k, v in list(details.items())[:4])
        else:
            det = str(details)[:80]
        data_rows.append([
            (r.get("created_at") or "")[:19].replace("T", " "),
            r.get("actor_email") or r.get("actor_id") or "—",
            r.get("action", ""),
            r.get("resource", ""),
            (r.get("resource_id") or "")[:24],
            det[:60],
        ])
    story.append(_data_table(
        ["When (UTC)", "Actor", "Action", "Resource", "ID", "Details"],
        data_rows,
        col_widths=[3.6 * cm, 4.5 * cm, 3 * cm, 2.4 * cm, 3.5 * cm, 7.2 * cm],
    ))
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


def build_capital_sources_pdf(sources: list[dict]) -> bytes:
    """List of capital sources with totals."""
    s = _styles()
    buf, doc = _new_doc(landscape_mode=True)
    total_principal = sum(float(x.get("principal_amount", 0) or 0) for x in sources)
    total_repaid = sum(float(x.get("total_repaid", 0) or 0) for x in sources)
    total_outstanding = sum(float(x.get("outstanding", 0) or 0) for x in sources)
    story = [
        _branded_header(s),
        Paragraph("Capital Sources · Fontes Kapitál", s["DocTitle"]),
        Paragraph(
            f"Sources: <b>{len(sources)}</b> · Principal: <b>{_money(total_principal)}</b> · "
            f"Repaid: <b>{_money(total_repaid)}</b> · Outstanding: <b>{_money(total_outstanding)}</b>",
            s["Body"]),
        Spacer(1, 0.3 * cm),
    ]
    rows = []
    for x in sources:
        rows.append([
            x.get("name", ""),
            str(x.get("source_type", "")).title(),
            _money(x.get("principal_amount", 0)),
            f"{float(x.get('interest_rate', 0) or 0):.2f}% / {x.get('interest_period', '')}",
            _money(x.get("total_repaid", 0)),
            _money(x.get("outstanding", 0)),
            x.get("start_date", "") or "—",
            x.get("due_date", "") or "—",
        ])
    footer = ["", "TOTAL", _money(total_principal), "",
              _money(total_repaid), _money(total_outstanding), "", ""]
    story.append(_data_table(
        ["Name", "Type", "Principal", "Rate / Period", "Repaid", "Outstanding", "Start", "Due"],
        rows,
        col_widths=[5 * cm, 2.4 * cm, 3 * cm, 3.4 * cm, 3 * cm, 3.2 * cm, 2.4 * cm, 2.4 * cm],
        footer_row=footer,
    ))
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


def build_expenses_pdf(expenses: list[dict], category: str | None = None,
                       month: int | None = None, year: int | None = None,
                       by_category: list[dict] | None = None) -> bytes:
    """Expenses list with optional filter; supports per-category breakdown."""
    s = _styles()
    buf, doc = _new_doc(landscape_mode=True)
    total = sum(float(e.get("amount", 0) or 0) for e in expenses)

    filters = []
    if category:
        filters.append(f"Category: <b>{category}</b>")
    if month:
        filters.append(f"Month: <b>{month:02d}</b>")
    if year:
        filters.append(f"Year: <b>{year}</b>")
    filter_line = " · ".join(filters) if filters else "All expenses"

    title = f"Operating Expenses — {category}" if category else "Operating Expenses · Despeza Operasional"

    story = [
        _branded_header(s),
        Paragraph(title, s["DocTitle"]),
        Paragraph(f"{filter_line} · Entries: <b>{len(expenses)}</b> · Total: <b>{_money(total)}</b>", s["Body"]),
        Spacer(1, 0.3 * cm),
    ]

    if by_category and not category:
        story.append(_section_title(s, "Summary by Category"))
        cat_rows = [[c.get("category", ""), _money(c.get("amount", 0))]
                    for c in by_category]
        cat_footer = ["TOTAL", _money(sum(float(c.get("amount", 0) or 0) for c in by_category))]
        story.append(_data_table(
            ["Category", "Amount"], cat_rows,
            col_widths=[10 * cm, 4 * cm], footer_row=cat_footer,
        ))
        story.append(Spacer(1, 0.4 * cm))
        story.append(_section_title(s, "Detailed Entries"))

    rows = []
    for e in expenses:
        rows.append([
            e.get("date", ""),
            e.get("category", ""),
            e.get("paid_to", "") or "—",
            str(e.get("payment_method", "")).title(),
            (e.get("description", "") or "—")[:55],
            _money(e.get("amount", 0)),
        ])
    footer = ["", "", "", "", "TOTAL", _money(total)]
    story.append(_data_table(
        ["Date", "Category", "Paid To", "Method", "Description", "Amount"], rows,
        col_widths=[2.4 * cm, 2.6 * cm, 4 * cm, 2.4 * cm, 8 * cm, 3 * cm],
        footer_row=footer,
    ))

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


def build_finance_summary_pdf(summary: dict, month: int | None = None, year: int | None = None) -> bytes:
    """Full Finance Summary PDF — KPIs + cash-flow breakdown + expenses by category."""
    s = _styles()
    buf, doc = _new_doc()

    period = []
    if month:
        period.append(f"Month {month:02d}")
    if year:
        period.append(f"Year {year}")
    period_line = " · ".join(period) if period else "Lifetime"

    story = [
        _branded_header(s),
        Paragraph("Finance Summary · Sumáriu Finanseiru", s["DocTitle"]),
        Paragraph(f"Period: <b>{period_line}</b>", s["Body"]),
        Spacer(1, 0.3 * cm),
    ]

    # KPI block
    def _row(label, key, color=None):
        v = summary.get(key)
        return [label, _money(v) if isinstance(v, (int, float)) else str(v)]

    kpis = [
        _row("Cash on Hand", "cash_on_hand"),
        _row("Capital Received", "capital_received"),
        _row("Capital Repaid", "capital_repaid"),
        _row("Capital Outstanding", "capital_outstanding"),
        _row("Loans Disbursed", "loans_disbursed"),
        _row("Client Payments", "client_payments"),
        _row("Auction Sales", "auction_sales"),
        _row("Interest Received", "interest_received"),
        _row("Total Penalty", "total_penalty"),
        _row("Expenses (Period)", "expenses_period"),
        _row("Expenses (Lifetime)", "expenses_total"),
        _row("Gross Profit", "gross_profit"),
        _row("Net Profit", "net_profit"),
        ["Total Invoices", str(summary.get("total_invoices", 0))],
        _row("Total Invoiced", "total_invoiced"),
    ]
    story.append(_section_title(s, "Key Indicators"))
    story.append(_kv_table(kpis, (8 * cm, 8 * cm)))
    story.append(Spacer(1, 0.4 * cm))

    # Expenses by category
    by_cat = summary.get("expenses_by_category") or []
    if by_cat:
        story.append(_section_title(s, "Expenses by Category"))
        rows = [[c.get("category", ""), _money(c.get("amount", 0))] for c in by_cat]
        total_cat = sum(float(c.get("amount", 0) or 0) for c in by_cat)
        footer = ["TOTAL", _money(total_cat)]
        story.append(_data_table(
            ["Category", "Amount"], rows,
            col_widths=[10 * cm, 6 * cm], footer_row=footer,
        ))
        story.append(Spacer(1, 0.4 * cm))

    # Cash flow snapshot
    story.append(_section_title(s, "Cash Flow Snapshot"))
    flow_rows = [
        ["Capital In (received)", _money(summary.get("capital_received", 0))],
        ["Client Payments", _money(summary.get("client_payments", 0))],
        ["Auction Sales", _money(summary.get("auction_sales", 0))],
        ["Loans Out (disbursed)", f"-{_money(summary.get('loans_disbursed', 0))}"],
        ["Expenses (lifetime)", f"-{_money(summary.get('expenses_total', 0))}"],
        ["Capital Repaid", f"-{_money(summary.get('capital_repaid', 0))}"],
    ]
    footer = ["NET CASH ON HAND", _money(summary.get("cash_on_hand", 0))]
    story.append(_data_table(
        ["Flow", "Amount"], flow_rows,
        col_widths=[10 * cm, 6 * cm], footer_row=footer,
    ))

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



# =====================================================================
# Member ID Card (CR80 credit-card size: 85.6 × 54 mm, front + back on A4)
# =====================================================================
def build_member_card_pdf(client: dict, verify_url: str, photo_bytes: bytes | None = None) -> bytes:
    """Generate a printable Member ID Card PDF for a client.

    Front (navy, credit-card sized): brand mark, name, member no, dates,
    photo. Back (white): QR code linking to public verify page + address /
    contact fine print. Two cards laid out on a single A4 for easy cutting.
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    import qrcode
    import urllib.request
    from datetime import datetime

    buf = BytesIO()
    page_w, page_h = A4  # portrait
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Member Card — {client.get('full_name', '')}")

    # Card dimensions — CR80
    card_w = 85.6 * mm
    card_h = 54.0 * mm
    # Center horizontally; stack front (upper) + back (lower) with a gap
    x = (page_w - card_w) / 2
    gap = 12 * mm
    top_y = page_h - 30 * mm - card_h  # front top card position
    bot_y = top_y - card_h - gap        # back card position

    name = (client.get("full_name") or "").upper()
    member_no = client.get("member_no", "")
    issued = client.get("member_issued_at", "") or ""
    expires = client.get("member_expires_at", "") or ""
    status = (client.get("member_status") or "").upper()
    photo_url = client.get("photo_url") or ""

    def _fmt_date(v: str) -> str:
        if not v:
            return ""
        try:
            return datetime.fromisoformat(v[:10]).strftime("%d %b %Y")
        except Exception:
            return v[:10]

    # ---------- FRONT (navy) ----------
    c.setFillColor(NAVY)
    c.rect(x, top_y, card_w, card_h, fill=1, stroke=0)

    # Silver accent strip along top
    c.setFillColor(SILVER)
    c.rect(x, top_y + card_h - 5 * mm, card_w, 5 * mm, fill=1, stroke=0)

    # Logo (top-left)
    logo_size = 12 * mm
    if LOGO_PATH.exists():
        try:
            c.drawImage(str(LOGO_PATH), x + 4 * mm, top_y + card_h - 22 * mm,
                        width=logo_size, height=logo_size,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    # Company wordmark
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 18 * mm, top_y + card_h - 12 * mm, "FATIN PENHORES")
    c.setFont("Helvetica", 6.5)
    c.setFillColor(SILVER)
    c.drawString(x + 18 * mm, top_y + card_h - 15.5 * mm, "UNIPESSOAL, LDA")

    # Ribbon: MEMBER ID CARD / KARTAUN MEMBRU
    c.setFillColor(colors.HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 7)
    c.drawRightString(x + card_w - 4 * mm, top_y + card_h - 12 * mm, "MEMBER ID CARD")
    c.setFont("Helvetica", 6)
    c.setFillColor(SILVER)
    c.drawRightString(x + card_w - 4 * mm, top_y + card_h - 15 * mm, "Kartaun Membru")

    # Photo box (right side)
    photo_w = 22 * mm
    photo_h = 27 * mm
    photo_x = x + card_w - photo_w - 4 * mm
    photo_y = top_y + 6 * mm
    c.setFillColor(colors.white)
    c.rect(photo_x, photo_y, photo_w, photo_h, fill=1, stroke=0)
    drew_photo = False
    if photo_bytes:
        try:
            img = ImageReader(BytesIO(photo_bytes))
            c.drawImage(img, photo_x, photo_y, width=photo_w, height=photo_h,
                        preserveAspectRatio=True, mask="auto")
            drew_photo = True
        except Exception:
            drew_photo = False
    if not drew_photo and photo_url:
        try:
            with urllib.request.urlopen(photo_url, timeout=5) as resp:
                img_bytes = resp.read()
            img = ImageReader(BytesIO(img_bytes))
            c.drawImage(img, photo_x, photo_y, width=photo_w, height=photo_h,
                        preserveAspectRatio=True, mask="auto")
            drew_photo = True
        except Exception:
            drew_photo = False
    if not drew_photo:
        # Initials avatar
        initials = "".join([w[0] for w in (client.get("full_name") or "?").split()[:2]]).upper()
        c.setFillColor(NAVY_DARK)
        c.rect(photo_x, photo_y, photo_w, photo_h, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(photo_x + photo_w / 2, photo_y + photo_h / 2 - 5, initials or "FP")

    # Name & details block (left side)
    left_x = x + 4 * mm
    detail_y = top_y + 26 * mm
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 11)
    # Truncate long names to fit
    display_name = name if len(name) <= 22 else name[:21] + "…"
    c.drawString(left_x, detail_y, display_name)

    c.setFont("Helvetica", 6)
    c.setFillColor(SILVER)
    c.drawString(left_x, detail_y - 3.2 * mm, "MEMBER NO.")
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.white)
    c.drawString(left_x, detail_y - 7.2 * mm, member_no or "—")

    c.setFont("Helvetica", 6)
    c.setFillColor(SILVER)
    c.drawString(left_x, detail_y - 11.2 * mm, "ISSUED")
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.white)
    c.drawString(left_x, detail_y - 14.4 * mm, _fmt_date(issued))

    c.setFont("Helvetica", 6)
    c.setFillColor(SILVER)
    c.drawString(left_x + 22 * mm, detail_y - 11.2 * mm, "EXPIRES")
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.white)
    c.drawString(left_x + 22 * mm, detail_y - 14.4 * mm, _fmt_date(expires))

    # Tagline strip
    c.setFillColor(NAVY_DARK)
    c.rect(x, top_y, card_w, 5 * mm, fill=1, stroke=0)
    c.setFillColor(SILVER)
    c.setFont("Helvetica-Oblique", 6)
    c.drawCentredString(x + card_w / 2, top_y + 1.6 * mm,
                        "Pawn with confidence. Recover with dignity.")

    # ---------- BACK (white) ----------
    c.setFillColor(colors.white)
    c.rect(x, bot_y, card_w, card_h, fill=1, stroke=1)
    c.setStrokeColor(RULE)
    c.setLineWidth(0.3)
    c.rect(x, bot_y, card_w, card_h, fill=0, stroke=1)

    # Header strip
    c.setFillColor(NAVY)
    c.rect(x, bot_y + card_h - 5 * mm, card_w, 5 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x + 3 * mm, bot_y + card_h - 3.5 * mm, "FATIN PENHORES  ·  MEMBER VERIFICATION")

    # QR code (left)
    qr_size = 30 * mm
    qr_x = x + 4 * mm
    qr_y = bot_y + (card_h - qr_size) / 2 - 2 * mm
    try:
        qr_img = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                                box_size=8, border=1)
        qr_img.add_data(verify_url)
        qr_img.make(fit=True)
        pil_img = qr_img.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_buf = BytesIO()
        pil_img.save(qr_buf, format="PNG")
        qr_buf.seek(0)
        c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size, mask="auto")
    except Exception:
        c.setFillColor(colors.lightgrey)
        c.rect(qr_x, qr_y, qr_size, qr_size, fill=1, stroke=0)

    # Right-side text block
    right_x = qr_x + qr_size + 4 * mm
    text_y = bot_y + card_h - 9 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(right_x, text_y, "SCAN TO VERIFY")
    c.setFont("Helvetica", 6)
    c.setFillColor(MUTED)
    c.drawString(right_x, text_y - 2.6 * mm, "Skan atu verifika kartaun ida-ne'e")

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 6)
    c.drawString(right_x, text_y - 7 * mm, "ADDRESS")
    c.setFont("Helvetica", 5.5)
    c.setFillColor(MUTED)
    c.drawString(right_x, text_y - 9.2 * mm, COMPANY_ADDR)

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 6)
    c.drawString(right_x, text_y - 12.5 * mm, "CONTACT")
    c.setFont("Helvetica", 5.5)
    c.setFillColor(MUTED)
    c.drawString(right_x, text_y - 14.7 * mm, "WhatsApp: +670 78372678")
    c.drawString(right_x, text_y - 17.0 * mm, "fatinpenhores@gmail.com")

    # Fine print bottom
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Oblique", 4.5)
    c.drawString(x + 3 * mm, bot_y + 3 * mm,
                 "Property of Fatin Penhores Unipessoal, Lda. If found, please return.")
    c.setFont("Helvetica", 4.5)
    c.drawRightString(x + card_w - 3 * mm, bot_y + 3 * mm, f"#{member_no}")

    # Cut guide (dashed rectangles are already the card borders — add subtle marks)
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.setLineWidth(0.2)
    c.setDash(1, 2)
    c.rect(x, top_y, card_w, card_h, fill=0, stroke=1)
    c.setDash()

    # Page footer note
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7)
    c.drawCentredString(page_w / 2, 15 * mm,
                        "Cut along the dashed border. Front (top) · Back (bottom).")
    if status and status != "ACTIVE":
        c.setFillColor(colors.HexColor("#993333"))
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(page_w / 2, 10 * mm, f"STATUS: {status}")

    c.showPage()
    c.save()
    return buf.getvalue()
