"""
Management command to run the SurplusSync Matching Engine (Task 3).

Usage:
    python manage.py match_surplus
    python manage.py match_surplus --listing-id 42 --notify
    python manage.py match_surplus --min-score 50 --top-n 3
"""
from django.core.management.base import BaseCommand, CommandError
from marketplace.matching import (
    batch_run_matching_engine,
    find_matching_requirements_for_listing,
    generate_match_notifications_for_listing,
)
from marketplace.models import SurplusListing


class Command(BaseCommand):
    help = "Run the SurplusSync matching engine to match surplus food with active NGO requirements."

    def add_arguments(self, parser):
        parser.add_argument(
            "--listing-id",
            type=int,
            default=None,
            help="Evaluate matches for a specific SurplusListing ID.",
        )
        parser.add_argument(
            "--notify",
            action="store_true",
            default=False,
            help="Dispatch in-app notifications to top matched NGOs.",
        )
        parser.add_argument(
            "--min-score",
            type=float,
            default=40.0,
            help="Minimum composite score threshold (0-100) for matches.",
        )
        parser.add_argument(
            "--top-n",
            type=int,
            default=5,
            help="Maximum number of top matches to display or notify per listing.",
        )

    def handle(self, *args, **options):
        listing_id = options["listing_id"]
        notify = options["notify"]
        min_score = options["min_score"]
        top_n = options["top_n"]

        if listing_id:
            try:
                listing = SurplusListing.objects.select_related("donor", "category").get(pk=listing_id)
            except SurplusListing.DoesNotExist:
                raise CommandError(f"SurplusListing with ID {listing_id} does not exist.")

            self.stdout.write(f"Evaluating matches for Listing #{listing.id}: '{listing.title}' ({listing.donor.name})")
            matches = find_matching_requirements_for_listing(
                listing=listing,
                limit=top_n,
                min_score=min_score,
                compatible_only=True,
            )

            self.stdout.write(f"Found {len(matches)} compatible match(es) above score {min_score}:")
            for idx, m in enumerate(matches, start=1):
                self.stdout.write(
                    f"  {idx}. [{m['score']:.1f}%] NGO '{m['ngo_name']}' - Req: '{m['requirement_title']}' "
                    f"({m['distance_km']:.1f} km away, qty {m['min_quantity']}-{m['max_quantity']} {m['unit']})"
                )

            if notify:
                notifs = generate_match_notifications_for_listing(
                    listing=listing,
                    top_n=top_n,
                    min_score=min_score,
                )
                self.stdout.write(self.style.SUCCESS(f"Dispatched {len(notifs)} notification(s) for Listing #{listing.id}."))
        else:
            self.stdout.write("Running batch matching engine for all open surplus listings...")
            stats = batch_run_matching_engine(
                min_score=min_score,
                top_n=top_n,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Batch matching complete: {stats['listings_evaluated']} listing(s) evaluated, "
                    f"{stats['matches_found']} match(es) identified, "
                    f"{stats['notifications_created']} notification(s) created."
                )
            )
