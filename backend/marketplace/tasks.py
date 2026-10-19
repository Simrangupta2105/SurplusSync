"""
Background and scheduled tasks for the marketplace application.
"""
import logging
from django.utils import timezone
from marketplace.models import Listing

logger = logging.getLogger(__name__)


def expire_stale_listings() -> int:
    """
    Cancels OPEN marketplace listings whose pickup window end date has passed.
    """
    now = timezone.now()
    logger.info("Starting expire_stale_listings at %s", now)
    
    stale_listings = Listing.objects.filter(
        status=Listing.Status.OPEN,
        pickup_window_end__lt=now,
    )
    count = stale_listings.count()
    updated = stale_listings.update(status=Listing.Status.CANCELLED)
    
    logger.info("Finished expire_stale_listings: marked %d listing(s) as CANCELLED", updated)
    return updated
