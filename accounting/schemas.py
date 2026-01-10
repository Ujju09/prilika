"""
Pydantic schemas for the accounting agent.
These enforce structural correctness that the LLM must adhere to.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import Optional, Literal
from enum import Enum


# ============== Enums ==============

class TransactionType(str, Enum):
    INVOICE = "invoice"
    RECEIPT = "receipt"
    RECEIPT_WITH_TDS = "receipt_with_tds"
    SALARY = "salary"
    DRAWINGS = "drawings"
    CAPITAL = "capital"


class AccountCode(str, Enum):
    """Valid account codes from Chart of Accounts"""
    SBI_CURRENT = "A001"
    ICICI = "A002"
    SHREE_CEMENT = "A003"
    TDS_RECEIVABLE = "A004"
    CGST_PAYABLE = "L001"
    SGST_PAYABLE = "L002"
    CFA_COMMISSION = "I001"
    SALARY_EXPENSE = "E001"
    OWNER_CAPITAL = "EQ001"
    OWNER_DRAWINGS = "EQ002"


ACCOUNT_NAMES = {
    AccountCode.SBI_CURRENT: "SBI Current A/c",
    AccountCode.ICICI: "ICICI A/c",
    AccountCode.SHREE_CEMENT: "Shree Cement A/c",
    AccountCode.TDS_RECEIVABLE: "TDS Receivable",
    AccountCode.CGST_PAYABLE: "CGST Payable",
    AccountCode.SGST_PAYABLE: "SGST Payable",
    AccountCode.CFA_COMMISSION: "CFA Commission",
    AccountCode.SALARY_EXPENSE: "Salary Expense",
    AccountCode.OWNER_CAPITAL: "Owner's Capital",
    AccountCode.OWNER_DRAWINGS: "Owner's Drawings",
}


# ============== Journal Entry Schemas ==============

class JournalLine(BaseModel):
    """Single line in a journal entry"""
    
    account_code: AccountCode
    account_name: str
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    
    @field_validator('debit', 'credit', mode='before')
    @classmethod
    def parse_decimal(cls, v):
        if v is None:
            return Decimal("0")
        if isinstance(v, (int, float, str)):
            return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return v
    
    @model_validator(mode='after')
    def exactly_one_side(self):
        """Each line must have either debit OR credit, not both, not neither"""
        has_debit = self.debit > 0
        has_credit = self.credit > 0
        
        if has_debit and has_credit:
            raise ValueError(
                f"Line for {self.account_name} has both debit ({self.debit}) and credit ({self.credit})"
            )
        if not has_debit and not has_credit:
            raise ValueError(
                f"Line for {self.account_name} has neither debit nor credit"
            )
        return self


class JournalEntry(BaseModel):
    """Complete journal entry from Maker"""
    
    transaction_date: date
    transaction_type: TransactionType
    narration: str = Field(min_length=1)
    reference: Optional[str] = None
    lines: list[JournalLine] = Field(min_length=2)
    reasoning: str
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    
    @model_validator(mode='after')
    def must_balance(self):
        """Debits must equal credits — fundamental accounting rule"""
        total_debit = sum(line.debit for line in self.lines)
        total_credit = sum(line.credit for line in self.lines)
        
        if total_debit != total_credit:
            raise ValueError(
                f"Entry does not balance. Debits: {total_debit}, Credits: {total_credit}"
            )
        return self
    
    @property
    def total_amount(self) -> Decimal:
        """Total value of the entry (sum of debits)"""
        return sum(line.debit for line in self.lines)


# ============== Checker Output Schema ==============

class CheckerResult(BaseModel):
    """Output from the Checker skill"""
    
    status: Literal["approved", "flagged"]
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str
    
    @model_validator(mode='after')
    def status_matches_issues(self):
        """Status must be consistent with errors/warnings"""
        has_issues = len(self.errors) > 0 or len(self.warnings) > 0
        
        if self.status == "approved" and has_issues:
            raise ValueError("Status is 'approved' but there are errors or warnings")
        if self.status == "flagged" and not has_issues:
            raise ValueError("Status is 'flagged' but there are no errors or warnings")
        
        return self


# ============== Input Schema ==============

class TransactionInput(BaseModel):
    """Raw input from user"""
    
    description: str = Field(min_length=1)
    transaction_date: Optional[date] = None  # Defaults to today if not provided
    
    @field_validator('description')
    @classmethod
    def clean_description(cls, v):
        return v.strip()


# ============== GST Calculation Helper ==============

class GSTBreakdown(BaseModel):
    """Calculated GST components for 18% inclusive"""
    
    total_amount: Decimal
    base_amount: Decimal
    cgst: Decimal
    sgst: Decimal
    
    @classmethod
    def from_inclusive_amount(cls, total: Decimal) -> 'GSTBreakdown':
        """
        Calculate GST breakdown from inclusive amount.
        Total = Base × 1.18
        Base = Total ÷ 1.18
        CGST = SGST = Base × 0.09
        """
        base = (total / Decimal("1.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cgst = (base * Decimal("0.09")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sgst = (base * Decimal("0.09")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Adjust for rounding to ensure total matches
        calculated_total = base + cgst + sgst
        if calculated_total != total:
            # Adjust SGST or Base to absorb rounding difference
            # Prefer adjusting SGST if it's just a penny, or Base if it's structural
            diff = total - calculated_total
            # With decimals, diff should be very small (e.g. 0.01)
            sgst += diff
        
        return cls(
            total_amount=total,
            base_amount=base,
            cgst=cgst,
            sgst=sgst
        )


# ============== Persistence Schema ==============

class StoredEntry(BaseModel):
    """Journal entry as stored in database"""
    
    id: int
    entry_number: str  # e.g., "JV-2024-00001"
    transaction_date: date
    transaction_type: TransactionType
    narration: str
    reference: Optional[str]
    lines: list[JournalLine]
    
    # AI metadata
    reasoning: str
    confidence: float
    warnings: list[str]
    
    # Review status
    status: Literal["draft", "pending_review", "approved", "posted", "rejected"]
    checker_result: Optional[CheckerResult] = None
    
    # Audit
    created_at: str  # ISO format datetime
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None