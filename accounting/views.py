from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q
import json
from datetime import date as dt_date

from .models import JournalEntry, AgentLog
from .service import process_and_save

def index(request):
    """Render the main UI"""
    return render(request, 'accounting/index.html')

def journal_view(request):
    """Render the Journal Register in ICAI format"""
    entries = JournalEntry.objects.filter(
        status__in=['posted', 'approved', 'pending_review']
    ).prefetch_related('lines').order_by('-transaction_date', '-entry_number')
    
    return render(request, 'accounting/journal.html', {'entries': entries})

def export_journal_pdf(request):
    """Generate and download Journal PDF"""
    from django.http import FileResponse
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

@csrf_exempt
@require_http_methods(["POST"])
def process_transaction(request):
    """
    API endpoint to process a natural language transaction.
    Expects JSON: { "description": "...", "date": "YYYY-MM-DD" }
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
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["GET"])
def get_entries(request):
    """
    API to list journal entries for the review queue.
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

@require_http_methods(["GET"])
def get_entry_logs(request, entry_id):
    """
    API to get logs for a specific entry.
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

@require_http_methods(["GET"])
def get_session_logs(request):
    """
    API to get logs by session_id (for real-time view before keeping).
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

@csrf_exempt
@require_http_methods(["POST"])
def approve_entry(request, entry_id):
    """Approve an entry"""
    entry = get_object_or_404(JournalEntry, id=entry_id)
    try:
        entry.approve(reviewer="Admin") # In real app, get user from request
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)

@csrf_exempt
@require_http_methods(["POST"])
def reject_entry(request, entry_id):
    """Reject an entry"""
    entry = get_object_or_404(JournalEntry, id=entry_id)
    try:
        data = json.loads(request.body)
        reason = data.get('reason', 'Rejected by user')
        entry.reject(reviewer="Admin", notes=reason)
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
