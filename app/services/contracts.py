from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import io
from datetime import datetime, date, timedelta
from typing import Optional, List
from app.logger import get_logger

logger = get_logger(__name__)

def generate_contract(
    client: dict,
    contract_data: dict
) -> bytes:
    """Generate a professional service contract"""
    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.25)

    # Title
    title = doc.add_heading("SERVICE AGREEMENT", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    # Contract metadata
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(
        f"Contract #: {contract_data.get('contract_number', 'N/A')}\n"
        f"Date: {datetime.now().strftime('%B %d, %Y')}\n"
        f"Valid Until: {contract_data.get('valid_until', 'N/A')}"
    ).italic = True

    doc.add_paragraph()

    # Parties
    doc.add_heading("PARTIES", level=1)

    parties_table = doc.add_table(rows=0, cols=2)
    parties_table.style = "Table Grid"

    row = parties_table.add_row().cells
    row[0].text = "Service Provider"
    row[1].text = contract_data.get(
        "provider_name", "Your Company Name"
    )
    row[0].paragraphs[0].runs[0].bold = True

    row = parties_table.add_row().cells
    row[0].text = "Provider Address"
    row[1].text = contract_data.get(
        "provider_address", "Your Address"
    )
    row[0].paragraphs[0].runs[0].bold = True

    row = parties_table.add_row().cells
    row[0].text = "Client Name"
    row[1].text = client.get("name", "")
    row[0].paragraphs[0].runs[0].bold = True

    row = parties_table.add_row().cells
    row[0].text = "Client Company"
    row[1].text = client.get("company", "N/A")
    row[0].paragraphs[0].runs[0].bold = True

    row = parties_table.add_row().cells
    row[0].text = "Client Email"
    row[1].text = client.get("email", "N/A")
    row[0].paragraphs[0].runs[0].bold = True

    doc.add_paragraph()

    # Scope of Work
    doc.add_heading("1. SCOPE OF WORK", level=1)
    doc.add_paragraph(
        contract_data.get(
            "scope_of_work",
            f"Provider agrees to deliver the following "
            f"services: {client.get('service', 'As discussed')}"
        )
    )

    # Deliverables
    if contract_data.get("deliverables"):
        doc.add_heading("2. DELIVERABLES", level=1)
        for i, d in enumerate(
            contract_data["deliverables"], 1
        ):
            doc.add_paragraph(
                f"{i}. {d}",
                style="List Number"
            )

    # Timeline
    doc.add_heading("3. TIMELINE", level=1)

    timeline_table = doc.add_table(rows=0, cols=2)
    timeline_table.style = "Table Grid"

    header = timeline_table.add_row().cells
    header[0].text = "Milestone"
    header[1].text = "Date"
    header[0].paragraphs[0].runs[0].bold = True
    header[1].paragraphs[0].runs[0].bold = True

    for milestone in contract_data.get("timeline", []):
        row = timeline_table.add_row().cells
        row[0].text = milestone.get("milestone", "")
        row[1].text = milestone.get("date", "")

    doc.add_paragraph()

    # Payment Terms
    doc.add_heading("4. PAYMENT TERMS", level=1)

    payment_table = doc.add_table(rows=0, cols=2)
    payment_table.style = "Table Grid"

    payment_fields = [
        ("Total Amount", f"${contract_data.get('total_amount', '0.00')}"),
        ("Payment Schedule", contract_data.get("payment_schedule", "Net 30")),
        ("Payment Method", contract_data.get("payment_method", "Bank Transfer")),
        ("Late Fee", contract_data.get("late_fee", "1.5% per month"))
    ]

    for label, value in payment_fields:
        row = payment_table.add_row().cells
        row[0].text = label
        row[1].text = value
        row[0].paragraphs[0].runs[0].bold = True

    doc.add_paragraph()

    # Terms and Conditions
    doc.add_heading("5. TERMS AND CONDITIONS", level=1)

    terms = contract_data.get("terms", [
        "Provider will maintain confidentiality of all client information.",
        "Client will provide timely feedback and approvals.",
        "Either party may terminate with 30 days written notice.",
        "Provider retains ownership of work until full payment received.",
        "This agreement is governed by the laws of Utah, USA.",
        "Any disputes will be resolved through mediation.",
        "Force majeure clause applies to unforeseeable circumstances.",
        "Amendments must be in writing and signed by both parties."
    ])

    for i, term in enumerate(terms, 1):
        doc.add_paragraph(f"{i}. {term}")

    doc.add_paragraph()

    # Confidentiality
    doc.add_heading("6. CONFIDENTIALITY", level=1)
    doc.add_paragraph(
        contract_data.get(
            "confidentiality",
            "Both parties agree to keep all shared information "
            "strictly confidential and not to disclose it to "
            "third parties without prior written consent."
        )
    )

    # Intellectual Property
    doc.add_heading("7. INTELLECTUAL PROPERTY", level=1)
    doc.add_paragraph(
        contract_data.get(
            "ip_clause",
            "Upon receipt of full payment, all deliverables "
            "become the exclusive property of the Client. "
            "Provider retains the right to use the work "
            "in portfolio with Client approval."
        )
    )

    # Signatures
    doc.add_paragraph()
    doc.add_heading("SIGNATURES", level=1)

    sig_table = doc.add_table(rows=0, cols=2)
    sig_table.style = "Table Grid"

    row = sig_table.add_row().cells
    row[0].text = "Service Provider"
    row[1].text = "Client"
    row[0].paragraphs[0].runs[0].bold = True
    row[1].paragraphs[0].runs[0].bold = True

    row = sig_table.add_row().cells
    row[0].text = "\n\nSignature: _______________________"
    row[1].text = "\n\nSignature: _______________________"

    row = sig_table.add_row().cells
    row[0].text = f"Name: {contract_data.get('provider_name', '')}"
    row[1].text = f"Name: {client.get('name', '')}"

    row = sig_table.add_row().cells
    row[0].text = "Date: _______________________"
    row[1].text = "Date: _______________________"

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    logger.info(
        f"Contract generated for client: "
        f"{client.get('client_id')}"
    )

    return buffer.getvalue()


def generate_invoice(
    client: dict,
    invoice_data: dict
) -> bytes:
    """Generate a professional invoice"""
    doc = Document()

    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.25)

    # Header
    title = doc.add_heading("INVOICE", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    # Invoice details
    info_table = doc.add_table(rows=0, cols=2)
    info_table.style = "Table Grid"

    invoice_fields = [
        ("Invoice #", invoice_data.get(
            "invoice_number",
            f"INV-{datetime.now().strftime('%Y%m%d%H%M')}"
        )),
        ("Invoice Date", datetime.now().strftime("%B %d, %Y")),
        ("Due Date", invoice_data.get(
            "due_date",
            (date.today() + timedelta(days=30)).strftime("%B %d, %Y")
        )),
        ("Status", invoice_data.get("status", "Unpaid"))
    ]

    for label, value in invoice_fields:
        row = info_table.add_row().cells
        row[0].text = label
        row[1].text = str(value)
        row[0].paragraphs[0].runs[0].bold = True

    doc.add_paragraph()

    # Bill To / From
    doc.add_heading("BILLING DETAILS", level=1)

    billing_table = doc.add_table(rows=0, cols=2)
    billing_table.style = "Table Grid"

    row = billing_table.add_row().cells
    row[0].text = "From"
    row[1].text = "Bill To"
    row[0].paragraphs[0].runs[0].bold = True
    row[1].paragraphs[0].runs[0].bold = True

    row = billing_table.add_row().cells
    row[0].text = (
        f"{invoice_data.get('provider_name', 'Your Company')}\n"
        f"{invoice_data.get('provider_email', '')}\n"
        f"{invoice_data.get('provider_address', '')}"
    )
    row[1].text = (
        f"{client.get('name', '')}\n"
        f"{client.get('company', '')}\n"
        f"{client.get('email', '')}\n"
        f"{client.get('phone', '')}"
    )

    doc.add_paragraph()

    # Line Items
    doc.add_heading("SERVICES", level=1)

    items_table = doc.add_table(rows=0, cols=4)
    items_table.style = "Table Grid"

    header = items_table.add_row().cells
    for i, h in enumerate(
        ["Description", "Quantity", "Unit Price", "Total"]
    ):
        header[i].text = h
        header[i].paragraphs[0].runs[0].bold = True

    subtotal = 0
    for item in invoice_data.get("line_items", []):
        qty = float(item.get("quantity", 1))
        price = float(item.get("unit_price", 0))
        total = qty * price
        subtotal += total

        row = items_table.add_row().cells
        row[0].text = item.get("description", "")
        row[1].text = str(qty)
        row[2].text = f"${price:.2f}"
        row[3].text = f"${total:.2f}"

    doc.add_paragraph()

    # Totals
    totals_table = doc.add_table(rows=0, cols=2)
    totals_table.style = "Table Grid"

    tax_rate = float(invoice_data.get("tax_rate", 0))
    tax_amount = subtotal * (tax_rate / 100)
    discount = float(invoice_data.get("discount", 0))
    total_due = subtotal + tax_amount - discount

    totals = [
        ("Subtotal", f"${subtotal:.2f}"),
        (f"Tax ({tax_rate}%)", f"${tax_amount:.2f}"),
        ("Discount", f"-${discount:.2f}"),
        ("TOTAL DUE", f"${total_due:.2f}")
    ]

    for label, value in totals:
        row = totals_table.add_row().cells
        row[0].text = label
        row[1].text = value
        row[0].paragraphs[0].runs[0].bold = True
        if label == "TOTAL DUE":
            row[1].paragraphs[0].runs[0].bold = True

    doc.add_paragraph()

    # Payment Instructions
    doc.add_heading("PAYMENT INSTRUCTIONS", level=1)
    doc.add_paragraph(
        invoice_data.get(
            "payment_instructions",
            "Please make payment via bank transfer to the "
            "account details provided separately. Reference "
            "the invoice number in your payment."
        )
    )

    # Notes
    if invoice_data.get("notes"):
        doc.add_heading("NOTES", level=1)
        doc.add_paragraph(invoice_data["notes"])

    # Footer
    doc.add_paragraph()
    footer = doc.add_paragraph(
        "Thank you for your business!"
    )
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    logger.info(
        f"Invoice generated for client: "
        f"{client.get('client_id')}"
    )

    return buffer.getvalue()


def generate_proposal(
    client: dict,
    proposal_data: dict
) -> bytes:
    """Generate a professional business proposal"""
    doc = Document()

    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.25)

    # Cover
    title = doc.add_heading("BUSINESS PROPOSAL", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    subtitle = doc.add_paragraph(
        f"Prepared for: {client.get('company') or client.get('name')}\n"
        f"Prepared by: {proposal_data.get('provider_name', 'Your Company')}\n"
        f"Date: {datetime.now().strftime('%B %d, %Y')}\n"
        f"Valid Until: {proposal_data.get('valid_until', 'N/A')}"
    )
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    # Executive Summary
    doc.add_heading("EXECUTIVE SUMMARY", level=1)
    doc.add_paragraph(
        proposal_data.get(
            "executive_summary",
            f"We are pleased to present this proposal for "
            f"{client.get('service', 'our services')} to "
            f"{client.get('company') or client.get('name')}."
        )
    )

    # Problem Statement
    doc.add_heading("PROBLEM STATEMENT", level=1)
    doc.add_paragraph(
        proposal_data.get(
            "problem_statement",
            client.get("notes", "As discussed in our meetings.")
        )
    )

    # Proposed Solution
    doc.add_heading("PROPOSED SOLUTION", level=1)
    doc.add_paragraph(
        proposal_data.get(
            "proposed_solution",
            f"We propose to deliver {client.get('service', 'our services')} "
            f"tailored to your specific needs."
        )
    )

    # Scope of Work
    if proposal_data.get("scope_items"):
        doc.add_heading("SCOPE OF WORK", level=1)
        for item in proposal_data["scope_items"]:
            doc.add_paragraph(f"• {item}")

    # Timeline
    if proposal_data.get("timeline"):
        doc.add_heading("PROJECT TIMELINE", level=1)

        timeline_table = doc.add_table(rows=0, cols=3)
        timeline_table.style = "Table Grid"

        header = timeline_table.add_row().cells
        for i, h in enumerate(
            ["Phase", "Description", "Duration"]
        ):
            header[i].text = h
            header[i].paragraphs[0].runs[0].bold = True

        for phase in proposal_data["timeline"]:
            row = timeline_table.add_row().cells
            row[0].text = phase.get("phase", "")
            row[1].text = phase.get("description", "")
            row[2].text = phase.get("duration", "")

        doc.add_paragraph()

    # Investment
    doc.add_heading("INVESTMENT", level=1)

    if proposal_data.get("pricing_tiers"):
        for tier in proposal_data["pricing_tiers"]:
            doc.add_heading(
                tier.get("name", "Option"),
                level=2
            )
            doc.add_paragraph(
                f"Price: ${tier.get('price', '0')}\n"
                f"{tier.get('description', '')}"
            )
            if tier.get("includes"):
                doc.add_paragraph("Includes:")
                for item in tier["includes"]:
                    doc.add_paragraph(
                        f"  ✓ {item}",
                        style="List Bullet"
                    )
    else:
        doc.add_paragraph(
            f"Total Investment: "
            f"${proposal_data.get('total_price', 'TBD')}\n"
            f"{proposal_data.get('pricing_notes', '')}"
        )

    doc.add_paragraph()

    # Why Us
    if proposal_data.get("why_us"):
        doc.add_heading("WHY CHOOSE US", level=1)
        for point in proposal_data["why_us"]:
            doc.add_paragraph(f"✓ {point}")

    # Next Steps
    doc.add_heading("NEXT STEPS", level=1)
    next_steps = proposal_data.get("next_steps", [
        "Review this proposal",
        "Schedule a follow-up call",
        "Sign the service agreement",
        "Begin project kickoff"
    ])
    for i, step in enumerate(next_steps, 1):
        doc.add_paragraph(f"{i}. {step}")

    # Call to Action
    doc.add_paragraph()
    cta = doc.add_paragraph(
        proposal_data.get(
            "call_to_action",
            f"Ready to get started? Contact us at "
            f"{proposal_data.get('provider_email', 'your@email.com')}"
        )
    )
    cta.alignment = WD_ALIGN_PARAGRAPH.CENTER

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    logger.info(
        f"Proposal generated for: "
        f"{client.get('client_id')}"
    )

    return buffer.getvalue()