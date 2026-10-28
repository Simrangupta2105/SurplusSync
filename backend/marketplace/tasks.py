"""
Background and scheduled tasks for SurplusSync marketplace logistics.
Includes 24h & 2h reminder notifications and overdue pickup tracking.
"""
from datetime import timedelta
from django.utils import timezone
from .models import DonationRequest, Listing, Notification, SurplusListing


def expire_stale_listings():
    """
    Cancels open Listing entries whose pickup_window_end has passed.
    Also expires SurplusListing entries whose available_until has passed.
    """
    now = timezone.now()
    count = Listing.objects.filter(
        status=Listing.Status.OPEN,
        pickup_window_end__lt=now,
    ).update(status=Listing.Status.CANCELLED)

    SurplusListing.objects.filter(
        status=SurplusListing.Status.OPEN,
        available_until__lt=now,
    ).update(status=SurplusListing.Status.EXPIRED)

    return count


def send_pickup_reminders_task():
    """
    Scans active donation requests and dispatches 24h and 2h reminder notifications
    to both donor and NGO organizations idempotently.
    """
    now = timezone.now()
    active_statuses = [
        DonationRequest.Status.APPROVED,
        DonationRequest.Status.SCHEDULED,
    ]

    requests = DonationRequest.objects.filter(
        status__in=active_statuses
    ).select_related("listing", "listing__donor", "ngo")

    sent_24h = 0
    sent_2h = 0

    for req in requests:
        start = req.confirmed_pickup_start or req.proposed_pickup_start
        if not start or start <= now:
            continue

        donor = req.listing.donor if req.listing else None
        ngo = req.ngo
        qty = req.quantity_approved or req.quantity_requested
        unit = req.listing.unit if req.listing else "kg"
        title = req.listing.title if req.listing else "Food Surplus"
        start_str = start.strftime("%b %d, %Y at %I:%M %p")

        # 1. 24-Hour Reminder: window starts within next 24 hours
        if start <= now + timedelta(hours=24):
            # Check donor
            if donor and not Notification.objects.filter(
                organization=donor,
                type="PICKUP_REMINDER_24H",
                link__contains=req.code,
            ).exists():
                Notification.objects.create(
                    organization=donor,
                    type="PICKUP_REMINDER_24H",
                    title=f"Pickup in 24 Hours: {req.code}",
                    body=f"Upcoming pickup of {qty} {unit} of '{title}' by {ngo.name if ngo else 'NGO'} is scheduled for {start_str}.",
                    link=f"/schedule?request={req.code}",
                )
                sent_24h += 1

            # Check NGO
            if ngo and not Notification.objects.filter(
                organization=ngo,
                type="PICKUP_REMINDER_24H",
                link__contains=req.code,
            ).exists():
                Notification.objects.create(
                    organization=ngo,
                    type="PICKUP_REMINDER_24H",
                    title=f"Pickup in 24 Hours: {req.code}",
                    body=f"Upcoming pickup of {qty} {unit} of '{title}' from {donor.name if donor else 'Donor'} is scheduled for {start_str}.",
                    link=f"/schedule?request={req.code}",
                )
                sent_24h += 1

        # 2. 2-Hour Reminder: window starts within next 2 hours
        if start <= now + timedelta(hours=2):
            # Check donor
            if donor and not Notification.objects.filter(
                organization=donor,
                type="PICKUP_REMINDER_2H",
                link__contains=req.code,
            ).exists():
                Notification.objects.create(
                    organization=donor,
                    type="PICKUP_REMINDER_2H",
                    title=f"Urgent: Pickup in 2 Hours: {req.code}",
                    body=f"Pickup of {qty} {unit} of '{title}' by {ngo.name if ngo else 'NGO'} begins shortly at {start_str}. Please ensure food items are packaged and ready.",
                    link=f"/schedule?request={req.code}",
                )
                sent_2h += 1

            # Check NGO
            if ngo and not Notification.objects.filter(
                organization=ngo,
                type="PICKUP_REMINDER_2H",
                link__contains=req.code,
            ).exists():
                Notification.objects.create(
                    organization=ngo,
                    type="PICKUP_REMINDER_2H",
                    title=f"Urgent: Pickup in 2 Hours: {req.code}",
                    body=f"Pickup of {qty} {unit} of '{title}' from {donor.name if donor else 'Donor'} begins shortly at {start_str}. Ensure driver/vehicle is dispatched.",
                    link=f"/schedule?request={req.code}",
                )
                sent_2h += 1

    return {
        "reminders_24h_sent": sent_24h,
        "reminders_2h_sent": sent_2h,
        "total_sent": sent_24h + sent_2h,
    }


def track_overdue_pickups_task():
    """
    Identifies active requests (APPROVED, SCHEDULED, IN_TRANSIT) where pickup
    window has expired, marks overdue status, and dispatches PICKUP_OVERDUE notifications
    once per overdue request to both donor and NGO.
    """
    now = timezone.now()
    active_statuses = [
        DonationRequest.Status.APPROVED,
        DonationRequest.Status.SCHEDULED,
        DonationRequest.Status.IN_TRANSIT,
    ]

    requests = DonationRequest.objects.filter(
        status__in=active_statuses
    ).select_related("listing", "listing__donor", "ngo")

    overdue_requests = []
    notifs_sent = 0

    for req in requests:
        end = req.confirmed_pickup_end or req.proposed_pickup_end
        if not end or end >= now:
            continue

        overdue_minutes = int((now - end).total_seconds() / 60)
        overdue_requests.append({
            "request_id": req.id,
            "code": req.code,
            "status": req.status,
            "overdue_minutes": overdue_minutes,
        })

        donor = req.listing.donor if req.listing else None
        ngo = req.ngo
        qty = req.quantity_approved or req.quantity_requested
        unit = req.listing.unit if req.listing else "kg"
        title = req.listing.title if req.listing else "Food Surplus"
        hours_overdue = overdue_minutes // 60
        mins_overdue = overdue_minutes % 60
        overdue_desc = f"{hours_overdue}h {mins_overdue}m" if hours_overdue > 0 else f"{mins_overdue}m"

        # Check donor overdue notification
        if donor and not Notification.objects.filter(
            organization=donor,
            type="PICKUP_OVERDUE",
            link__contains=req.code,
        ).exists():
            Notification.objects.create(
                organization=donor,
                type="PICKUP_OVERDUE",
                title=f"Action Required: Pickup Overdue - {req.code}",
                body=f"Pickup window for {qty} {unit} of '{title}' ended {overdue_desc} ago. Please coordinate with {ngo.name if ngo else 'NGO'} or update status.",
                link=f"/schedule?request={req.code}",
            )
            notifs_sent += 1

        # Check NGO overdue notification
        if ngo and not Notification.objects.filter(
            organization=ngo,
            type="PICKUP_OVERDUE",
            link__contains=req.code,
        ).exists():
            Notification.objects.create(
                organization=ngo,
                type="PICKUP_OVERDUE",
                title=f"Action Required: Pickup Overdue - {req.code}",
                body=f"Pickup window for {qty} {unit} of '{title}' from {donor.name if donor else 'Donor'} ended {overdue_desc} ago. Please complete handoff or report no-show.",
                link=f"/schedule?request={req.code}",
            )
            notifs_sent += 1

    return {
        "overdue_count": len(overdue_requests),
        "notifications_sent": notifs_sent,
        "overdue_requests": overdue_requests,
    }
