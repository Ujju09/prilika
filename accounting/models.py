"""
Django models for the accounting system.
Stores journal entries and their review status.
"""

from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class JournalEntry(models.Model):
    """
    Journal entry created by the Maker skill.
    Goes through review before posting.
    """
    
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        FLAGGED = 'flagged', 'Flagged for Review'
        PENDING_REVIEW = 'pending_review', 'Pending Review'
        APPROVED = 'approved', 'Approved'
        POSTED = 'posted', 'Posted'
        REJECTED = 'rejected', 'Rejected'
    
    class TransactionType(models.TextChoices):
        INVOICE = 'invoice', 'Invoice'
        RECEIPT = 'receipt', 'Receipt'
        RECEIPT_WITH_TDS = 'receipt_with_tds', 'Receipt with TDS'
        SALARY = 'salary', 'Salary'
        EXPENSE = 'expense', 'Expense'
        DRAWINGS = 'drawings', 'Drawings'
        CAPITAL = 'capital', 'Capital'
        GST_PAYMENT = 'gst_payment', 'GST Payment'

    
    # Entry identification
    entry_number = models.CharField(max_length=50, unique=True, blank=True)
    
    # Transaction details
    transaction_date = models.DateField()
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    narration = models.TextField()
    reference = models.CharField(max_length=100, blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )
    
    # Original input
    source_text = models.TextField(help_text="Original natural language input")
    
    # Maker output
    ai_reasoning = models.TextField(blank=True)
    ai_confidence = models.FloatField(default=0.0)
    ai_warnings = models.JSONField(default=list, blank=True)
    
    # Checker output
    checker_status = models.CharField(max_length=20, blank=True)  # approved/flagged
    checker_errors = models.JSONField(default=list, blank=True)
    checker_warnings = models.JSONField(default=list, blank=True)
    checker_summary = models.TextField(blank=True)
    
    @property
    def confidence_color(self) -> str:
        """Return color code based on confidence score (0.0 to 1.0)"""
        if self.ai_confidence > 0.8:
            return '#16a34a'  # Green
        elif self.ai_confidence > 0.5:
            return '#ca8a04'  # Yellow
        else:
            return '#dc2626'  # Red
    
    @property
    def status_color(self) -> str:
        """Return text color for status pill"""
        if self.status == self.Status.POSTED:
            return '#166534'  # Green-800
        elif self.status == self.Status.APPROVED:
            return '#1e40af'  # Blue-800
        return '#475569'  # Slate-600

    @property
    def status_bg_color(self) -> str:
        """Return background color for status pill"""
        if self.status == self.Status.POSTED:
            return '#dcfce7'  # Green-100
        elif self.status == self.Status.APPROVED:
            return '#dbeafe'  # Blue-100
        return '#f1f5f9'  # Slate-100
    
    # Review
    reviewed_by = models.CharField(max_length=100, blank=True)
    review_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-transaction_date', '-created_at']
        verbose_name_plural = 'Journal Entries'
    
    def save(self, *args, **kwargs):
        if not self.entry_number:
            # Generate entry number: JV-2024-00001
            year = self.transaction_date.year
            prefix = f"JV-{year}-"
            
            last = JournalEntry.objects.filter(
                entry_number__startswith=prefix
            ).order_by('-entry_number').first()
            
            if last:
                num = int(last.entry_number.split('-')[-1]) + 1
            else:
                num = 1
            
            self.entry_number = f"{prefix}{num:05d}"
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.entry_number} - {self.narration[:50]}"
    
    @property
    def total_amount(self) -> Decimal:
        return self.lines.aggregate(
            total=models.Sum('debit')
        )['total'] or Decimal('0')
    
    @property
    def is_balanced(self) -> bool:
        totals = self.lines.aggregate(
            total_debit=models.Sum('debit'),
            total_credit=models.Sum('credit')
        )
        debit = totals['total_debit'] or Decimal('0')
        credit = totals['total_credit'] or Decimal('0')
        return debit == credit
    
    def approve(self, reviewer: str, notes: str = ""):
        """Approve entry for posting"""
        from django.utils import timezone
        
        if not self.is_balanced:
            raise ValueError("Cannot approve unbalanced entry")
        
        self.status = self.Status.APPROVED
        self.reviewed_by = reviewer
        self.review_notes = notes
        self.reviewed_at = timezone.now()
        self.save()
    
    def reject(self, reviewer: str, notes: str):
        """Reject entry"""
        from django.utils import timezone
        
        self.status = self.Status.REJECTED
        self.reviewed_by = reviewer
        self.review_notes = notes
        self.reviewed_at = timezone.now()
        self.save()
    
    def post(self):
        """Post approved entry to books"""
        from django.utils import timezone
        
        if self.status != self.Status.APPROVED:
            raise ValueError("Only approved entries can be posted")
        
        self.status = self.Status.POSTED
        self.posted_at = timezone.now()
        self.save()


class JournalLine(models.Model):
    """Single debit/credit line in a journal entry"""
    
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    
    account_code = models.CharField(max_length=10)
    account_name = models.CharField(max_length=100)
    
    debit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    credit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    
    class Meta:
        ordering = ['id']
    
    def __str__(self):
        if self.debit > 0:
            return f"Dr. {self.account_name}: {self.debit}"
        return f"Cr. {self.account_name}: {self.credit}"


class Account(models.Model):
    """
    Chart of Accounts.
    Pre-populated with the 10 accounts defined in the skill.
    """
    
    class AccountType(models.TextChoices):
        ASSET = 'asset', 'Asset'
        LIABILITY = 'liability', 'Liability'
        INCOME = 'income', 'Income'
        EXPENSE = 'expense', 'Expense'
        EQUITY = 'equity', 'Equity'
    
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    account_subtype = models.CharField(max_length=50, blank=True, help_text="Subtype for finer classification (e.g., 'sundry_debtors', 'security_deposit')")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def is_current_asset(self) -> bool:
        """Check if this is a current asset for balance sheet classification"""
        if self.account_type != 'asset':
            return False
        # Non-current asset subtypes
        non_current_subtypes = ['security_deposit', 'fixed_asset', 'long_term_investment']
        return self.account_subtype not in non_current_subtypes
    
    @property
    def balance(self) -> Decimal:
        """Calculate current balance from posted entries"""
        lines = JournalLine.objects.filter(
            account_code=self.code,
            journal_entry__status='posted'
        ).aggregate(
            total_debit=models.Sum('debit'),
            total_credit=models.Sum('credit')
        )
        
        debit = lines['total_debit'] or Decimal('0')
        credit = lines['total_credit'] or Decimal('0')
        
        # Assets & Expenses = Debit balance
        # Liabilities, Income, Equity = Credit balance
        if self.account_type in ('asset', 'expense'):
            return debit - credit
        else:
            return credit - debit
    
    @classmethod
    def setup_chart_of_accounts(cls):
        """Create the standard chart of accounts"""
        accounts = [
            ('A001', 'SBI Current A/c', 'asset', 'cash_and_bank', 'Primary bank account'),
            ('A002', 'ICICI Current A/c', 'asset', 'cash_and_bank', 'Secondary bank account'),
            ('A003', 'Shree Cement A/c', 'asset', '', 'DEPRECATED - Split into A003-SD and A003-CR'),
            ('A003-SD', 'Shree Cement - Security Deposit', 'asset', 'security_deposit', 'Security deposit with Shree Cement - Non-Current Asset'),
            ('A003-CR', 'Shree Cement - Commission Receivable', 'asset', 'sundry_debtors', 'Commission receivable from Shree Cement - Current Asset'),
            ('A004', 'TDS Receivable', 'asset', 'tax_receivable', 'Tax deducted at source by payers'),
            ('L001', 'CGST Payable', 'liability', 'tax_payable', 'Central GST collected'),
            ('L002', 'SGST Payable', 'liability', 'tax_payable', 'State GST collected'),
            ('I001', 'CFA Commission', 'income', 'service_income', 'Commission income from CFA services'),
            ('E001', 'Salary Expense', 'expense', 'salary', 'Employee salaries'),
            ('E002', 'Rake Expense', 'expense', 'operational', 'Expenses related to rake operations and handling'),
            ('E003', 'Godown Expense', 'expense', 'operational', 'Expenses related to godown/warehouse operations'),
            ('E004', 'Miscellaneous Expense', 'expense', 'other', 'Other miscellaneous expenses not covered by specific categories'),
            ('EQ001', "Owner's Capital", 'equity', 'capital', 'Capital contributed by owner'),
            ('EQ002', "Owner's Drawings", 'equity', 'drawings', 'Withdrawals by owner'),
        ]
        
        for code, name, acc_type, subtype, desc in accounts:
            account, created = cls.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'account_type': acc_type,
                    'account_subtype': subtype,
                    'description': desc,
                    'is_active': False if code == 'A003' else True  # Mark old A003 as inactive
                }
            )
            # Update existing accounts with new subtypes if they don't have one
            if not created and not account.account_subtype and subtype:
                account.account_subtype = subtype
                account.save()
            # Deactivate A003 if it already exists
            if not created and code == 'A003':
                account.is_active = False
                account.description = desc
                account.save()


class AgentLog(models.Model):
    """
    Log of AI agent interactions for transparency and debugging.
    """
    
    class Stage(models.TextChoices):
        INPUT = 'input', 'Input Received'
        MAKER = 'maker', 'Maker Agent'
        VALIDATION = 'validation', 'Validation'
        CHECKER = 'checker', 'Checker Agent'
        COMPLETE = 'complete', 'Pipeline Complete'
    
    class Level(models.TextChoices):
        INFO = 'info', 'Info'
        WARN = 'warn', 'Warning'
        ERROR = 'error', 'Error'
        DEBUG = 'debug', 'Debug'

    session_id = models.CharField(max_length=50, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    stage = models.CharField(max_length=20, choices=Stage.choices)
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    message = models.TextField()
    
    # API specific details
    prompt_sent = models.TextField(blank=True)
    response_received = models.TextField(blank=True)
    input_tokens = models.IntegerField(null=True, blank=True)
    output_tokens = models.IntegerField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    
    # Link to entry if applicable
    journal_entry = models.ForeignKey(
        'JournalEntry', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='logs'
    )

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['session_id', 'timestamp']),
        ]

    def __str__(self):
        return f"[{self.timestamp}] {self.stage}: {self.message}"