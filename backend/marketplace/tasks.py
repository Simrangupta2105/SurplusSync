"""
Background and scheduled tasks for the marketplace application.
"""
import logging
from django.utils import timezone
from marketplace.models import Listing
from marketplace.services import process_donations

logger = logging.getLogger(__name__)


def expire_stale_listings() -> int:
    """
    Cancels OPEN marketplace listings whose pickup window end date has passed.
    """
    now = timezone.now()
    logger.info("Starting expire_stale_listings at %s", now)
    
    stale_listings = Listing.objects.filter(
        status=Listing.Status.OPEN,
        available_until__lt=now,
    )
    count = stale_listings.count()
    updated = stale_listings.update(status=Listing.Status.CANCELLED)
    
    logger.info("Finished expire_stale_listings: marked %d listing(s) as CANCELLED", updated)
    return updated


def process_donations_task() -> dict:
    """
    Periodic task to process donation lifecycle timeouts,
    auto-expirations, and auto-completions.
    """
    logger.info("Starting process_donations_task")
    summary = process_donations()
    logger.info("Finished process_donations_task: %s", summary)
    return summary


def run_matching_engine_task() -> dict:
    """
    Periodic task to match open surplus food listings with active NGO requirements
    and dispatch notification alerts.
    """
    from marketplace.matching import batch_run_matching_engine
    logger.info("Starting run_matching_engine_task")
    stats = batch_run_matching_engine(min_score=40.0, top_n=5)
    logger.info("Finished run_matching_engine_task: %s", stats)
    return stats


