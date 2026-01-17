"""
Email notification service for accounting application.

Handles sending notifications for:
- Entry approvals
- Entry rejections
- Flagged entries requiring review
"""
import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger('accounting')


def send_entry_approval_notification(entry, reviewer='System'):
    """
    Send email notification when a journal entry is approved.

    Args:
        entry: JournalEntry instance
        reviewer: Name of person/system who approved (default: 'System')
    """
    subject = f'Journal Entry Approved: {entry.entry_number}'

    message = f"""
Journal Entry {entry.entry_number} has been approved by {reviewer}.

Transaction Details:
- Entry Number: {entry.entry_number}
- Date: {entry.transaction_date}
- Narration: {entry.narration}
- Total Amount: ₹{entry.total_amount}
- Status: {entry.get_status_display()}

View entry: {settings.SITE_URL}/accounting/journal/{entry.id}/

---
This is an automated notification from Rural Accounting System.
"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.NOTIFICATION_EMAIL],
            fail_silently=False,
        )
        logger.info(f"Approval notification sent for entry {entry.entry_number}")
        return True
    except Exception as e:
        logger.error(
            f"Failed to send approval notification for entry {entry.entry_number}: {str(e)}",
            exc_info=True
        )
        return False


def send_entry_rejection_notification(entry, reviewer='System', reason=''):
    """
    Send email notification when a journal entry is rejected.

    Args:
        entry: JournalEntry instance
        reviewer: Name of person/system who rejected (default: 'System')
        reason: Reason for rejection (optional)
    """
    subject = f'Journal Entry Rejected: {entry.entry_number}'

    reason_text = f'\nReason: {reason}' if reason else ''

    message = f"""
Journal Entry {entry.entry_number} has been rejected by {reviewer}.{reason_text}

Transaction Details:
- Entry Number: {entry.entry_number}
- Date: {entry.transaction_date}
- Narration: {entry.narration}
- Total Amount: ₹{entry.total_amount}

View entry: {settings.SITE_URL}/accounting/journal/{entry.id}/

---
This is an automated notification from Rural Accounting System.
"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.NOTIFICATION_EMAIL],
            fail_silently=False,
        )
        logger.info(f"Rejection notification sent for entry {entry.entry_number}")
        return True
    except Exception as e:
        logger.error(
            f"Failed to send rejection notification for entry {entry.entry_number}: {str(e)}",
            exc_info=True
        )
        return False


def send_entry_flagged_notification(entry, errors):
    """
    Send email notification when a journal entry is flagged by the checker.

    Args:
        entry: JournalEntry instance
        errors: List of error messages or single error string
    """
    subject = f'Journal Entry Flagged for Review: {entry.entry_number}'

    # Handle both list and string errors
    if isinstance(errors, list):
        errors_text = '\n'.join(f'  - {error}' for error in errors)
    else:
        errors_text = f'  - {errors}'

    message = f"""
Journal Entry {entry.entry_number} has been flagged for review.

Issues Found:
{errors_text}

Transaction Details:
- Entry Number: {entry.entry_number}
- Date: {entry.transaction_date}
- Narration: {entry.narration}
- Total Amount: ₹{entry.total_amount}

Review entry: {settings.SITE_URL}/accounting/review/
View details: {settings.SITE_URL}/accounting/journal/{entry.id}/

---
This is an automated notification from Rural Accounting System.
"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.NOTIFICATION_EMAIL],
            fail_silently=False,
        )
        logger.info(f"Flagged notification sent for entry {entry.entry_number}")
        return True
    except Exception as e:
        logger.error(
            f"Failed to send flagged notification for entry {entry.entry_number}: {str(e)}",
            exc_info=True
        )
        return False


def send_processing_error_notification(description, error_message):
    """
    Send email notification when transaction processing fails.

    Args:
        description: Transaction description
        error_message: Error message from the system
    """
    subject = 'Transaction Processing Failed'

    message = f"""
A transaction failed to process in the Rural Accounting System.

Transaction Description:
{description[:200]}{'...' if len(description) > 200 else ''}

Error:
{error_message}

Please review the system logs for more details.

---
This is an automated notification from Rural Accounting System.
"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.NOTIFICATION_EMAIL],
            fail_silently=False,
        )
        logger.info("Processing error notification sent")
        return True
    except Exception as e:
        logger.error(
            f"Failed to send processing error notification: {str(e)}",
            exc_info=True
        )
        return False
