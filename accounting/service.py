"""
Django service for the accounting agent.
Orchestrates Maker and Checker skills via Claude API.
"""

import json
import anthropic
import uuid
import time
import html
import logging
from pathlib import Path
from datetime import date
from decimal import Decimal
from typing import Optional
from django.conf import settings
from django.utils import timezone

from .schemas import (
    TransactionInput,
    JournalEntry,
    JournalLine,
    CheckerResult,
    TransactionType,
    AccountCode,
    GSTBreakdown,
)
from .models import AgentLog

logger = logging.getLogger('accounting')


def sanitize_user_input(text: str) -> str:
    """
    Sanitize user input to prevent prompt injection attacks.
    Escapes XML/HTML special characters that could break prompt structure.

    Args:
        text: User-provided input string

    Returns:
        Sanitized string with HTML/XML entities escaped
    """
    if not text:
        return text

    # Escape HTML/XML special characters
    sanitized = html.escape(text, quote=True)

    # Additional check: detect and log potential injection attempts
    suspicious_patterns = ['</input>', '</skill>', '<eval>', '<system>']
    if any(pattern.lower() in text.lower() for pattern in suspicious_patterns):
        logger.warning(f"Potential prompt injection attempt detected: {text[:100]}")

    return sanitized


class AccountingAgentService:
    """
    Main service for processing transactions through Maker and Checker.
    
    Usage:
        service = AccountingAgentService(api_key="sk-ant-...")
        result = service.process("Raising invoice to Shree Cement for 1,18,000")
    """
    
    def __init__(self, api_key: str, skills_path: Optional[str] = None):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
        
        today_str = date.today().isoformat()
        
        self.maker_skill = Path(settings.ACCOUNTING_SKILLS['MAKER']).read_text().replace("{{CURRENT_DATE}}", today_str)
        self.checker_skill = Path(settings.ACCOUNTING_SKILLS['CHECKER']).read_text().replace("{{CURRENT_DATE}}", today_str)
    
    def _create_log(self, session_id: str, stage: str, level: str, message: str, **kwargs):
        """Helper to create AgentLog entry"""
        try:
            return AgentLog.objects.create(
                session_id=session_id,
                stage=stage,
                level=level,
                message=message,
                **kwargs
            )
        except Exception as e:
            # Fallback if DB logging fails, just print to console to avoid breaking flow
            print(f"LOGGING FAILED: {e}")
            return None

    def _call_maker(self, description: str, transaction_date: date) -> dict:
        """
        Call Claude with Maker skill to generate journal entry.
        Returns detailed response dict with content and usage stats.
        """
        start_time = time.time()
        
        prompt = f"""You are an accounting assistant. Follow the skill document exactly.

<skill>
{self.maker_skill}
</skill>

<input>
Description: {sanitize_user_input(description)}
Date: {transaction_date.isoformat()}
</input>

Generate the journal entry as specified in the skill. Output ONLY the JSON object, no other text."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Extract JSON from response
        text_content = response.content[0].text
        
        # Try to parse JSON (handle markdown code blocks if present)
        clean_content = text_content
        if "```json" in text_content:
            clean_content = text_content.split("```json")[1].split("```")[0]
        elif "```" in text_content:
            clean_content = text_content.split("```")[1].split("```")[0]
        
        try:
            parsed_json = json.loads(clean_content.strip())
        except json.JSONDecodeError:
            parsed_json = None
            
        return {
            "parsed": parsed_json,
            "raw_text": text_content,
            "prompt": prompt,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "duration_ms": duration_ms
        }
    
    def _call_checker(self, entry_json: dict, original_input: str) -> dict:
        """
        Call Claude with Checker skill to validate entry.
        Returns detailed response dict with content and usage stats.
        """
        start_time = time.time()
        
        prompt = f"""You are an accounting auditor. Follow the skill document exactly.

<skill>
{self.checker_skill}
</skill>

<original_input>
{sanitize_user_input(original_input)}
</original_input>

<entry_to_validate>
{json.dumps(entry_json, indent=2)}
</entry_to_validate>

Validate the entry as specified in the skill. Output ONLY the JSON object, no other text."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        text_content = response.content[0].text
        
        clean_content = text_content
        if "```json" in text_content:
            clean_content = text_content.split("```json")[1].split("```")[0]
        elif "```" in text_content:
            clean_content = text_content.split("```")[1].split("```")[0]
            
        try:
            parsed_json = json.loads(clean_content.strip())
        except json.JSONDecodeError:
            parsed_json = None
        
        return {
            "parsed": parsed_json,
            "raw_text": text_content,
            "prompt": prompt,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "duration_ms": duration_ms
        }
    
    def process(self, description: str, transaction_date: Optional[date] = None) -> dict:
        """
        Process a transaction description through Maker and Checker.
        """
        if transaction_date is None:
            transaction_date = date.today()
            
        session_id = str(uuid.uuid4())
        
        result = {
            "success": False,
            "entry": None,
            "checker_result": None,
            "errors": [],
            "raw_maker_output": None,
            "raw_checker_output": None,
            "session_id": session_id,
            "logs": [] # Just for internal return, actual logs in DB
        }
        
        # Log: Input Received
        self._create_log(
            session_id=session_id,
            stage=AgentLog.Stage.INPUT,
            level=AgentLog.Level.INFO,
            message=f"Received input: {description}",
        )
        
        # Step 1: Call Maker
        try:
            self._create_log(
                session_id=session_id,
                stage=AgentLog.Stage.MAKER,
                level=AgentLog.Level.INFO,
                message="Starting Maker Agent..."
            )
            
            maker_resp = self._call_maker(description, transaction_date)
            
            # Log Maker Result
            self._create_log(
                session_id=session_id,
                stage=AgentLog.Stage.MAKER,
                level=AgentLog.Level.INFO,
                message="Maker Agent completed",
                prompt_sent=maker_resp["prompt"],
                response_received=maker_resp["raw_text"],
                input_tokens=maker_resp["input_tokens"],
                output_tokens=maker_resp["output_tokens"],
                duration_ms=maker_resp["duration_ms"]
            )
            
            result["raw_maker_output"] = maker_resp["parsed"]
            
            if maker_resp["parsed"] is None:
                raise ValueError("Maker output could not be parsed as JSON")
                
        except Exception as e:
            error_msg = f"Maker failed: {str(e)}"
            result["errors"].append(error_msg)
            self._create_log(
                session_id=session_id,
                stage=AgentLog.Stage.MAKER,
                level=AgentLog.Level.ERROR,
                message=error_msg
            )
            return result
        
        # Step 2: Validate with Pydantic
        try:
            self._create_log(
                session_id=session_id,
                stage=AgentLog.Stage.VALIDATION,
                level=AgentLog.Level.INFO,
                message="Starting Pydantic validation..."
            )
            
            maker_output = maker_resp["parsed"]
            
            # --- Neuro-Symbolic Repair (Fix Math) ---
            if maker_output.get("transaction_type") == "invoice":
                try:
                    # 1. Identify Total Amount from Debit line (Shree Cement)
                    total_debit = Decimal("0")
                    for line in maker_output["lines"]:
                        if line.get("debit", 0) > 0:
                            total_debit += Decimal(str(line["debit"]))
                    
                    if total_debit > 0:
                        # 2. Calculate correct split
                        breakdown = GSTBreakdown.from_inclusive_amount(total_debit)
                        
                        # 3. Repair the lines
                        for line in maker_output["lines"]:
                            ac = line.get("account_code")
                            if ac == AccountCode.CFA_COMMISSION.value:
                                line["credit"] = float(breakdown.base_amount)
                            elif ac == AccountCode.CGST_PAYABLE.value:
                                line["credit"] = float(breakdown.cgst)
                            elif ac == AccountCode.SGST_PAYABLE.value:
                                line["credit"] = float(breakdown.sgst)
                                
                        self._create_log(
                            session_id=session_id,
                            stage=AgentLog.Stage.MAKER,
                            level=AgentLog.Level.INFO,
                            message=f"Applied Math Repair: Base={breakdown.base_amount}, Tax={breakdown.cgst}"
                        )
                except Exception as repair_e:
                    # Log but don't fail, let validator handle it
                    print(f"Repair failed: {repair_e}")
            # ----------------------------------------
            entry = JournalEntry(
                transaction_date=date.fromisoformat(maker_output["transaction_date"]),
                transaction_type=TransactionType(maker_output["transaction_type"]),
                narration=maker_output["narration"],
                reference=maker_output.get("reference"),
                lines=[
                    JournalLine(
                        account_code=AccountCode(line["account_code"]),
                        account_name=line["account_name"],
                        debit=Decimal(str(line.get("debit", 0))),
                        credit=Decimal(str(line.get("credit", 0)))
                    )
                    for line in maker_output["lines"]
                ],
                reasoning=maker_output["reasoning"],
                confidence=maker_output["confidence"],
                warnings=maker_output.get("warnings", [])
            )
            result["entry"] = entry
            
            self._create_log(
                session_id=session_id,
                stage=AgentLog.Stage.VALIDATION,
                level=AgentLog.Level.INFO,
                message=f"Validation Passed. Balance: {entry.total_amount}"
            )
            
        except Exception as e:
            error_msg = f"Pydantic validation failed: {str(e)}"
            result["errors"].append(error_msg)
            self._create_log(
                session_id=session_id,
                stage=AgentLog.Stage.VALIDATION,
                level=AgentLog.Level.ERROR,
                message=error_msg
            )
            # We continue to checker anyway, effectively "Repair" strategy could go here
        
        # Step 3: Call Checker
        try:
            self._create_log(
                session_id=session_id,
                stage=AgentLog.Stage.CHECKER,
                level=AgentLog.Level.INFO,
                message="Starting Checker Agent..."
            )
            
            checker_resp = self._call_checker(maker_output, description)
            
            self._create_log(
                session_id=session_id,
                stage=AgentLog.Stage.CHECKER,
                level=AgentLog.Level.INFO,
                message=f"Checker Agent completed. Verdict: {checker_resp['parsed'].get('status', 'unknown')}",
                prompt_sent=checker_resp["prompt"],
                response_received=checker_resp["raw_text"],
                input_tokens=checker_resp["input_tokens"],
                output_tokens=checker_resp["output_tokens"],
                duration_ms=checker_resp["duration_ms"]
            )
            
            result["raw_checker_output"] = checker_resp["parsed"]
            
            if checker_resp["parsed"] is None:
                raise ValueError("Checker output could not be parsed as JSON")
                
            checker_result = CheckerResult(
                status=checker_resp["parsed"]["status"],
                errors=checker_resp["parsed"].get("errors", []),
                warnings=checker_resp["parsed"].get("warnings", []),
                summary=checker_resp["parsed"]["summary"]
            )
            result["checker_result"] = checker_result
            
        except Exception as e:
            error_msg = f"Checker failed: {str(e)}"
            result["errors"].append(error_msg)
            self._create_log(
                session_id=session_id,
                stage=AgentLog.Stage.CHECKER,
                level=AgentLog.Level.ERROR,
                message=error_msg
            )
            return result
        
        # Step 4: Determine success
        if result["entry"] is not None and checker_result.status == "approved":
            result["success"] = True
        elif result["entry"] is not None and checker_result.status == "flagged":
            result["success"] = True  # Structurally OK, just needs human review
            
        self._create_log(
            session_id=session_id,
            stage=AgentLog.Stage.COMPLETE,
            level=AgentLog.Level.INFO,
            message=f"Pipeline complete. Success: {result['success']}"
        )
        
        return result
    
    def process_batch(self, descriptions: list[str]) -> list[dict]:
        """Process multiple transactions"""
        results = []
        for desc in descriptions:
            result = self.process(desc)
            result["input"] = desc
            results.append(result)
        return results


# ============== Django Integration Helpers ==============

def get_service(api_key: Optional[str] = None) -> AccountingAgentService:
    """Get configured service instance using Django settings or provided key"""
    from django.conf import settings
    # Prefer provided key, fallback to settings
    key = api_key or settings.ANTHROPIC_API_KEY
    return AccountingAgentService(
        api_key=key,
        skills_path=getattr(settings, 'ACCOUNTING_SKILLS_PATH', None)
    )


def process_and_save(description: str, transaction_date: Optional[date] = None, api_key: Optional[str] = None) -> dict:
    """
    Process transaction and save to database.
    
    Returns the result dict with additional 'db_entry' key containing
    the Django model instance.
    """
    from .models import JournalEntry as DjangoJournalEntry, JournalLine as DjangoJournalLine
    from django.db import transaction
    
    service = get_service(api_key)
    result = service.process(description, transaction_date)
    
    if result["entry"] is None:
        return result
    
    entry = result["entry"]
    checker = result["checker_result"]
    log_session_id = result.get("session_id")
    
    # Determine status based on checker result
    if checker.status == "approved":
        status = "pending_review"  # Still needs human sign-off
    else:
        status = "flagged"
    
    try:
        with transaction.atomic():
            # Create Django model
            db_entry = DjangoJournalEntry.objects.create(
                transaction_date=entry.transaction_date,
                transaction_type=entry.transaction_type.value,
                narration=entry.narration,
                reference=entry.reference or "",
                status=status,
                source_text=description,
                ai_reasoning=entry.reasoning,
                ai_confidence=entry.confidence,
                ai_warnings=entry.warnings,
                checker_status=checker.status,
                checker_errors=checker.errors,
                checker_warnings=checker.warnings,
                checker_summary=checker.summary,
            )
            
            # Create lines
            for line in entry.lines:
                DjangoJournalLine.objects.create(
                    journal_entry=db_entry,
                    account_code=line.account_code.value,
                    account_name=line.account_name,
                    debit=line.debit,
                    credit=line.credit
                )
            
            # Link logs to this entry
            if log_session_id:
                AgentLog.objects.filter(session_id=log_session_id).update(journal_entry=db_entry)
        
        result["db_entry"] = db_entry
        
    except Exception as e:
        # Log database error
        AgentLog.objects.create(
            session_id=log_session_id,
            stage=AgentLog.Stage.COMPLETE,
            level=AgentLog.Level.ERROR,
            message=f"Database save failed: {str(e)}"
        )
        raise e
        
    return result