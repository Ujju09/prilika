# Generated migration — creates the v_financial_summary SQL view.
#
# This view pre-aggregates all posted journal lines into a single summary row
# containing the key balance-sheet and P&L totals needed for ratio
# calculations.  It is intended for analytics dashboards and external tooling.
#
# NOTE: ratios_service.py does NOT query this view; it calls the Python
# service layer instead so that current/non-current classification logic
# lives in one place (models.py → is_current_asset).  If that property
# changes, update the CASE WHEN below to match.
#
# SQL compatibility: uses only standard SQL features (SUM, CASE WHEN,
# COALESCE, INNER JOIN).  is_active = TRUE works on both SQLite
# (TRUE → 1) and PostgreSQL (native BOOLEAN).

from django.db import migrations


FORWARD_SQL = """
CREATE VIEW v_financial_summary AS
SELECT
    -- Current Assets  (asset accounts whose subtype is NOT a non-current marker)
    COALESCE(SUM(CASE
        WHEN a.account_type = 'asset'
         AND a.account_subtype NOT IN ('security_deposit', 'fixed_asset', 'long_term_investment')
        THEN jl.debit ELSE 0 END), 0)
    - COALESCE(SUM(CASE
        WHEN a.account_type = 'asset'
         AND a.account_subtype NOT IN ('security_deposit', 'fixed_asset', 'long_term_investment')
        THEN jl.credit ELSE 0 END), 0)
        AS total_current_assets,

    -- Non-Current Assets
    COALESCE(SUM(CASE
        WHEN a.account_type = 'asset'
         AND a.account_subtype IN ('security_deposit', 'fixed_asset', 'long_term_investment')
        THEN jl.debit ELSE 0 END), 0)
    - COALESCE(SUM(CASE
        WHEN a.account_type = 'asset'
         AND a.account_subtype IN ('security_deposit', 'fixed_asset', 'long_term_investment')
        THEN jl.credit ELSE 0 END), 0)
        AS total_non_current_assets,

    -- Total Assets
    COALESCE(SUM(CASE
        WHEN a.account_type = 'asset'
        THEN jl.debit ELSE 0 END), 0)
    - COALESCE(SUM(CASE
        WHEN a.account_type = 'asset'
        THEN jl.credit ELSE 0 END), 0)
        AS total_assets,

    -- Current Liabilities  (all liabilities are current in this schema;
    --  add a subtype guard here if long-term liabilities are introduced)
    COALESCE(SUM(CASE
        WHEN a.account_type = 'liability'
        THEN jl.credit ELSE 0 END), 0)
    - COALESCE(SUM(CASE
        WHEN a.account_type = 'liability'
        THEN jl.debit ELSE 0 END), 0)
        AS total_current_liabilities,

    -- Total Liabilities  (= current for now)
    COALESCE(SUM(CASE
        WHEN a.account_type = 'liability'
        THEN jl.credit ELSE 0 END), 0)
    - COALESCE(SUM(CASE
        WHEN a.account_type = 'liability'
        THEN jl.debit ELSE 0 END), 0)
        AS total_liabilities,

    -- Total Income  (credit-normal)
    COALESCE(SUM(CASE
        WHEN a.account_type = 'income'
        THEN jl.credit ELSE 0 END), 0)
    - COALESCE(SUM(CASE
        WHEN a.account_type = 'income'
        THEN jl.debit ELSE 0 END), 0)
        AS total_income,

    -- Total Expenses  (debit-normal)
    COALESCE(SUM(CASE
        WHEN a.account_type = 'expense'
        THEN jl.debit ELSE 0 END), 0)
    - COALESCE(SUM(CASE
        WHEN a.account_type = 'expense'
        THEN jl.credit ELSE 0 END), 0)
        AS total_expenses,

    -- Net Profit  = Income − Expenses  (negative = loss)
    (COALESCE(SUM(CASE
        WHEN a.account_type = 'income'
        THEN jl.credit ELSE 0 END), 0)
    - COALESCE(SUM(CASE
        WHEN a.account_type = 'income'
        THEN jl.debit ELSE 0 END), 0))
    - (COALESCE(SUM(CASE
        WHEN a.account_type = 'expense'
        THEN jl.debit ELSE 0 END), 0)
    - COALESCE(SUM(CASE
        WHEN a.account_type = 'expense'
        THEN jl.credit ELSE 0 END), 0))
        AS net_profit

FROM accounting_journalline jl
INNER JOIN accounting_journalentry je
    ON jl.journal_entry_id = je.id
INNER JOIN accounting_account a
    ON jl.account_code = a.code
WHERE je.status = 'posted'
  AND a.is_active = TRUE;
"""

REVERSE_SQL = "DROP VIEW IF EXISTS v_financial_summary;"


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0011_sharedreport'),
    ]

    operations = [
        migrations.RunSQL(
            sql=FORWARD_SQL,
            reverse_sql=REVERSE_SQL,
        ),
    ]
