"""
Management command to seed initial default categories for Expense Tracker.
"""

from django.core.management.base import BaseCommand
from tracker.models import Category
from tracker.constants import DEFAULT_CATEGORIES

class Command(BaseCommand):
    """
    Seeds initial expense categories into the database idempotently.
    """
    help = "Seeds initial expense categories into the database."

    def handle(self, *args, **options):
        created_count = 0
        for name, color in DEFAULT_CATEGORIES:
            _, created = Category.objects.get_or_create(
                name=name,
                defaults={'color': color}
            )
            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded categories. {created_count} created, {len(DEFAULT_CATEGORIES) - created_count} already existed."
            )
        )
