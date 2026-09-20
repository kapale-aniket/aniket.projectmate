"""Re-generate LinkedIn job Excel files from JSON/xlsx data with current export settings."""

from django.core.management.base import BaseCommand

from apps.linkedin.services.job_output_service import refresh_all_job_output_excel


class Command(BaseCommand):
    help = "Refresh existing LinkedIn job Excel outputs (clickable Apply links, current branding)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-merged",
            action="store_true",
            help="Skip merged_*.xlsx files",
        )
        parser.add_argument(
            "--no-orphan",
            action="store_true",
            help="Skip xlsx files without a matching daily JSON",
        )

    def handle(self, *args, **options):
        result = refresh_all_job_output_excel(
            include_merged=not options["no_merged"],
            include_orphan_xlsx=not options["no_orphan"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Refreshed {result['refreshed_count']} Excel file(s)."
            )
        )
        for path in result["refreshed"]:
            self.stdout.write(f"  - {path}")
        for item in result["errors"]:
            self.stdout.write(
                self.style.ERROR(f"  FAILED {item['path']}: {item['error']}")
            )
        if result["errors"]:
            raise SystemExit(1)
