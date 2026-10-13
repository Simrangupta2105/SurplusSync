from datetime import date, timedelta
from django.core.management.base import BaseCommand
from inventory.models import Batch, AlertRule, Alert


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

        # Fetch all active batches
        active_batches = Batch.objects.filter(status=Batch.Status.ACTIVE).select_related(
            'product', 'product__category', 'organization'
        )

        alerts_created = 0
        batches_expired = 0

        for batch in active_batches:
            days_left = (batch.expiry_date - today).days

            # 1. Check if already past expiry
            if days_left < 0:
                batch.status = Batch.Status.EXPIRED
                batch.save(update_fields=['status'])
                batches_expired += 1

                # Generate critical alert
                alert, created = Alert.objects.get_or_create(
                    organization=batch.organization,
                    batch=batch,
                    severity=Alert.Severity.CRITICAL,
                    is_acknowledged=False,
                    defaults={
                        'message': f"Batch {batch.batch_code or batch.id} of {batch.product.name} EXPIRED on {batch.expiry_date} ({batch.quantity} {batch.product.unit} remaining).",
                    }
                )
                if created:
                    alerts_created += 1
                continue

            # 2. Check category-specific AlertRules or fallback to default
            category = batch.product.category
            matching_rules = AlertRule.objects.filter(
                organization=batch.organization,
                is_active=True
            ).filter(category=category) | AlertRule.objects.filter(
                organization=batch.organization,
                is_active=True,
                category__isnull=True
            )

            threshold_days = default_days
            matched_rule = None

            if matching_rules.exists():
                matched_rule = matching_rules.first()
                threshold_days = matched_rule.days_before_expiry

            if days_left <= threshold_days:
                # Determine severity based on days remaining
                if days_left <= 2:
                    severity = Alert.Severity.CRITICAL
                elif days_left <= 5:
                    severity = Alert.Severity.WARNING
                else:
                    severity = Alert.Severity.INFO

                msg = (
                    f"Batch {batch.batch_code or batch.id} ({batch.product.name}) expires in {days_left} day(s) "
                    f"on {batch.expiry_date}."
                )

                alert, created = Alert.objects.get_or_create(
                    organization=batch.organization,
                    batch=batch,
                    rule=matched_rule,
                    is_acknowledged=False,
                    defaults={
                        'severity': severity,
                        'message': msg,
                    }
                )
                if created:
                    alerts_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Expiry check complete. Created {alerts_created} new alert(s); marked {batches_expired} batch(es) as expired.'
            )
        )
