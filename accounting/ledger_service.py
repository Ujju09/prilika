"""
Account Ledger Service

Provides ledger data for individual accounts showing all transactions
with running balance calculations.
"""

from decimal import Decimal
from datetime import date
from typing import Optional
from django.db.models import Q

from .models import Account, JournalLine, JournalEntry


def get_account_ledger(
    account_code: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> dict:
    """
    Get ledger for a specific account with all transactions and running balance.
    
    Args:
        account_code: Account code to get ledger for
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        dict with account info and transactions list
    """
    try:
        account = Account.objects.get(code=account_code)
    except Account.DoesNotExist:
        return {
            'error': f'Account {account_code} not found',
            'account': None,
            'transactions': []
        }
    
    # Get all posted journal lines for this account
    lines_query = JournalLine.objects.filter(
        account_code=account_code,
        journal_entry__status='posted'
    ).select_related('journal_entry').order_by(
        'journal_entry__transaction_date',
        'journal_entry__id',
        'id'
    )
    
    # Apply date filters if provided
    if start_date:
        lines_query = lines_query.filter(journal_entry__transaction_date__gte=start_date)
    if end_date:
        lines_query = lines_query.filter(journal_entry__transaction_date__lte=end_date)
    
    # Calculate opening balance if start_date is provided
    opening_balance = Decimal('0')
    if start_date:
        opening_lines = JournalLine.objects.filter(
            account_code=account_code,
            journal_entry__status='posted',
            journal_entry__transaction_date__lt=start_date
        ).select_related('journal_entry')
        
        opening_debit = sum(line.debit for line in opening_lines)
        opening_credit = sum(line.credit for line in opening_lines)
        
        # Calculate based on account type
        if account.account_type in ('asset', 'expense'):
            opening_balance = opening_debit - opening_credit
        else:
            opening_balance = opening_credit - opening_debit
    
    # Build transactions list with running balance
    transactions = []
    running_balance = opening_balance
    
    for line in lines_query:
        entry = line.journal_entry
        
        # Update running balance
        if account.account_type in ('asset', 'expense'):
            # Debit increases, credit decreases
            running_balance += line.debit - line.credit
        else:
            # Credit increases, debit decreases
            running_balance += line.credit - line.debit
        
        transactions.append({
            'date': entry.transaction_date,
            'entry_number': entry.entry_number,
            'entry_id': entry.id,
            'narration': entry.narration,
            'reference': entry.reference,
            'transaction_type': entry.transaction_type,
            'debit': line.debit,
            'credit': line.credit,
            'balance': running_balance,
        })
    
    # Calculate totals
    total_debit = sum(t['debit'] for t in transactions)
    total_credit = sum(t['credit'] for t in transactions)
    
    return {
        'account': account,
        'opening_balance': opening_balance,
        'transactions': transactions,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'closing_balance': running_balance,
        'start_date': start_date,
        'end_date': end_date,
    }
