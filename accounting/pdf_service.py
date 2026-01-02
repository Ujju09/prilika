import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from decimal import Decimal

def generate_journal_pdf(entries):
    """
    Generate a PDF for the journal entries in ICAI format.
    Returns a BytesIO buffer containing the PDF.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
        title="Journal Register"
    )

    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'JournalTitle',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        spaceAfter=20
    )
    elements.append(Paragraph("JOURNAL REGISTER", title_style))
    
    # Table Data
    # Headers
    data = [['Date', 'Particulars', 'L.F.', 'Debit (Rs.)', 'Credit (Rs.)']]
    
    # Rows
    for entry in entries:
        # Date only on first line of entry
        date_str = entry.transaction_date.strftime('%Y-%m-%d')
        
        # 1. Debit Lines
        first_line = True
        for line in entry.lines.all():
            if line.debit > 0:
                row = [
                    date_str if first_line else '',
                    f"{line.account_name} Dr.",
                    '', # LF
                    f"{line.debit:,.2f}",
                    ''  # Credit empty
                ]
                data.append(row)
                first_line = False
        
        # 2. Credit Lines
        for line in entry.lines.all():
            if line.credit > 0:
                # Add indentation for "To ..."
                # ReportLab Table doesn't support rich HTML in cells easily without Paragraphs,
                # but standard text indentation works with non-breaking spaces or just visual indent
                # We'll use prefix string
                row = [
                    date_str if first_line else '',
                    f"   To {line.account_name}",
                    '',
                    '',
                    f"{line.credit:,.2f}"
                ]
                data.append(row)
                first_line = False
                
        # 3. Narration
        row = [
            '',
            f"   (Being {entry.narration})",
            '',
            '',
            ''
        ]
        data.append(row)
        
        # Spacer row (optional, acts as visual separator)
        data.append(['', '', '', '', ''])

    # Column Widths
    # A4 width = ~595 pts. Margins 60 total. Usable = 535.
    # Col widths: Date(12%), Particulars(58%), LF(6%), Debit(12%), Credit(12%)
    col_widths = [65, 310, 30, 65, 65]

    # Style
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
        ('ALIGN', (0, 1), (0, -1), 'CENTER'), # Date
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),   # Particulars
        ('ALIGN', (2, 1), (2, -1), 'CENTER'), # LF
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'), # Amounts
        
        # Fonts
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        
        # Remove borders for data rows to look like journal
        # We keep vertical lines for columns usually, but let's stick to simple grid for readability
        ('GRID', (0, 1), (-1, -1), 0.25, colors.lightgrey),
        
        # Specific styling for Narration rows? 
        # Hard to target dynamically without logic, but we can assume logic in loop above handles content.
    ])
    
    # Styling narration rows (italic) - this is tricky with TableStyle alone iteratively
    # Instead, we rely on the content string format being distinct.
    
    t = Table(data, colWidths=col_widths)
    t.setStyle(table_style)
    
    elements.append(t)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer
