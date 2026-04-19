"""
Logarithmic growth metrics service.
Computes Kelly/log-space analytics from rolling 12-month PnL data.
"""

import math
import statistics
from datetime import date
from typing import Optional, List, Dict, Tuple
from .pnl_service import get_rolling_twelve_pnl


def _safe_log_rate(current, previous) -> Optional[float]:
    if float(current) <= 0 or float(previous) <= 0:
        return None
    return math.log(float(current) / float(previous))


def _percentile(sorted_vals: List[float], p: float) -> float:
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = (p / 100) * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (idx - lo) * (sorted_vals[hi] - sorted_vals[lo])


def _rolling3_avg(values: List[Optional[float]]) -> List[Optional[float]]:
    result = []
    for i, _ in enumerate(values):
        window = [v for v in values[max(0, i - 2):i + 1] if v is not None]
        result.append(round(statistics.mean(window), 6) if len(window) >= 2 else None)
    return result


def get_log_metrics(as_of_date: Optional[date] = None) -> Dict:
    if as_of_date is None:
        as_of_date = date.today()

    months = get_rolling_twelve_pnl(as_of_date)  # 12 dicts, oldest first

    # --- Phase 2 & 3: log rates (11 values max) ---
    income_log_rates: List[float] = []
    expense_log_rates: List[float] = []

    # aligned chart arrays (one per month pair, index 1..11)
    chart_income_log: List[Optional[float]] = []
    chart_expense_log: List[Optional[float]] = []
    chart_labels: List[str] = []

    # aligned pairs for divergence
    aligned_pairs: List[Tuple[float, float]] = []

    for i in range(1, 12):
        label = months[i]['month_label']
        chart_labels.append(label)

        inc_rate = _safe_log_rate(months[i]['total_income'], months[i - 1]['total_income'])
        exp_rate = _safe_log_rate(months[i]['total_expenses'], months[i - 1]['total_expenses'])

        chart_income_log.append(round(inc_rate, 6) if inc_rate is not None else None)
        chart_expense_log.append(round(exp_rate, 6) if exp_rate is not None else None)

        if inc_rate is not None:
            income_log_rates.append(inc_rate)
        if exp_rate is not None:
            expense_log_rates.append(exp_rate)
        if inc_rate is not None and exp_rate is not None:
            aligned_pairs.append((inc_rate, exp_rate))

    # --- Phase 4: raw value lists ---
    monthly_incomes = sorted([float(m['total_income']) for m in months if float(m['total_income']) > 0])
    monthly_expenses = sorted([float(m['total_expenses']) for m in months if float(m['total_expenses']) > 0])

    # --- Phase 5: monthly retention ---
    monthly_retention: List[Optional[float]] = []
    for m in months:
        inc = float(m['total_income'])
        net = float(m['net_profit_loss'])  # signed in get_rolling_twelve_pnl
        monthly_retention.append(net / inc if inc > 0 else None)

    # === Metric computations ===

    # 1. Geometric mean income (monthly compounding factor)
    geo_mean_income = math.exp(statistics.mean(income_log_rates)) if income_log_rates else None

    # 2. Volatility penalty (Kelly drag)
    volatility_penalty = statistics.variance(income_log_rates) / 2 if len(income_log_rates) >= 2 else None

    # 3. Cumulative multiplier
    cum_multiplier = math.exp(sum(income_log_rates)) if income_log_rates else None

    # 4. Income floor p10
    income_floor_p10 = _percentile(monthly_incomes, 10) if monthly_incomes else None

    # 5. Log rate std deviation
    log_rate_std = statistics.stdev(income_log_rates) if len(income_log_rates) >= 2 else None

    # 6. 3-month drift signal
    drift_3m = statistics.mean(income_log_rates[-3:]) if len(income_log_rates) >= 3 else None

    # 7. Expense log volatility
    expense_log_vol = statistics.stdev(expense_log_rates) if len(expense_log_rates) >= 2 else None

    # 8. Income-expense divergence (latest aligned pair)
    inc_exp_divergence = (aligned_pairs[-1][0] - aligned_pairs[-1][1]) if aligned_pairs else None

    # 9. Ruin reserve (months of expenses sustainable from 12m net surplus)
    expense_floor_p10 = _percentile(monthly_expenses, 10) if monthly_expenses else None
    cumulative_net = sum(float(m['net_profit_loss']) for m in months)
    ruin_reserve = (cumulative_net / expense_floor_p10
                    if expense_floor_p10 and expense_floor_p10 > 0 and cumulative_net > 0
                    else None)

    # 10. Surplus retention rate (average monthly fraction retained, as %)
    valid_retention = [r for r in monthly_retention if r is not None]
    surplus_retention_pct = statistics.mean(valid_retention) * 100 if valid_retention else None

    # 11. Recovery lag (months to recover from worst shock at average rate)
    mean_log = statistics.mean(income_log_rates) if income_log_rates else None
    recovery_lag = (abs(min(income_log_rates)) / mean_log
                    if income_log_rates and mean_log and mean_log > 0
                    else None)

    # === Chart data ===

    chart_income_rolling3 = _rolling3_avg(chart_income_log)

    # Retention bar chart (12 months)
    chart_retention_labels = [m['month_label'] for m in months]
    chart_retention_values: List[Optional[float]] = []
    for m in months:
        inc = float(m['total_income'])
        net = float(m['net_profit_loss'])
        chart_retention_values.append(round((net / inc) * 100, 2) if inc > 0 else None)

    # Cumulative log charts
    chart_income_cumlog: List[float] = []
    chart_expense_cumlog: List[float] = []
    running_inc = 0.0
    running_exp = 0.0
    for v_inc, v_exp in zip(chart_income_log, chart_expense_log):
        if v_inc is not None:
            running_inc += v_inc
        if v_exp is not None:
            running_exp += v_exp
        chart_income_cumlog.append(round(running_inc, 6))
        chart_expense_cumlog.append(round(running_exp, 6))

    data_start = months[1]['month_label'] if len(months) > 1 else ''

    return {
        # Group 1 — Compounding Health
        'geo_mean_income': round(geo_mean_income, 4) if geo_mean_income is not None else None,
        'volatility_penalty': round(volatility_penalty, 4) if volatility_penalty is not None else None,
        'cum_multiplier': round(cum_multiplier, 4) if cum_multiplier is not None else None,
        'income_floor_p10': round(income_floor_p10, 2) if income_floor_p10 is not None else None,

        # Group 2 — Stability & Regime
        'log_rate_std': round(log_rate_std, 4) if log_rate_std is not None else None,
        'drift_3m': round(drift_3m, 4) if drift_3m is not None else None,
        'expense_log_vol': round(expense_log_vol, 4) if expense_log_vol is not None else None,
        'inc_exp_divergence': round(inc_exp_divergence, 4) if inc_exp_divergence is not None else None,

        # Group 3 — Ruin & Resilience
        'ruin_reserve_months': round(ruin_reserve, 1) if ruin_reserve is not None else None,
        'surplus_retention_pct': round(surplus_retention_pct, 1) if surplus_retention_pct is not None else None,
        'recovery_lag': round(recovery_lag, 1) if recovery_lag is not None else None,

        # Chart series
        'chart_labels': chart_labels,
        'chart_income_log': chart_income_log,
        'chart_income_rolling3': chart_income_rolling3,
        'chart_expense_log': chart_expense_log,
        'chart_retention_labels': chart_retention_labels,
        'chart_retention_values': chart_retention_values,
        'chart_income_cumlog': chart_income_cumlog,
        'chart_expense_cumlog': chart_expense_cumlog,

        # Metadata
        'data_start_month': data_start,
        'months_of_data': len(income_log_rates),
    }
