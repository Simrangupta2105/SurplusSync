"""
Management command to idempotently configure django-q2 periodic task schedules.
"""
import zoneinfo
from datetime import datetime, time, timedelta

from django.apps import apps
from django.conf import settings
from django.core.management import get_commands
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_q.models import Schedule


class Command(BaseCommand):
    help = "Idempotently configure django-q2 periodic task schedules."

    def handle(self, *args, **options):
        # 1. Determine configured timezone (default Asia/Kolkata)
        tz_name = (
            getattr(settings, "Q_CLUSTER", {}).get("time_zone")
            or getattr(settings, "TIME_ZONE", "UTC")
        )
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            tz = zoneinfo.ZoneInfo("Asia/Kolkata")
            tz_name = "Asia/Kolkata"

        self.stdout.write(f"Configuring schedules using timezone: {tz_name}")

        # Compute next 00:05 local time
        now_local = datetime.now(tz)
        target_time = time(0, 5)
        today_0005 = datetime.combine(now_local.date(), target_time, tzinfo=tz)
        if now_local >= today_0005:
            next_run_expiry = today_0005 + timedelta(days=1)
        else:
            next_run_expiry = today_0005

        # 2. Expiry check schedule (daily at 00:05 local time)
        expiry_schedule, created_exp = Schedule.objects.update_or_create(
            name="daily_expiry_check",
            defaults={
                "func": "inventory.tasks.run_expiry_check",
                "schedule_type": Schedule.DAILY,
                "repeats": -1,
                "cluster": "SurplusSync",
                "next_run": next_run_expiry,
            },
        )
        action_exp = "Created" if created_exp else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action_exp} schedule 'daily_expiry_check': daily at 00:05 {tz_name} (next_run: {next_run_expiry})."
            )
        )

        # 3. Expire stale marketplace listings schedule (every 15 minutes)
        has_marketplace = apps.is_installed("marketplace")
        has_expire_command = "expire_listings" in get_commands()

        if has_marketplace or has_expire_command:
            now_utc = timezone.now()
            listing_schedule, created_list = Schedule.objects.update_or_create(
                name="expire_stale_marketplace_listings",
                defaults={
                    "func": "marketplace.tasks.expire_stale_listings",
                    "schedule_type": Schedule.MINUTES,
                    "minutes": 15,
                    "repeats": -1,
                    "cluster": "SurplusSync",
                    "next_run": now_utc,
                },
            )
            action_list = "Created" if created_list else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action_list} schedule 'expire_stale_marketplace_listings': every 15 minutes."
                )
            )

            # 4. Process donation lifecycle timeouts (every 15 minutes)
            donation_schedule, created_don = Schedule.objects.update_or_create(
                name="process_donation_lifecycle",
                defaults={
                    "func": "marketplace.tasks.process_donations_task",
                    "schedule_type": Schedule.MINUTES,
                    "minutes": 15,
                    "repeats": -1,
                    "cluster": "SurplusSync",
                    "next_run": now_utc,
                },
            )
            action_don = "Created" if created_don else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action_don} schedule 'process_donation_lifecycle': every 15 minutes."
                )
            )

            # 5. Matching engine batch runs & notifications (every 15 minutes)
            matching_schedule, created_match = Schedule.objects.update_or_create(
                name="run_surplus_matching_engine",
                defaults={
                    "func": "marketplace.tasks.run_matching_engine_task",
                    "schedule_type": Schedule.MINUTES,
                    "minutes": 15,
                    "repeats": -1,
                    "cluster": "SurplusSync",
                    "next_run": now_utc,
                },
            )
            action_match = "Created" if created_match else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action_match} schedule 'run_surplus_matching_engine': every 15 minutes."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Marketplace app and expire_listings command not found. Skipping marketplace listings schedule."
                )
            )


