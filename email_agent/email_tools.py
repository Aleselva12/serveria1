import json
import os
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from langchain_core.tools import tool
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from email_agent.email_connector import (
    messages_for_day,
    save_as_draft,
    search_messages,
)


QUOTE_ROOT = Path(
    os.getenv(
        "CORA_QUOTE_ROOT",
        str(Path(__file__).resolve().parents[1] / "quotes"),
    )
).expanduser().resolve()


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


@tool
def search_email_archive(query: str, max_results: int = 30) -> str:
    """
    Cerca nell'archivio Gmail usando la sintassi di ricerca Gmail.
    Esempi: 'from:cliente@example.com ombrelloni', 'subject:preventivo Rossi'.
    """
    try:
        emails = search_messages(query=query, max_results=max_results)
        return _json({
            "status": "ok",
            "query": query,
            "count": len(emails),
            "emails": emails,
        })
    except Exception as error:
        return _json({"status": "error", "error": str(error)})


@tool
def get_daily_emails(day_iso: str = "") -> str:
    """
    Recupera le email di un giorno specifico nel formato YYYY-MM-DD.
    Se day_iso è vuoto usa la data locale corrente.
    """
    try:
        selected_day = date.fromisoformat(day_iso) if day_iso else date.today()
        emails = messages_for_day(selected_day)
        return _json({
            "status": "ok",
            "day": selected_day.isoformat(),
            "count": len(emails),
            "emails": emails,
        })
    except Exception as error:
        return _json({"status": "error", "error": str(error)})


@tool
def save_email_draft(to_email: str, subject: str, body: str) -> str:
    """
    Salva una bozza Gmail. Non invia mai la mail.
    Usare solo quando l'utente chiede esplicitamente di salvare una bozza.
    """
    try:
        result = save_as_draft(to_email, subject, body)
        return _json({
            "status": "ok",
            "draft_id": result.get("id"),
            "message_id": result.get("message", {}).get("id"),
        })
    except Exception as error:
        return _json({"status": "error", "error": str(error)})


@tool
def generate_quote_pdf(
    customer_name: str,
    items_json: str,
    quote_number: str = "",
    quote_date: str = "",
    customer_address: str = "",
    notes: str = "",
    vat_percent: float = 22.0,
    filename: str = "",
) -> str:
    """
    Genera un preventivo PDF locale.

    items_json deve essere una lista JSON di righe:
    [{"description":"Ombrellone...", "quantity":2, "unit_price":150.0}]
    """
    try:
        items = json.loads(items_json)
        if not isinstance(items, list) or not items:
            raise ValueError("items_json deve contenere una lista non vuota.")

        normalized = []
        subtotal = 0.0

        for index, item in enumerate(items, start=1):
            description = str(item.get("description", "")).strip()
            quantity = float(item.get("quantity", 0))
            unit_price = float(item.get("unit_price", 0))

            if not description:
                raise ValueError(f"Descrizione mancante alla riga {index}.")
            if quantity <= 0:
                raise ValueError(f"Quantità non valida alla riga {index}.")
            if unit_price < 0:
                raise ValueError(f"Prezzo non valido alla riga {index}.")

            line_total = quantity * unit_price
            subtotal += line_total
            normalized.append({
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
            })

        vat = subtotal * (float(vat_percent) / 100.0)
        total = subtotal + vat

        QUOTE_ROOT.mkdir(parents=True, exist_ok=True)

        safe_number = (
            quote_number.strip().replace("/", "-").replace("\\", "-")
            or date.today().strftime("%Y%m%d")
        )
        output_name = filename.strip() or f"preventivo_{safe_number}.pdf"
        if not output_name.lower().endswith(".pdf"):
            output_name += ".pdf"

        output_path = (QUOTE_ROOT / output_name).resolve()
        if output_path != QUOTE_ROOT and QUOTE_ROOT not in output_path.parents:
            raise ValueError("Percorso PDF non consentito.")

        styles = getSampleStyleSheet()
        right = ParagraphStyle(
            "Right",
            parent=styles["Normal"],
            alignment=TA_RIGHT,
        )

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
        )

        story = [
            Paragraph("PREVENTIVO", styles["Title"]),
            Spacer(1, 5 * mm),
            Paragraph(
                f"<b>Cliente:</b> {escape(customer_name)}",
                styles["Normal"],
            ),
        ]

        if customer_address:
            story.append(
                Paragraph(
                    f"<b>Indirizzo:</b> {escape(customer_address)}",
                    styles["Normal"],
                )
            )
        if quote_number:
            story.append(
                Paragraph(
                    f"<b>Numero:</b> {escape(quote_number)}",
                    styles["Normal"],
                )
            )
        story.append(
            Paragraph(
                f"<b>Data:</b> {quote_date or date.today().isoformat()}",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 7 * mm))

        data = [[
            "Descrizione",
            "Q.tà",
            "Prezzo unit.",
            "Totale",
        ]]
        for item in normalized:
            data.append([
                item["description"],
                f'{item["quantity"]:g}',
                f'€ {item["unit_price"]:,.2f}',
                f'€ {item["line_total"]:,.2f}',
            ])

        table = Table(
            data,
            colWidths=[90 * mm, 20 * mm, 32 * mm, 32 * mm],
            repeatRows=1,
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
        ]))
        story.append(table)
        story.append(Spacer(1, 6 * mm))

        story.extend([
            Paragraph(f"Imponibile: € {subtotal:,.2f}", right),
            Paragraph(
                f"IVA {float(vat_percent):g}%: € {vat:,.2f}",
                right,
            ),
            Paragraph(f"<b>Totale: € {total:,.2f}</b>", right),
        ])

        if notes.strip():
            story.extend([
                Spacer(1, 7 * mm),
                Paragraph("<b>Note</b>", styles["Heading3"]),
                Paragraph(escape(notes.strip()), styles["Normal"]),
            ])

        doc.build(story)

        return _json({
            "status": "ok",
            "pdf_path": str(output_path),
            "subtotal": round(subtotal, 2),
            "vat": round(vat, 2),
            "total": round(total, 2),
            "items": normalized,
        })
    except Exception as error:
        return _json({"status": "error", "error": str(error)})


EMAIL_TOOLS = [
    search_email_archive,
    get_daily_emails,
    save_email_draft,
    generate_quote_pdf,
]
