"""
Service module for Balance Sheet calculations.
Generates Balance Sheet statement following ICAI conventions.
"""

from django.db.models import Sum
from decimal import Decimal
from datetime import date
from typing import Optional, Dict, List
from .models import Account, JournalLine
from .pnl_service import get_profit_loss


def get_balance_sheet(as_of_date: Optional[date] = None) -> Dict:
    """
    Calculate Balance Sheet as of a specific date.

    Args:
        as_of_date: Date for which to calculate balances. Defaults to current date.

    Returns:
        Dictionary containing:
        - current_assets: List of current asset accounts with balances
        - non_current_assets: List of non-current asset accounts with balances
        - total_current_assets: Sum of current asset balances
        - total_non_current_assets: Sum of non-current asset balances
        - total_assets: Total of all assets
        - current_liabilities: List of current liability accounts with balances
        - total_current_liabilities: Sum of current liability balances
        - total_liabilities: Total of all liabilities
        - equity_accounts: List of equity accounts (Capital, Drawings)
        - retained_earnings: Calculated from P&L
        - total_equity: Capital - Drawings + Retained Earnings
        - liabilities_plus_equity: Total liabilities + Total equity
        - is_balanced: Whether Assets = Liabilities + Equity
        - difference: Assets - (Liabilities + Equity)
        - as_of_date: The date used for calculation
    """
    if as_of_date is None:
        as_of_date = date.today()

    # Get all active accounts
    asset_accounts = Account.objects.filter(
        is_active=True,
        account_type='asset'
    ).order_by('code')

    liability_accounts = Account.objects.filter(
        is_active=True,
        account_type='liability'
    ).order_by('code')

    equity_accounts = Account.objects.filter(
        is_active=True,
        account_type='equity'
    ).order_by('code')

    # OPTIMIZED: Get all balances in a single query using GROUP BY
    balances_query = JournalLine.objects.filter(
        journal_entry__status='posted',
        journal_entry__transaction_date__lte=as_of_date
    ).values('account_code').annotate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit')
    )

    # Create a lookup dict for fast access
    balances_dict = {
        item['account_code']: {
            'debit': item['total_debit'] or Decimal('0'),
            'credit': item['total_credit'] or Decimal('0')
        }
        for item in balances_query
    }

    # Process Assets - separate into current and non-current
    current_assets = []
    non_current_assets = []
    total_current_assets = Decimal('0')
    total_non_current_assets = Decimal('0')

    for account in asset_accounts:
        balance = _calculate_account_balance(
            account.code,
            'asset',
            balances_dict
        )

        # Only include accounts with non-zero balances
        if balance != Decimal('0'):
            account_data = {
                'code': account.code,
                'name': account.name,
                'balance': balance
            }

            if account.is_current_asset:
                current_assets.append(account_data)
                total_current_assets += balance
            else:
                non_current_assets.append(account_data)
                total_non_current_assets += balance

    total_assets = total_current_assets + total_non_current_assets

    # Process Liabilities - all current for now
    current_liabilities = []
    total_current_liabilities = Decimal('0')

    for account in liability_accounts:
        balance = _calculate_account_balance(
            account.code,
            'liability',
            balances_dict
        )

        # Only include accounts with non-zero balances
        if balance != Decimal('0'):
            current_liabilities.append({
                'code': account.code,
                'name': account.name,
                'balance': balance
            })
            total_current_liabilities += balance

    total_liabilities = total_current_liabilities

    # Process Equity - Capital, Drawings, and Retained Earnings
    equity_list = []

    for account in equity_accounts:
        balance = _calculate_account_balance(
            account.code,
            'equity',
            balances_dict
        )

        # Show equity accounts even with zero balance for visibility
        equity_list.append({
            'code': account.code,
            'name': account.name,
            'balance': balance
        })

    # Calculate Retained Earnings from P&L (from inception to as_of_date)
    pnl_data = get_profit_loss(from_date=None, to_date=as_of_date)
    if pnl_data['is_profit']:
        retained_earnings = pnl_data['net_profit_loss']
    else:
        retained_earnings = -pnl_data['net_profit_loss']

    # Calculate Total Equity
    # Total Equity = Sum of equity account balances + Retained Earnings
    equity_sum = sum(eq['balance'] for eq in equity_list)
    total_equity = equity_sum + retained_earnings

    # Calculate combined liabilities and equity
    liabilities_plus_equity = total_liabilities + total_equity

    # Validate accounting equation: Assets = Liabilities + Equity
    difference = total_assets - liabilities_plus_equity
    is_balanced = abs(difference) < Decimal('0.01')  # Allow for minor rounding

    return {
        # Assets
        'current_assets': current_assets,
        'non_current_assets': non_current_assets,
        'total_current_assets': total_current_assets,
        'total_non_current_assets': total_non_current_assets,
        'total_assets': total_assets,

        # Liabilities
        'current_liabilities': current_liabilities,
        'total_current_liabilities': total_current_liabilities,
        'total_liabilities': total_liabilities,

        # Equity
        'equity_accounts': equity_list,
        'retained_earnings': retained_earnings,
        'total_equity': total_equity,

        # Validation
        'liabilities_plus_equity': liabilities_plus_equity,
        'is_balanced': is_balanced,
        'difference': difference,
        'as_of_date': as_of_date,
    }


def _calculate_account_balance(account_code: str, account_type: str,
                               balances_dict: Dict) -> Decimal:
    """
    Calculate balance from pre-fetched debit/credit totals.

    Args:
        account_code: The account code
        account_type: Type of account (asset, liability, equity)
        balances_dict: Dictionary with pre-fetched debit/credit totals

    Returns:
        Account balance as Decimal
    """
    balance_totals = balances_dict.get(account_code, {
        'debit': Decimal('0'),
        'credit': Decimal('0')
    })
    debit = balance_totals['debit']
    credit = balance_totals['credit']

    # Assets: Debit - Credit (normal debit balance)
    if account_type == 'asset':
        return debit - credit
    # Liabilities & Equity: Credit - Debit (normal credit balance)
    elif account_type in ('liability', 'equity'):
        return credit - debit
    else:
        return Decimal('0')


def get_balance_sheet_summary(as_of_date: Optional[date] = None) -> str:
    """
    Get a text summary of the balance sheet.

    Args:
        as_of_date: Date for which to calculate balances

    Returns:
        Human-readable summary string
    """
    bs_data = get_balance_sheet(as_of_date)

    if bs_data['is_balanced']:
        return (f"Balance Sheet is balanced. "
                f"Assets = Liabilities + Equity = ₹{bs_data['total_assets']:,.2f}")
    else:
        return (f"Balance Sheet is NOT balanced. "
                f"Assets: ₹{bs_data['total_assets']:,.2f}, "
                f"Liabilities + Equity: ₹{bs_data['liabilities_plus_equity']:,.2f}, "
                f"Difference: ₹{bs_data['difference']:,.2f}")
