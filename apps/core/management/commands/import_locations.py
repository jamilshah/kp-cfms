"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to import TMA locations from CSV.
-------------------------------------------------------------------------
"""
import csv
from typing import Dict, Any
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Division, District, Tehsil, Organization


class Command(BaseCommand):
    """
    Import TMA location data from docs/loc.csv.
    
    Usage:
        python manage.py import_locations
        python manage.py import_locations --clear  # Clear existing data first
    """
    
    help = 'Import TMA location data (Division, District, Tehsil) from CSV file.'
    
    def add_arguments(self, parser) -> None:
        """Add command line arguments."""
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing location data before import.',
        )
        parser.add_argument(
            '--file',
            type=str,
            default='docs/loc.csv',
            help='Path to the CSV file (default: docs/loc.csv).',
        )
    
    @transaction.atomic
    def handle(self, *args, **options) -> None:
        """Execute the import command."""
        csv_path = Path(options['file'])
        
        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")
        
        # Clear existing data if requested
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing existing location data...'))
            Organization.objects.all().delete()
            Tehsil.objects.all().delete()
            District.objects.all().delete()
            Division.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Existing data cleared.'))
        
        # Track statistics
        stats: Dict[str, int] = {
            'divisions_created': 0,
            'districts_created': 0,
            'tehsils_created': 0,
            'tehsils_skipped': 0,
        }
        
        # Read CSV and import
        self.stdout.write(f'Reading from {csv_path}...')
        
        with open(csv_path, 'r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                # Skip empty rows
                if not row.get('Division') or not row.get('District') or not row.get('Tehsil'):
                    continue
                
                division_name = row['Division'].strip()
                district_name = row['District'].strip()
                tehsil_name = row['Tehsil'].strip()
                
                # Create or get Division
                division, created = Division.objects.get_or_create(
                    name=division_name,
                    defaults={'is_active': True}
                )
                if created:
                    stats['divisions_created'] += 1
                    self.stdout.write(f'  Created Division: {division_name}')
                
                # Create or get District
                district, created = District.objects.get_or_create(
                    division=division,
                    name=district_name,
                    defaults={'is_active': True}
                )
                if created:
                    stats['districts_created'] += 1
                    self.stdout.write(f'    Created District: {district_name}')
                
                # Create or get Tehsil
                tehsil, created = Tehsil.objects.get_or_create(
                    district=district,
                    name=tehsil_name,
                    defaults={'is_active': True}
                )
                if created:
                    stats['tehsils_created'] += 1
                    self.stdout.write(f'      Created Tehsil: {tehsil_name}')
                else:
                    stats['tehsils_skipped'] += 1
        
        # Print summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('Import Complete!'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(f"Divisions created: {stats['divisions_created']}")
        self.stdout.write(f"Districts created: {stats['districts_created']}")
        self.stdout.write(f"Tehsils created: {stats['tehsils_created']}")
        self.stdout.write(f"Tehsils skipped (existing): {stats['tehsils_skipped']}")
        self.stdout.write('')
        self.stdout.write(f"Total Divisions: {Division.objects.count()}")
        self.stdout.write(f"Total Districts: {District.objects.count()}")
        self.stdout.write(f"Total Tehsils: {Tehsil.objects.count()}")
