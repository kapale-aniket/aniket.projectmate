"""Sync free-class statuses from system date/time."""
from django.core.management.base import BaseCommand
from apps.classes.services import ClassStatusService


class Command(BaseCommand):
    help = "Update free class statuses (upcoming → live → completed) from schedule"

    def handle(self, *args, **options):
        updated = ClassStatusService.sync_all()
        self.stdout.write(self.style.SUCCESS(f"Updated {updated} class status(es)."))
