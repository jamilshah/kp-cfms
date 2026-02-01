"""
Management command to distribute salary budget among departments.

Usage:
    python manage.py distribute_salary_budget --fy=2025-26 --fund=GEN --account=A01151 --amount=942657799

This command:
1. Counts active employees per department
2. Calculates proportional allocation
3. Creates DepartmentSalaryBudget records
"""

from django.core.management.base import BaseCommand, CommandError
from decimal import Decimal
from apps.core.models import FiscalYear, Department
from apps.finance.models import Fund, GlobalHead
from apps.budgeting.services_salary_budget import SalaryBudgetDistributor


class Command(BaseCommand):
    help = 'Distribute centralized salary budget among departments based on employee strength'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fy',
            type=str,
            required=True,
            help='Fiscal year code (e.g., 2025-26)'
        )
        parser.add_argument(
            '--fund',
            type=str,
            required=True,
            help='Fund code (e.g., GEN)'
        )
        parser.add_argument(
            '--account',
            type=str,
            required=True,
            help='Account code (e.g., A01151)'
        )
        parser.add_argument(
            '--amount',
            type=str,
            required=True,
            help='Total budget amount (e.g., 942657799)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show distribution without saving'
        )
    
    def handle(self, *args, **options):
        fy_code = options['fy']
        fund_code = options['fund']
        account_code = options['account']
        amount = Decimal(options['amount'])
        dry_run = options['dry_run']
        
        # Validate inputs
        try:
            fiscal_year = FiscalYear.objects.get(year=fy_code)
        except FiscalYear.DoesNotExist:
            raise CommandError(f"Fiscal year '{fy_code}' not found")
        
        try:
            fund = Fund.objects.get(code=fund_code)
        except Fund.DoesNotExist:
            raise CommandError(f"Fund '{fund_code}' not found")
        
        try:
            global_head = GlobalHead.objects.get(code=account_code)
        except GlobalHead.DoesNotExist:
            raise CommandError(f"Account code '{account_code}' not found")
        
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS(f"SALARY BUDGET DISTRIBUTION"))
        self.stdout.write("="*80)
        self.stdout.write(f"Fiscal Year: {fiscal_year}")
        self.stdout.write(f"Fund: {fund}")
        self.stdout.write(f"Account: {global_head.code} - {global_head.name}")
        self.stdout.write(f"Total Budget: Rs. {amount:,.2f}")
        self.stdout.write("")
        
        # Calculate distribution
        try:
            allocations = SalaryBudgetDistributor.distribute_budget(
                fiscal_year, fund, global_head, amount
            )
        except Exception as e:
            raise CommandError(f"Distribution failed: {str(e)}")
        
        # Display allocation plan
        self.stdout.write(self.style.WARNING("ALLOCATION PLAN:"))
        self.stdout.write("-"*80)
        self.stdout.write(f"{'Department':<30} {'Employees':>10} {'Allocation':>20} {'%':>8}")
        self.stdout.write("-"*80)
        
        from apps.budgeting.models_employee import BudgetEmployee
        
        total_employees = 0
        total_allocated = Decimal('0.00')
        
        for dept in sorted(allocations.keys(), key=lambda d: d.name):
            emp_count = BudgetEmployee.objects.filter(
                schedule__department=dept.name,
                schedule__fiscal_year=fiscal_year,
                is_vacant=False
            ).count()
            
            allocation = allocations[dept]
            percentage = (allocation / amount * 100) if amount > 0 else 0
            
            self.stdout.write(
                f"{dept.name:<30} {emp_count:>10} "
                f"Rs. {allocation:>15,.2f} {percentage:>7.2f}%"
            )
            
            total_employees += emp_count
            total_allocated += allocation
        
        self.stdout.write("-"*80)
        self.stdout.write(
            f"{'TOTAL':<30} {total_employees:>10} "
            f"Rs. {total_allocated:>15,.2f} {'100.00':>7}%"
        )
        self.stdout.write("")
        
        # Verify total matches
        if total_allocated != amount:
            self.stdout.write(
                self.style.WARNING(
                    f"Note: Rounding adjustment of Rs. {abs(amount - total_allocated):.2f}"
                )
            )
        
        # Save if not dry-run
        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY RUN] No records created"))
        else:
            self.stdout.write(self.style.WARNING("\nCreating DepartmentSalaryBudget records..."))
            
            try:
                created = SalaryBudgetDistributor.create_department_budgets(
                    fiscal_year, fund, global_head, amount
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✓ Created {len(created)} DepartmentSalaryBudget records"
                    )
                )
            except Exception as e:
                raise CommandError(f"Failed to create records: {str(e)}")
        
        self.stdout.write("="*80 + "\n")
