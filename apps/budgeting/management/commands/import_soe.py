"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to import Schedule of Establishment data
             from PUGF and Non-PUGF CSV files. Creates ScheduleOfEstablishment
             entries and populates DesignationMaster table.
-------------------------------------------------------------------------
"""
import csv
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.budgeting.models import (
    DesignationMaster, ScheduleOfEstablishment, FiscalYear,
    PostType, EstablishmentStatus, ApprovalStatus
)
from apps.finance.models import BudgetHead


# BPS 2024 Pay Commission initial salary rates (approximate monthly)
BPS_INITIAL_RATES = {
    1: 22000, 2: 22500, 3: 23000, 4: 24000, 5: 25000,
    6: 26000, 7: 28000, 8: 30000, 9: 32000, 10: 35000,
    11: 40000, 12: 45000, 13: 50000, 14: 55000, 15: 60000,
    16: 70000, 17: 80000, 18: 100000, 19: 120000, 20: 150000,
    21: 180000, 22: 220000
}


class Command(BaseCommand):
    """
    Management command to import Schedule of Establishment.
    
    Imports establishment data from CSV files and creates:
    1. DesignationMaster entries (unique designations)
    2. ScheduleOfEstablishment entries (posts per fiscal year)
    
    Expected CSV Format:
        - designation: Name of the post (e.g., "Junior Clerk")
        - bps: BPS grade (1-22)
        - department: Department/wing name
        - sanctioned_posts: Number of sanctioned positions
    
    Usage:
        python manage.py import_soe docs/PUGF.csv --post-type=PUGF --fiscal-year=2026-27
        python manage.py import_soe docs/Non-PUGF.csv --post-type=LOCAL --fiscal-year=2026-27
    """
    
    help = 'Import Schedule of Establishment from CSV'
    
    def add_arguments(self, parser) -> None:
        """Add command-line arguments."""
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to the CSV file to import'
        )
        parser.add_argument(
            '--post-type',
            type=str,
            choices=['PUGF', 'LOCAL'],
            required=True,
            help='Post type: PUGF (Provincial) or LOCAL (TMA)'
        )
        parser.add_argument(
            '--fiscal-year',
            type=str,
            required=True,
            help='Fiscal year name (e.g., "2026-27")'
        )
        parser.add_argument(
            '--designation-col',
            type=str,
            default='designation',
            help='Column name for designation (default: designation)'
        )
        parser.add_argument(
            '--bps-col',
            type=str,
            default='bps',
            help='Column name for BPS scale (default: bps)'
        )
        parser.add_argument(
            '--department-col',
            type=str,
            default='department',
            help='Column name for department (default: department)'
        )
        parser.add_argument(
            '--count-col',
            type=str,
            default='sanctioned_posts',
            help='Column name for sanctioned post count (default: sanctioned_posts)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without saving to database'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing entries if they differ'
        )
    
    def handle(self, *args, **options) -> str:
        """Execute the command."""
        csv_path = Path(options['csv_file'])
        post_type_str = options['post_type']
        fiscal_year_name = options['fiscal_year']
        designation_col = options['designation_col']
        bps_col = options['bps_col']
        department_col = options['department_col']
        count_col = options['count_col']
        dry_run = options['dry_run']
        update_existing = options['update_existing']
        
        # Validate file exists
        if not csv_path.exists():
            raise CommandError(f'CSV file not found: {csv_path}')
        
        # Map post type string to enum
        post_type = PostType.PUGF if post_type_str == 'PUGF' else PostType.LOCAL
        
        # Get or validate fiscal year
        fiscal_year = self._get_fiscal_year(fiscal_year_name, dry_run)
        
        # Get default salary budget head
        default_budget_head = self._get_default_salary_head()
        
        # Stats
        designations_created = 0
        designations_updated = 0
        establishment_created = 0
        establishment_updated = 0
        skipped_count = 0
        errors: List[Tuple[int, str]] = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                # Normalize column names
                fieldnames = [n.strip().lower() for n in reader.fieldnames] if reader.fieldnames else []
                
                # Find matching columns
                designation_field = self._find_column(fieldnames, [
                    designation_col.lower(), 'designation', 'designation_name', 
                    'post', 'post_name', 'name'
                ])
                bps_field = self._find_column(fieldnames, [
                    bps_col.lower(), 'bps', 'bps_scale', 'grade', 'scale'
                ])
                department_field = self._find_column(fieldnames, [
                    department_col.lower(), 'department', 'dept', 'wing', 'section'
                ])
                count_field = self._find_column(fieldnames, [
                    count_col.lower(), 'sanctioned_posts', 'posts', 'count', 
                    'sanctioned', 'strength'
                ])
                
                # Validate required columns
                if not designation_field:
                    raise CommandError(f'Could not find designation column. Available: {fieldnames}')
                if not bps_field:
                    raise CommandError(f'Could not find BPS column. Available: {fieldnames}')
                
                self.stdout.write(
                    f'Using columns: designation="{designation_field}", bps="{bps_field}", '
                    f'department="{department_field or "N/A"}", count="{count_field or "N/A"}"'
                )
                
                rows = list(reader)
                
            with transaction.atomic():
                for row_num, row in enumerate(rows, start=2):
                    # Normalize row keys
                    row_normalized = {k.strip().lower(): v for k, v in row.items()}
                    
                    try:
                        result = self._process_row(
                            row_normalized=row_normalized,
                            row_num=row_num,
                            fiscal_year=fiscal_year,
                            post_type=post_type,
                            default_budget_head=default_budget_head,
                            designation_field=designation_field,
                            bps_field=bps_field,
                            department_field=department_field,
                            count_field=count_field,
                            update_existing=update_existing,
                            dry_run=dry_run
                        )
                        
                        if result['skipped']:
                            skipped_count += 1
                        else:
                            if result['designation_created']:
                                designations_created += 1
                            elif result['designation_updated']:
                                designations_updated += 1
                            if result['establishment_created']:
                                establishment_created += 1
                            elif result['establishment_updated']:
                                establishment_updated += 1
                    
                    except Exception as e:
                        errors.append((row_num, str(e)))
                
                if dry_run:
                    transaction.set_rollback(True)
        
        except Exception as e:
            raise CommandError(f'Error processing CSV: {str(e)}')
        
        # Report results
        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING('=== DRY RUN (no changes saved) ==='))
        
        self.stdout.write(self.style.SUCCESS(f'Designations Created: {designations_created}'))
        self.stdout.write(self.style.SUCCESS(f'Designations Updated: {designations_updated}'))
        self.stdout.write(self.style.SUCCESS(f'Establishment Created: {establishment_created}'))
        self.stdout.write(self.style.SUCCESS(f'Establishment Updated: {establishment_updated}'))
        self.stdout.write(f'Skipped: {skipped_count}')
        
        if errors:
            self.stdout.write(self.style.WARNING(f'Errors: {len(errors)}'))
            for row_num, error in errors[:10]:
                self.stdout.write(self.style.ERROR(f'  Row {row_num}: {error}'))
            if len(errors) > 10:
                self.stdout.write(f'  ... and {len(errors) - 10} more errors')
        
        return (
            f'Import complete: {designations_created} designations, '
            f'{establishment_created} establishment entries created'
        )
    
    def _get_fiscal_year(self, year_name: str, dry_run: bool) -> Optional[FiscalYear]:
        """Get or create fiscal year."""
        fiscal_year = FiscalYear.objects.filter(year_name=year_name).first()
        
        if not fiscal_year:
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f'Fiscal year "{year_name}" not found. Will be created during actual run.'
                ))
                return None
            else:
                raise CommandError(
                    f'Fiscal year "{year_name}" not found. '
                    f'Please create it first via admin or budgeting dashboard.'
                )
        
        self.stdout.write(f'Using fiscal year: {fiscal_year}')
        return fiscal_year
    
    def _get_default_salary_head(self) -> Optional[BudgetHead]:
        """Get default salary budget head (A01)."""
        salary_head = BudgetHead.objects.filter(
            pifra_object__startswith='A01',
            is_active=True
        ).first()
        
        if not salary_head:
            self.stdout.write(self.style.WARNING(
                'No salary budget head (A01*) found. Establishment entries may have missing budget_head.'
            ))
        
        return salary_head
    
    def _process_row(
        self,
        row_normalized: Dict[str, str],
        row_num: int,
        fiscal_year: Optional[FiscalYear],
        post_type: str,
        default_budget_head: Optional[BudgetHead],
        designation_field: str,
        bps_field: str,
        department_field: Optional[str],
        count_field: Optional[str],
        update_existing: bool,
        dry_run: bool
    ) -> Dict[str, bool]:
        """Process a single CSV row."""
        result = {
            'skipped': False,
            'designation_created': False,
            'designation_updated': False,
            'establishment_created': False,
            'establishment_updated': False,
        }
        
        # Extract values
        designation_name = row_normalized.get(designation_field, '').strip()
        bps_raw = row_normalized.get(bps_field, '').strip()
        department = row_normalized.get(department_field, 'General').strip() if department_field else 'General'
        count_raw = row_normalized.get(count_field, '1').strip() if count_field else '1'
        
        if not designation_name:
            result['skipped'] = True
            return result
        
        # Parse BPS scale
        try:
            bps_scale = int(bps_raw)
            if not 1 <= bps_scale <= 22:
                raise ValueError(f'BPS must be 1-22, got {bps_scale}')
        except (ValueError, TypeError) as e:
            raise ValueError(f'Invalid BPS "{bps_raw}": {e}')
        
        # Parse sanctioned posts count
        try:
            sanctioned_posts = int(count_raw) if count_raw else 1
            if sanctioned_posts < 0:
                sanctioned_posts = 1
        except (ValueError, TypeError):
            sanctioned_posts = 1
        
        # Calculate annual salary (initial stage × 12)
        monthly_rate = BPS_INITIAL_RATES.get(bps_scale, 25000)
        annual_salary = Decimal(str(monthly_rate * 12))
        
        # 1. Create/Update DesignationMaster
        if not dry_run:
            designation_obj, created = DesignationMaster.objects.get_or_create(
                name__iexact=designation_name,
                defaults={
                    'name': designation_name,
                    'bps_scale': bps_scale,
                    'post_type': post_type,
                    'is_active': True
                }
            )
            
            if created:
                result['designation_created'] = True
            elif update_existing:
                if designation_obj.bps_scale != bps_scale or designation_obj.post_type != post_type:
                    designation_obj.bps_scale = bps_scale
                    designation_obj.post_type = post_type
                    designation_obj.save()
                    result['designation_updated'] = True
        else:
            # Dry run - just check if exists
            existing = DesignationMaster.objects.filter(name__iexact=designation_name).exists()
            result['designation_created'] = not existing
        
        # 2. Create/Update ScheduleOfEstablishment
        if fiscal_year and not dry_run:
            establishment_obj, created = ScheduleOfEstablishment.objects.get_or_create(
                fiscal_year=fiscal_year,
                department=department,
                designation_name=designation_name,
                bps_scale=bps_scale,
                defaults={
                    'post_type': post_type,
                    'sanctioned_posts': sanctioned_posts,
                    'occupied_posts': 0,  # Will be filled during calibration
                    'annual_salary': annual_salary,
                    'budget_head': default_budget_head,
                    'establishment_status': EstablishmentStatus.SANCTIONED,
                    'approval_status': ApprovalStatus.DRAFT,
                }
            )
            
            if created:
                result['establishment_created'] = True
            elif update_existing:
                changed = False
                if establishment_obj.sanctioned_posts != sanctioned_posts:
                    establishment_obj.sanctioned_posts = sanctioned_posts
                    changed = True
                if establishment_obj.annual_salary != annual_salary:
                    establishment_obj.annual_salary = annual_salary
                    changed = True
                if changed:
                    establishment_obj.save()
                    result['establishment_updated'] = True
        elif dry_run and fiscal_year:
            # Dry run check
            existing = ScheduleOfEstablishment.objects.filter(
                fiscal_year=fiscal_year,
                department=department,
                designation_name=designation_name,
                bps_scale=bps_scale
            ).exists()
            result['establishment_created'] = not existing
        
        return result
    
    def _find_column(self, fieldnames: List[str], candidates: List[str]) -> str:
        """Find a column name from a list of candidates."""
        for candidate in candidates:
            if candidate in fieldnames:
                return candidate
        return ''
