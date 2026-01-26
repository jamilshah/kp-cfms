"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to import employees from CSV.
             Bulk uploads employees for a specific TMA/Department.
-------------------------------------------------------------------------
"""
import csv
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.budgeting.models import ScheduleOfEstablishment, FiscalYear
from apps.budgeting.models_employee import BudgetEmployee
from apps.core.models import Organization


class Command(BaseCommand):
    help = 'Import employees from CSV for budget estimation (BDC-2)'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to the CSV file containing employee data'
        )
        parser.add_argument(
            '--organization',
            type=str,
            required=True,
            help='Organization/TMA name or DDO code'
        )
        parser.add_argument(
            '--fiscal-year',
            type=str,
            required=True,
            help='Fiscal year name (e.g., "2026-27")'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview import without saving to database'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        org_identifier = options['organization']
        fy_name = options['fiscal_year']
        dry_run = options['dry_run']
        
        # Find Organization
        org = Organization.objects.filter(
            name__icontains=org_identifier
        ).first() or Organization.objects.filter(
            ddo_code=org_identifier
        ).first()
        
        if not org:
            raise CommandError(f'Organization not found: {org_identifier}')
        
        self.stdout.write(f'Organization: {org.name}')
        
        # Find Fiscal Year
        fy = FiscalYear.objects.filter(
            organization=org,
            year_name=fy_name
        ).first()
        
        if not fy:
            raise CommandError(f'Fiscal Year not found: {fy_name} for {org.name}')
        
        self.stdout.write(f'Fiscal Year: {fy.year_name}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY RUN MODE - No changes will be saved]'))
        
        # Read CSV
        try:
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except FileNotFoundError:
            raise CommandError(f'CSV file not found: {csv_file}')
        except Exception as e:
            raise CommandError(f'Error reading CSV: {e}')
        
        self.stdout.write(f'Found {len(rows)} rows in CSV')
        
        # Expected columns: Department, Designation, Employee Name, Basic Pay, Allowances, Increment
        required_columns = ['Department', 'Designation', 'Employee Name', 'Basic Pay', 'Allowances', 'Increment']
        
        if rows:
            missing = [col for col in required_columns if col not in rows[0]]
            if missing:
                raise CommandError(f'Missing required columns: {", ".join(missing)}')
        
        # Process rows
        created_count = 0
        skipped_count = 0
        error_count = 0
        schedules_updated = set()
        
        with transaction.atomic():
            for idx, row in enumerate(rows, start=2):  # Start at 2 (header is row 1)
                try:
                    department = row['Department'].strip()
                    designation = row['Designation'].strip()
                    emp_name = row['Employee Name'].strip()
                    
                    if not emp_name:
                        self.stdout.write(
                            self.style.WARNING(f'Row {idx}: Skipping empty employee name')
                        )
                        skipped_count += 1
                        continue
                    
                    # Parse decimal values
                    try:
                        basic_pay = Decimal(row['Basic Pay'].replace(',', '').strip() or '0')
                        allowances = Decimal(row['Allowances'].replace(',', '').strip() or '0')
                        increment = Decimal(row['Increment'].replace(',', '').strip() or '0')
                    except InvalidOperation as e:
                        self.stdout.write(
                            self.style.ERROR(f'Row {idx}: Invalid number format - {e}')
                        )
                        error_count += 1
                        continue
                    
                    # Find matching ScheduleOfEstablishment
                    schedule = ScheduleOfEstablishment.objects.filter(
                        organization=org,
                        fiscal_year=fy,
                        department__iexact=department,
                        designation_name__iexact=designation
                    ).first()
                    
                    if not schedule:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Row {idx}: No schedule found for {department}/{designation}'
                            )
                        )
                        skipped_count += 1
                        continue
                    
                    if not dry_run:
                        # Create BudgetEmployee
                        BudgetEmployee.objects.create(
                            schedule=schedule,
                            name=emp_name,
                            current_basic_pay=basic_pay,
                            monthly_allowances=allowances,
                            annual_increment_amount=increment,
                            is_vacant=False
                        )
                    
                    schedules_updated.add(schedule.id)
                    created_count += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Row {idx}: Error - {e}')
                    )
                    error_count += 1
            
            if not dry_run:
                # Trigger budget recalculation for all updated schedules
                self.stdout.write('\nRecalculating budget requirements...')
                for schedule_id in schedules_updated:
                    schedule = ScheduleOfEstablishment.objects.get(id=schedule_id)
                    result = schedule.calculate_total_budget_requirement()
                    self.stdout.write(
                        f'  {schedule.designation_name}: '
                        f'Filled={result["filled_cost"]:,.2f}, '
                        f'Vacant={result["vacant_cost"]:,.2f}, '
                        f'Total={result["total_cost"]:,.2f}'
                    )
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Import completed:'))
        self.stdout.write(f'  Created: {created_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')
        self.stdout.write(f'  Errors: {error_count}')
        self.stdout.write(f'  Schedules updated: {len(schedules_updated)}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN - No changes were saved]'))
