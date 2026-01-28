from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('', views.index, name='index'),
    path('review/', views.review_entries, name='review_entries'),
    path('journal/', views.journal_view, name='journal_view'),
    path('journal/export/', views.export_journal_pdf, name='export_journal_pdf'),
    path('journal/<int:entry_id>/', views.journal_detail, name='journal_detail'),
    path('trial-balance/', views.trial_balance_view, name='trial_balance_view'),
    path('trial-balance/export/', views.export_trial_balance_pdf, name='export_trial_balance_pdf'),
    path('ledger/<str:account_code>/', views.account_ledger, name='account_ledger'),
    path('profit-loss/', views.profit_loss_view, name='profit_loss_view'),
    path('profit-loss/export/', views.export_pnl_pdf, name='export_pnl_pdf'),
    path('balance-sheet/', views.balance_sheet_view, name='balance_sheet_view'),
    path('balance-sheet/export/', views.export_balance_sheet_pdf, name='export_balance_sheet_pdf'),
    path('evals/', views.evals_view, name='evals_view'),
    path('evals/export/', views.export_evals_json, name='export_evals_json'),
    path('api/process/', views.process_transaction, name='process_transaction'),
    path('api/entries/', views.get_entries, name='get_entries'),
    path('api/entries/<int:entry_id>/logs/', views.get_entry_logs, name='get_entry_logs'),
    path('api/logs/', views.get_session_logs, name='get_session_logs'),
    path('api/entries/<int:entry_id>/approve/', views.approve_entry, name='approve_entry'),
    path('api/entries/<int:entry_id>/reject/', views.reject_entry, name='reject_entry'),
    path('api/entries/<int:entry_id>/post/', views.post_entry, name='post_entry'),
]

