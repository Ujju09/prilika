"""
PDF generation service for Trial Balance.
"""
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from decimal import Decimal


def generate_trial_balance_pdf(tb_data):
    """
    Generate a PDF for the Trial Balance in ICAI format.
    
    Args:
        tb_data: Dictionary containing trial balance data from get_trial_balance()
        
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
        title="Trial Balance"
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
    elements.append(Paragraph("TRIAL BALANCE", title_style))
    
    # Date
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontStyle='italic',
        spaceAfter=20
    )
    as_of_date = tb_data['as_of_date'].strftime('%d %B %Y')
    elements.append(Paragraph(f"As of: {as_of_date}", date_style))
    
    # Table Data
    data = [['Account Code', 'Account Name', 'Debit Balance (Rs.)', 'Credit Balance (Rs.)']]
    
    # Iterate through accounts by type
    for acc_type in tb_data['account_type_order']:
        accounts = tb_data['accounts_by_type'].get(acc_type, [])
        if accounts:
            # Add section header
            section_header = [tb_data['account_type_labels'][acc_type], '', '', '']
            data.append(section_header)
            
            # Add accounts
            for account in accounts:
                debit_str = f"{account['debit_balance']:,.2f}" if account['debit_balance'] > 0 else '-'
                credit_str = f"{account['credit_balance']:,.2f}" if account['credit_balance'] > 0 else '-'
                
                row = [
                    account['code'],
                    account['name'],
                    debit_str,
                    credit_str
                ]
                data.append(row)
    
    # Total row
    total_row = [
        '',
        'TOTAL',
        f"{tb_data['total_debit']:,.2f}",
        f"{tb_data['total_credit']:,.2f}"
    ]
    data.append(total_row)
    
    # Column Widths
    col_widths = [80, 280, 90, 90]
    
    # Find section header rows for styling
    section_row_indices = []
    for i, row in enumerate(data):
        if i > 0 and row[1] == '' and row[2] == '' and row[3] == '':
            section_row_indices.append(i)
    
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
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),    # Account Name
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Amounts
        
        # Fonts
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        
        # Grid
        ('GRID', (0, 1), (-1, -1), 0.25, colors.lightgrey),
        
        # Total row
        ('BACKGROUND', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, -1), (-1, -1), 12),
    ])
    
    # Add section header styling
    for idx in section_row_indices:
        table_style.add('BACKGROUND', (0, idx), (-1, idx), colors.lightgrey)
        table_style.add('FONTNAME', (0, idx), (-1, idx), 'Helvetica-Bold')
        table_style.add('SPAN', (0, idx), (-1, idx))
        table_style.add('ALIGN', (0, idx), (-1, idx), 'LEFT')
    
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
    
    if tb_data['is_balanced']:
        status_text = f"✓ Trial Balance is Balanced: Total Debits = Total Credits = Rs. {tb_data['total_debit']:,.2f}"
    else:
        status_text = f"⚠ Trial Balance is NOT Balanced | Difference: Rs. {tb_data['difference']:,.2f}"
    
    elements.append(Paragraph(status_text, balance_status_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer
