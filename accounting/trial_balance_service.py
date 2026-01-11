"""
Service module for Trial Balance calculations.
Generates Trial Balance statement following ICAI conventions.
"""

from django.db.models import Sum, Q
from decimal import Decimal
from datetime import date
from typing import Optional, Dict, List
from .models import Account, JournalLine


def get_trial_balance(as_of_date: Optional[date] = None) -> Dict:
    """
    Calculate Trial Balance as of a specific date.
    
    Args:
        as_of_date: Date for which to calculate balances. Defaults to current date.
        
    Returns:
        Dictionary containing:
        - accounts_by_type: Dict mapping account type to list of account data
        - total_debit: Sum of all debit balances
        - total_credit: Sum of all credit balances
        - is_balanced: Whether debits equal credits
        - as_of_date: The date used for calculation
    """
    if as_of_date is None:
        as_of_date = date.today()
    
    # Get all active accounts ordered by code
    accounts = Account.objects.filter(is_active=True).order_by('code')
    
    # Account type ordering for display (standard accounting order)
    account_type_order = ['asset', 'liability', 'equity', 'income', 'expense']
    account_type_labels = {
        'asset': 'Assets',
        'liability': 'Liabilities',
        'equity': 'Equity',
        'income': 'Income',
        'expense': 'Expenses'
    }
    
    accounts_by_type = {acc_type: [] for acc_type in account_type_order}
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    
    for account in accounts:
        # Calculate balance for this account up to the specified date
        balance_data = _calculate_account_balance(account, as_of_date)
        
        # For expense accounts, always show them even with zero balance for visibility
        # For other account types, only show if they have a non-zero balance
        should_include = (
            account.account_type == 'expense' or
            balance_data['debit_balance'] != Decimal('0') or 
            balance_data['credit_balance'] != Decimal('0')
        )
        
        if should_include:
            accounts_by_type[account.account_type].append({
                'code': account.code,
                'name': account.name,
                'debit_balance': balance_data['debit_balance'],
                'credit_balance': balance_data['credit_balance'],
            })
            
            total_debit += balance_data['debit_balance']
            total_credit += balance_data['credit_balance']
    
    # Calculate difference (should be zero for balanced books)
    difference = total_debit - total_credit
    is_balanced = abs(difference) < Decimal('0.01')  # Allow for minor rounding
    
    return {
        'accounts_by_type': accounts_by_type,
        'account_type_labels': account_type_labels,
        'account_type_order': account_type_order,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'difference': difference,
        'is_balanced': is_balanced,
        'as_of_date': as_of_date,
    }


def _calculate_account_balance(account: Account, as_of_date: date) -> Dict[str, Decimal]:
    """
    Calculate debit and credit balance for a single account.
    
    Args:
        account: Account instance
        as_of_date: Calculate balance up to this date
        
    Returns:
        Dictionary with 'debit_balance' and 'credit_balance' keys
    """
    # Get all posted journal lines for this account up to the specified date
    lines = JournalLine.objects.filter(
        account_code=account.code,
        journal_entry__status='posted',
        journal_entry__transaction_date__lte=as_of_date
    ).aggregate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit')
    )
    
    debit = lines['total_debit'] or Decimal('0')
    credit = lines['total_credit'] or Decimal('0')
    
    # Calculate balance based on account type
    # Assets & Expenses: Show debit balance (debit - credit) in debit column
    # Liabilities, Income, Equity: Show credit balance (credit - debit) in credit column
    if account.account_type in ('asset', 'expense'):
        balance = debit - credit
        if balance >= 0:
            return {'debit_balance': balance, 'credit_balance': Decimal('0')}
        else:
            # Negative balance for asset/expense shows as credit
            return {'debit_balance': Decimal('0'), 'credit_balance': abs(balance)}
    else:  # liability, income, equity
        balance = credit - debit
        if balance >= 0:
            return {'debit_balance': Decimal('0'), 'credit_balance': balance}
        else:
            # Negative balance for liability/income/equity shows as debit
            return {'debit_balance': abs(balance), 'credit_balance': Decimal('0')}


def get_trial_balance_summary(as_of_date: Optional[date] = None) -> str:
    """
    Get a text summary of the trial balance status.
    
    Args:
        as_of_date: Date for which to calculate balances
        
    Returns:
        Human-readable summary string
    """
    tb_data = get_trial_balance(as_of_date)
    
    if tb_data['is_balanced']:
        return f"Trial Balance is balanced. Total Debits = Total Credits = ₹{tb_data['total_debit']:,.2f}"
    else:
        return (f"Trial Balance is NOT balanced. "
                f"Debits: ₹{tb_data['total_debit']:,.2f}, "
                f"Credits: ₹{tb_data['total_credit']:,.2f}, "
                f"Difference: ₹{tb_data['difference']:,.2f}")
