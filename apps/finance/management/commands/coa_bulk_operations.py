"""
Management command for CoA bulk operations.

Provides bulk operations for Chart of Accounts management:
- Bulk activate/deactivate budget heads
- Bulk lock/unlock configurations
- Find and fix orphaned budget heads
- Export/import configurations
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.finance.models import BudgetHead, DepartmentFunctionConfiguration, GlobalHead
from apps.budgeting.models import Department
import csv
from io import StringIO
from decimal import Decimal


class Command(BaseCommand):
    help = 'Bulk operations for Chart of Accounts management'

    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            'operation',
            type=str,
            choices=[
                'activate_heads',
                'deactivate_heads',
                'lock_configs',
                'unlock_configs',
                'find_orphaned',
                'fix_orphaned',
                'export_configs',
                'import_configs',
                'stats',
            ],
            help='Bulk operation to perform'
        )
        parser.add_argument(
            '--department',
            type=str,
            help='Department code or ID (for filtering)'
        )
        parser.add_argument(
            '--function',
            type=str,
            help='Function code (for filtering)'
        )
        parser.add_argument(
            '--file',
            type=str,
            help='File path for export/import operations'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force operation without confirmation'
        )

    def handle(self, *args, **options):
        """Handle the command execution."""
        operation = options['operation']
        
        # Map operations to handler methods
        operations = {
            'activate_heads': self.activate_heads,
            'deactivate_heads': self.deactivate_heads,
            'lock_configs': self.lock_configs,
            'unlock_configs': self.unlock_configs,
            'find_orphaned': self.find_orphaned_heads,
            'fix_orphaned': self.fix_orphaned_heads,
            'export_configs': self.export_configurations,
            'import_configs': self.import_configurations,
            'stats': self.show_statistics,
        }
        
        handler = operations.get(operation)
        if handler:
            handler(options)
        else:
            raise CommandError(f'Unknown operation: {operation}')

    def activate_heads(self, options):
        """Bulk activate budget heads."""
        department = options.get('department')
        function = options.get('function')
        dry_run = options.get('dry_run', False)
        
        queryset = BudgetHead.objects.filter(is_active=False)
        
        if department:
            queryset = queryset.filter(department__code=department)
        if function:
            queryset = queryset.filter(function__code=function)
        
        count = queryset.count()
        
        self.stdout.write(self.style.WARNING(f'Found {count} inactive budget heads'))
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('DRY RUN - No changes made'))
            for head in queryset[:10]:
                self.stdout.write(f'  - {head.code}')
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
            return
        
        if not options.get('force'):
            confirm = input(f'Activate {count} budget heads? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        with transaction.atomic():
            queryset.update(is_active=True)
        
        self.stdout.write(self.style.SUCCESS(f'Activated {count} budget heads'))

    def deactivate_heads(self, options):
        """Bulk deactivate budget heads."""
        department = options.get('department')
        function = options.get('function')
        dry_run = options.get('dry_run', False)
        
        queryset = BudgetHead.objects.filter(is_active=True)
        
        if department:
            queryset = queryset.filter(department__code=department)
        if function:
            queryset = queryset.filter(function__code=function)
        
        count = queryset.count()
        
        self.stdout.write(self.style.WARNING(f'Found {count} active budget heads'))
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('DRY RUN - No changes made'))
            for head in queryset[:10]:
                self.stdout.write(f'  - {head.code}')
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
            return
        
        if not options.get('force'):
            confirm = input(f'Deactivate {count} budget heads? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        with transaction.atomic():
            queryset.update(is_active=False)
        
        self.stdout.write(self.style.SUCCESS(f'Deactivated {count} budget heads'))

    def lock_configs(self, options):
        """Lock department-function configurations."""
        department = options.get('department')
        dry_run = options.get('dry_run', False)
        
        queryset = DepartmentFunctionConfiguration.objects.filter(is_locked=False)
        
        if department:
            queryset = queryset.filter(department__code=department)
        
        count = queryset.count()
        
        self.stdout.write(self.style.WARNING(f'Found {count} unlocked configurations'))
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('DRY RUN - No changes made'))
            for config in queryset[:10]:
                self.stdout.write(f'  - {config}')
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
            return
        
        if not options.get('force'):
            confirm = input(f'Lock {count} configurations? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        with transaction.atomic():
            queryset.update(is_locked=True)
        
        self.stdout.write(self.style.SUCCESS(f'Locked {count} configurations'))

    def unlock_configs(self, options):
        """Unlock department-function configurations."""
        department = options.get('department')
        dry_run = options.get('dry_run', False)
        
        queryset = DepartmentFunctionConfiguration.objects.filter(is_locked=True)
        
        if department:
            queryset = queryset.filter(department__code=department)
        
        count = queryset.count()
        
        self.stdout.write(self.style.WARNING(f'Found {count} locked configurations'))
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('DRY RUN - No changes made'))
            for config in queryset[:10]:
                self.stdout.write(f'  - {config}')
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
            return
        
        if not options.get('force'):
            confirm = input(f'Unlock {count} configurations? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        with transaction.atomic():
            queryset.update(is_locked=False)
        
        self.stdout.write(self.style.SUCCESS(f'Unlocked {count} configurations'))

    def find_orphaned_heads(self, options):
        """Find budget heads without corresponding dept-func configuration."""
        orphaned = []
        
        active_heads = BudgetHead.objects.filter(
            is_active=True
        ).select_related('department', 'function', 'global_head')
        
        for head in active_heads:
            if not head.department or not head.function:
                orphaned.append(head)
                continue
            
            try:
                config = DepartmentFunctionConfiguration.objects.get(
                    department=head.department,
                    function=head.function
                )
                
                # Check if global head is in allowed list
                if not config.validate_global_head(head.global_head):
                    orphaned.append(head)
            except DepartmentFunctionConfiguration.DoesNotExist:
                orphaned.append(head)
        
        self.stdout.write(self.style.WARNING(f'Found {len(orphaned)} orphaned budget heads'))
        
        if orphaned:
            self.stdout.write('\nOrphaned Budget Heads:')
            for head in orphaned[:20]:
                reason = 'No department/function' if not head.department or not head.function else 'Not in configuration'
                self.stdout.write(f'  - {head.code} ({head.department}) - {reason}')
            if len(orphaned) > 20:
                self.stdout.write(f'  ... and {len(orphaned) - 20} more')
        
        return orphaned

    def fix_orphaned_heads(self, options):
        """Fix orphaned budget heads by creating configurations."""
        orphaned = self.find_orphaned_heads(options)
        dry_run = options.get('dry_run', False)
        
        if not orphaned:
            self.stdout.write(self.style.SUCCESS('No orphaned heads found!'))
            return
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('DRY RUN - Would create configurations for orphaned heads'))
            return
        
        if not options.get('force'):
            confirm = input(f'Auto-fix {len(orphaned)} orphaned heads by creating appropriate configurations? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        fixed_count = 0
        
        with transaction.atomic():
            for head in orphaned:
                if not head.department or not head.function:
                    continue
                
                # Get or create configuration
                config, created = DepartmentFunctionConfiguration.objects.get_or_create(
                    department=head.department,
                    function=head.function
                )
                
                # Add this global head to allowed heads
                if head.global_head:
                    config.allowed_global_heads.add(head.global_head)
                    fixed_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Fixed {fixed_count} orphaned budget heads'))

    def export_configurations(self, options):
        """Export department-function configurations to CSV."""
        file_path = options.get('file', 'dept_func_configs_export.csv')
        
        configs = DepartmentFunctionConfiguration.objects.all().prefetch_related(
            'allowed_global_heads'
        ).select_related('department', 'function')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Department Code',
                'Department Name',
                'Function Code',
                'Function Name',
                'Allowed Global Heads (Codes)',
                'Head Count',
                'Is Locked',
                'Notes'
            ])
            
            for config in configs:
                head_codes = ', '.join(
                    config.allowed_global_heads.values_list('code', flat=True)
                )
                
                writer.writerow([
                    config.department.code,
                    config.department.name,
                    config.function.code,
                    config.function.name,
                    head_codes,
                    config.get_head_count(),
                    'Yes' if config.is_locked else 'No',
                    config.notes
                ])
        
        self.stdout.write(self.style.SUCCESS(f'Exported {configs.count()} configurations to {file_path}'))

    def import_configurations(self, options):
        """Import department-function configurations from CSV."""
        file_path = options.get('file')
        if not file_path:
            raise CommandError('--file argument is required for import operations')
        
        dry_run = options.get('dry_run', False)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                imported_count = 0
                errors = []
                
                for row_num, row in enumerate(reader, start=2):
                    try:
                        department = Department.objects.get(code=row['Department Code'])
                        function = FunctionCode.objects.get(code=row['Function Code'])
                        
                        head_codes = [c.strip() for c in row['Allowed Global Heads (Codes)'].split(',')]
                        global_heads = GlobalHead.objects.filter(code__in=head_codes)
                        
                        if dry_run:
                            self.stdout.write(f'Would import: {department.code} - {function.code} ({len(global_heads)} heads)')
                            continue
                        
                        config, created = DepartmentFunctionConfiguration.objects.get_or_create(
                            department=department,
                            function=function,
                            defaults={
                                'is_locked': row.get('Is Locked', 'No') == 'Yes',
                                'notes': row.get('Notes', '')
                            }
                        )
                        
                        # Set allowed global heads
                        config.allowed_global_heads.set(global_heads)
                        
                        imported_count += 1
                        
                    except Exception as e:
                        errors.append(f'Row {row_num}: {str(e)}')
                
                if dry_run:
                    self.stdout.write(self.style.SUCCESS(f'DRY RUN - Would import {imported_count} configurations'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'Imported {imported_count} configurations'))
                
                if errors:
                    self.stdout.write(self.style.ERROR('\nErrors:'))
                    for error in errors:
                        self.stdout.write(f'  - {error}')
                        
        except FileNotFoundError:
            raise CommandError(f'File not found: {file_path}')

    def show_statistics(self, options):
        """Show CoA statistics and health metrics."""
        from apps.budgeting.models import BudgetAllocation
        
        self.stdout.write(self.style.SUCCESS('=== Chart of Accounts Statistics ===\n'))
        
        # Budget Heads
        total_heads = BudgetHead.objects.count()
        active_heads = BudgetHead.objects.filter(is_active=True).count()
        postable_heads = BudgetHead.objects.filter(posting_allowed=True, is_active=True).count()
        
        self.stdout.write(f'Budget Heads:')
        self.stdout.write(f'  Total: {total_heads}')
        self.stdout.write(f'  Active: {active_heads}')
        self.stdout.write(f'  Postable: {postable_heads}')
        
        # Configurations
        total_configs = DepartmentFunctionConfiguration.objects.count()
        locked_configs = DepartmentFunctionConfiguration.objects.filter(is_locked=True).count()
        complete_configs = sum(1 for c in DepartmentFunctionConfiguration.objects.all() if c.is_complete())
        
        self.stdout.write(f'\nDepartment-Function Configurations:')
        self.stdout.write(f'  Total: {total_configs}')
        self.stdout.write(f'  Locked: {locked_configs}')
        self.stdout.write(f'  Complete (≥10 heads): {complete_configs}')
        
        # Health metrics
        orphaned = self.find_orphaned_heads(options)
        
        self.stdout.write(f'\nHealth Metrics:')
        self.stdout.write(f'  Orphaned heads: {len(orphaned)}')
        
        # Coverage
        if total_configs > 0:
            completion_rate = (complete_configs / total_configs) * 100
            self.stdout.write(f'  Configuration completion: {completion_rate:.1f}%')
        
        self.stdout.write(self.style.SUCCESS('\n=== End of Statistics ==='))
