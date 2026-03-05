"""
Service module for financial ratio calculations.
Computes 7 key financial ratios from Balance Sheet and P&L data.

The ratios service deliberately calls the existing Python services
(get_balance_sheet, get_profit_loss) rather than querying the
v_financial_summary DB view directly.  This keeps classification logic
(current vs non-current assets, signed net profit) in one place and
makes unit-testing straightforward.  The SQL view exists as an
analytics / external-tooling artifact.
"""

from decimal import Decimal
from datetime import date
from typing import Optional, Dict

from django.db.models import Sum

from .balance_sheet_service import get_balance_sheet
from .pnl_service import get_profit_loss
from .models import Account, JournalLine


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_financial_ratios(as_of_date: Optional[date] = None) -> Dict:
    """
    Compute all financial ratios as of *as_of_date*.

    Each ratio in the returned dict is a sub-dict:
        title             – human-readable name
        value             – computed ratio (float) or None when denominator == 0
        numerator         – raw Decimal value
        denominator       – raw Decimal value
        numerator_label   – display label for numerator
        denominator_label – display label for denominator
        formula           – symbolic formula string (e.g. "CA / CL")
        health            – 'good' | 'warning' | 'danger' | None
        is_percentage     – True when the ratio is expressed as %
    """
    if as_of_date is None:
        as_of_date = date.today()

    # --- pull from existing services ----------------------------------------
    bs  = get_balance_sheet(as_of_date)
    pnl = get_profit_loss(from_date=None, to_date=as_of_date)   # inception → date

    # pnl['net_profit_loss'] is abs(); sign lives in pnl['is_profit']
    net_profit = pnl['net_profit_loss'] if pnl['is_profit'] else -pnl['net_profit_loss']

    # --- extract components -------------------------------------------------
    current_assets      = bs['total_current_assets']
    current_liabilities = bs['total_current_liabilities']
    total_assets        = bs['total_assets']
    total_liabilities   = bs['total_liabilities']
    total_equity        = bs['total_equity']
    total_income        = pnl['total_income']
    capital_employed    = total_assets - current_liabilities   # TA − CL

    # Labor cost: sum all expense accounts with sub_type = 'salary'
    salary_account_codes = list(
        Account.objects.filter(is_active=True, account_type='expense', account_subtype='salary')
        .values_list('code', flat=True)
    )
    labor_cost = Decimal('0')
    if salary_account_codes:
        filters = {
            'account_code__in': salary_account_codes,
            'journal_entry__status': 'posted',
            'journal_entry__transaction_date__lte': as_of_date,
        }
        agg = JournalLine.objects.filter(**filters).aggregate(
            total_debit=Sum('debit'), total_credit=Sum('credit')
        )
        labor_cost = (agg['total_debit'] or Decimal('0')) - (agg['total_credit'] or Decimal('0'))

    # --- helpers ------------------------------------------------------------
    def _div(num: Decimal, den: Decimal) -> Optional[float]:
        return None if den == Decimal('0') else float(num / den)

    def _pct(num: Decimal, den: Decimal) -> Optional[float]:
        return None if den == Decimal('0') else float((num / den) * 100)

    # --- build ratio dicts (insertion order = display order) ----------------
    ratios = {}

    # 1. Liquidity Ratio (Current Ratio)
    ratios['current_ratio'] = _ratio(
        title='Liquidity Ratio',
        value=_div(current_assets, current_liabilities),
        numerator=current_assets,
        denominator=current_liabilities,
        num_label='Current Assets',
        den_label='Current Liabilities',
        formula='Current Assets  /  Current Liabilities',
        health=_health_current_ratio(_div(current_assets, current_liabilities)),
        is_pct=False,
    )

    # 2. Debt-Equity Ratio
    ratios['debt_equity'] = _ratio(
        title='Debt-Equity Ratio',
        value=_div(total_liabilities, total_equity),
        numerator=total_liabilities,
        denominator=total_equity,
        num_label='Total Liabilities',
        den_label='Total Equity',
        formula='Total Liabilities  /  Total Equity',
        health=_health_debt_equity(_div(total_liabilities, total_equity)),
        is_pct=False,
    )

    # 3. Profit Margin  (GPM = NPM here; no COGS in this business)
    ratios['profit_margin'] = _ratio(
        title='Profit Margin',
        value=_pct(net_profit, total_income),
        numerator=net_profit,
        denominator=total_income,
        num_label='Net Profit',
        den_label='Total Income',
        formula='Net Profit  /  Total Income  ×  100',
        health=_health_profit_margin(_pct(net_profit, total_income)),
        is_pct=True,
    )

    # 4. Return on Assets
    ratios['roa'] = _ratio(
        title='Return on Assets',
        value=_pct(net_profit, total_assets),
        numerator=net_profit,
        denominator=total_assets,
        num_label='Net Profit',
        den_label='Total Assets',
        formula='Net Profit  /  Total Assets  ×  100',
        health=_health_roa_roce(_pct(net_profit, total_assets)),
        is_pct=True,
    )

    # 5. Earning Power  (top-line income vs assets — distinct from ROA)
    ratios['earning_power'] = _ratio(
        title='Earning Power',
        value=_pct(total_income, total_assets),
        numerator=total_income,
        denominator=total_assets,
        num_label='Total Income',
        den_label='Total Assets',
        formula='Total Income  /  Total Assets  ×  100',
        health=_health_earning_power(_pct(total_income, total_assets)),
        is_pct=True,
    )

    # 6. Return on Capital Employed
    ratios['roce'] = _ratio(
        title='Return on Capital Employed',
        value=_pct(net_profit, capital_employed),
        numerator=net_profit,
        denominator=capital_employed,
        num_label='Net Profit',
        den_label='Capital Employed',
        formula='Net Profit  /  Capital Employed  ×  100',
        health=_health_roa_roce(_pct(net_profit, capital_employed)),
        is_pct=True,
    )

    # 7. Debt-to-Assets Ratio
    ratios['debt_to_assets'] = _ratio(
        title='Debt-to-Assets Ratio',
        value=_div(total_liabilities, total_assets),
        numerator=total_liabilities,
        denominator=total_assets,
        num_label='Total Liabilities',
        den_label='Total Assets',
        formula='Total Liabilities  /  Total Assets',
        health=_health_debt_to_assets(_div(total_liabilities, total_assets)),
        is_pct=False,
    )

    # 8. Labor Cost Percentage
    ratios['labor_cost_pct'] = _ratio(
        title='Labor Cost Percentage',
        value=_pct(labor_cost, total_income),
        numerator=labor_cost,
        denominator=total_income,
        num_label='Salary Expenses',
        den_label='Total Income',
        formula='Salary Expenses  /  Total Income  ×  100',
        health=_health_labor_cost_pct(_pct(labor_cost, total_income)),
        is_pct=True,
    )

    return ratios


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ratio(title, value, numerator, denominator, num_label, den_label,
           formula, health, is_pct) -> Dict:
    """Assemble a single ratio sub-dict."""
    return {
        'title':             title,
        'value':             value,
        'numerator':         numerator,
        'denominator':       denominator,
        'numerator_label':   num_label,
        'denominator_label': den_label,
        'formula':           formula,
        'health':            health,
        'is_percentage':     is_pct,
    }


# ---------------------------------------------------------------------------
# Health classifiers
# ---------------------------------------------------------------------------

def _health_current_ratio(v: Optional[float]) -> Optional[str]:
    if v is None:   return None
    if v >= 1.5:    return 'good'
    if v >= 1.0:    return 'warning'
    return 'danger'


def _health_debt_equity(v: Optional[float]) -> Optional[str]:
    if v is None:   return None
    if v < 1.0:     return 'good'
    if v <= 2.0:    return 'warning'
    return 'danger'


def _health_profit_margin(v: Optional[float]) -> Optional[str]:
    if v is None:   return None
    if v > 15.0:    return 'good'
    if v >= 5.0:    return 'warning'
    return 'danger'


def _health_roa_roce(v: Optional[float]) -> Optional[str]:
    if v is None:   return None
    if v > 10.0:    return 'good'
    if v >= 5.0:    return 'warning'
    return 'danger'


def _health_earning_power(v: Optional[float]) -> Optional[str]:
    if v is None:   return None
    if v > 20.0:    return 'good'
    if v >= 10.0:   return 'warning'
    return 'danger'


def _health_debt_to_assets(v: Optional[float]) -> Optional[str]:
    if v is None:   return None
    if v < 0.5:     return 'good'
    if v <= 0.75:   return 'warning'
    return 'danger'


def _health_labor_cost_pct(v: Optional[float]) -> Optional[str]:
    if v is None:   return None
    if v <= 30.0:   return 'good'
    if v <= 50.0:   return 'warning'
    return 'danger'
