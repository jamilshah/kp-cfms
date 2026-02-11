"""
Management command to import application data from JSON fixtures.
Properly handles relationships and sequences.

Usage:
    python manage.py import_data backup.json              # Import from file
    python manage.py import_data backup.json --noinput   # Skip confirmation
"""
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from pathlib import Path
from django.db import connection


class Command(BaseCommand):
    help = 'Import application data from JSON fixtures'

    def add_arguments(self, parser):
        parser.add_argument(
            'fixture_file',
            type=str,
            help='Path to the JSON fixture file to import',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Skip confirmation prompt',
        )
        parser.add_argument(
            '--disable-constraints',
            action='store_true',
            help='Temporarily disable foreign key constraints during import',
        )

    def handle(self, *args, **options):
        fixture_file = options['fixture_file']
        noinput = options['noinput']
        disable_constraints = options['disable_constraints']
        
        # Validate file exists
        if not Path(fixture_file).exists():
            raise CommandError(f"Fixture file not found: {fixture_file}")
        
        file_size = Path(fixture_file).stat().st_size / (1024 * 1024)  # MB
        
        self.stdout.write("=" * 80)
        self.stdout.write("DATA IMPORT TOOL")
        self.stdout.write("=" * 80)
        self.stdout.write(f"\nFixture file: {fixture_file}")
        self.stdout.write(f"File size: {file_size:.2f} MB")
        self.stdout.write("\n⚠ WARNING: This will import data and may overwrite existing records!")
        
        if not noinput:
            confirm = input("\nDo you want to proceed? Type 'yes' to confirm: ").strip()
            if confirm != 'yes':
                self.stdout.write(self.style.WARNING("Import cancelled."))
                return
        
        try:
            # Disable foreign key constraints if requested (PostgreSQL)
            if disable_constraints:
                self.stdout.write("\nDisabling foreign key constraints...")
                with connection.cursor() as cursor:
                    cursor.execute("SET session_replication_role = 'replica';")
                self.stdout.write(self.style.WARNING("  ⚠ Constraints disabled (will be restored after)"))
            
            self.stdout.write("\nImporting data...")
            call_command(
                'loaddata',
                fixture_file,
                verbosity=2,
            )
            
            # Re-enable constraints
            if disable_constraints:
                self.stdout.write("\nRe-enabling foreign key constraints...")
                with connection.cursor() as cursor:
                    cursor.execute("SET session_replication_role = 'origin';")
                self.stdout.write(self.style.SUCCESS("  ✓ Constraints re-enabled"))
            
            self.stdout.write(self.style.SUCCESS(
                f"\n✓ Data imported successfully!"
                f"\n  All relationships and sequences have been restored."
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Import failed: {str(e)}"))
            
            # Try to re-enable constraints if they were disabled
            if disable_constraints:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("SET session_replication_role = 'origin';")
                    self.stdout.write(self.style.WARNING("  ✓ Constraints re-enabled after error"))
                except:
                    pass
            
            raise
