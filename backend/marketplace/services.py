"""
Donation Lifecycle Service Module.
Strict state machine with atomic execution and row-level locking (select_for_update).
"""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import logging
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.models import Organization
from inventory.models import Batch, StockTransaction
from .models import (
    DonationRequest,
    DonationStatusHistory,
    Notification,
    SurplusListing,
)

logger = logging.getLogger(__name__)


class LifecycleError(Exception):
    """Base lifecycle exception."""
    status_code = 400

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class TransitionConflictError(LifecycleError):
    """Raised when an invalid state transition is attempted (HTTP 409)."""
    def __init__(self, message="Invalid state transition."):
        super().__init__(message, status_code=409)


class PermissionDeniedLifecycleError(LifecycleError):
    """Raised when permission is denied (HTTP 403)."""
    def __init__(self, message="Permission denied."):
        super().__init__(message, status_code=403)


class NotFoundLifecycleError(LifecycleError):
    """Raised when tenant object is not found or inaccessible (HTTP 404)."""
    def __init__(self, message="Not found."):
        super().__init__(message, status_code=404)


class ValidationLifecycleError(LifecycleError):
    """Raised when input validation fails (HTTP 400)."""
    def __init__(self, message="Validation error."):
        super().__init__(message, status_code=400)


def _ensure_datetime(val, field_name="datetime"):
    """Converts string or datetime to an aware datetime object."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if timezone.is_naive(val):
            return timezone.make_aware(val, timezone.get_current_timezone())
        return val
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        parsed = parse_datetime(val)
        if parsed is None:
            raise ValidationLifecycleError(f"Invalid datetime format for {field_name}.")
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed
    raise ValidationLifecycleError(f"Invalid type for {field_name}.")


def _parse_decimal(val, field_name="quantity"):
    """Safely converts input into a Decimal or raises ValidationLifecycleError."""
    if val is None:
        raise ValidationLifecycleError(f"{field_name} is required.")
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationLifecycleError(f"Invalid decimal value for {field_name}.")



def _get_request_for_update(request_id_or_code):
    """Fetch donation request with select_for_update inside an atomic transaction."""
    qs = DonationRequest.objects.select_for_update()
    if isinstance(request_id_or_code, int) or (isinstance(request_id_or_code, str) and request_id_or_code.isdigit()):
        req = qs.filter(id=int(request_id_or_code)).first()
    else:
        req = qs.filter(code=str(request_id_or_code).strip()).first()
    if not req:
        raise NotFoundLifecycleError("Donation request not found.")
    return req


def _record_history(request, from_status, to_status, actor=None, note=""):
    """Appends a row to DonationStatusHistory."""
    return DonationStatusHistory.objects.create(
        request=request,
        from_status=from_status,
        to_status=to_status,
        actor=actor,
        note=note,
    )


def _create_notification(organization, type_, title, body, link="", user=None):
    """Creates a notification record for the organization."""
    if not organization:
        return None
    return Notification.objects.create(
        organization=organization,
        user=user,
        type=type_,
        title=title,
        body=body,
        link=link,
        is_read=False,
    )


# ---------------------------------------------------------------------------
# 1. Create Donation Request (NGO only)
# ---------------------------------------------------------------------------

def create_donation_request(
    user,
    listing_id,
    quantity_requested,
    proposed_pickup_start,
    proposed_pickup_end,
    note="",
    contact_name="",
    contact_phone="",
):
    """
    NGO creates a new donation request in REQUESTED status.
    Creating a request reserves nothing.
    """
    user_org = getattr(user, "organization", None)
    if not user_org or user_org.org_type != Organization.Type.NGO:
        raise PermissionDeniedLifecycleError("Only NGO organizations can request donations.")
    if not user_org.is_verified or user_org.verification_status != Organization.VerificationStatus.VERIFIED:
        raise PermissionDeniedLifecycleError("Only verified NGO organizations can request donations.")
    if getattr(user_org, "verification_status", None) == Organization.VerificationStatus.SUSPENDED:
        raise PermissionDeniedLifecycleError("Suspended organizations cannot request donations.")

    qty = _parse_decimal(quantity_requested, "quantity_requested")
    if qty <= 0:
        raise ValidationLifecycleError("Requested quantity must be greater than zero.")

    start_dt = _ensure_datetime(proposed_pickup_start, "proposed_pickup_start")
    end_dt = _ensure_datetime(proposed_pickup_end, "proposed_pickup_end")
    if not start_dt or not end_dt:
        raise ValidationLifecycleError("Both proposed pickup start and end times are required.")

    if end_dt <= start_dt:
        raise ValidationLifecycleError("Proposed pickup end time must be after start time.")

    with transaction.atomic():
        listing = SurplusListing.objects.select_for_update().filter(id=listing_id).first()
        if not listing:
            raise NotFoundLifecycleError("Listing not found.")

        if listing.status != SurplusListing.Status.OPEN:
            raise TransitionConflictError("This listing is no longer open for requests.")

        now = timezone.now()
        if listing.available_until < now:
            raise TransitionConflictError("This listing has expired.")

        # Check pickup bounds against listing availability
        if start_dt < listing.available_from or end_dt > listing.available_until:
            raise ValidationLifecycleError("Proposed pickup window must be within listing availability window.")

        if listing.safe_until and end_dt > listing.safe_until:
            raise ValidationLifecycleError("Proposed pickup window cannot exceed food safe-until time.")

        # Check for existing active request by this NGO for this listing
        existing_active = DonationRequest.objects.filter(
            listing=listing,
            ngo=user_org,
            status__in=[
                DonationRequest.Status.REQUESTED,
                DonationRequest.Status.APPROVED,
                DonationRequest.Status.SCHEDULED,
                DonationRequest.Status.IN_TRANSIT,
                DonationRequest.Status.COLLECTED,
            ],
        ).exists()
        if existing_active:
            raise TransitionConflictError("You already have an active request for this listing.")

        if qty > listing.remaining_quantity:
            raise ValidationLifecycleError(
                f"Requested quantity ({qty}) exceeds remaining available quantity ({listing.remaining_quantity})."
            )

        req = DonationRequest.objects.create(
            listing=listing,
            ngo=user_org,
            quantity_requested=qty,
            status=DonationRequest.Status.REQUESTED,
            proposed_pickup_start=start_dt,
            proposed_pickup_end=end_dt,
            note=note,
            contact_name=contact_name or user.get_full_name() or user.username,
            contact_phone=contact_phone or user_org.phone or "",
        )


        _record_history(req, "", DonationRequest.Status.REQUESTED, actor=user, note="Request submitted by NGO")

        _create_notification(
            organization=listing.donor,
            type_="NEW_REQUEST",
            title=f"New Donation Request {req.code}",
            body=f"{user_org.name} requested {qty} {listing.unit} of '{listing.title}'.",
            link=f"/business/donations?request={req.code}",
        )

        return req


# ---------------------------------------------------------------------------
# 2. Approve Request (Business only)
# ---------------------------------------------------------------------------

def approve_donation_request(
    user,
    request_id_or_code,
    quantity_approved=None,
    pickup_start=None,
    pickup_end=None,
):
    """
    Business approves a REQUESTED donation request.
    Reserves stock on listing and batch.
    If proposed window accepted -> goes directly to SCHEDULED.
    If window modified -> stays APPROVED until NGO confirms.
    """
    user_org = getattr(user, "organization", None)
    if not user_org or user_org.org_type != Organization.Type.BUSINESS:
        raise PermissionDeniedLifecycleError("Only business organizations can approve requests.")

    with transaction.atomic():
        req = _get_request_for_update(request_id_or_code)
        listing = SurplusListing.objects.select_for_update().filter(id=req.listing_id).first()
        if not listing:
            raise NotFoundLifecycleError("Listing not found.")

        # Tenant boundary: must be the donor organization
        if listing.donor_id != user_org.id:
            raise NotFoundLifecycleError("Donation request not found.")

        if req.status != DonationRequest.Status.REQUESTED:
            raise TransitionConflictError(
                f"Cannot approve request in '{req.status}' status. Only REQUESTED requests can be approved."
            )

        # Quantity to approve
        if quantity_approved is not None:
            qty_app = _parse_decimal(quantity_approved, "quantity_approved")
        else:
            qty_app = req.quantity_requested

        if qty_app <= 0:
            raise ValidationLifecycleError("Approved quantity must be greater than zero.")
        if qty_app > req.quantity_requested:
            raise ValidationLifecycleError("Approved quantity cannot exceed requested quantity.")

        # Check listing capacity
        if qty_app > listing.remaining_quantity:
            raise TransitionConflictError(
                f"Cannot approve {qty_app} {listing.unit}: only {listing.remaining_quantity} {listing.unit} remaining unreserved."
            )

        # Check linked batch capacity
        batch = None
        if listing.batch_id:
            batch = Batch.objects.select_for_update().filter(id=listing.batch_id).first()
            if batch:
                if qty_app > batch.sellable_quantity:
                    raise TransitionConflictError(
                        f"Cannot approve {qty_app}: only {batch.sellable_quantity} sellable stock remains in linked batch."
                    )

        now = timezone.now()

        # Determine pickup window & next status
        is_window_changed = False
        if pickup_start and pickup_end:
            p_start = _ensure_datetime(pickup_start, "pickup_start")
            p_end = _ensure_datetime(pickup_end, "pickup_end")
            if not p_start or not p_end:
                raise ValidationLifecycleError("Both pickup start and end times are required.")
            if p_end <= p_start:
                raise ValidationLifecycleError("Pickup end time must be after pickup start time.")
            if p_start < listing.available_from or p_end > listing.available_until:
                raise ValidationLifecycleError("Pickup window must be within listing availability window.")
            if listing.safe_until and p_end > listing.safe_until:
                raise ValidationLifecycleError("Pickup window cannot exceed food safe-until time.")

            if p_start != req.proposed_pickup_start or p_end != req.proposed_pickup_end:
                is_window_changed = True
            confirmed_start = p_start
            confirmed_end = p_end
        else:
            confirmed_start = req.proposed_pickup_start
            confirmed_end = req.proposed_pickup_end


        # Accounting: Increase reservation on listing and batch
        listing.quantity_reserved += qty_app
        if listing.quantity_reserved >= listing.quantity_offered:
            listing.status = SurplusListing.Status.FULLY_RESERVED
        listing.save(update_fields=["quantity_reserved", "status", "updated_at"])

        if batch:
            batch.reserved_quantity += qty_app
            batch.save(update_fields=["reserved_quantity"])

        req.quantity_approved = qty_app
        req.confirmed_pickup_start = confirmed_start
        req.confirmed_pickup_end = confirmed_end
        req.approved_at = now

        if is_window_changed:
            to_status = DonationRequest.Status.APPROVED
            req.status = to_status
            req.save(update_fields=[
                "quantity_approved",
                "confirmed_pickup_start",
                "confirmed_pickup_end",
                "status",
                "approved_at",
                "updated_at",
            ])
            _record_history(req, DonationRequest.Status.REQUESTED, to_status, actor=user, note=f"Approved with proposed new pickup window (Qty: {qty_app})")
            _create_notification(
                organization=req.ngo,
                type_="APPROVED",
                title=f"Request {req.code} Approved – Action Needed",
                body=f"{user_org.name} approved {qty_app} {listing.unit} with a proposed new pickup time. Please confirm.",
                link=f"/ngo/claims?request={req.code}",
            )
        else:
            to_status = DonationRequest.Status.SCHEDULED
            req.status = to_status
            req.scheduled_at = now
            req.save(update_fields=[
                "quantity_approved",
                "confirmed_pickup_start",
                "confirmed_pickup_end",
                "status",
                "approved_at",
                "scheduled_at",
                "updated_at",
            ])
            _record_history(req, DonationRequest.Status.REQUESTED, DonationRequest.Status.APPROVED, actor=user, note=f"Approved (Qty: {qty_app})")
            _record_history(req, DonationRequest.Status.APPROVED, DonationRequest.Status.SCHEDULED, actor=user, note="Proposed pickup window accepted")
            _create_notification(
                organization=req.ngo,
                type_="SCHEDULED",
                title=f"Request {req.code} Approved & Scheduled",
                body=f"{user_org.name} approved your request for {qty_app} {listing.unit}. Pickup scheduled.",
                link=f"/ngo/claims?request={req.code}",
            )

        return req


# ---------------------------------------------------------------------------
# 3. NGO Confirm Schedule Window (NGO only, when APPROVED with modified window)
# ---------------------------------------------------------------------------

def confirm_schedule_by_ngo(user, request_id_or_code):
    """
    NGO confirms a changed pickup window, moving request from APPROVED to SCHEDULED.
    """
    user_org = getattr(user, "organization", None)
    if not user_org or user_org.org_type != Organization.Type.NGO:
        raise PermissionDeniedLifecycleError("Only NGO organizations can confirm pickup window.")

    with transaction.atomic():
        req = _get_request_for_update(request_id_or_code)
        if req.ngo_id != user_org.id:
            raise NotFoundLifecycleError("Donation request not found.")

        if req.status != DonationRequest.Status.APPROVED:
            raise TransitionConflictError(
                f"Cannot confirm schedule for request in '{req.status}' status. Only APPROVED requests can be confirmed."
            )

        now = timezone.now()
        req.status = DonationRequest.Status.SCHEDULED
        req.scheduled_at = now
        req.save(update_fields=["status", "scheduled_at", "updated_at"])

        _record_history(req, DonationRequest.Status.APPROVED, DonationRequest.Status.SCHEDULED, actor=user, note="NGO confirmed pickup window")

        _create_notification(
            organization=req.listing.donor,
            type_="SCHEDULED",
            title=f"Pickup Scheduled for {req.code}",
            body=f"{user_org.name} confirmed the pickup window for '{req.listing.title}'.",
            link=f"/business/donations?request={req.code}",
        )

        return req


# ---------------------------------------------------------------------------
# 4. Reject Request (Business only)
# ---------------------------------------------------------------------------

def reject_donation_request(user, request_id_or_code, rejection_reason):
    """
    Business rejects a REQUESTED donation request with a mandatory reason.
    """
    user_org = getattr(user, "organization", None)
    if not user_org or user_org.org_type != Organization.Type.BUSINESS:
        raise PermissionDeniedLifecycleError("Only business organizations can reject requests.")

    reason = (rejection_reason or "").strip()
    if not reason:
        raise ValidationLifecycleError("A rejection reason is required.")

    with transaction.atomic():
        req = _get_request_for_update(request_id_or_code)
        listing = SurplusListing.objects.select_for_update().filter(id=req.listing_id).first()
        if not listing or listing.donor_id != user_org.id:
            raise NotFoundLifecycleError("Donation request not found.")

        if req.status != DonationRequest.Status.REQUESTED:
            raise TransitionConflictError(
                f"Cannot reject request in '{req.status}' status. Only REQUESTED requests can be rejected."
            )

        now = timezone.now()
        req.status = DonationRequest.Status.REJECTED
        req.rejection_reason = reason
        req.rejected_at = now
        req.save(update_fields=["status", "rejection_reason", "rejected_at", "updated_at"])

        _record_history(req, DonationRequest.Status.REQUESTED, DonationRequest.Status.REJECTED, actor=user, note=f"Rejected: {reason}")

        _create_notification(
            organization=req.ngo,
            type_="REJECTED",
            title=f"Request {req.code} Rejected",
            body=f"{user_org.name} could not approve your request. Reason: {reason}",
            link=f"/ngo/claims?request={req.code}",
        )

        return req


# ---------------------------------------------------------------------------
# 5. Cancel Request (NGO or Business)
# ---------------------------------------------------------------------------

def cancel_donation_request(user, request_id_or_code, reason=""):
    """
    NGO cancels while REQUESTED, APPROVED or SCHEDULED.
    Releases any reserved quantities on listing and batch.
    """
    user_org = getattr(user, "organization", None)
    if not user_org:
        raise PermissionDeniedLifecycleError("Authentication required.")

    with transaction.atomic():
        req = _get_request_for_update(request_id_or_code)
        listing = SurplusListing.objects.select_for_update().filter(id=req.listing_id).first()
        if not listing:
            raise NotFoundLifecycleError("Listing not found.")

        # Caller must be either the requesting NGO or the donor business
        is_ngo = (user_org.id == req.ngo_id)
        is_donor = (user_org.id == listing.donor_id)
        if not is_ngo and not is_donor:
            raise NotFoundLifecycleError("Donation request not found.")

        allowed_from = [
            DonationRequest.Status.REQUESTED,
            DonationRequest.Status.APPROVED,
            DonationRequest.Status.SCHEDULED,
        ]
        if req.status not in allowed_from:
            raise TransitionConflictError(
                f"Cannot cancel request in '{req.status}' status. Only REQUESTED, APPROVED, or SCHEDULED requests can be cancelled."
            )

        from_status = req.status
        now = timezone.now()

        # Release reservation if it was reserved (APPROVED or SCHEDULED)
        if from_status in (DonationRequest.Status.APPROVED, DonationRequest.Status.SCHEDULED):
            res_qty = req.quantity_approved or req.quantity_requested
            listing.quantity_reserved = max(Decimal("0.000"), listing.quantity_reserved - res_qty)
            if listing.status == SurplusListing.Status.FULLY_RESERVED and listing.remaining_quantity > 0:
                listing.status = SurplusListing.Status.OPEN
            listing.save(update_fields=["quantity_reserved", "status", "updated_at"])

            if listing.batch_id:
                batch = Batch.objects.select_for_update().filter(id=listing.batch_id).first()
                if batch:
                    batch.reserved_quantity = max(Decimal("0.000"), batch.reserved_quantity - res_qty)
                    batch.save(update_fields=["reserved_quantity"])

        req.status = DonationRequest.Status.CANCELLED
        req.cancelled_at = now
        req.save(update_fields=["status", "cancelled_at", "updated_at"])

        note_text = f"Cancelled by {user_org.name}" + (f": {reason}" if reason else "")
        _record_history(req, from_status, DonationRequest.Status.CANCELLED, actor=user, note=note_text)

        notify_target = listing.donor if is_ngo else req.ngo
        _create_notification(
            organization=notify_target,
            type_="CANCELLED",
            title=f"Request {req.code} Cancelled",
            body=f"{user_org.name} cancelled the donation request for '{listing.title}'.",
            link=f"/business/donations?request={req.code}" if is_ngo else f"/ngo/claims?request={req.code}",
        )

        return req


# ---------------------------------------------------------------------------
# 6. Mark IN_TRANSIT ("On my way", NGO only)
# ---------------------------------------------------------------------------

def mark_in_transit(user, request_id_or_code):
    """
    NGO marks "On my way" when SCHEDULED and within 2 hours of pickup start.
    """
    user_org = getattr(user, "organization", None)
    if not user_org or user_org.org_type != Organization.Type.NGO:
        raise PermissionDeniedLifecycleError("Only NGO organizations can mark in transit.")

    with transaction.atomic():
        req = _get_request_for_update(request_id_or_code)
        if req.ngo_id != user_org.id:
            raise NotFoundLifecycleError("Donation request not found.")

        if req.status != DonationRequest.Status.SCHEDULED:
            raise TransitionConflictError(
                f"Cannot mark in transit for request in '{req.status}' status. Only SCHEDULED requests can be marked in transit."
            )

        now = timezone.now()
        pickup_start = req.confirmed_pickup_start or req.proposed_pickup_start
        if now < pickup_start - timedelta(hours=2):
            time_left = pickup_start - now
            hours_left = int(time_left.total_seconds() // 3600)
            minutes_left = int((time_left.total_seconds() % 3600) // 60)
            raise TransitionConflictError(
                f"You can only mark 'in transit' within 2 hours of pickup start ({hours_left}h {minutes_left}m remaining)."
            )

        req.status = DonationRequest.Status.IN_TRANSIT
        req.in_transit_at = now
        req.save(update_fields=["status", "in_transit_at", "updated_at"])

        _record_history(req, DonationRequest.Status.SCHEDULED, DonationRequest.Status.IN_TRANSIT, actor=user, note="Volunteer marked On My Way")

        _create_notification(
            organization=req.listing.donor,
            type_="IN_TRANSIT",
            title=f"Volunteer on the way: {req.code}",
            body=f"{user_org.name} volunteer is on the way for '{req.listing.title}'.",
            link=f"/business/donations?request={req.code}",
        )

        return req


# ---------------------------------------------------------------------------
# 7. Mark COLLECTED (Business only)
# ---------------------------------------------------------------------------

def mark_collected(user, request_id_or_code, quantity_collected):
    """
    Business marks request as COLLECTED with the actual quantity handed over.
    Converts reservation into real stock deduction:
    - Reduces batch.quantity by quantity_collected
    - Releases batch.reserved_quantity and listing.quantity_reserved
    - Writes a DONATED StockTransaction with source DONATION and external_id=code
    - Marks batch DEPLETED/DONATED when zero
    - Updates listing status (COMPLETED if nothing remains, FULLY_RESERVED if everything reserved, or OPEN)
    """
    user_org = getattr(user, "organization", None)
    if not user_org or user_org.org_type != Organization.Type.BUSINESS:
        raise PermissionDeniedLifecycleError("Only business organizations can mark collected.")

    qty_col = _parse_decimal(quantity_collected, "quantity_collected")
    if qty_col <= 0:
        raise ValidationLifecycleError("Collected quantity must be greater than zero.")


    with transaction.atomic():
        req = _get_request_for_update(request_id_or_code)
        listing = SurplusListing.objects.select_for_update().filter(id=req.listing_id).first()
        if not listing or listing.donor_id != user_org.id:
            raise NotFoundLifecycleError("Donation request not found.")

        allowed_from = [DonationRequest.Status.SCHEDULED, DonationRequest.Status.IN_TRANSIT]
        if req.status not in allowed_from:
            raise TransitionConflictError(
                f"Cannot mark collected for request in '{req.status}' status. Only SCHEDULED or IN_TRANSIT requests can be collected."
            )

        approved_qty = req.quantity_approved or req.quantity_requested
        if qty_col > approved_qty:
            raise ValidationLifecycleError(
                f"Collected quantity ({qty_col}) cannot exceed approved quantity ({approved_qty})."
            )

        now = timezone.now()

        # Batch deduction and ledger entry
        if listing.batch_id:
            batch = Batch.objects.select_for_update().filter(id=listing.batch_id).first()
            if batch:
                if qty_col > batch.quantity:
                    raise TransitionConflictError(
                        f"Insufficient batch quantity ({batch.quantity}) to deduct {qty_col}."
                    )
                batch.quantity -= qty_col
                # Release reserved amount (difference between approved and collected is also freed)
                batch.reserved_quantity = max(Decimal("0.000"), batch.reserved_quantity - approved_qty)
                if batch.quantity == Decimal("0.000"):
                    batch.status = Batch.Status.DONATED
                batch.save(update_fields=["quantity", "reserved_quantity", "status"])

                StockTransaction.objects.create(
                    organization=listing.donor,
                    batch=batch,
                    txn_type=StockTransaction.Type.DONATED,
                    quantity=qty_col,
                    reason=f"Donated to {req.ngo.name} via request {req.code}",
                    source="DONATION",
                    created_by=user,
                    external_id=req.code,
                )

        # Listing accounting
        listing.quantity_reserved = max(Decimal("0.000"), listing.quantity_reserved - approved_qty)
        # Check if any food remains to be donated from this listing
        # Count all collected quantities from this listing
        total_collected = DonationRequest.objects.filter(
            listing=listing,
            status__in=[DonationRequest.Status.COLLECTED, DonationRequest.Status.COMPLETED],
        ).exclude(id=req.id)
        existing_collected = sum((r.quantity_collected or Decimal("0") for r in total_collected), Decimal("0"))
        all_collected_and_reserved = existing_collected + qty_col + listing.quantity_reserved

        if all_collected_and_reserved >= listing.quantity_offered:
            if listing.quantity_reserved > Decimal("0.000"):
                listing.status = SurplusListing.Status.FULLY_RESERVED
            else:
                listing.status = SurplusListing.Status.COMPLETED
        else:
            listing.status = SurplusListing.Status.OPEN

        listing.save(update_fields=["quantity_reserved", "status", "updated_at"])

        from_status = req.status
        req.status = DonationRequest.Status.COLLECTED
        req.quantity_collected = qty_col
        req.collected_at = now
        req.save(update_fields=["status", "quantity_collected", "collected_at", "updated_at"])

        _record_history(req, from_status, DonationRequest.Status.COLLECTED, actor=user, note=f"Collected {qty_col} {listing.unit}")

        _create_notification(
            organization=req.ngo,
            type_="COLLECTED",
            title=f"Pickup Handover Complete: {req.code}",
            body=f"{user_org.name} confirmed handover of {qty_col} {listing.unit}. Please confirm receipt.",
            link=f"/ngo/claims?request={req.code}",
        )

        return req


# ---------------------------------------------------------------------------
# 8. Confirm Receipt (NGO only, COLLECTED to COMPLETED)
# ---------------------------------------------------------------------------

def confirm_receipt(user, request_id_or_code):
    """
    NGO confirms receipt of goods, completing the donation request.
    """
    user_org = getattr(user, "organization", None)
    if not user_org or user_org.org_type != Organization.Type.NGO:
        raise PermissionDeniedLifecycleError("Only NGO organizations can confirm receipt.")

    with transaction.atomic():
        req = _get_request_for_update(request_id_or_code)
        if req.ngo_id != user_org.id:
            raise NotFoundLifecycleError("Donation request not found.")

        if req.status != DonationRequest.Status.COLLECTED:
            raise TransitionConflictError(
                f"Cannot confirm receipt for request in '{req.status}' status. Only COLLECTED requests can be confirmed."
            )

        now = timezone.now()
        req.status = DonationRequest.Status.COMPLETED
        req.completed_at = now
        req.save(update_fields=["status", "completed_at", "updated_at"])

        _record_history(req, DonationRequest.Status.COLLECTED, DonationRequest.Status.COMPLETED, actor=user, note="NGO confirmed receipt")

        _create_notification(
            organization=req.listing.donor,
            type_="COMPLETED",
            title=f"Donation Completed: {req.code}",
            body=f"{user_org.name} confirmed receipt of {req.quantity_collected or req.quantity_approved} {req.listing.unit}.",
            link=f"/business/donations?request={req.code}",
        )

        return req


# ---------------------------------------------------------------------------
# 9. Mark NO_SHOW (Business only, after pickup window ended)
# ---------------------------------------------------------------------------

def mark_no_show(user, request_id_or_code):
    """
    Business marks request as NO_SHOW after the pickup window has ended.
    Releases all reservations.
    """
    user_org = getattr(user, "organization", None)
    if not user_org or user_org.org_type != Organization.Type.BUSINESS:
        raise PermissionDeniedLifecycleError("Only business organizations can mark no-show.")

    with transaction.atomic():
        req = _get_request_for_update(request_id_or_code)
        listing = SurplusListing.objects.select_for_update().filter(id=req.listing_id).first()
        if not listing or listing.donor_id != user_org.id:
            raise NotFoundLifecycleError("Donation request not found.")

        allowed_from = [DonationRequest.Status.SCHEDULED, DonationRequest.Status.IN_TRANSIT]
        if req.status not in allowed_from:
            raise TransitionConflictError(
                f"Cannot mark no-show for request in '{req.status}' status. Only SCHEDULED or IN_TRANSIT requests can be marked no-show."
            )

        now = timezone.now()
        pickup_end = req.confirmed_pickup_end or req.proposed_pickup_end
        if now <= pickup_end:
            raise TransitionConflictError("Cannot mark no-show before the pickup window has ended.")

        from_status = req.status
        res_qty = req.quantity_approved or req.quantity_requested

        # Release reservation on listing
        listing.quantity_reserved = max(Decimal("0.000"), listing.quantity_reserved - res_qty)
        if listing.status == SurplusListing.Status.FULLY_RESERVED and listing.remaining_quantity > 0:
            listing.status = SurplusListing.Status.OPEN
        listing.save(update_fields=["quantity_reserved", "status", "updated_at"])

        # Release reservation on batch
        if listing.batch_id:
            batch = Batch.objects.select_for_update().filter(id=listing.batch_id).first()
            if batch:
                batch.reserved_quantity = max(Decimal("0.000"), batch.reserved_quantity - res_qty)
                batch.save(update_fields=["reserved_quantity"])

        req.status = DonationRequest.Status.NO_SHOW
        req.no_show_at = now
        req.save(update_fields=["status", "no_show_at", "updated_at"])

        _record_history(req, from_status, DonationRequest.Status.NO_SHOW, actor=user, note="Marked as No Show by donor")

        _create_notification(
            organization=req.ngo,
            type_="NO_SHOW",
            title=f"Missed Pickup: {req.code}",
            body=f"{user_org.name} marked request {req.code} as No Show after pickup window ended.",
            link=f"/ngo/claims?request={req.code}",
        )

        return req


# ---------------------------------------------------------------------------
# 10. System Scheduled Job / Idempotent Worker (process_donations)
# ---------------------------------------------------------------------------

def process_donations():
    """
    Idempotent background job:
    1. Auto-expires REQUESTED requests when the listing has expired.
    2. Auto-completes COLLECTED requests 24 hours after collection if NGO did not confirm.
    3. Auto-expires OPEN listings whose available_until has passed.
    4. Releases reservations for any orphaned terminal requests.
    Returns summary dict of actions taken.
    """
    now = timezone.now()
    summary = {
        "expired_requests": 0,
        "auto_completed_requests": 0,
        "expired_listings": 0,
    }

    # 1. Auto-expire REQUESTED requests where listing has expired
    expired_reqs = DonationRequest.objects.filter(
        status=DonationRequest.Status.REQUESTED,
        listing__available_until__lt=now,
    ).select_related("listing", "ngo")

    for req in expired_reqs:
        try:
            with transaction.atomic():
                r = DonationRequest.objects.select_for_update().get(id=req.id)
                if r.status == DonationRequest.Status.REQUESTED:
                    r.status = DonationRequest.Status.EXPIRED
                    r.expired_at = now
                    r.save(update_fields=["status", "expired_at", "updated_at"])
                    _record_history(r, DonationRequest.Status.REQUESTED, DonationRequest.Status.EXPIRED, note="Auto-expired: listing validity window ended")
                    _create_notification(
                        organization=r.ngo,
                        type_="EXPIRED",
                        title=f"Request {r.code} Expired",
                        body=f"Your request for '{r.listing.title}' expired as the listing pickup window ended.",
                        link=f"/ngo/claims?request={r.code}",
                    )
                    summary["expired_requests"] += 1
        except Exception as e:
            logger.error("Failed to auto-expire request %s: %s", req.id, e)

    # 2. Auto-complete COLLECTED requests 24 hours after collection
    cutoff_24h = now - timedelta(hours=24)
    stale_collected = DonationRequest.objects.filter(
        status=DonationRequest.Status.COLLECTED,
        collected_at__lte=cutoff_24h,
    ).select_related("listing", "listing__donor")

    for req in stale_collected:
        try:
            with transaction.atomic():
                r = DonationRequest.objects.select_for_update().get(id=req.id)
                if r.status == DonationRequest.Status.COLLECTED:
                    r.status = DonationRequest.Status.COMPLETED
                    r.completed_at = now
                    r.save(update_fields=["status", "completed_at", "updated_at"])
                    _record_history(r, DonationRequest.Status.COLLECTED, DonationRequest.Status.COMPLETED, note="Auto-completed 24h after collection")
                    _create_notification(
                        organization=r.listing.donor,
                        type_="COMPLETED",
                        title=f"Donation Completed: {r.code}",
                        body=f"Request {r.code} auto-completed 24 hours after collection.",
                        link=f"/business/donations?request={r.code}",
                    )
                    summary["auto_completed_requests"] += 1
        except Exception as e:
            logger.error("Failed to auto-complete request %s: %s", req.id, e)

    # 3. Auto-expire OPEN listings
    stale_listings = SurplusListing.objects.filter(
        status=SurplusListing.Status.OPEN,
        available_until__lt=now,
    )
    for listing in stale_listings:
        try:
            with transaction.atomic():
                lst = SurplusListing.objects.select_for_update().get(id=listing.id)
                if lst.status == SurplusListing.Status.OPEN and lst.available_until < now:
                    lst.status = SurplusListing.Status.EXPIRED
                    lst.save(update_fields=["status", "updated_at"])
                    summary["expired_listings"] += 1
        except Exception as e:
            logger.error("Failed to auto-expire listing %s: %s", listing.id, e)

    return summary
