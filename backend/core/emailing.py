"""
Core emailing service for SurplusSync.
Provides asynchronous, retry-safe email delivery with simple serializable arguments.
Uses Django-Q2 PostgreSQL task broker and standard Django email/MAILERS backend.
"""
import logging
import time
from typing import List, Optional, Union
from django.conf import settings
from django.core.mail import send_mail
from django_q.tasks import async_task

logger = logging.getLogger(__name__)


def send_email_task(
    subject: str,
    message: str,
    recipient_list: Union[List[str], str],
    from_email: Optional[str] = None,
    html_message: Optional[str] = None,
    max_retries: int = 3,
    retry_backoff: float = 0.5,
) -> int:
    """
    Worker task to send an email using Django's configured mailer.
    All arguments are strictly primitive / JSON-serializable types.
    Retries up to `max_retries` with exponential backoff on transient errors.
    """
    if isinstance(recipient_list, str):
        recipient_list = [recipient_list]
    cleaned_recipients = [str(r).strip() for r in recipient_list if r and str(r).strip()]
    if not cleaned_recipients:
        logger.warning("send_email_task invoked without valid recipients; skipping.")
        return 0

    if not from_email:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@surplussync.com")

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            count = send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=cleaned_recipients,
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(
                "Async email sent successfully (subject='%s', recipients=%s)",
                subject, cleaned_recipients
            )
            return count
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Failed to send email attempt %d/%d (subject='%s', recipients=%s): %s",
                attempt, max_retries, subject, cleaned_recipients, exc
            )
            if attempt < max_retries:
                # Exponential backoff: e.g. 0.5s, 1.0s, 2.0s
                sleep_duration = retry_backoff * (2 ** (attempt - 1))
                time.sleep(sleep_duration)

    logger.error(
        "Exhausted %d retries sending email (subject='%s', recipients=%s): %s",
        max_retries, subject, cleaned_recipients, last_error
    )
    raise last_error


def send_notification_email_async(
    subject: str,
    message: str,
    recipient_list: Union[List[str], str],
    from_email: Optional[str] = None,
    html_message: Optional[str] = None,
    sync: bool = False,
) -> Optional[str]:
    """
    Enqueues an email sending job into django-q2 with serializable arguments.
    If sync=True, executes inline immediately.
    """
    if isinstance(recipient_list, str):
        recipients = [recipient_list.strip()]
    else:
        recipients = [str(r).strip() for r in recipient_list if r and str(r).strip()]

    if not recipients:
        logger.warning("send_notification_email_async called with empty recipients; skipping.")
        return None

    from_email = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@surplussync.com")

    if sync:
        send_email_task(
            subject=subject,
            message=message,
            recipient_list=recipients,
            from_email=from_email,
            html_message=html_message,
        )
        return "sync"

    task_id = async_task(
        "core.emailing.send_email_task",
        subject,
        message,
        recipients,
        from_email=from_email,
        html_message=html_message,
    )
    return task_id


def send_registration_welcome_email(user_id: int) -> Optional[str]:
    """
    Sends a welcome email to a newly registered user asynchronously.
    """
    from accounts.models import User

    try:
        user = User.objects.select_related("organization").get(id=user_id)
    except User.DoesNotExist:
        logger.warning("send_registration_welcome_email: user_id %s does not exist", user_id)
        return None

    if not user.email:
        return None

    org_name = user.organization.name if user.organization else "SurplusSync"
    org_type = f" ({user.organization.org_type})" if user.organization else ""

    subject = f"Welcome to SurplusSync, {user.username}!"
    body = (
        f"Hello {user.username},\n\n"
        f"Welcome to SurplusSync! Your account for {org_name}{org_type} has been successfully created.\n\n"
        f"You can now log in and manage your food inventory, monitor batch expiry dates, and connect with "
        f"community partners for surplus redistribution.\n\n"
        f"Best regards,\n"
        f"The SurplusSync Team"
    )

    return send_notification_email_async(
        subject=subject,
        message=body,
        recipient_list=[user.email],
    )


def send_expiry_digest_for_organization(organization_id: int, target_date_str: Optional[str] = None) -> Optional[str]:
    """
    Sends a consolidated daily expiry digest email for a single organization.
    Respects organization.email_alerts_enabled and global settings.EMAIL_ALERTS_ENABLED.
    """
    from accounts.models import Organization
    from inventory.models import Alert, Batch
    from datetime import date

    global_enabled = getattr(settings, "EMAIL_ALERTS_ENABLED", True)
    if not global_enabled:
        logger.info("Global EMAIL_ALERTS_ENABLED is False; skipping expiry digest for org %s", organization_id)
        return None

    try:
        org = Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        logger.warning("send_expiry_digest: organization_id %s not found", organization_id)
        return None

    # Check organization level setting
    if not getattr(org, "email_alerts_enabled", True):
        logger.info("email_alerts_enabled is False for organization '%s' (%s); skipping digest.", org.name, org.id)
        return None

    # Gather active unacknowledged alerts for active non-expired batches for this organization
    today = date.today()
    active_alerts = list(
        Alert.objects.filter(
            organization=org,
            is_acknowledged=False,
            batch__status=Batch.Status.ACTIVE,
            batch__expiry_date__gte=today,
        ).select_related("batch", "batch__product").order_by("batch__expiry_date")
    )

    if not active_alerts:
        logger.info("No active unacknowledged alerts for organization '%s' (%s); skipping digest.", org.name, org.id)
        return None

    # Gather recipient emails from active users in this organization
    recipients = list(
        org.users.filter(is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )

    if not recipients:
        logger.info("No active user email addresses found for organization '%s' (%s); skipping digest.", org.name, org.id)
        return None

    digest_date = target_date_str or str(date.today())
    subject = f"[SurplusSync] Daily Expiry Digest: {org.name} ({len(active_alerts)} alert{'s' if len(active_alerts) > 1 else ''})"

    lines = [
        f"Hello {org.name} Team,",
        "",
        f"This is your automated daily surplus food expiry digest for {digest_date}.",
        f"There are currently {len(active_alerts)} item(s) requiring attention:",
        "",
    ]

    for alert in active_alerts[:50]:  # Cap listing in email for clean formatting
        batch = alert.batch
        product_name = batch.product.name if batch and batch.product else "Item"
        batch_code = batch.batch_code if batch else "N/A"
        expiry = batch.expiry_date if batch else "N/A"
        qty = f"{batch.quantity} {batch.product.unit}" if batch and batch.product else ""
        lines.append(f"• [{alert.severity}] {product_name} (Batch: {batch_code}, Qty: {qty}) - Expires: {expiry}")
        lines.append(f"  Alert: {alert.message}")

    if len(active_alerts) > 50:
        lines.append(f"... and {len(active_alerts) - 50} more alert(s).")

    lines.extend([
        "",
        "Please log in to your SurplusSync dashboard to mark items for reduction or donation.",
        "",
        "Best regards,",
        "SurplusSync Automated Expiry System",
    ])

    message = "\n".join(lines)

    return send_notification_email_async(
        subject=subject,
        message=message,
        recipient_list=recipients,
    )
