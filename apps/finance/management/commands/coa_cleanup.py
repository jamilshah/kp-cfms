"""
Management command for CoA data cleanup and validation.

Provides tools to find and fix data quality issues:
- Unused budget heads
- Invalid configurations
- Budget heads without allocations
- Duplicate configurations
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Q, Exists, OuterRef
from apps.finance.models import BudgetHead, DepartmentFunctionConfiguration, GlobalHead
from apps.budgeting.models import BudgetAllocation, FiscalYear
from decimal import Decimal


class Command(BaseCommand):
    help = 'CoA data cleanup and validation utilities'

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            'operation',
            type=str,
            choices=[
                'unused_heads',
                'invalid_configs',
                'heads_without_budget',
                'duplicate_configs',
                'report',
                'fix_all',
            ],
            help='Cleanup operation to perform'
        )
        parser.add_argument(
            '--fiscal-year',
            type=str,
            help='Fiscal year code (e.g., "2025-26")'
        )
        parser.add_argument(
            '--auto-fix',
            action='store_true',
            help='Automatically fix issues (use with caution)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them'
        )

    def handle(self, *args, **options):
        """Handle the command execution."""
        operation = options['operation']
        
        # Map operations to handler methods
        operations = {
            'unused_heads': self.find_unused_heads,
            'invalid_configs': self.find_invalid_configs,
            'heads_without_budget': self.find_heads_without_budget,
            'duplicate_configs': self.find_duplicate_configs,
            'report': self.generate_cleanup_report,
            'fix_all': self.fix_all_issues,
        }
        
        handler = operations.get(operation)
        if handler:
            handler(options)
        else:
            raise CommandError(f'Unknown operation: {operation}')

    def find_unused_heads(self, options):
        """Find budget heads with no transactions."""
        from apps.expenditure.models import BillLine
        from apps.finance.models import JournalEntry
        
        self.stdout.write(self.style.WARNING('Searching for unused budget heads...'))
        
        # Find heads without any transactions
        unused_heads = BudgetHead.objects.filter(
            is_active=True
        ).annotate(
            has_bill_lines=Exists(
                BillLine.objects.filter(budget_head=OuterRef('pk'))
            ),
            has_journal_entries=Exists(
                JournalEntry.objects.filter(budget_head=OuterRef('pk'))
            )
        ).filter(
            has_bill_lines=False,
            has_journal_entries=False
        ).select_related('department', 'function', 'global_head')
        
        count = unused_heads.count()
        
        self.stdout.write(f'Found {count} unused budget heads')
        
        if count > 0:
            self.stdout.write('\nUnused Budget Heads (first 20):')
            for head in unused_heads[:20]:
                self.stdout.write(
                    f'  - {head.code} | {head.department.code if head.department else "N/A"} | '
                    f'{head.function.code if head.function else "N/A"} | {head.name}'
                )
            if count > 20:
                self.stdout.write(f'  ... and {count - 20} more')
            
            if options.get('auto_fix') and not options.get('dry_run'):
                confirm = input(f'\nDeactivate {count} unused budget heads? (yes/no): ')
                if confirm.lower() == 'yes':
                    with transaction.atomic():
                        unused_heads.update(is_active=False)
                    self.stdout.write(self.style.SUCCESS(f'Deactivated {count} unused heads'))
                else:
                    self.stdout.write(self.style.WARNING('Operation cancelled'))
            elif options.get('dry_run'):
                self.stdout.write(self.style.SUCCESS('DRY RUN - No changes made'))

    def find_invalid_configs(self, options):
        """Find invalid department-function configurations."""
        self.stdout.write(self.style.WARNING('Searching for invalid configurations...'))
        
        issues = []
        
        # Issue 1: Configurations with no allowed heads
        empty_configs = DepartmentFunctionConfiguration.objects.annotate(
            head_count=Count('allowed_global_heads')
        ).filter(head_count=0)
        
        if empty_configs.exists():
            issues.append({
                'type': 'Empty Configuration',
                'count': empty_configs.count(),
                'queryset': empty_configs,
                'message': 'configurations have no allowed global heads'
            })
        
        # Issue 2: Configurations with only 1-3 heads (likely incomplete)
        sparse_configs = DepartmentFunctionConfiguration.objects.annotate(
            head_count=Count('allowed_global_heads')
        ).filter(head_count__gte=1, head_count__lt=5)
        
        if sparse_configs.exists():
            issues.append({
                'type': 'Sparse Configuration',
                'count': sparse_configs.count(),
                'queryset': sparse_configs,
                'message': 'configurations have fewer than 5 heads (likely incomplete)'
            })
        
        # Issue 3: Locked configurations with no heads
        locked_empty = DepartmentFunctionConfiguration.objects.annotate(
            head_count=Count('allowed_global_heads')
        ).filter(is_locked=True, head_count=0)
        
        if locked_empty.exists():
            issues.append({
                'type': 'Locked Empty Configuration',
                'count': locked_empty.count(),
                'queryset': locked_empty,
                'message': 'configurations are locked but have no heads (CRITICAL)'
            })
        
        if not issues:
            self.stdout.write(self.style.SUCCESS('No invalid configurations found!'))
            return
        
        # Display issues
        for issue in issues:
            self.stdout.write(f'\n{issue["type"]}: {issue["count"]} {issue["message"]}')
            for config in issue['queryset'][:5]:
                count = config.allowed_global_heads.count()
                self.stdout.write(f'  - {config} ({count} heads)')
            if issue['count'] > 5:
                self.stdout.write(f'  ... and {issue["count"] - 5} more')
        
        if options.get('auto_fix') and not options.get('dry_run'):
            # Auto-fix: Unlock empty locked configurations
            if locked_empty.exists():
                confirm = input(f'\nUnlock {locked_empty.count()} empty locked configurations? (yes/no): ')
                if confirm.lower() == 'yes':
                    with transaction.atomic():
                        locked_empty.update(is_locked=False)
                    self.stdout.write(self.style.SUCCESS(f'Unlocked {locked_empty.count()} configurations'))

    def find_heads_without_budget(self, options):
        """Find budget heads without budget allocations."""
        fiscal_year_code = options.get('fiscal_year')
        
        if fiscal_year_code:
            try:
                fiscal_year = FiscalYear.objects.get(code=fiscal_year_code)
            except FiscalYear.DoesNotExist:
                raise CommandError(f'Fiscal year not found: {fiscal_year_code}')
        else:
            fiscal_year = FiscalYear.get_current_operating_year()
            if not fiscal_year:
                raise CommandError('No active fiscal year found. Please specify --fiscal-year')
        
        self.stdout.write(f'Checking budget allocations for FY: {fiscal_year.code}')
        
        # Find active budget heads without allocations
        heads_without_budget = BudgetHead.objects.filter(
            is_active=True,
            posting_allowed=True
        ).annotate(
            has_allocation=Exists(
                BudgetAllocation.objects.filter(
                    budget_head=OuterRef('pk'),
                    fiscal_year=fiscal_year
                )
            )
        ).filter(
            has_allocation=False
        ).select_related('department', 'function', 'global_head')
        
        count = heads_without_budget.count()
        
        self.stdout.write(f'Found {count} budget heads without allocations')
        
        if count > 0:
            self.stdout.write('\nBudget Heads Without Allocations (first 20):')
            for head in heads_without_budget[:20]:
                self.stdout.write(
                    f'  - {head.code} | {head.department.code if head.department else "N/A"} | '
                    f'{head.name}'
                )
            if count > 20:
                self.stdout.write(f'  ... and {count - 20} more')
            
            self.stdout.write(self.style.WARNING(
                '\nNote: These heads can receive transactions but have no budget. '
                'Consider creating allocations or disabling posting.'
            ))

    def find_duplicate_configs(self, options):
        """Find duplicate department-function configurations."""
        self.stdout.write(self.style.WARNING('Searching for duplicate configurations...'))
        
        # Check for duplicates (shouldn't exist due to unique_together, but check anyway)
        duplicates = DepartmentFunctionConfiguration.objects.values(
            'department', 'function'
        ).annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if duplicates.exists():
            self.stdout.write(self.style.ERROR(
                f'Found {duplicates.count()} duplicate configurations (DATABASE INTEGRITY ISSUE!)'
            ))
            for dup in duplicates:
                configs = DepartmentFunctionConfiguration.objects.filter(
                    department_id=dup['department'],
                    function_id=dup['function']
                )
                self.stdout.write(f'  - Dept {dup["department"]}, Function {dup["function"]}: {dup["count"]} records')
        else:
            self.stdout.write(self.style.SUCCESS('No duplicate configurations found'))

    def generate_cleanup_report(self, options):
        """Generate comprehensive cleanup report."""
        self.stdout.write(self.style.SUCCESS('=== CoA Cleanup Report ===\n'))
        
        # Run all checks
        self.stdout.write('1. Unused Budget Heads:')
        self.find_unused_heads({**options, 'dry_run': True})
        
        self.stdout.write('\n2. Invalid Configurations:')
        self.find_invalid_configs({**options, 'dry_run': True})
        
        self.stdout.write('\n3. Budget Heads Without Allocations:')
        self.find_heads_without_budget({**options, 'dry_run': True})
        
        self.stdout.write('\n4. Duplicate Configurations:')
        self.find_duplicate_configs({**options, 'dry_run': True})
        
        self.stdout.write(self.style.SUCCESS('\n=== End of Report ==='))
        self.stdout.write('\nTo fix issues, run specific operations with --auto-fix flag')

    def fix_all_issues(self, options):
        """Auto-fix all detectable issues."""
        if options.get('dry_run'):
            self.stdout.write(self.style.WARNING('DRY RUN - Showing what would be fixed'))
            self.generate_cleanup_report({**options, 'dry_run': True})
            return
        
        self.stdout.write(self.style.WARNING('This will attempt to auto-fix all issues'))
        confirm = input('Continue? (yes/no): ')
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING('Operation cancelled'))
            return
        
        self.stdout.write('\nFixing issues...')
        
        # Fix 1: Deactivate unused heads
        self.stdout.write('\n1. Deactivating unused heads...')
        self.find_unused_heads({**options, 'auto_fix': True})
        
        # Fix 2: Unlock empty locked configurations
        self.stdout.write('\n2. Fixing invalid configurations...')
        self.find_invalid_configs({**options, 'auto_fix': True})
        
        self.stdout.write(self.style.SUCCESS('\nAll auto-fixable issues have been addressed'))
        self.stdout.write('Run "report" operation again to verify')
