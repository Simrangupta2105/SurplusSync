from datetime import date
from django.core.management.base import BaseCommand
from inventory.tasks import run_expiry_check


class Command(BaseCommand):
    help = 'Evaluates expiry dates for active batches and generates expiry alerts according to AlertRules.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Default lookahead window in days if no AlertRule is defined for a category',
        )

    def handle(self, *args, **options):
        today = date.today()
        default_days = options['days']
        self.stdout.write(self.style.NOTICE(f'Running expiry check for {today}...'))

        res = run_expiry_check(days=default_days, organization=None)

        self.stdout.write(
            self.style.SUCCESS(
                f"Expiry check complete. Created {res['alerts_created']} new alert(s); marked {res['batches_expired']} batch(es) as expired."
            )
        )

