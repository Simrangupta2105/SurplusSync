"""
RFC 5545 compliant iCalendar (.ics) generation for SurplusSync pickup events.
"""
from datetime import datetime, timezone as dt_timezone, timedelta
from typing import Iterable
from django.utils import timezone


def escape_ics_text(text: str) -> str:
    """
    Escapes text characters according to RFC 5545 section 3.3.11.
    Backslashes, semicolons, and commas are escaped.
    Newlines are converted to literal '\\n'.
    """
    if not text:
        return ""
    text = str(text)
    # First escape backslashes
    text = text.replace("\\", "\\\\")
    # Escape semicolons and commas
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    # Normalize and escape newlines
    text = text.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")
    return text


def fold_line(line: str, max_octets: int = 75) -> str:
    """
    Folds a line so that no folded line exceeds max_octets (RFC 5545 section 3.1).
    Folded continuation lines begin with a space.
    """
    encoded = line.encode("utf-8")
    if len(encoded) <= max_octets:
        return line

    chunks = []
    current_chunk = bytearray()
    limit = max_octets

    for byte in encoded:
        current_chunk.append(byte)
        if len(current_chunk) >= limit:
            chunks.append(current_chunk.decode("utf-8", errors="ignore"))
            current_chunk = bytearray()
            limit = max_octets - 1  # 1 byte reserved for leading space

    if current_chunk:
        chunks.append(current_chunk.decode("utf-8", errors="ignore"))

    return "\r\n ".join(chunks)


def format_utc_dt(dt: datetime) -> str:
    """Formats datetime into RFC 5545 UTC date-time string YYYYMMDDTHHMMSSZ."""
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, dt_timezone.utc)
    else:
        dt = dt.astimezone(dt_timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def generate_ics_calendar(requests: Iterable, calendar_name: str = "SurplusSync Pickups") -> str:
    """
    Builds an RFC 5545 VCALENDAR document from a collection of DonationRequest objects.
    """
    now_utc = format_utc_dt(timezone.now())

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SurplusSync//Redistribution Logistics//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_ics_text(calendar_name)}",
        "X-WR-TIMEZONE:UTC",
    ]

    for req in requests:
        start = req.confirmed_pickup_start or req.proposed_pickup_start or req.created_at
        end = req.confirmed_pickup_end or req.proposed_pickup_end
        if not end or (start and end <= start):
            end = (start or timezone.now()) + timedelta(hours=1)

        start_str = format_utc_dt(start)
        end_str = format_utc_dt(end)

        uid = f"pickup-{req.id}-{req.code}@surplussync.org"
        listing = req.listing
        qty = req.quantity_approved or req.quantity_requested
        unit = listing.unit if listing else "kg"
        item_title = listing.title if listing else "Food Surplus"
        donor_name = listing.donor.name if listing and listing.donor else "Donor"
        ngo_name = req.ngo.name if req.ngo else "NGO"

        status_val = "CONFIRMED"
        if req.status in ["COLLECTED", "COMPLETED"]:
            status_val = "COMPLETED"
        elif req.status in ["CANCELLED", "REJECTED", "NO_SHOW", "EXPIRED"]:
            status_val = "CANCELLED"
        elif req.status == "REQUESTED":
            status_val = "TENTATIVE"

        location = (listing.pickup_address or (listing.donor.address if listing and listing.donor else "")) if listing else ""
        summary = f"Surplus Food Pickup: {item_title} ({qty} {unit})"

        desc_parts = [
            f"Donation Request: {req.code}",
            f"Item: {item_title}",
            f"Quantity: {qty} {unit}",
            f"Donor: {donor_name}",
            f"Recipient: {ngo_name}",
            f"Status: {req.status}",
        ]
        if req.contact_name:
            contact = req.contact_name + (f" ({req.contact_phone})" if req.contact_phone else "")
            desc_parts.append(f"Contact: {contact}")
        if location:
            desc_parts.append(f"Location: {location}")
        if req.note:
            desc_parts.append(f"Notes: {req.note}")

        description = "\\n".join(escape_ics_text(p) for p in desc_parts)

        event_lines = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{start_str}",
            f"DTEND:{end_str}",
            f"SUMMARY:{escape_ics_text(summary)}",
            f"DESCRIPTION:{description}",
        ]
        if location:
            event_lines.append(f"LOCATION:{escape_ics_text(location)}")
        event_lines.append(f"STATUS:{status_val}")
        event_lines.append("END:VEVENT")

        lines.extend(event_lines)

    lines.append("END:VCALENDAR")

    # Fold lines and join with CRLF
    folded = [fold_line(line) for line in lines]
    return "\r\n".join(folded) + "\r\n"
