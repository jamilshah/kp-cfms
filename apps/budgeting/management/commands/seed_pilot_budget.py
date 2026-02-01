"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to seed pilot budget allocations for
             active fiscal years to ensure system operability.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.budgeting.models import FiscalYear, BudgetAllocation
from apps.finance.models import BudgetHead

class Command(BaseCommand):
    """
    Management command to seed pilot budget allocations.
    
    This ensures that vital budget heads have non-zero allocations
    and released amounts, preventing 'Insufficient Budget' errors
    during the pilot phase.
    """
    help = 'Seed pilot budget allocations for active fiscal years'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Pilot Budget Seeding...'))
        
        active_fys = FiscalYear.objects.filter(is_active=True)
        if not active_fys.exists():
            self.stdout.write(self.style.WARNING('No active fiscal years found.'))
            return

        for fy in active_fys:
            self.stdout.write(f"Processing Fiscal Year: {fy.year_name} for {fy.organization}")
            self.seed_for_fy(fy)

        self.stdout.write(self.style.SUCCESS('\nSuccessfully completed pilot budget seeding.'))

    @transaction.atomic
    def seed_for_fy(self, fy):
        """
        Seed allocations for a specific fiscal year.
        """
        heads = BudgetHead.objects.filter(is_active=True)
        
        created_count = 0
        updated_count = 0
        
        for head in heads:
            # Check if allocation already exists or create a shell
            allocation, created = BudgetAllocation.objects.get_or_create(
                organization=fy.organization,
                fiscal_year=fy,
                budget_head=head,
                defaults={
                    'original_allocation': Decimal('0.00'),
                    'revised_allocation': Decimal('0.00'),
                    'released_amount': Decimal('0.00'),
                    'spent_amount': Decimal('0.00'),
                }
            )
            
            # Fill the gaps: Only update if allocation is zero
            if allocation.original_allocation == Decimal('0.00'):
                code = head.global_head.code
                amount = Decimal('0.00')
                
                # Logic per Pilot Requirements:
                # - Salary (A01): PKR 5,000,000
                # - O&M (A03): PKR 1,000,000
                # - Other Exp (A*): PKR 500,000
                # - Revenue (C0*): PKR 10,000,000 (Targets)
                
                if code.startswith('A01'):   # Employee Related Expenses
                    amount = Decimal('5000000.00')
                elif code.startswith('A03'): # Operating Expenses
                    amount = Decimal('1000000.00')
                elif code.startswith('A'):   # General Expenditure
                    amount = Decimal('500000.00')
                elif code.startswith('C0'):  # Revenue Heads
                    amount = Decimal('10000000.00')
                
                if amount > 0:
                    allocation.original_allocation = amount
                    allocation.revised_allocation = amount
                    # CRITICAL: Release 100% so the Bill form budget check passes
                    allocation.released_amount = amount
                    allocation.save()
                    
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
        
        if created_count > 0 or updated_count > 0:
            self.stdout.write(f"  - Created {created_count} and updated {updated_count} allocations.")
        else:
            self.stdout.write(f"  - No zero-allocation heads found for this FY.")
