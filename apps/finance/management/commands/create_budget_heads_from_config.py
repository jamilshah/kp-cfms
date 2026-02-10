"""
Management command to create BudgetHead records from DepartmentFunctionConfiguration.

This reads the dept-func configuration matrix and creates actual BudgetHead records
for all configured NAM heads.

Usage:
    python manage.py create_budget_heads_from_config --fund GEN
    python manage.py create_budget_heads_from_config --fund GEN --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.finance.models import (
    DepartmentFunctionConfiguration,
    BudgetHead,
    Fund
)


class Command(BaseCommand):
    help = 'Create BudgetHead records from DepartmentFunctionConfiguration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fund',
            type=str,
            required=True,
            help='Fund code (e.g., GEN, DEV)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating'
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Update existing budget heads if they exist'
        )

    def handle(self, *args, **options):
        fund_code = options['fund']
        dry_run = options['dry_run']
        overwrite = options['overwrite']
        
        try:
            fund = Fund.objects.get(code=fund_code, is_active=True)
        except Fund.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Fund "{fund_code}" not found or inactive'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Processing configurations for Fund: {fund.code} - {fund.name}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Get all configurations with allowed NAM heads
        configs = DepartmentFunctionConfiguration.objects.filter(
            allowed_nam_heads__isnull=False
        ).prefetch_related('allowed_nam_heads').distinct()
        
        if not configs.exists():
            self.stdout.write(self.style.WARNING('No configurations found with allowed NAM heads'))
            return
        
        self.stdout.write(f'\nFound {configs.count()} department-function configurations')
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []
        
        with transaction.atomic():
            for config in configs:
                dept = config.department
                func = config.function
                allowed_heads = config.allowed_nam_heads.all()
                
                if not allowed_heads:
                    continue
                
                self.stdout.write(f'\n{dept.name} + {func.code} ({func.name}):')
                self.stdout.write(f'  {allowed_heads.count()} allowed NAM heads')
                
                for nam_head in allowed_heads:
                    try:
                        # Check if budget head already exists
                        existing = BudgetHead.objects.filter(
                            department=dept,
                            function=func,
                            fund=fund,
                            nam_head=nam_head,
                            sub_head__isnull=True  # Only NAM heads, not sub-heads
                        ).first()
                        
                        if existing:
                            if overwrite:
                                if not dry_run:
                                    existing.is_active = True
                                    existing.save(update_fields=['is_active'])
                                self.stdout.write(f'    ✓ Updated: {nam_head.code} - {nam_head.name}')
                                updated_count += 1
                            else:
                                self.stdout.write(f'    - Skipped (exists): {nam_head.code}')
                                skipped_count += 1
                        else:
                            if not dry_run:
                                BudgetHead.objects.create(
                                    department=dept,
                                    function=func,
                                    fund=fund,
                                    nam_head=nam_head,
                                    sub_head=None,
                                    is_active=True,
                                    budget_control=True,
                                    posting_allowed=True  # Allow posting by default for usability
                                )
                            self.stdout.write(f'    + Created: {nam_head.code} - {nam_head.name}')
                            created_count += 1
                    
                    except Exception as e:
                        error_msg = f'{dept.code} + {func.code} + {nam_head.code}: {str(e)}'
                        errors.append(error_msg)
                        self.stdout.write(self.style.ERROR(f'    ✗ Error: {error_msg}'))
            
            if dry_run:
                # Rollback in dry-run mode
                transaction.set_rollback(True)
        
        # Summary
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('\nSUMMARY:'))
        self.stdout.write(f'  Created: {created_count}')
        self.stdout.write(f'  Updated: {updated_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')
        
        if errors:
            self.stdout.write(self.style.ERROR(f'  Errors: {len(errors)}'))
            self.stdout.write('\nError Details:')
            for error in errors:
                self.stdout.write(self.style.ERROR(f'  - {error}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nℹ DRY RUN - No changes were saved'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Budget heads created successfully'))
            self.stdout.write(f'\nView them at: http://127.0.0.1:8000/budgeting/setup/coa/')
