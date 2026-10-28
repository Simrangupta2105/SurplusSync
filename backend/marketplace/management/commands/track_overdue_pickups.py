from django.core.management.base import BaseCommand
from marketplace.tasks import track_overdue_pickups_task


class Command(BaseCommand):
    help = "Tracks overdue pickups and dispatches notifications for expired pickup windows."

    def handle(self, *args, **options):
        self.stdout.write("Checking active donation requests for overdue pickup windows...")
        result = track_overdue_pickups_task()
        self.stdout.write(
            self.style.SUCCESS(
                f"Overdue pickups processed: {result['overdue_count']} overdue pickups found, "
                f"{result['notifications_sent']} notifications dispatched."
            )
        )
