"""
Background tasks for the inventory application.
"""
import logging
from datetime import date
from typing import Optional

from inventory.services import evaluate_expiry_alerts

logger = logging.getLogger(__name__)


def run_expiry_check(days: int = 7, organization=None) -> dict:
    """
    Evaluates expiry dates for batches and generates or escalates alerts according to AlertRules.
    Used by both the 'check_expiry' management command and django-q2 scheduled tasks.

    Idempotent: running it multiple times consecutively does not generate duplicate alerts
    or mark already expired batches again.

    Logs start, end, and counts: batches checked, batches marked EXPIRED, alerts created.
    """
    today = date.today()
    logger.info(
        "Expiry check started for %s (organization=%s, days=%d)",
        today,
        organization,
        days,
    )

    try:
        res = evaluate_expiry_alerts(organization=organization, default_days=days)
    except Exception as exc:
        logger.error(
            "Expiry check failed for %s (organization=%s): %s",
            today,
            organization,
            exc,
            exc_info=True,
        )
        raise

    batches_checked = res.get("batches_checked", 0)
    batches_expired = res.get("batches_expired", 0)
    alerts_created = res.get("alerts_created", 0)
    alerts_updated = res.get("alerts_updated", 0)

    logger.info(
        "Expiry check finished for %s: %d batches checked, %d batches marked EXPIRED, %d alerts created, %d alerts updated.",
        today,
        batches_checked,
        batches_expired,
        alerts_created,
        alerts_updated,
    )

    # Dispatch daily expiry digests (1 digest per organization per run)
    try:
        from core.emailing import send_expiry_digest_for_organization
        from inventory.models import Alert

        if organization is not None:
            org_id = organization.id if hasattr(organization, 'id') else int(organization)
            send_expiry_digest_for_organization(org_id, target_date_str=str(today))
        else:
            org_ids = list(
                Alert.objects.filter(is_acknowledged=False)
                .values_list("organization_id", flat=True)
                .distinct()
            )
            for org_id in org_ids:
                send_expiry_digest_for_organization(org_id, target_date_str=str(today))
    except Exception as email_err:
        logger.warning("Error dispatching expiry digests: %s", email_err)

    return res


def process_import_job(job_id: int):
    """
    Asynchronous task to process a CSV ImportJob.
    Takes simple serializable integer job_id.
    Reuses the existing importer service.
    """
    from inventory.models import ImportJob
    from inventory.services import process_import_job as service_process_import_job

    logger.info("Starting background import job for job_id=%s", job_id)
    try:
        import_job = ImportJob.objects.get(id=job_id)
    except ImportJob.DoesNotExist:
        logger.error("ImportJob with id=%s does not exist", job_id)
        return None

    return service_process_import_job(import_job)

