"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to import Chart of Accounts from CoA.csv.
             Validates and creates BudgetHead records following NAM structure.
-------------------------------------------------------------------------
"""
import csv
from pathlib import Path
from typing import Dict, Any, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.finance.models import BudgetHead, FunctionCode, AccountType
from apps.finance.models import Fund, MajorHead, MinorHead, GlobalHead


class Command(BaseCommand):
    """
    Import Chart of Accounts from CSV file.
    
    Usage:
        python manage.py import_coa
        python manage.py import_coa --file=/path/to/custom.csv
        python manage.py import_coa --dry-run
    """
    
    help = 'Import Chart of Accounts from docs/CoA.csv into BudgetHead model.'
    
    # Mapping from CSV Account_Type to model AccountType
    ACCOUNT_TYPE_MAP: Dict[str, str] = {
        'Expenditure': AccountType.EXPENDITURE,
        'Revenue': AccountType.REVENUE,
        'Liability': AccountType.LIABILITY,
        'Asset': AccountType.ASSET,
        'Equity': AccountType.EQUITY,
    }
    
    def add_arguments(self, parser) -> None:
        """Add command arguments."""
        parser.add_argument(
            '--file',
            type=str,
            default='docs/CoA.csv',
            help='Path to the CSV file (default: docs/CoA.csv)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate without saving to database'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing BudgetHead records before import'
        )
    
    def handle(self, *args, **options) -> None:
        """Execute the import command."""
        file_path = Path(options['file'])
        dry_run = options['dry_run']
        clear_existing = options['clear']
        
        # Use New COA.csv as default if not specified
        if file_path.name == 'CoA.csv' and not file_path.exists():
            new_file_path = file_path.parent / 'New COA.csv'
            if new_file_path.exists():
                file_path = new_file_path
                self.stdout.write(self.style.NOTICE(f"Defaulting to: {file_path}"))
        
        if not file_path.exists():
            raise CommandError(f"CSV file not found: {file_path}")
        
        self.stdout.write(self.style.NOTICE(f"Reading from: {file_path}"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes will be saved."))
        
        try:
            with transaction.atomic():
                if clear_existing and not dry_run:
                    deleted_count = BudgetHead.objects.all().delete()[0]
                    self.stdout.write(
                        self.style.WARNING(f"Deleted {deleted_count} existing records.")
                    )
                
                created_count, updated_count, error_count = self._import_csv_new(file_path, dry_run)
                
                if dry_run:
                    raise transaction.TransactionManagementError("Dry run - rolling back.")
                
        except transaction.TransactionManagementError:
            pass  # Expected for dry run
        
        # Summary
        self.stdout.write(self.style.SUCCESS(
            f"\nImport Summary:\n"
            f"  Created: {created_count}\n"
            f"  Updated: {updated_count}\n"
            f"  Errors: {error_count}"
        ))

    def _import_csv_new(self, file_path: Path, dry_run: bool) -> tuple:
        """Import from New COA.csv format (6 columns, 2 header rows)."""
        created_count = 0
        updated_count = 0
        error_count = 0
        
        # Caches
        major_cache = {}
        minor_cache = {}
        global_cache = {}
        
        # Defaults for BudgetHead (since CSV lacks them)
        default_function, _ = FunctionCode.objects.get_or_create(
            code='AD', defaults={'name': 'Administration'}
        )
        
        default_fund = Fund.objects.filter(code='GEN').first()
        if not default_fund:
            default_fund = Fund.objects.filter(is_active=True).first()
            
        if not default_fund:
             self.stdout.write(self.style.ERROR("No active Fund found. Cannot create BudgetHeads."))
             return 0, 0, 1

        self.stdout.write(f"Using Default Fund: {default_fund.code}")
        self.stdout.write(f"Using Default Function: {default_function.code}")

        with open(file_path, 'r', encoding='latin-1') as csvfile:
            reader = csv.reader(csvfile)
            
            # Skip first 2 header rows
            try:
                next(reader) # Row 1: Major Object...
                next(reader) # Row 2: Code Description...
            except StopIteration:
                pass
            
            for row_num, row in enumerate(reader, start=3):
                if not row or len(row) < 6:
                    continue
                    
                try:
                    # Columns: 
                    # 0: Major Code, 1: Major Desc
                    # 2: Minor Code, 3: Minor Desc
                    # 4: Global Code, 5: Global Desc
                    
                    # 1. Major Head
                    major_code = row[0].strip()
                    major_desc = row[1].strip()
                    
                    if major_code and major_code not in major_cache:
                        major_obj, _ = MajorHead.objects.get_or_create(
                            code=major_code,
                            defaults={'name': major_desc or f"Major Head {major_code}"}
                        )
                        major_cache[major_code] = major_obj
                    major_obj = major_cache.get(major_code)
                    
                    # 2. Minor Head
                    minor_code = row[2].strip()
                    minor_desc = row[3].strip()
                    
                    if minor_code and minor_code not in minor_cache and major_obj:
                        minor_obj, _ = MinorHead.objects.get_or_create(
                            code=minor_code,
                            defaults={'name': minor_desc or f"Minor Head {minor_code}", 'major': major_obj}
                        )
                        minor_cache[minor_code] = minor_obj
                    minor_obj = minor_cache.get(minor_code)
                    
                    # 3. Global Head
                    pifra_code = row[4].strip()
                    pifra_desc = row[5].strip()
                    
                    # Infer account type from first letter
                    account_type = AccountType.EXPENDITURE
                    if pifra_code:
                        first_char = pifra_code[0].upper()
                        if first_char == 'C': account_type = AccountType.REVENUE
                        elif first_char == 'G': account_type = AccountType.LIABILITY
                        elif first_char == 'F': account_type = AccountType.ASSET
                        elif first_char == '3': account_type = AccountType.EQUITY # Equity usually starts with 3
                    
                    if pifra_code and pifra_code not in global_cache and minor_obj:
                        global_obj, _ = GlobalHead.objects.get_or_create(
                            code=pifra_code,
                            defaults={
                                'name': pifra_desc, 
                                'minor': minor_obj,
                                'account_type': account_type
                            }
                        )
                        global_cache[pifra_code] = global_obj
                    global_obj = global_cache.get(pifra_code)
                    
                    if not global_obj:
                         continue

                    # 4. Create/Update BudgetHead (Default Fund/Function)
                    if dry_run:
                        created_count += 1
                        continue
                        
                    budget_head, created = BudgetHead.objects.update_or_create(
                        fund=default_fund,
                        global_head=global_obj,
                        function=default_function,
                        defaults={
                            'budget_control': True,
                            'project_required': False,
                            'posting_allowed': True,
                            'is_active': True 
                        }
                    )
                    
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                        
                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(
                        f"Row {row_num}: Error - {e}"
                    ))
                    
        return created_count, updated_count, error_count

    def _process_row(self, *args, **kwargs):
        # Deprecated method, kept for safety but unused
        pass
