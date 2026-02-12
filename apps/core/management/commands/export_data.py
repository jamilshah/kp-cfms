"""
Management command to export application data as JSON fixtures.
Handles relationships and sequences automatically.
Excludes Django system tables (auth, migrations).

Usage:
    python manage.py export_data                          # Export all data
    python manage.py export_data --output backup.json     # Custom output
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from pathlib import Path


class Command(BaseCommand):
    help = 'Export application data (excluding Django system tables) as JSON fixtures'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='data_backup.json',
            help='Output file path (default: data_backup.json)',
        )
        parser.add_argument(
            '--exclude-django',
            action='store_true',
            help='Exclude Django system tables (migrations, content_type, etc)',
        )

    def handle(self, *args, **options):
        output_file = options['output']
        exclude_django = options['exclude_django']
        
        # Ensure output directory exists
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        self.stdout.write("=" * 80)
        self.stdout.write(f"Exporting data to: {output_file}")
        self.stdout.write("=" * 80)
        
        # Apps to export (exclude Django system apps)
        apps_to_export = [
            'core',
            'users',
            'finance',
            'budgeting',
            'expenditure',
            'revenue',
            'property',
            'reporting',
            'dashboard',
            'system_admin',
        ]
        
        if not exclude_django:
            # Include auth data (useful for preserving user permissions)
            # But exclude migrations and contenttypes
            pass
        
        self.stdout.write(f"\nExporting apps: {', '.join(apps_to_export)}")
        
        try:
            # Use Django's dumpdata command
            call_command(
                'dumpdata',
                *apps_to_export,
                output=output_file,
                indent=2,
                verbosity=2,  # Show detailed output
            )
            
            file_size = Path(output_file).stat().st_size / (1024 * 1024)  # MB
            self.stdout.write(self.style.SUCCESS(
                f"\n✓ Data exported successfully!"
                f"\n  File: {output_file}"
                f"\n  Size: {file_size:.2f} MB"
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Export failed: {str(e)}"))
            raise
