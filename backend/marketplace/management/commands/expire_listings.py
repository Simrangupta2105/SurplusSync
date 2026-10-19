"""
Management command to expire stale marketplace listings.
"""
from django.core.management.base import BaseCommand
from marketplace.tasks import expire_stale_listings


class Command(BaseCommand):
    help = "Expire stale marketplace listings whose pickup window has passed."

    def handle(self, *args, **options):
        self.stdout.write("Checking for stale marketplace listings...")
        count = expire_stale_listings()
        self.stdout.write(
            self.style.SUCCESS(f"Successfully marked {count} stale listing(s) as CANCELLED.")
        )
