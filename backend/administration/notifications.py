"""
Notification service for platform admin decisions on organizations.
Uses Django's configured EMAIL_BACKEND.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def notify_organization_decision(organization, action: str, reason: str = ""):
    """
    Sends an email notification to all active users belonging to the organization
    about an administrative decision (VERIFIED, REJECTED, SUSPENDED, REINSTATED).
    """
    status_display = {
        "VERIFIED": "Verified",
        "REJECTED": "Rejected",
        "SUSPENDED": "Suspended",
        "REINSTATED": "Reinstated",
    }.get(action, action.title())

    subject = f"[SurplusSync] Organization Status Update: {status_display}"

    body_lines = [
        f"Dear {organization.name} team,",
        "",
        f"This is an official notice that your organization '{organization.name}' has been marked as {status_display.upper()} on SurplusSync.",
    ]

    if reason:
        body_lines.append("")
        body_lines.append(f"Notes / Reason provided: {reason}")

    if action == "VERIFIED":
        body_lines.append("")
        body_lines.append("You now have full access to surplus food listings and donation features.")
    elif action == "SUSPENDED":
        body_lines.append("")
        body_lines.append("Your account access and operations have been temporarily suspended. Please contact platform support.")
    elif action == "REJECTED":
        body_lines.append("")
        body_lines.append("Your verification request was rejected. Please review the reason above and resubmit with updated documents if applicable.")
    elif action == "REINSTATED":
        body_lines.append("")
        body_lines.append("Your account privileges have been restored. You can log in and resume platform activities.")

    body_lines.extend([
        "",
        "Best regards,",
        "The SurplusSync Administration Team",
    ])
    message = "\n".join(body_lines)

    # Gather user emails
    recipient_list = list(
        organization.users.filter(is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )

    if not recipient_list:
        # Fallback to organization contact email or default domain
        fallback_email = f"contact@{organization.name.lower().replace(' ', '')}.org"
        recipient_list = [fallback_email]

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "admin@surplussync.com")

    try:
        from core.emailing import send_notification_email_async
        send_notification_email_async(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
        )
        logger.info("Enqueued %s notification for organization %s to %s", action, organization.id, recipient_list)
    except Exception as e:
        logger.error("Failed to enqueue notification for organization %s: %s", organization.id, e)
        raise


def notify_issue_status_change(issue, previous_status: str, new_status: str, note: str = ""):
    """
    Sends an email notification to the reporter (and organization) when an issue status changes.
    """
    subject = f"[SurplusSync] Issue #{issue.id} Status Updated: {new_status}"

    body_lines = [
        f"Hello {issue.reporter.username},",
        "",
        f"The status of your reported issue #{issue.id} ({issue.get_category_display()}) has been updated from {previous_status} to {new_status}.",
    ]

    if note:
        body_lines.append("")
        body_lines.append(f"Admin Notes / Resolution: {note}")

    body_lines.extend([
        "",
        "You can view the full issue details in your portal.",
        "",
        "Best regards,",
        "SurplusSync Support & Moderation Team",
    ])
    message = "\n".join(body_lines)

    recipient_list = []
    if issue.reporter and issue.reporter.email:
        recipient_list.append(issue.reporter.email)
    elif issue.reporter_org:
        recipient_list = list(
            issue.reporter_org.users.filter(is_active=True)
            .exclude(email="")
            .values_list("email", flat=True)
        )

    if not recipient_list:
        recipient_list = [f"user_{issue.reporter_id}@surplussync.com"]

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "support@surplussync.com")

    try:
        from core.emailing import send_notification_email_async
        send_notification_email_async(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
        )
        logger.info("Enqueued issue status notification for issue #%s to %s", issue.id, recipient_list)
    except Exception as e:
        logger.error("Failed to enqueue issue notification for issue #%s: %s", issue.id, e)
        raise

