"""
PDF generation service for Balance Sheet.
"""
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from decimal import Decimal


def generate_balance_sheet_pdf(bs_data):
    """
    Generate a PDF for the Balance Sheet in ICAI format.

    Args:
        bs_data: Dictionary containing balance sheet data from get_balance_sheet()

    Returns:
        BytesIO buffer containing the PDF
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
        title="Balance Sheet"
    )

    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        spaceAfter=10
    )
    elements.append(Paragraph("BALANCE SHEET", title_style))

    # Date
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontStyle='italic',
        spaceAfter=20
    )
    as_of_date = bs_data['as_of_date'].strftime('%d %B %Y')
    elements.append(Paragraph(f"As at: {as_of_date}", date_style))

    # Table Data
    data = [['Account Code', 'Particulars', 'Amount (Rs.)']]

    # Track row indices for styling
    section_row_indices = []
    subsection_row_indices = []
    subtotal_row_indices = []
    total_row_indices = []

    # ASSETS SECTION
    assets_header_idx = len(data)
    section_row_indices.append(assets_header_idx)
    data.append(['ASSETS', '', ''])

    # Current Assets
    if bs_data['current_assets']:
        current_assets_header_idx = len(data)
        subsection_row_indices.append(current_assets_header_idx)
        data.append(['Current Assets', '', ''])

        for account in bs_data['current_assets']:
            row = [
                account['code'],
                f"  {account['name']}",
                f"{account['balance']:,.2f}"
            ]
            data.append(row)

        # Current Assets Subtotal
        subtotal_idx = len(data)
        subtotal_row_indices.append(subtotal_idx)
        data.append(['', 'Total Current Assets', f"{bs_data['total_current_assets']:,.2f}"])

    # Non-Current Assets
    if bs_data['non_current_assets']:
        non_current_assets_header_idx = len(data)
        subsection_row_indices.append(non_current_assets_header_idx)
        data.append(['Non-Current Assets', '', ''])

        for account in bs_data['non_current_assets']:
            row = [
                account['code'],
                f"  {account['name']}",
                f"{account['balance']:,.2f}"
            ]
            data.append(row)

        # Non-Current Assets Subtotal
        subtotal_idx = len(data)
        subtotal_row_indices.append(subtotal_idx)
        data.append(['', 'Total Non-Current Assets', f"{bs_data['total_non_current_assets']:,.2f}"])

    # Total Assets
    total_assets_idx = len(data)
    total_row_indices.append(total_assets_idx)
    data.append(['', 'TOTAL ASSETS', f"{bs_data['total_assets']:,.2f}"])

    # LIABILITIES SECTION
    liabilities_header_idx = len(data)
    section_row_indices.append(liabilities_header_idx)
    data.append(['LIABILITIES', '', ''])

    # Current Liabilities
    if bs_data['current_liabilities']:
        current_liabilities_header_idx = len(data)
        subsection_row_indices.append(current_liabilities_header_idx)
        data.append(['Current Liabilities', '', ''])

        for account in bs_data['current_liabilities']:
            row = [
                account['code'],
                f"  {account['name']}",
                f"{account['balance']:,.2f}"
            ]
            data.append(row)

        # Current Liabilities Subtotal
        subtotal_idx = len(data)
        subtotal_row_indices.append(subtotal_idx)
        data.append(['', 'Total Current Liabilities', f"{bs_data['total_current_liabilities']:,.2f}"])
    else:
        current_liabilities_header_idx = len(data)
        subsection_row_indices.append(current_liabilities_header_idx)
        data.append(['Current Liabilities', '', ''])

        subtotal_idx = len(data)
        subtotal_row_indices.append(subtotal_idx)
        data.append(['', 'Total Current Liabilities', '0.00'])

    # Total Liabilities
    total_liabilities_idx = len(data)
    total_row_indices.append(total_liabilities_idx)
    data.append(['', 'TOTAL LIABILITIES', f"{bs_data['total_liabilities']:,.2f}"])

    # EQUITY SECTION
    equity_header_idx = len(data)
    section_row_indices.append(equity_header_idx)
    data.append(['EQUITY', '', ''])

    for account in bs_data['equity_accounts']:
        if account['balance'] < 0:
            amount_str = f"({abs(account['balance']):,.2f})"
        else:
            amount_str = f"{account['balance']:,.2f}"

        row = [
            account['code'],
            f"  {account['name']}",
            amount_str
        ]
        data.append(row)

    # Retained Earnings
    if bs_data['retained_earnings'] < 0:
        re_str = f"({abs(bs_data['retained_earnings']):,.2f})"
    else:
        re_str = f"{bs_data['retained_earnings']:,.2f}"

    data.append(['', '  Retained Earnings', re_str])

    # Total Equity
    total_equity_idx = len(data)
    total_row_indices.append(total_equity_idx)
    data.append(['', 'TOTAL EQUITY', f"{bs_data['total_equity']:,.2f}"])

    # Grand Total
    grand_total_idx = len(data)
    data.append(['', 'TOTAL LIABILITIES + EQUITY', f"{bs_data['liabilities_plus_equity']:,.2f}"])

    # Column Widths
    col_widths = [80, 320, 100]

    # Table Style
    table_style = TableStyle([
        # Header formatting
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, 0), 0.5, colors.grey),

        # Data alignment
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Account Code
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),    # Particulars
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Amounts

        # Fonts
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),

        # Grid
        ('GRID', (0, 1), (-1, -1), 0.25, colors.lightgrey),

        # Grand total row
        ('BACKGROUND', (0, grand_total_idx), (-1, grand_total_idx), colors.grey),
        ('TEXTCOLOR', (0, grand_total_idx), (-1, grand_total_idx), colors.whitesmoke),
        ('FONTNAME', (0, grand_total_idx), (-1, grand_total_idx), 'Helvetica-Bold'),
        ('FONTSIZE', (0, grand_total_idx), (-1, grand_total_idx), 11),
    ])

    # Add section header styling
    for idx in section_row_indices:
        table_style.add('BACKGROUND', (0, idx), (-1, idx), colors.lightgrey)
        table_style.add('FONTNAME', (0, idx), (-1, idx), 'Helvetica-Bold')
        table_style.add('SPAN', (0, idx), (-1, idx))
        table_style.add('ALIGN', (0, idx), (-1, idx), 'LEFT')

    # Add subsection header styling
    for idx in subsection_row_indices:
        table_style.add('BACKGROUND', (0, idx), (-1, idx), colors.Color(0.9, 0.9, 0.9))
        table_style.add('FONTNAME', (0, idx), (-1, idx), 'Helvetica-Bold')
        table_style.add('SPAN', (0, idx), (-1, idx))
        table_style.add('ALIGN', (0, idx), (-1, idx), 'LEFT')
        table_style.add('FONTSIZE', (0, idx), (-1, idx), 8)

    # Add subtotal styling
    for idx in subtotal_row_indices:
        table_style.add('BACKGROUND', (0, idx), (-1, idx), colors.whitesmoke)
        table_style.add('FONTNAME', (0, idx), (-1, idx), 'Helvetica-Bold')
        table_style.add('FONTSIZE', (0, idx), (-1, idx), 9)
        table_style.add('FONTNAME', (1, idx), (1, idx), 'Helvetica-Oblique')

    # Add total styling
    for idx in total_row_indices:
        table_style.add('BACKGROUND', (0, idx), (-1, idx), colors.lightgrey)
        table_style.add('FONTNAME', (0, idx), (-1, idx), 'Helvetica-Bold')
        table_style.add('FONTSIZE', (0, idx), (-1, idx), 10)

    t = Table(data, colWidths=col_widths)
    t.setStyle(table_style)

    elements.append(t)

    # Add balance verification note
    elements.append(Spacer(1, 20))
    balance_status_style = ParagraphStyle(
        'BalanceStatus',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontWeight='bold'
    )

    if bs_data['is_balanced']:
        status_text = f"✓ Balance Sheet Equation: Assets = Liabilities + Equity = Rs. {bs_data['total_assets']:,.2f}"
    else:
        status_text = f"⚠ Balance Sheet NOT Balanced | Difference: Rs. {bs_data['difference']:,.2f}"

    elements.append(Paragraph(status_text, balance_status_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer
