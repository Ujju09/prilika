"""
Service module for Profit & Loss Statement calculations.
Generates P&L statement following ICAI conventions.
"""

from django.db.models import Sum, Q
from decimal import Decimal
from datetime import date
from typing import Optional, Dict, List
from .models import Account, JournalLine


def get_profit_loss(from_date: Optional[date] = None, to_date: Optional[date] = None) -> Dict:
    """
    Calculate Profit & Loss statement for a date range.

    Args:
        from_date: Start date of the period. If None, includes all historical data.
        to_date: End date of the period. If None, uses current date.

    Returns:
        Dictionary containing:
        - income_accounts: List of income accounts with balances
        - total_income: Sum of all income
        - expense_accounts: List of expense accounts with balances
        - total_expenses: Sum of all expenses
        - net_profit_loss: Income - Expenses (positive = profit, negative = loss)
        - from_date: Start date used
        - to_date: End date used
        - is_profit: Boolean indicating if result is profit (True) or loss (False)
    """
    if to_date is None:
        to_date = date.today()

    # Get all active income and expense accounts
    income_accounts = Account.objects.filter(
        is_active=True,
        account_type='income'
    ).order_by('code')

    expense_accounts = Account.objects.filter(
        is_active=True,
        account_type='expense'
    ).order_by('code')

    # OPTIMIZED: Batch query for all income account balances
    income_filters = Q(
        journal_entry__status='posted',
        journal_entry__transaction_date__lte=to_date
    )
    if from_date:
        income_filters &= Q(journal_entry__transaction_date__gte=from_date)

    income_balances = JournalLine.objects.filter(
        income_filters,
        account_code__in=[acc.code for acc in income_accounts]
    ).values('account_code').annotate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit')
    )

    # Create lookup dict for income balances
    income_balances_dict = {
        item['account_code']: (item['total_credit'] or Decimal('0')) - (item['total_debit'] or Decimal('0'))
        for item in income_balances
    }

    # OPTIMIZED: Batch query for all expense account balances
    expense_filters = Q(
        journal_entry__status='posted',
        journal_entry__transaction_date__lte=to_date
    )
    if from_date:
        expense_filters &= Q(journal_entry__transaction_date__gte=from_date)

    expense_balances = JournalLine.objects.filter(
        expense_filters,
        account_code__in=[acc.code for acc in expense_accounts]
    ).values('account_code').annotate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit')
    )

    # Create lookup dict for expense balances
    expense_balances_dict = {
        item['account_code']: (item['total_debit'] or Decimal('0')) - (item['total_credit'] or Decimal('0'))
        for item in expense_balances
    }

    # Build income list from pre-calculated balances
    income_list = []
    total_income = Decimal('0')
    for account in income_accounts:
        balance = income_balances_dict.get(account.code, Decimal('0'))
        if balance != Decimal('0'):
            income_list.append({
                'code': account.code,
                'name': account.name,
                'amount': balance
            })
            total_income += balance

    # Build expense list from pre-calculated balances
    expense_list = []
    total_expenses = Decimal('0')
    for account in expense_accounts:
        balance = expense_balances_dict.get(account.code, Decimal('0'))
        if balance != Decimal('0'):
            expense_list.append({
                'code': account.code,
                'name': account.name,
                'amount': balance
            })
            total_expenses += balance

    # Calculate net profit/loss
    net_profit_loss = total_income - total_expenses
    is_profit = net_profit_loss >= 0

    return {
        'income_accounts': income_list,
        'total_income': total_income,
        'expense_accounts': expense_list,
        'total_expenses': total_expenses,
        'net_profit_loss': abs(net_profit_loss),
        'is_profit': is_profit,
        'from_date': from_date,
        'to_date': to_date,
        'period_label': _get_period_label(from_date, to_date)
    }


def _calculate_pnl_account_balance(account: Account, from_date: Optional[date], to_date: date) -> Decimal:
    """
    Calculate the balance for an income or expense account within a date range.
    
    For income accounts: Returns credit - debit (normal credit balance)
    For expense accounts: Returns debit - credit (normal debit balance)
    
    Args:
        account: Account instance
        from_date: Start date (inclusive), None for all history
        to_date: End date (inclusive)
        
    Returns:
        Account balance for the period
    """
    # Build query filter
    filters = Q(
        account_code=account.code,
        journal_entry__status='posted',
        journal_entry__transaction_date__lte=to_date
    )
    
    if from_date:
        filters &= Q(journal_entry__transaction_date__gte=from_date)
    
    # Get aggregated debits and credits
    lines = JournalLine.objects.filter(filters).aggregate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit')
    )
    
    debit = lines['total_debit'] or Decimal('0')
    credit = lines['total_credit'] or Decimal('0')
    
    # Calculate balance based on account type
    if account.account_type == 'income':
        # Income has normal credit balance
        return credit - debit
    elif account.account_type == 'expense':
        # Expense has normal debit balance
        return debit - credit
    else:
        return Decimal('0')


def _get_period_label(from_date: Optional[date], to_date: date) -> str:
    """
    Generate a human-readable period label.
    
    Args:
        from_date: Start date or None
        to_date: End date
        
    Returns:
        Formatted period string
    """
    if from_date:
        return f"For the period from {from_date.strftime('%d-%m-%Y')} to {to_date.strftime('%d-%m-%Y')}"
    else:
        return f"For the period up to {to_date.strftime('%d-%m-%Y')}"


def get_pnl_summary(from_date: Optional[date] = None, to_date: Optional[date] = None) -> str:
    """
    Get a text summary of the P&L statement.
    
    Args:
        from_date: Start date of the period
        to_date: End date of the period
        
    Returns:
        Human-readable summary string
    """
    pnl_data = get_profit_loss(from_date, to_date)
    
    result_type = "Net Profit" if pnl_data['is_profit'] else "Net Loss"
    
    return (f"{result_type}: ₹{pnl_data['net_profit_loss']:,.2f} | "
            f"Income: ₹{pnl_data['total_income']:,.2f} | "
            f"Expenses: ₹{pnl_data['total_expenses']:,.2f}")
