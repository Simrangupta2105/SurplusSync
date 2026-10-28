from django.core.management.base import BaseCommand
from marketplace.tasks import send_pickup_reminders_task


class Command(BaseCommand):
    help = "Dispatches 24h and 2h pickup reminder notifications to donors and NGOs."

    def handle(self, *args, **options):
        self.stdout.write("Checking active donation requests for pickup reminders...")
        result = send_pickup_reminders_task()
        self.stdout.write(
            self.style.SUCCESS(
                f"Pickup reminders processed: {result['reminders_24h_sent']} 24h reminders sent, "
                f"{result['reminders_2h_sent']} 2h reminders sent. Total: {result['total_sent']}."
            )
        )
