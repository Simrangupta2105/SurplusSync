from django.core.management.base import BaseCommand, CommandError
from accounts.models import Organization
from inventory.authentication import create_pos_key


class Command(BaseCommand):
    help = 'Generates a new POS API key for an organization and displays the raw key once.'

    def add_arguments(self, parser):
        parser.add_argument('org_id', type=int, help='ID of the Organization')
        parser.add_argument('label', type=str, help='Label for the API key (e.g. "Register 1")')

    def handle(self, *args, **options):
        org_id = options['org_id']
        label = options['label']

        try:
            org = Organization.objects.get(id=org_id)
        except Organization.DoesNotExist:
            raise CommandError(f"Organization with ID {org_id} does not exist.")

        raw_key = create_pos_key(org, label)
        self.stdout.write(self.style.SUCCESS(f"Successfully generated POS API key for '{org.name}' ({label}):"))
        self.stdout.write(self.style.WARNING(raw_key))
