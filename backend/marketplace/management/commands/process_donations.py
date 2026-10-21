"""
Management command to run the donation lifecycle processing job.
Auto-expires stale listings, auto-completes unconfirmed collections after 24 hours,
and auto-expires requested donations whose listing availability has ended.
"""
from django.core.management.base import BaseCommand
from marketplace.services import process_donations


class Command(BaseCommand):
    help = "Process donation timeouts: auto-expire listings/requests, auto-complete collections."

    def handle(self, *args, **options):
        self.stdout.write("Running donation lifecycle processing...")
        summary = process_donations()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed donations: "
                f"{summary.get('expired_requests', 0)} requests expired, "
                f"{summary.get('auto_completed_requests', 0)} requests completed, "
                f"{summary.get('expired_listings', 0)} listings expired."
            )
        )
