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
from apps.finance.models import Fund


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
                
                created_count, updated_count, error_count = self._import_csv(file_path, dry_run)
                
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
    
    def _import_csv(self, file_path: Path, dry_run: bool) -> tuple:
        """
        Import CSV data into BudgetHead model.
        
        Args:
            file_path: Path to the CSV file.
            dry_run: If True, don't save to database.
            
        Returns:
            Tuple of (created_count, updated_count, error_count).
        """
        created_count = 0
        updated_count = 0
        error_count = 0
        
        # Pre-create function codes
        function_cache: Dict[str, FunctionCode] = {}
        
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
                try:
                    result = self._process_row(row, function_cache, dry_run)
                    if result == 'created':
                        created_count += 1
                    elif result == 'updated':
                        updated_count += 1
                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(
                        f"Row {row_num}: Error processing {row.get('TMA_Sub_Object', 'UNKNOWN')} - {e}"
                    ))
        
        return created_count, updated_count, error_count
    
    def _process_row(
        self,
        row: Dict[str, Any],
        function_cache: Dict[str, FunctionCode],
        dry_run: bool
    ) -> str:
        """
        Process a single CSV row.
        
        Args:
            row: Dictionary of CSV columns.
            function_cache: Cache of FunctionCode objects.
            dry_run: If True, don't save to database.
            
        Returns:
            'created' or 'updated' status string.
        """
        # Get or create FunctionCode
        func_code = row.get('Function', '').strip()
        if func_code and func_code not in function_cache:
            func_obj, _ = FunctionCode.objects.get_or_create(
                code=func_code,
                defaults={'name': func_code}
            )
            function_cache[func_code] = func_obj
        
        function_obj = function_cache.get(func_code)
        
        # Map account type
        account_type_str = row.get('Account_Type', 'Expenditure').strip()
        account_type = self.ACCOUNT_TYPE_MAP.get(account_type_str, AccountType.EXPENDITURE)
        
        # Parse boolean fields
        budget_control = row.get('Budget_Control', 'Yes').strip().lower() == 'yes'
        project_required = row.get('Project_Required', 'No').strip().lower() == 'yes'
        posting_allowed = row.get('Posting_Allowed', 'Yes').strip().lower() == 'yes'
        
        # Parse fund_id and resolve to an existing Fund id
        try:
            orig_fund_id = int(row.get('Fund', 1))
        except (ValueError, TypeError):
            orig_fund_id = 1

        # If the fund id from CSV does not exist in DB, try to map by common codes
        fund_id = orig_fund_id
        if not Fund.objects.filter(pk=fund_id).exists():
            # Fallback mapping: CSV numeric -> expected Fund.code
            FALLBACK_FUND_MAP = {
                1: 'GEN',  # General / Current
                2: 'DEV',  # Development
                5: 'PEN',  # Pension
            }
            fallback_code = FALLBACK_FUND_MAP.get(orig_fund_id)
            if fallback_code:
                fund_obj = Fund.objects.filter(code__iexact=fallback_code).first()
                if fund_obj:
                    fund_id = fund_obj.id
            # If still not found, use any active fund as default
            if not Fund.objects.filter(pk=fund_id).exists():
                default_fund = Fund.objects.filter(is_active=True).first()
                if default_fund:
                    fund_id = default_fund.id
        
        # Prepare data
        tma_sub_object = row.get('TMA_Sub_Object', '').strip()
        
        data = {
            'fund_id': fund_id,
            'function': function_obj,
            'pifra_object': row.get('PIFRA_Object', '').strip(),
            'pifra_description': row.get('PIFRA_Description', '').strip(),
            'tma_description': row.get('TMA_Sub_Description', '').strip(),
            'account_type': account_type,
            'budget_control': budget_control,
            'project_required': project_required,
            'posting_allowed': posting_allowed,
        }
        
        if dry_run:
            # Validate only
            self.stdout.write(f"  [DRY] Would process: {tma_sub_object}")
            return 'created'
        
        # Create or update
        budget_head, created = BudgetHead.objects.update_or_create(
            tma_sub_object=tma_sub_object,
            defaults=data
        )
        
        return 'created' if created else 'updated'
