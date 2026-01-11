"""
PDF generation service for Profit & Loss Statement.
"""
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from decimal import Decimal


def generate_pnl_pdf(pnl_data):
    """
    Generate a PDF for the Profit & Loss Statement in ICAI format.
    
    Args:
        pnl_data: Dictionary containing P&L data from get_profit_loss()
        
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
        title="Profit & Loss Statement"
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
    elements.append(Paragraph("PROFIT & LOSS STATEMENT", title_style))
    
    # Period
    period_style = ParagraphStyle(
        'PeriodStyle',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontStyle='italic',
        spaceAfter=20
    )
    elements.append(Paragraph(pnl_data['period_label'], period_style))
    
    # Table Data
    data = [['Particulars', 'Amount (Rs.)']]
    
    # INCOME SECTION
    income_header = ['INCOME', '']
    data.append(income_header)
    
    if pnl_data['income_accounts']:
        for account in pnl_data['income_accounts']:
            row = [
                f"  {account['name']} ({account['code']})",
                f"{account['amount']:,.2f}"
            ]
            data.append(row)
    else:
        data.append(['  No income recorded', '-'])
    
    # Income subtotal
    income_subtotal = ['Total Income', f"{pnl_data['total_income']:,.2f}"]
    data.append(income_subtotal)
    
    # EXPENSES SECTION
    expense_header = ['EXPENSES', '']
    data.append(expense_header)
    
    if pnl_data['expense_accounts']:
        for account in pnl_data['expense_accounts']:
            row = [
                f"  {account['name']} ({account['code']})",
                f"{account['amount']:,.2f}"
            ]
            data.append(row)
    else:
        data.append(['  No expenses recorded', '-'])
    
    # Expense subtotal
    expense_subtotal = ['Total Expenses', f"{pnl_data['total_expenses']:,.2f}"]
    data.append(expense_subtotal)
    
    # NET PROFIT/LOSS
    result_label = 'NET PROFIT' if pnl_data['is_profit'] else 'NET LOSS'
    net_row = [result_label, f"{pnl_data['net_profit_loss']:,.2f}"]
    data.append(net_row)
    
    # Column Widths
    col_widths = [380, 160]
    
    # Find special rows for styling
    income_header_idx = 1
    income_subtotal_idx = 1 + (len(pnl_data['income_accounts']) if pnl_data['income_accounts'] else 1) + 1
    expense_header_idx = income_subtotal_idx + 1
    expense_subtotal_idx = expense_header_idx + (len(pnl_data['expense_accounts']) if pnl_data['expense_accounts'] else 1) + 1
    net_row_idx = len(data) - 1
    
    # Table Style
    table_style = TableStyle([
        # Header formatting
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, 0), 0.5, colors.grey),
        
        # Data alignment
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        
        # Fonts
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        
        # Grid
        ('GRID', (0, 1), (-1, -1), 0.25, colors.lightgrey),
        
        # Section headers (INCOME, EXPENSES)
        ('BACKGROUND', (0, income_header_idx), (-1, income_header_idx), colors.lightgrey),
        ('FONTNAME', (0, income_header_idx), (-1, income_header_idx), 'Helvetica-Bold'),
        ('BACKGROUND', (0, expense_header_idx), (-1, expense_header_idx), colors.lightgrey),
        ('FONTNAME', (0, expense_header_idx), (-1, expense_header_idx), 'Helvetica-Bold'),
        
        # Subtotal rows
        ('BACKGROUND', (0, income_subtotal_idx), (-1, income_subtotal_idx), colors.whitesmoke),
        ('FONTNAME', (0, income_subtotal_idx), (-1, income_subtotal_idx), 'Helvetica-Bold'),
        ('BACKGROUND', (0, expense_subtotal_idx), (-1, expense_subtotal_idx), colors.whitesmoke),
        ('FONTNAME', (0, expense_subtotal_idx), (-1, expense_subtotal_idx), 'Helvetica-Bold'),
        
        # Net profit/loss row
        ('BACKGROUND', (0, net_row_idx), (-1, net_row_idx), colors.lightgrey),
        ('FONTNAME', (0, net_row_idx), (-1, net_row_idx), 'Helvetica-Bold'),
        ('FONTSIZE', (0, net_row_idx), (-1, net_row_idx), 11),
        ('TOPPADDING', (0, net_row_idx), (-1, net_row_idx), 12),
    ])
    
    t = Table(data, colWidths=col_widths)
    t.setStyle(table_style)
    
    elements.append(t)
    
    # Add result summary
    elements.append(Spacer(1, 20))
    result_style = ParagraphStyle(
        'ResultStyle',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=12,
        fontWeight='bold'
    )
    
    if pnl_data['is_profit']:
        result_text = f"✓ Net Profit: Rs. {pnl_data['net_profit_loss']:,.2f}"
    else:
        result_text = f"⚠ Net Loss: Rs. {pnl_data['net_profit_loss']:,.2f}"
    
    elements.append(Paragraph(result_text, result_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer
