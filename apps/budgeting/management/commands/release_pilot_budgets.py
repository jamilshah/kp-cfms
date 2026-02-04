"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: One-time command to release all pilot budgets (set released_amount = revised_allocation)
-------------------------------------------------------------------------
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from apps.budgeting.models import BudgetAllocation

class Command(BaseCommand):
    """
    One-time command to release all pilot budgets.
    
    Sets released_amount = revised_allocation for all allocations
    where released_amount is currently 0 or less than revised_allocation.
    """
    help = 'Release all pilot budgets (set released_amount = revised_allocation)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        self.stdout.write(self.style.SUCCESS('Releasing pilot budgets...'))
        
        # Find allocations where released_amount < revised_allocation
        allocations = BudgetAllocation.objects.filter(
            revised_allocation__gt=Decimal('0.00')
        ).exclude(
            released_amount=F('revised_allocation')
        )
        
        total_count = allocations.count()
        self.stdout.write(f"Found {total_count} allocations to release")
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('All budgets are already released!'))
            return
        
        updated_count = 0
        for allocation in allocations:
            old_released = allocation.released_amount
            new_released = allocation.revised_allocation
            
            self.stdout.write(
                f"  {allocation.budget_head.code}: "
                f"Rs. {old_released:,.2f} -> Rs. {new_released:,.2f}"
            )
            
            if not dry_run:
                allocation.released_amount = allocation.revised_allocation
                allocation.save(update_fields=['released_amount', 'updated_at'])
                updated_count += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\nDRY RUN: Would have released {total_count} budgets. '
                    'Run without --dry-run to apply changes.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully released {updated_count} budgets!'
                )
            )
