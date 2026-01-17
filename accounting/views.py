from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.db.models import Count, Q
from django.utils.http import url_has_allowed_host_and_scheme
import json
import logging
from datetime import date as dt_date

from .models import JournalEntry, AgentLog
from .service import process_and_save
from .trial_balance_service import get_trial_balance
from .pnl_service import get_profit_loss
from .ledger_service import get_account_ledger

logger = logging.getLogger('accounting')


def login_view(request):
    """Handle user login"""
    if request.user.is_authenticated:
        return redirect('/accounting/')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            next_url = request.GET.get('next', '/accounting/')

            # Validate the redirect URL to prevent open redirect attacks
            if not url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure()
            ):
                next_url = '/accounting/'

            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password')

    return render(request, 'accounting/login.html')


def logout_view(request):
    """Handle user logout"""
    auth_logout(request)
    messages.success(request, 'You have been logged out successfully')
    return redirect('/login/')


@login_required
def index(request):
    """Render the main UI - requires authentication"""
    return render(request, 'accounting/index.html')


@login_required
def journal_view(request):
    """Render the Journal Register in ICAI format - requires authentication"""
    entries = JournalEntry.objects.filter(
        status__in=['posted', 'approved', 'pending_review']
    ).prefetch_related('lines').order_by('-transaction_date', '-entry_number')

    return render(request, 'accounting/journal.html', {'entries': entries})


@login_required
def review_entries(request):
    """Render the Review page for non-posted entries - requires authentication"""
    # Exclude posted entries - show everything else
    entries = JournalEntry.objects.exclude(
        status='posted'
    ).prefetch_related('lines').order_by('-transaction_date', '-created_at')

    return render(request, 'accounting/review_entries.html', {'entries': entries})


@login_required
def journal_detail(request, entry_id):
    """Render the detailed view of a journal entry - requires authentication"""
    entry = get_object_or_404(JournalEntry, id=entry_id)
    return render(request, 'accounting/journal_detail.html', {'entry': entry})

@login_required
def export_journal_pdf(request):
    """Generate and download Journal PDF - requires authentication"""
    from .pdf_service import generate_journal_pdf

    entries = JournalEntry.objects.filter(
        status__in=['posted', 'approved', 'pending_review']
    ).prefetch_related('lines').order_by('-transaction_date', '-entry_number')

    buffer = generate_journal_pdf(entries)

    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"journal_register_{dt_date.today()}.pdf"
    )


@login_required
def trial_balance_view(request):
    """Render Trial Balance in ICAI format - requires authentication"""
    # Get date parameter (default to today)
    as_of_date_str = request.GET.get('as_of_date')
    if as_of_date_str:
        try:
            as_of_date = dt_date.fromisoformat(as_of_date_str)
        except ValueError:
            as_of_date = dt_date.today()
    else:
        as_of_date = dt_date.today()

    # Get trial balance data
    tb_data = get_trial_balance(as_of_date)

    return render(request, 'accounting/trial_balance.html', tb_data)


@login_required
def export_trial_balance_pdf(request):
    """Generate and download Trial Balance PDF - requires authentication"""
    from .trial_balance_pdf import generate_trial_balance_pdf
    
    # Get date parameter (default to today)
    as_of_date_str = request.GET.get('as_of_date')
    if as_of_date_str:
        try:
            as_of_date = dt_date.fromisoformat(as_of_date_str)
        except ValueError:
            as_of_date = dt_date.today()
    else:
        as_of_date = dt_date.today()
    
    # Get trial balance data
    tb_data = get_trial_balance(as_of_date)
    
    buffer = generate_trial_balance_pdf(tb_data)
    
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"trial_balance_{as_of_date}.pdf"
    )

@login_required
def profit_loss_view(request):
    """Render Profit & Loss Statement in ICAI format - requires authentication"""
    # Get date parameters
    from_date_str = request.GET.get('from_date')
    to_date_str = request.GET.get('to_date')

    from_date = None
    if from_date_str:
        try:
            from_date = dt_date.fromisoformat(from_date_str)
        except ValueError:
            pass

    to_date = dt_date.today()
    if to_date_str:
        try:
            to_date = dt_date.fromisoformat(to_date_str)
        except ValueError:
            to_date = dt_date.today()

    # Get P&L data
    pnl_data = get_profit_loss(from_date, to_date)

    return render(request, 'accounting/profit_loss.html', pnl_data)


@login_required
def export_pnl_pdf(request):
    """Generate and download P&L PDF - requires authentication"""
    from .pnl_pdf import generate_pnl_pdf
    
    # Get date parameters
    from_date_str = request.GET.get('from_date')
    to_date_str = request.GET.get('to_date')
    
    from_date = None
    if from_date_str:
        try:
            from_date = dt_date.fromisoformat(from_date_str)
        except ValueError:
            pass
    
    to_date = dt_date.today()
    if to_date_str:
        try:
            to_date = dt_date.fromisoformat(to_date_str)
        except ValueError:
            to_date = dt_date.today()
    
    # Get P&L data
    pnl_data = get_profit_loss(from_date, to_date)
    
    buffer = generate_pnl_pdf(pnl_data)
    
    filename = f"profit_loss_{from_date or 'inception'}_{to_date}.pdf"
    
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=filename
    )


@login_required
@require_http_methods(["POST"])
def process_transaction(request):
    """
    API endpoint to process a natural language transaction.
    Expects JSON: { "description": "...", "date": "YYYY-MM-DD" }

    Note: CSRF protection enabled. Frontend must include CSRF token in headers.
    Requires authentication.
    """
    try:
        data = json.loads(request.body)
        description = data.get('description')
        date_str = data.get('date')

        if not description:
            return JsonResponse({'error': 'Description is required'}, status=400)

        if date_str:
            try:
                transaction_date = dt_date.fromisoformat(date_str)
            except ValueError:
                return JsonResponse({'error': 'Invalid date format'}, status=400)
        else:
            transaction_date = None

        api_key = request.headers.get('X-Anthropic-ApiKey')
        result = process_and_save(description, transaction_date, api_key)

        # Serialize result for frontend
        response_data = {
            "success": result["success"],
            "session_id": result.get("session_id"),
            "errors": result["errors"],
            "maker_output": result["raw_maker_output"],
            "checker_output": result["raw_checker_output"],
            "checker_result": result["checker_result"].model_dump() if result.get("checker_result") else None
        }

        if result.get("entry"):
            response_data["entry"] = result["entry"].model_dump(mode='json')

        if result.get("db_entry"):
            response_data["db_entry_id"] = result["db_entry"].id

        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Transaction processing error: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def get_entries(request):
    """
    API to list journal entries for the review queue - requires authentication.
    """
    entries = JournalEntry.objects.all().order_by('-created_at')
    
    data = []
    for entry in entries:
        data.append({
            "id": entry.id,
            "entry_number": entry.entry_number,
            "date": entry.transaction_date,
            "narration": entry.narration,
            "amount": entry.total_amount, # Uses property
            "confidence": entry.ai_confidence,
            "checker_status": entry.checker_status,
            "status": entry.status,
            "created_at": entry.created_at
        })
        
    return JsonResponse({"entries": data})

@login_required
@require_http_methods(["GET"])
def get_entry_logs(request, entry_id):
    """
    API to get logs for a specific entry - requires authentication.
    """
    entry = get_object_or_404(JournalEntry, id=entry_id)
    logs = entry.logs.all().order_by('timestamp')
    
    data = []
    for log in logs:
        data.append({
            "timestamp": log.timestamp,
            "stage": log.stage,
            "level": log.level,
            "message": log.message,
            "prompt": log.prompt_sent,
            "response": log.response_received,
            "tokens": {
                "input": log.input_tokens,
                "output": log.output_tokens
            } if log.input_tokens is not None else None,
            "duration_ms": log.duration_ms
        })
        
    return JsonResponse({"logs": data})

@login_required
@require_http_methods(["GET"])
def get_session_logs(request):
    """
    API to get logs by session_id (for real-time view before keeping) - requires authentication.
    """
    session_id = request.GET.get('session_id')
    if not session_id:
        return JsonResponse({'error': 'session_id required'}, status=400)
        
    logs = AgentLog.objects.filter(session_id=session_id).order_by('timestamp')
    
    data = []
    for log in logs:
        data.append({
            "timestamp": log.timestamp,
            "stage": log.stage,
            "level": log.level,
            "message": log.message,
            "prompt": log.prompt_sent,
            "response": log.response_received,
            "tokens": {
                "input": log.input_tokens,
                "output": log.output_tokens
            } if log.input_tokens is not None else None,
            "duration_ms": log.duration_ms
        })
        
    return JsonResponse({"logs": data})

@login_required
@require_http_methods(["POST"])
def approve_entry(request, entry_id):
    """
    Approve an entry - requires authentication.

    Note: CSRF protection enabled. Frontend must include CSRF token in headers.
    """
    entry = get_object_or_404(JournalEntry, id=entry_id)
    try:
        reviewer = request.user.username
        entry.approve(reviewer=reviewer)

        return JsonResponse({"success": True})
    except Exception as e:
        logger.error(f"Entry approval error: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
def reject_entry(request, entry_id):
    """
    Reject an entry - requires authentication.

    Note: CSRF protection enabled. Frontend must include CSRF token in headers.
    """
    entry = get_object_or_404(JournalEntry, id=entry_id)
    try:
        data = json.loads(request.body)
        reason = data.get('reason', 'Rejected by user')
        reviewer = "Admin"  # In real app, get from request.user
        entry.reject(reviewer=reviewer, notes=reason)

        return JsonResponse({"success": True})
    except Exception as e:
        logger.error(f"Entry rejection error: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
def account_ledger(request, account_code):
    """Render account ledger showing all transactions for an account - requires authentication"""
    # Get date parameters (optional)
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    start_date = None
    end_date = None
    
    if start_date_str:
        try:
            start_date = dt_date.fromisoformat(start_date_str)
        except ValueError:
            pass
    
    if end_date_str:
        try:
            end_date = dt_date.fromisoformat(end_date_str)
        except ValueError:
            pass
    
    # Get ledger data
    ledger_data = get_account_ledger(account_code, start_date, end_date)
    
    # Handle account not found
    if ledger_data.get('error'):
        return render(request, 'accounting/account_ledger.html', {
            'error': ledger_data['error']
        })
    
    return render(request, 'accounting/account_ledger.html', ledger_data)


@login_required
def evals_view(request):
    """Render the evals page for exporting agent behavior data - requires authentication"""
    from django.db.models import Sum, Avg
    
    # Get statistics for display
    total_entries = JournalEntry.objects.count()
    avg_confidence = JournalEntry.objects.aggregate(avg=Avg('ai_confidence'))['avg'] or 0
    
    stats = {
        'total_entries': total_entries,
        'avg_confidence': avg_confidence,
        'by_status': {}
    }
    
    # Count by status
    status_counts = JournalEntry.objects.values('status').annotate(count=Count('id'))
    for item in status_counts:
        stats['by_status'][item['status']] = item['count']
    
    return render(request, 'accounting/evals.html', {'stats': stats})


@login_required
@require_http_methods(["GET"])
def export_evals_json(request):
    """Export agent behavior data as JSON for evaluation and training - requires authentication"""
    from django.utils import timezone
    from decimal import Decimal
    
    # Get filter parameters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    status_filter = request.GET.get('status')
    min_confidence = request.GET.get('min_confidence')
    transaction_type = request.GET.get('transaction_type')
    
    # Build query
    entries_query = JournalEntry.objects.all().prefetch_related('lines', 'logs')
    
    filters_applied = {}
    
    if start_date_str:
        try:
            start_date = dt_date.fromisoformat(start_date_str)
            entries_query = entries_query.filter(transaction_date__gte=start_date)
            filters_applied['start_date'] = start_date_str
        except ValueError:
            pass
    
    if end_date_str:
        try:
            end_date = dt_date.fromisoformat(end_date_str)
            entries_query = entries_query.filter(transaction_date__lte=end_date)
            filters_applied['end_date'] = end_date_str
        except ValueError:
            pass
    
    if status_filter:
        entries_query = entries_query.filter(status=status_filter)
        filters_applied['status'] = status_filter
    
    if min_confidence:
        try:
            min_conf = float(min_confidence)
            entries_query = entries_query.filter(ai_confidence__gte=min_conf)
            filters_applied['min_confidence'] = min_conf
        except ValueError:
            pass
    
    if transaction_type:
        entries_query = entries_query.filter(transaction_type=transaction_type)
        filters_applied['transaction_type'] = transaction_type
    
    # Build export data
    export_data = {
        "export_metadata": {
            "exported_at": timezone.now().isoformat(),
            "total_entries": entries_query.count(),
            "filters_applied": filters_applied
        },
        "entries": []
    }
    
    for entry in entries_query.order_by('-transaction_date', '-created_at'):
        # Build journal entry lines
        lines_data = []
        for line in entry.lines.all():
            lines_data.append({
                "account_code": line.account_code,
                "account_name": line.account_name,
                "debit": float(line.debit) if line.debit else 0,
                "credit": float(line.credit) if line.credit else 0
            })
        
        # Build agent logs
        logs_data = []
        for log in entry.logs.all().order_by('timestamp'):
            log_entry = {
                "timestamp": log.timestamp.isoformat(),
                "stage": log.stage,
                "level": log.level,
                "message": log.message
            }
            
            # Include prompt and completion if available
            if log.prompt_sent:
                log_entry["prompt"] = log.prompt_sent
            if log.response_received:
                log_entry["completion"] = log.response_received
            
            # Include token usage if available
            if log.input_tokens is not None:
                log_entry["tokens"] = {
                    "input": log.input_tokens,
                    "output": log.output_tokens
                }
            
            if log.duration_ms is not None:
                log_entry["duration_ms"] = log.duration_ms
            
            logs_data.append(log_entry)
        
        # Aggregate performance metrics
        total_input_tokens = 0
        total_output_tokens = 0
        total_duration_ms = 0
        
        for log in entry.logs.all():
            if log.input_tokens:
                total_input_tokens += log.input_tokens
            if log.output_tokens:
                total_output_tokens += log.output_tokens
            if log.duration_ms:
                total_duration_ms += log.duration_ms
        
        # Build entry data
        entry_data = {
            "entry_id": str(entry.id),
            "entry_number": entry.entry_number,
            "transaction_date": entry.transaction_date.isoformat(),
            "created_at": entry.created_at.isoformat(),
            
            "input": {
                "source_text": entry.source_text,
                "transaction_type": entry.transaction_type,
                "reference": entry.reference
            },
            
            "maker_output": {
                "reasoning": entry.ai_reasoning,
                "confidence": float(entry.ai_confidence),
                "warnings": entry.ai_warnings,
                "journal_entry": {
                    "narration": entry.narration,
                    "lines": lines_data
                }
            },
            
            "checker_output": {
                "status": entry.checker_status,
                "errors": entry.checker_errors,
                "warnings": entry.checker_warnings,
                "summary": entry.checker_summary
            },
            
            "ground_truth": {
                "final_status": entry.status,
                "reviewed_by": entry.reviewed_by,
                "review_notes": entry.review_notes,
                "reviewed_at": entry.reviewed_at.isoformat() if entry.reviewed_at else None,
                "posted_at": entry.posted_at.isoformat() if entry.posted_at else None
            },
            
            "performance": {
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
                "processing_time_ms": total_duration_ms
            },
            
            "agent_logs": logs_data
        }
        
        export_data["entries"].append(entry_data)
    
    # Return JSON response
    response = JsonResponse(export_data, json_dumps_params={'indent': 2})
    response['Content-Disposition'] = f'attachment; filename="agent_evals_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
    
    return response
