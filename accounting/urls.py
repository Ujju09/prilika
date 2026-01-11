from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('', views.index, name='index'),
    path('journal/', views.journal_view, name='journal_view'),
    path('journal/export/', views.export_journal_pdf, name='export_journal_pdf'),
    path('journal/<int:entry_id>/', views.journal_detail, name='journal_detail'),
    path('trial-balance/', views.trial_balance_view, name='trial_balance_view'),
    path('trial-balance/export/', views.export_trial_balance_pdf, name='export_trial_balance_pdf'),
    path('profit-loss/', views.profit_loss_view, name='profit_loss_view'),
    path('profit-loss/export/', views.export_pnl_pdf, name='export_pnl_pdf'),
    path('api/process/', views.process_transaction, name='process_transaction'),
    path('api/entries/', views.get_entries, name='get_entries'),
    path('api/entries/<int:entry_id>/logs/', views.get_entry_logs, name='get_entry_logs'),
    path('api/logs/', views.get_session_logs, name='get_session_logs'),
    path('api/entries/<int:entry_id>/approve/', views.approve_entry, name='approve_entry'),
    path('api/entries/<int:entry_id>/reject/', views.reject_entry, name='reject_entry'),
]
